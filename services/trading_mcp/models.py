"""Trading MCP server — models."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Quote:
    symbol: str
    ltp: float
    open: float | None = None
    high: float | None = None
    low: float | None = None
    prev_close: float | None = None
    change: float | None = None
    change_pct: float | None = None
    volume: int | None = None
    currency: str = "INR"
    fetched_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Candle:
    symbol: str
    timestamp: str  # ISO 8601
    open: float
    high: float
    low: float
    close: float
    volume: int | None = None
    interval: str = "1d"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MarketStatus:
    is_open: bool
    market: str
    current_time: str
    next_holiday: str | None = None
    today_expiry: bool = False
    expiry_instrument: str | None = None  # 'NIFTY' | 'SENSEX' | None
    vix: float | None = None
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Trade:
    trade_id: str
    symbol: str
    direction: str  # 'LONG' | 'SHORT'
    entry_price: float
    entry_time: str  # ISO 8601
    quantity: int
    stop_loss: float | None = None
    target: float | None = None
    exit_price: float | None = None
    exit_time: str | None = None
    pnl: float | None = None
    strategy: str | None = None
    tags: str | None = None  # JSON array as string
    notes: str | None = None
    review: str | None = None
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    status: str = "OPEN"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["tags"] = d.get("tags") or "[]"
        return d
