"""Backend TCP server for the outbound MQL5 EA connection.

Native MQL5 sockets can connect to a server but cannot listen/accept. Therefore
the Python backend owns the listening socket and the EA connects outward.
"""

from __future__ import annotations

import hmac
import json
import socket
import threading
import uuid
from datetime import datetime, timezone

from app.core.enums import AccountType, BridgeHealth, OrderSide
from app.core.logging import get_logger
from app.domain.errors import BridgeUnavailableError
from app.domain.models import (
    AccountInfo,
    BridgeHealthStatus,
    Candle,
    ClosedTrade,
    OrderRequest,
    Position,
    SymbolInfo,
    SymbolQuote,
)

logger = get_logger(__name__)


class EaSocketBridge:
    def __init__(
        self,
        host: str,
        port: int,
        timeout: float = 5.0,
        *,
        shared_secret: str,
    ) -> None:
        if not shared_secret:
            raise ValueError("MT5 EA shared secret is required")
        self.host = host
        self.port = port
        self.timeout = timeout
        self._shared_secret = shared_secret
        self._connection: socket.socket | None = None
        self._connection_lock = threading.Lock()
        self._rpc_lock = threading.Lock()
        self._stop = threading.Event()
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listener.bind((host, port))
        self._listener.listen(1)
        self._listener.settimeout(1.0)
        self.port = self._listener.getsockname()[1]
        self._thread = threading.Thread(
            target=self._accept_loop,
            name="mt5-ea-socket-server",
            daemon=True,
        )
        self._thread.start()
        logger.info("MT5 EA socket server listening on %s:%s", self.host, self.port)

    def _accept_loop(self) -> None:
        while not self._stop.is_set():
            try:
                connection, address = self._listener.accept()
            except TimeoutError:
                continue
            except OSError:
                if not self._stop.is_set():
                    logger.exception("MT5 EA socket accept failed")
                return
            connection.settimeout(self.timeout)
            try:
                auth = json.loads(self._read_line(connection).decode("utf-8"))
                supplied_secret = auth.get("secret", "") if isinstance(auth, dict) else ""
                authenticated = (
                    isinstance(auth, dict)
                    and auth.get("type") == "auth"
                    and isinstance(supplied_secret, str)
                    and hmac.compare_digest(supplied_secret, self._shared_secret)
                )
            except (BridgeUnavailableError, OSError, ValueError, UnicodeError) as exc:
                logger.warning("MT5 EA authentication failed from %s:%s: %s", *address, exc)
                authenticated = False
            if not authenticated:
                logger.warning("Rejected unauthenticated MT5 EA connection from %s:%s", *address)
                try:
                    connection.close()
                except OSError:
                    pass
                continue
            with self._rpc_lock:
                with self._connection_lock:
                    previous = self._connection
                    self._connection = connection
                if previous is not None:
                    try:
                        previous.close()
                    except OSError:
                        pass
            logger.info("Authenticated MT5 EA connected from %s:%s", *address)

    def _clear_connection(self, connection: socket.socket) -> None:
        with self._connection_lock:
            if self._connection is connection:
                self._connection = None
        try:
            connection.close()
        except OSError:
            pass

    def _current_connection(self) -> socket.socket:
        with self._connection_lock:
            connection = self._connection
        if connection is None:
            raise BridgeUnavailableError("MQL5 EA is not connected")
        return connection

    def _read_line(self, connection: socket.socket) -> bytes:
        buffer = bytearray()
        while b"\n" not in buffer:
            chunk = connection.recv(4096)
            if not chunk:
                raise BridgeUnavailableError("MQL5 EA disconnected")
            buffer.extend(chunk)
            if len(buffer) > 1_000_000:
                raise BridgeUnavailableError("MQL5 EA response exceeded size limit")
        return bytes(buffer).split(b"\n", 1)[0]

    def _rpc(self, method: str, params: dict | None = None) -> dict:
        request_id = uuid.uuid4().hex
        payload = {
            "id": request_id,
            "method": method,
            "params": params or {},
        }
        wire = (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")
        with self._rpc_lock:
            connection = self._current_connection()
            try:
                connection.sendall(wire)
                response = json.loads(self._read_line(connection).decode("utf-8"))
            except (OSError, ValueError, UnicodeError) as exc:
                self._clear_connection(connection)
                raise BridgeUnavailableError(f"MQL5 EA transport failed: {exc}") from exc
        if response.get("id") not in {None, request_id}:
            raise BridgeUnavailableError("MQL5 EA response id did not match request")
        if response.get("error"):
            raise BridgeUnavailableError(f"MQL5 EA error: {response['error']}")
        result = response.get("result", response)
        if not isinstance(result, dict):
            raise BridgeUnavailableError("MQL5 EA returned a non-object result")
        return result

    def health(self) -> BridgeHealthStatus:
        try:
            result = self._rpc("health")
        except BridgeUnavailableError as exc:
            return BridgeHealthStatus(health=BridgeHealth.UNKNOWN, detail=str(exc))
        heartbeat_epoch = result.get("server_time_epoch")
        heartbeat = result.get("server_time")
        try:
            if heartbeat_epoch is not None:
                heartbeat_at = datetime.fromtimestamp(float(heartbeat_epoch), timezone.utc)
            else:
                heartbeat_at = (
                    datetime.fromisoformat(heartbeat)
                    if heartbeat
                    else datetime.now(timezone.utc)
                )
        except (TypeError, ValueError, OSError):
            heartbeat_at = None
        return BridgeHealthStatus(
            health=BridgeHealth.HEALTHY if result.get("ok") else BridgeHealth.UNHEALTHY,
            last_heartbeat=heartbeat_at,
            detail=result.get("detail", ""),
        )

    def account_info(self) -> AccountInfo:
        result = self._rpc("account_info")
        return AccountInfo(
            account_type=AccountType(result.get("account_type", "UNKNOWN")),
            login=result.get("login"),
            server=result.get("server"),
            currency=result.get("currency", "USD"),
            balance=result.get("balance", 0.0),
            equity=result.get("equity", 0.0),
            margin=result.get("margin", 0.0),
            free_margin=result.get("free_margin", 0.0),
            leverage=result.get("leverage", 0),
        )

    def quote(self, symbol: str) -> SymbolQuote:
        result = self._rpc("quote", {"symbol": symbol})
        timestamp = result.get("time")
        timestamp_epoch = result.get("time_epoch")
        return SymbolQuote(
            symbol=symbol,
            bid=result["bid"],
            ask=result["ask"],
            spread_points=result["spread_points"],
            time=(
                datetime.fromtimestamp(float(timestamp_epoch), timezone.utc)
                if timestamp_epoch is not None
                else datetime.fromisoformat(timestamp)
                if timestamp
                else datetime.now(timezone.utc)
            ),
        )

    def symbol_info(self, symbol: str) -> SymbolInfo:
        result = self._rpc("symbol_info", {"symbol": symbol})
        return SymbolInfo(
            symbol=symbol,
            tick_size=result["tick_size"],
            tick_value=result["tick_value"],
            volume_min=result["volume_min"],
            volume_max=result["volume_max"],
            volume_step=result["volume_step"],
        )

    def candles(self, symbol: str, timeframe: str, count: int) -> list[Candle]:
        result = self._rpc(
            "candles", {"symbol": symbol, "timeframe": timeframe, "count": count}
        )
        bars: list[Candle] = []
        for item in result.get("candles", []):
            bars.append(
                Candle(
                    time=self._epoch_or_iso(item, "time_epoch", "time"),
                    open=item["open"],
                    high=item["high"],
                    low=item["low"],
                    close=item["close"],
                    volume=item.get("volume", 0.0),
                )
            )
        return bars

    def positions(self) -> list[Position]:
        result = self._rpc("positions")
        return [
            Position(
                ticket=item["ticket"],
                symbol=item["symbol"],
                side=OrderSide(item["side"]),
                volume=item["volume"],
                open_price=item["open_price"],
                sl=item.get("sl"),
                tp=item.get("tp"),
                profit=item.get("profit", 0.0),
                open_time=(
                    datetime.fromtimestamp(float(item["open_time_epoch"]), timezone.utc)
                    if item.get("open_time_epoch") is not None
                    else datetime.fromisoformat(item["open_time"])
                    if item.get("open_time")
                    else None
                ),
            )
            for item in result.get("positions", [])
        ]

    @staticmethod
    def _epoch_or_iso(item: dict, epoch_key: str, iso_key: str) -> datetime | None:
        if item.get(epoch_key) is not None:
            return datetime.fromtimestamp(float(item[epoch_key]), timezone.utc)
        if item.get(iso_key):
            return datetime.fromisoformat(item[iso_key])
        return None

    @classmethod
    def _parse_closed_trade(cls, item: dict) -> ClosedTrade:
        side = item.get("side")
        return ClosedTrade(
            ticket=item["ticket"],
            symbol=item["symbol"],
            profit=item["profit"],
            close_time=cls._epoch_or_iso(item, "close_time_epoch", "close_time"),
            side=OrderSide(side) if side else None,
            volume=item.get("volume"),
            entry_price=item.get("entry_price"),
            exit_price=item.get("exit_price"),
            open_time=cls._epoch_or_iso(item, "open_time_epoch", "open_time"),
            exit_reason=item.get("exit_reason"),
        )

    def closed_trades_today(self) -> list[ClosedTrade]:
        result = self._rpc("closed_trades_today")
        return [self._parse_closed_trade(item) for item in result.get("trades", [])]

    def closed_trades_range(self, start: datetime, end: datetime) -> list[ClosedTrade]:
        result = self._rpc(
            "closed_trades_range",
            {"start_epoch": start.timestamp(), "end_epoch": end.timestamp()},
        )
        return [self._parse_closed_trade(item) for item in result.get("trades", [])]

    def order_status(self, idempotency_key: str) -> dict | None:
        result = self._rpc("order_status", {"idempotency_key": idempotency_key})
        if result.get("found") is False:
            return None
        order = result.get("order", result)
        return order if isinstance(order, dict) else None

    def execute_order(self, request: OrderRequest) -> dict:
        return self._rpc(
            "execute_order",
            {
                "symbol": request.symbol,
                "side": request.side.value,
                "volume": request.volume,
                "sl": request.sl,
                "tp": request.tp,
                "idempotency_key": request.idempotency_key,
            },
        )

    def close(self) -> None:
        self._stop.set()
        try:
            self._listener.close()
        except OSError:
            pass
        with self._connection_lock:
            connection = self._connection
            self._connection = None
        if connection is not None:
            try:
                connection.close()
            except OSError:
                pass
        self._thread.join(timeout=2.0)
