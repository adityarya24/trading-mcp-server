"""Morning brief JSON builder (pre-market analytics, data-only)."""
from __future__ import annotations

from typing import Any

from market.providers.nse import fetch_fii_dii_trade
from market.providers.upstox import (
    UpstoxError,
    UpstoxProvider,
    index_keys_for,
    quotes_as_rows,
)
from market.providers.yahoo import YahooFinanceProvider
from market.reports.common import (
    SEBI_DISCLAIMER,
    market_session_tag,
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

_UPSTOX_INDICES = [
    "NIFTY 50",
    "SENSEX",
    "BANK NIFTY",
    "FIN NIFTY",
    "INDIA VIX",
]


def _build_opening_outlook() -> dict[str, Any]:
    """GIFT Nifty: no free reliable source on this VPS — never proxy from spot."""
    return {
        "gift_nifty": {
            "ltp": None,
            "available": False,
            "is_proxy": False,
            "message": "GIFT Nifty: unavailable",
        },
        "nifty_spot_reference": None,
        "premium_discount_pts": None,
        "premium_discount_pct": None,
        "expected_open_range": {"low": None, "high": None},
        "gap_assessment": "unavailable",
        "note": "GIFT Nifty: unavailable — no free reliable feed from this host; premium not computed.",
    }


def _upstox_indices(provider: UpstoxProvider | None) -> tuple[list[dict[str, Any]], str | None]:
    if provider is None:
        return [], "Upstox unavailable: no client"
    try:
        keys = index_keys_for(_UPSTOX_INDICES)
        quotes = provider.get_quotes(keys)
        return quotes_as_rows(quotes), None
    except UpstoxError as exc:
        return [], f"Upstox unavailable: {exc}"
    except Exception as exc:  # noqa: BLE001 — report still renders
        return [], f"Upstox unavailable: {exc}"


def _option_sections(
    provider: UpstoxProvider | None,
    quotes_by_name: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if provider is None:
        return {
            "NIFTY": {"symbol": "NIFTY", "available": False, "message": "Upstox unavailable"},
            "BANKNIFTY": {
                "symbol": "BANKNIFTY",
                "available": False,
                "message": "Upstox unavailable",
            },
        }
    nifty_spot = (quotes_by_name.get("NIFTY 50") or {}).get("ltp")
    bank_spot = (quotes_by_name.get("BANK NIFTY") or {}).get("ltp")
    return {
        "NIFTY": provider.option_chain_highlights("NIFTY", spot=nifty_spot),
        "BANKNIFTY": provider.option_chain_highlights("BANKNIFTY", spot=bank_spot),
    }


def build_morning_brief(
    report_date: str | None = None,
    *,
    upstox: UpstoxProvider | None = ...,  # type: ignore[assignment]
    yahoo: YahooFinanceProvider | None = None,
) -> dict[str, Any]:
    d = parse_report_date(report_date)
    yahoo_provider = yahoo or YahooFinanceProvider()

    upstox_err: str | None = None
    upstox_provider: UpstoxProvider | None
    if upstox is ...:
        try:
            upstox_provider = UpstoxProvider()
        except UpstoxError as exc:
            upstox_provider = None
            upstox_err = f"Upstox unavailable: {exc}"
    else:
        upstox_provider = upstox

    market_pulse, pulse_err = _upstox_indices(upstox_provider)
    if not market_pulse:
        # Soft fallback so the report still has structure; mark source.
        market_pulse = [
            quote_row(yahoo_provider.get_quote(sym).to_dict())
            for sym in ["NIFTY 50", "SENSEX", "BANK NIFTY", "INDIA VIX"]
        ]
        for row in market_pulse:
            row["source"] = "yahoo_fallback"
        upstox_err = upstox_err or pulse_err or "Upstox unavailable"

    quotes_map = {row["symbol"]: row for row in market_pulse if row.get("symbol")}

    global_cues = []
    for sym, label in _GLOBAL_SYMBOLS:
        q = yahoo_provider.get_quote(sym)
        global_cues.append({"label": label, **quote_row(q.to_dict())})

    # Technicals: prefer Yahoo history (stable); pivots from prev day OHLC
    nifty_candles = yahoo_provider.get_ohlc("NIFTY 50", count=60)
    technical: dict[str, Any] = {"symbol": "NIFTY 50", "levels": None, "dma_20": None}
    if len(nifty_candles) >= 2:
        prev = nifty_candles[-2]
        technical["levels"] = pivot_levels(prev.high, prev.low, prev.close)
        closes = [c.close for c in nifty_candles]
        technical["dma_20"] = simple_moving_average(closes, 20)
        dma_50 = simple_moving_average(closes, 50)
        if dma_50 is not None:
            technical["dma_50"] = dma_50
        # omit dma_50 key when None — never print "None"

    try:
        fii_dii = fetch_fii_dii_trade()
    except Exception as exc:
        fii_dii = {
            "error": str(exc),
            "disclaimer": "FII/DII unavailable — NSE endpoint blocked or down.",
        }

    status = compute_market_status(yahoo_provider)
    opening_outlook = _build_opening_outlook()
    option_chain = _option_sections(upstox_provider, quotes_map)

    session_tag = market_session_tag()

    return {
        "report_type": "morning_brief",
        "report_date": d.isoformat(),
        "generated_at": report_timestamp_ist(),
        "title": "Morning Brief",
        "session_tag": session_tag,
        "market_status": status,
        "upstox_error": upstox_err or pulse_err,
        "sections": {
            "market_pulse": market_pulse,
            "opening_outlook": opening_outlook,
            "global_cues": global_cues,
            "fii_dii": fii_dii,
            "technical_levels": technical,
            "option_chain_highlights": option_chain,
        },
        "disclaimer": SEBI_DISCLAIMER,
    }
