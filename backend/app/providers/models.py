"""Validated non-secret analysis provider configuration."""

from __future__ import annotations

from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ProviderType = Literal["mcp", "claude", "openai", "local"]
McpTransport = Literal["streamable_http", "sse"]
AnalysisCapability = Literal[
    "news_search",
    "economic_calendar",
    "chart_market",
    "volatility_session",
    "proposal_explanation",
    "loss_review",
]

ANALYSIS_CAPABILITIES: tuple[AnalysisCapability, ...] = (
    "news_search",
    "economic_calendar",
    "chart_market",
    "volatility_session",
    "proposal_explanation",
    "loss_review",
)


class AnalysisProviderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=2, max_length=100)
    provider_type: ProviderType
    enabled: bool = False
    transport: McpTransport | None = None
    endpoint: str | None = Field(default=None, max_length=2048)
    model_name: str | None = Field(default=None, max_length=200)
    web_search_enabled: bool = False
    secret_ref: str | None = Field(
        default=None,
        pattern=r"^(MCP_PROVIDER|ANALYSIS_PROVIDER)_[A-Z0-9_]+$",
        max_length=128,
    )
    timeout_sec: float = Field(default=10.0, ge=1.0, le=120.0)
    priority: int = Field(default=100, ge=1, le=1000)
    capabilities: list[str] = Field(default_factory=list, max_length=20)
    allowed_tools: list[str] = Field(default_factory=list, max_length=200)
    capability_tools: dict[str, str] = Field(default_factory=dict)

    @field_validator("display_name")
    @classmethod
    def _clean_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("capabilities")
    @classmethod
    def _validate_capabilities(cls, values: list[str]) -> list[str]:
        unique = list(dict.fromkeys(values))
        invalid = sorted(set(unique) - set(ANALYSIS_CAPABILITIES))
        if invalid:
            raise ValueError(f"Unsupported capabilities: {', '.join(invalid)}")
        return unique

    @field_validator("allowed_tools")
    @classmethod
    def _clean_tools(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if value.strip()]
        return list(dict.fromkeys(cleaned))

    @field_validator("capability_tools")
    @classmethod
    def _validate_capability_tools(cls, values: dict[str, str]) -> dict[str, str]:
        cleaned = {
            capability.strip(): tool.strip()
            for capability, tool in values.items()
            if capability.strip() and tool.strip()
        }
        invalid = sorted(set(cleaned) - set(ANALYSIS_CAPABILITIES))
        if invalid:
            raise ValueError(f"Unsupported capability tool mappings: {', '.join(invalid)}")
        return cleaned

    @field_validator("model_name")
    @classmethod
    def _clean_model_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def _validate_provider(self) -> AnalysisProviderConfig:
        if self.provider_type == "mcp":
            if not self.transport:
                raise ValueError("MCP provider requires a transport")
            if not self.endpoint:
                raise ValueError("MCP provider requires an endpoint")
            unmapped = [
                capability
                for capability in self.capabilities
                if capability not in self.capability_tools
            ]
            if self.enabled and unmapped:
                raise ValueError(
                    "Enabled MCP provider requires a tool mapping for: "
                    + ", ".join(unmapped)
                )
            invalid_tools = sorted(
                set(self.capability_tools.values()) - set(self.allowed_tools)
            )
            if invalid_tools:
                raise ValueError(
                    "Capability tool mappings must reference allowed tools: "
                    + ", ".join(invalid_tools)
                )
        if self.provider_type == "local":
            if not self.endpoint:
                raise ValueError("Local/Open WebUI provider requires an endpoint")
            if not self.model_name:
                raise ValueError("Local/Open WebUI provider requires a model name")
        if self.provider_type == "openai":
            if not self.endpoint:
                raise ValueError("OpenAI provider requires an endpoint")
            if not self.model_name:
                raise ValueError("OpenAI provider requires a model name")
            if self.enabled and not self.secret_ref:
                raise ValueError(
                    "Enabled OpenAI provider requires a secret reference"
                )
        if self.endpoint:
            parsed = urlparse(self.endpoint)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                raise ValueError("Provider endpoint must be an http(s) URL")
            self.endpoint = self.endpoint.rstrip("/")
        return self
