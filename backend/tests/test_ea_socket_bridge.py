"""TCP server contract used by the outbound MQL5 EA client."""

from __future__ import annotations

import json
import socket
import threading
import time
from datetime import datetime, timezone

from app.bridge.ea_socket_bridge import EaSocketBridge
from app.core.enums import BridgeHealth, OrderSide
from app.domain.models import OrderRequest


def _fake_ea(host: str, port: int, stop: threading.Event, secret: str) -> None:
    connection = socket.create_connection((host, port), timeout=2)
    connection.settimeout(2)
    connection.sendall(
        (json.dumps({"type": "auth", "secret": secret}) + "\n").encode()
    )
    reader = connection.makefile("rb")
    try:
        while not stop.is_set():
            line = reader.readline()
            if not line:
                return
            request = json.loads(line)
            method = request["method"]
            if method == "health":
                result = {
                    "ok": True,
                    "detail": "fake EA",
                    "server_time": datetime.now(timezone.utc).isoformat(),
                }
            elif method == "symbol_info":
                result = {
                    "tick_size": 0.01,
                    "tick_value": 1.0,
                    "volume_min": 0.01,
                    "volume_max": 100.0,
                    "volume_step": 0.01,
                }
            elif method == "execute_order":
                result = {
                    "retcode": 10009,
                    "retcode_text": "Request completed",
                    "ticket": 123,
                }
            else:
                result = {}
            response = {"id": request["id"], "result": result}
            connection.sendall((json.dumps(response) + "\n").encode())
    finally:
        reader.close()
        connection.close()


def test_backend_accepts_outbound_ea_and_runs_json_rpc():
    bridge = EaSocketBridge(
        "127.0.0.1",
        0,
        timeout=2,
        shared_secret="test-shared-secret",
    )
    stop = threading.Event()
    client = threading.Thread(
        target=_fake_ea,
        args=("127.0.0.1", bridge.port, stop, "test-shared-secret"),
        daemon=True,
    )
    client.start()
    try:
        deadline = time.monotonic() + 2
        health = bridge.health()
        while health.health is not BridgeHealth.HEALTHY and time.monotonic() < deadline:
            time.sleep(0.01)
            health = bridge.health()
        assert health.health is BridgeHealth.HEALTHY
        assert bridge.symbol_info("XAUUSD").tick_value == 1.0
        response = bridge.execute_order(
            OrderRequest(
                symbol="XAUUSD",
                side=OrderSide.BUY,
                volume=0.1,
                sl=2349.0,
                risk_pct=1.0,
                idempotency_key="socket-order-123",
            )
        )
        assert response["retcode"] == 10009
        assert response["ticket"] == 123
    finally:
        stop.set()
        bridge.close()
        client.join(timeout=2)


def test_backend_rejects_ea_with_wrong_secret():
    bridge = EaSocketBridge(
        "127.0.0.1",
        0,
        timeout=0.2,
        shared_secret="expected-secret",
    )
    connection = socket.create_connection(("127.0.0.1", bridge.port), timeout=2)
    try:
        connection.sendall(
            (json.dumps({"type": "auth", "secret": "wrong-secret"}) + "\n").encode()
        )
        time.sleep(0.05)
        assert bridge.health().health is BridgeHealth.UNKNOWN
    finally:
        connection.close()
        bridge.close()
