"""NSE market status helpers (open/holiday/expiry/VIX).

Holiday calendar, expiry schedule, and market timings come from
``market/config/defaults.yaml`` so they can be updated without code changes.
All clock logic is pinned to IST regardless of host timezone.
"""
from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from market.models import MarketStatus
from market.providers.yahoo import YahooFinanceProvider

IST = ZoneInfo("Asia/Kolkata")

_CONFIG_PATH = Path(__file__).resolve().parent / "config" / "defaults.yaml"

_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _is_weekend(d) -> bool:
    return d.weekday() >= 5


@lru_cache(maxsize=1)
def _load_config() -> dict:
    if _CONFIG_PATH.exists():
        return yaml.safe_load(_CONFIG_PATH.read_text()) or {}
    return {}


def _load_holidays() -> list[dict]:
    return _load_config().get("holidays") or []


def _expiry_for_weekday(weekday: int) -> str | None:
    schedule = _load_config().get("expiry") or {}
    for instrument, day_name in schedule.items():
        if _WEEKDAYS.index(str(day_name).lower()) == weekday:
            return instrument.upper()
    return None


def _market_timings() -> tuple[str, str]:
    timings = (_load_config().get("timings") or {}).get("equity") or {}
    return timings.get("open", "09:15"), timings.get("close", "15:30")


def compute_market_status(provider: YahooFinanceProvider | None = None) -> dict:
    provider = provider or YahooFinanceProvider()
    now = datetime.now(IST)
    today = now.date()
    today_str = today.isoformat()

    holidays = _load_holidays()
    holiday_today = next((h for h in holidays if h["date"] == today_str), None)
    future_holidays = sorted(
        (h for h in holidays if h["date"] > today_str),
        key=lambda h: h["date"],
    )
    next_holiday = future_holidays[0] if future_holidays else None

    expiry_instrument = _expiry_for_weekday(today.weekday())
    today_expiry = expiry_instrument is not None

    open_str, close_str = _market_timings()
    now_time = now.time()
    market_open_time = now_time >= datetime.strptime(open_str, "%H:%M").time()
    market_close_time = now_time >= datetime.strptime(close_str, "%H:%M").time()
    is_holiday = holiday_today is not None
    is_open = (
        not _is_weekend(today)
        and not is_holiday
        and market_open_time
        and not market_close_time
    )

    vix = None
    try:
        vix_quote = provider.get_quote("INDIA VIX")
        vix = vix_quote.ltp
    except Exception:
        pass

    message_parts = []
    if is_holiday:
        message_parts.append(f"Holiday: {holiday_today['reason']}")
    if today_expiry:
        message_parts.append(f"{expiry_instrument} Expiry Day — gamma zone 1:30-3PM")

    return MarketStatus(
        is_open=is_open,
        market="NSE",
        current_time=now.isoformat(),
        next_holiday=(
            f"{next_holiday['date']} — {next_holiday['reason']}" if next_holiday else None
        ),
        today_expiry=today_expiry,
        expiry_instrument=expiry_instrument,
        vix=round(vix, 2) if vix is not None else None,
        message=" | ".join(message_parts) if message_parts else "Regular trading day",
    ).to_dict()