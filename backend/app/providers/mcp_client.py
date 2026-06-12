"""Restricted MCP connection test and tool discovery adapter."""

from __future__ import annotations

import os
import json
import time
from datetime import timedelta
from urllib.parse import urlparse

import httpx
from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamable_http_client

from app.core.config import Settings
from app.providers.models import AnalysisProviderConfig


class ProviderConnectionError(RuntimeError):
    pass


def validate_mcp_endpoint(endpoint: str, settings: Settings) -> None:
    parsed = urlparse(endpoint)
    host = (parsed.hostname or "").lower()
    if host not in set(settings.mcp_allowed_host_list):
        raise ProviderConnectionError(
            f"MCP host {host!r} is not in MCP_ALLOWED_HOSTS"
        )
    if parsed.scheme != "https" and host not in {"localhost", "127.0.0.1", "::1"}:
        raise ProviderConnectionError("Remote MCP endpoints must use HTTPS")


def _headers(config: AnalysisProviderConfig) -> dict[str, str]:
    headers: dict[str, str] = {}
    if config.secret_ref:
        secret = os.getenv(config.secret_ref, "")
        if not secret:
            raise ProviderConnectionError(
                f"Secret reference {config.secret_ref} is not configured"
            )
        headers["Authorization"] = f"Bearer {secret}"
    return headers


def _tool_summary(tool) -> dict:
    return {
        "name": tool.name,
        "title": getattr(tool, "title", None),
        "description": (tool.description or "")[:500],
    }


async def inspect_mcp_provider(
    config: AnalysisProviderConfig,
    settings: Settings,
) -> tuple[float, list[dict]]:
    if config.provider_type != "mcp" or not config.endpoint or not config.transport:
        raise ProviderConnectionError("Provider is not a complete MCP configuration")

    validate_mcp_endpoint(config.endpoint, settings)
    headers = _headers(config)
    started = time.perf_counter()
    read_timeout = timedelta(seconds=config.timeout_sec)

    try:
        if config.transport == "streamable_http":
            timeout = httpx.Timeout(config.timeout_sec)
            async with httpx.AsyncClient(
                headers=headers,
                timeout=timeout,
                follow_redirects=False,
            ) as http_client:
                async with streamable_http_client(
                    config.endpoint,
                    http_client=http_client,
                    terminate_on_close=False,
                ) as (read_stream, write_stream, _):
                    async with ClientSession(
                        read_stream,
                        write_stream,
                        read_timeout_seconds=read_timeout,
                    ) as client:
                        await client.initialize()
                        result = await client.list_tools()
        else:
            async with sse_client(
                config.endpoint,
                headers=headers,
                timeout=config.timeout_sec,
                sse_read_timeout=config.timeout_sec,
            ) as (read_stream, write_stream):
                async with ClientSession(
                    read_stream,
                    write_stream,
                    read_timeout_seconds=read_timeout,
                ) as client:
                    await client.initialize()
                    result = await client.list_tools()
    except Exception as exc:
        raise ProviderConnectionError(str(exc) or type(exc).__name__) from exc

    tools = [_tool_summary(tool) for tool in result.tools[: settings.mcp_max_discovered_tools]]
    latency_ms = round((time.perf_counter() - started) * 1000, 1)
    return latency_ms, tools


def _tool_result_text(result, max_chars: int) -> str:
    payload = result.model_dump(mode="json", by_alias=True)
    structured = payload.get("structuredContent") or payload.get("structured_content")
    if structured is not None:
        text = json.dumps(structured, ensure_ascii=False, default=str)
    else:
        parts: list[str] = []
        for item in payload.get("content", []):
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        text = "\n".join(parts)
    text = text.strip()
    if not text:
        raise ProviderConnectionError("MCP tool returned an empty result")
    if len(text) > max_chars:
        raise ProviderConnectionError("MCP tool result exceeded the configured size limit")
    if payload.get("isError") or payload.get("is_error"):
        raise ProviderConnectionError(text[:2000])
    return text


async def call_mcp_tool(
    config: AnalysisProviderConfig,
    settings: Settings,
    *,
    tool_name: str,
    arguments: dict,
) -> tuple[float, str]:
    if tool_name not in config.allowed_tools:
        raise ProviderConnectionError(f"MCP tool {tool_name!r} is not in the allowlist")
    if config.provider_type != "mcp" or not config.endpoint or not config.transport:
        raise ProviderConnectionError("Provider is not a complete MCP configuration")

    validate_mcp_endpoint(config.endpoint, settings)
    headers = _headers(config)
    started = time.perf_counter()
    read_timeout = timedelta(seconds=config.timeout_sec)
    try:
        if config.transport == "streamable_http":
            timeout = httpx.Timeout(config.timeout_sec)
            async with httpx.AsyncClient(
                headers=headers,
                timeout=timeout,
                follow_redirects=False,
            ) as http_client:
                async with streamable_http_client(
                    config.endpoint,
                    http_client=http_client,
                    terminate_on_close=False,
                ) as (read_stream, write_stream, _):
                    async with ClientSession(
                        read_stream,
                        write_stream,
                        read_timeout_seconds=read_timeout,
                    ) as client:
                        await client.initialize()
                        result = await client.call_tool(tool_name, arguments=arguments)
        else:
            async with sse_client(
                config.endpoint,
                headers=headers,
                timeout=config.timeout_sec,
                sse_read_timeout=config.timeout_sec,
            ) as (read_stream, write_stream):
                async with ClientSession(
                    read_stream,
                    write_stream,
                    read_timeout_seconds=read_timeout,
                ) as client:
                    await client.initialize()
                    result = await client.call_tool(tool_name, arguments=arguments)
    except ProviderConnectionError:
        raise
    except Exception as exc:
        raise ProviderConnectionError(str(exc) or type(exc).__name__) from exc

    text = _tool_result_text(result, settings.analysis_provider_max_response_chars)
    return round((time.perf_counter() - started) * 1000, 1), text
