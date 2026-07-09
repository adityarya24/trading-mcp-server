"""Morning brief JSON builder (pre-market analytics, data-only)."""
from __future__ import annotations

from typing import Any

from market.providers.nse import fetch_fii_dii_trade
from market.providers.yahoo import YahooFinanceProvider
from market.reports.common import (
    SEBI_DISCLAIMER,
    parse_report_date,
    pivot_levels,
    quote_row,
    report_timestamp_ist,
    simple_moving_average,
)

from market.status import compute_market_status

_GLOBAL_SYMBOLS = [
    ("S&P 500", "S&P 500"),
    ("NASDAQ", "NASDAQ"),
    ("XAUUSD", "Gold"),
    ("USDINR", "USD/INR"),
    ("BRENT CRUDE", "Brent Crude"),
]


def _gap_assessment(premium_pct: float | None) -> str:
    if premium_pct is None:
        return "unknown"
    if premium_pct >= 0.5:
        return "mild_positive_gap"
    if premium_pct <= -0.5:
        return "mild_negative_gap"
    return "flat_to_mild"


def _build_opening_outlook(provider: YahooFinanceProvider) -> dict[str, Any]:
    gift = provider.get_gift_nifty_quote()
    spot = provider.get_quote("NIFTY 50")
    spot_ref = spot.prev_close or spot.ltp
    gift_ltp = float(gift.get("ltp") or 0)
    premium_pts = round(gift_ltp - spot_ref, 2) if spot_ref else None
    premium_pct = round((premium_pts / spot_ref) * 100, 4) if spot_ref and premium_pts is not None else None
    band = (spot_ref or 0) * 0.0025
    expected_low = round(spot_ref + (premium_pts or 0) - band, 2) if spot_ref else None
    expected_high = round(spot_ref + (premium_pts or 0) + band, 2) if spot_ref else None
    return {
        "gift_nifty": gift,
        "nifty_spot_reference": spot_ref,
        "premium_discount_pts": premium_pts,
        "premium_discount_pct": premium_pct,
        "expected_open_range": {"low": expected_low, "high": expected_high},
        "gap_assessment": _gap_assessment(premium_pct),
    }


def build_morning_brief(report_date: str | None = None) -> dict[str, Any]:
    d = parse_report_date(report_date)
    provider = YahooFinanceProvider()

    indices = ["NIFTY 50", "SENSEX", "BANK NIFTY", "INDIA VIX"]
    market_pulse = [quote_row(provider.get_quote(sym).to_dict()) for sym in indices]

    global_cues = []
    for sym, label in _GLOBAL_SYMBOLS:
        q = provider.get_quote(sym)
        global_cues.append({"label": label, **quote_row(q.to_dict())})

    nifty_candles = provider.get_ohlc("NIFTY 50", count=60)
    technical: dict[str, Any] = {"symbol": "NIFTY 50", "levels": None, "dma_20": None, "dma_50": None}
    if len(nifty_candles) >= 2:
        prev = nifty_candles[-2]
        technical["levels"] = pivot_levels(prev.high, prev.low, prev.close)
        closes = [c.close for c in nifty_candles]
        technical["dma_20"] = simple_moving_average(closes, 20)
        technical["dma_50"] = simple_moving_average(closes, 50)

    try:
        fii_dii = fetch_fii_dii_trade()
    except Exception as exc:
        fii_dii = {
            "error": str(exc),
            "disclaimer": "FII/DII unavailable — NSE endpoint blocked or down.",
        }

    status = compute_market_status(provider)
    opening_outlook = _build_opening_outlook(provider)

    options_section: dict[str, Any] | None = None
    if status.get("today_expiry"):
        options_section = provider.get_option_chain("NIFTY 50")

    return {
        "report_type": "morning_brief",
        "report_date": d.isoformat(),
        "generated_at": report_timestamp_ist(),
        "title": "Morning Brief",
        "market_status": status,
        "sections": {
            "market_pulse": market_pulse,
            "opening_outlook": opening_outlook,
            "global_cues": global_cues,
            "fii_dii": fii_dii,
            "technical_levels": technical,
            "option_chain_highlights": options_section,
        },
        "disclaimer": SEBI_DISCLAIMER,
    }