"""NSE market status helpers (open/holiday/expiry/VIX)."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from market.providers.yahoo import YahooFinanceProvider
from services.trading_mcp.models import MarketStatus

_HOLIDAYS_PATH = Path(__file__).resolve().parent / "data" / "holidays.json"


def _is_weekend(d) -> bool:
    return d.weekday() >= 5


def _load_holidays() -> list[dict]:
    if _HOLIDAYS_PATH.exists():
        return json.loads(_HOLIDAYS_PATH.read_text())
    return []


def compute_market_status(provider: YahooFinanceProvider | None = None) -> dict:
    provider = provider or YahooFinanceProvider()
    now = datetime.now()
    today = now.date()
    today_str = today.isoformat()

    holidays = _load_holidays()
    holiday_today = next((h for h in holidays if h["date"] == today_str), None)
    future_holidays = [h for h in holidays if h["date"] > today_str]
    next_holiday = future_holidays[0] if future_holidays else None

    weekday = today.weekday()
    today_expiry = weekday in (1, 3)
    expiry_instrument = "NIFTY" if weekday == 1 else "SENSEX" if weekday == 3 else None

    now_time = now.time()
    market_open_time = now_time >= datetime.strptime("09:15", "%H:%M").time()
    market_close_time = now_time >= datetime.strptime("15:30", "%H:%M").time()
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
        vix=round(vix, 2) if vix else None,
        message=" | ".join(message_parts) if message_parts else "Regular trading day",
    ).to_dict()