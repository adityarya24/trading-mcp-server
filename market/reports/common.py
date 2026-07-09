"""Shared report helpers — disclaimers, pivots, formatting."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

SEBI_DISCLAIMER = (
    "For informational purposes only. Not investment advice. "
    "SEBI registration: N/A. Data may be delayed or incomplete."
)


def report_timestamp_ist() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")


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
    }


def parse_report_date(value: str | None) -> date:
    if not value:
        return date.today()
    return date.fromisoformat(value[:10])