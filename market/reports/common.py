"""Shared report helpers — disclaimers, pivots, formatting."""
from __future__ import annotations

from datetime import date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

SEBI_DISCLAIMER = (
    "For informational purposes only. Not investment advice. "
    "SEBI registration: N/A. Data may be delayed or incomplete."
)


def report_timestamp_ist() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")


def market_session_tag(now: datetime | None = None) -> str:
    """'Previous close' before 09:15 IST, 'Live' in market hours, 'Close' after 15:30.

    Weekends read as 'Previous close' (holidays aren't known here).
    """
    now = now or datetime.now(IST)
    if now.tzinfo is None:
        now = now.replace(tzinfo=IST)
    else:
        now = now.astimezone(IST)
    if now.weekday() >= 5 or now.time() < time(9, 15):
        return "Previous close"
    return "Live" if now.time() <= time(15, 30) else "Close"


def pivot_levels(high: float, low: float, close: float) -> dict[str, float]:
    pivot = (high + low + close) / 3.0
    r1 = 2 * pivot - low
    s1 = 2 * pivot - high
    r2 = pivot + (high - low)
    s2 = pivot - (high - low)
    return {
        "pivot": round(pivot, 2),
        "r1": round(r1, 2),
        "r2": round(r2, 2),
        "s1": round(s1, 2),
        "s2": round(s2, 2),
    }


def simple_moving_average(closes: list[float], window: int) -> float | None:
    if len(closes) < window:
        return None
    segment = closes[-window:]
    return round(sum(segment) / window, 2)


def quote_row(quote_dict: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": quote_dict.get("symbol"),
        "ltp": quote_dict.get("ltp"),
        "open": quote_dict.get("open"),
        "high": quote_dict.get("high"),
        "low": quote_dict.get("low"),
        "prev_close": quote_dict.get("prev_close"),
        "change": quote_dict.get("change"),
        "change_pct": quote_dict.get("change_pct"),
        "volume": quote_dict.get("volume"),
        "currency": quote_dict.get("currency"),
        "error": quote_dict.get("error"),
    }


def parse_report_date(value: str | None) -> date:
    if not value:
        return date.today()
    return date.fromisoformat(value[:10])


def fmt_price(value: Any, decimals: int = 2) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):,.{decimals}f}"
    except (TypeError, ValueError):
        return str(value)


def fmt_pct(value: Any, decimals: int = 2) -> str:
    if value is None:
        return "—"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{v:+.{decimals}f}%"


def fmt_oi(value: Any) -> str:
    """Format OI in lakh/crore (Indian)."""
    if value is None:
        return "—"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    if abs(v) >= 1_00_00_000:  # 1 crore
        return f"{v / 1_00_00_000:.2f} Cr"
    if abs(v) >= 1_00_000:  # 1 lakh
        return f"{v / 1_00_000:.2f} L"
    return f"{v:,.0f}"


def fmt_signed_cr(value: Any) -> str:
    if value is None:
        return "—"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    sign = "+" if v >= 0 else "−"
    return f"{sign}₹{abs(v):,.0f} Cr"
