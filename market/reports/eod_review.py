"""End-of-day review JSON builder."""
from __future__ import annotations

from pathlib import Path
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
    quote_row,
    report_timestamp_ist,
)
from market.status import compute_market_status
from services.trading_mcp.storage import default_db_path, query_trades

_UPSTOX_INDICES = [
    "NIFTY 50",
    "SENSEX",
    "BANK NIFTY",
    "FIN NIFTY",
    "INDIA VIX",
]


def _sector_performance(sectors: list[dict[str, Any]]) -> dict[str, Any]:
    ranked = [s for s in sectors if s.get("change_pct") is not None]
    ranked.sort(key=lambda s: s["change_pct"], reverse=True)
    return {
        "top_3": ranked[:3],
        "bottom_3": list(reversed(ranked[-3:])) if len(ranked) >= 3 else ranked[:0],
        "all": sectors,
    }


def _upstox_scorecard(provider: UpstoxProvider | None) -> tuple[list[dict[str, Any]], str | None]:
    if provider is None:
        return [], "Upstox unavailable: no client"
    try:
        keys = index_keys_for(_UPSTOX_INDICES)
        quotes = provider.get_quotes(keys)
        return quotes_as_rows(quotes), None
    except UpstoxError as exc:
        return [], f"Upstox unavailable: {exc}"
    except Exception as exc:  # noqa: BLE001
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
    return {
        "NIFTY": provider.option_chain_highlights(
            "NIFTY", spot=(quotes_by_name.get("NIFTY 50") or {}).get("ltp")
        ),
        "BANKNIFTY": provider.option_chain_highlights(
            "BANKNIFTY", spot=(quotes_by_name.get("BANK NIFTY") or {}).get("ltp")
        ),
    }


def build_eod_review(
    report_date: str | None = None,
    db_path: Path | str | None = None,
    *,
    upstox: UpstoxProvider | None = ...,  # type: ignore[assignment]
    yahoo: YahooFinanceProvider | None = None,
) -> dict[str, Any]:
    d = parse_report_date(report_date)
    yahoo_provider = yahoo or YahooFinanceProvider()
    day = d.isoformat()

    upstox_err: str | None = None
    if upstox is ...:
        try:
            upstox_provider: UpstoxProvider | None = UpstoxProvider()
        except UpstoxError as exc:
            upstox_provider = None
            upstox_err = f"Upstox unavailable: {exc}"
    else:
        upstox_provider = upstox

    scorecard, pulse_err = _upstox_scorecard(upstox_provider)
    if not scorecard:
        scorecard = [
            quote_row(yahoo_provider.get_quote(sym).to_dict())
            for sym in ["NIFTY 50", "SENSEX", "BANK NIFTY"]
        ]
        for row in scorecard:
            row["source"] = "yahoo_fallback"
        upstox_err = upstox_err or pulse_err or "Upstox unavailable"

    quotes_map = {row["symbol"]: row for row in scorecard if row.get("symbol")}
    option_chain = _option_sections(upstox_provider, quotes_map)

    try:
        fii_dii = fetch_fii_dii_trade()
    except Exception as exc:
        fii_dii = {"error": str(exc)}

    db = db_path or default_db_path()
    trades = query_trades(db, day, day)
    journal = {
        "date": day,
        "count": len(trades),
        "trades": [t.to_dict() for t in trades],
    }

    status = compute_market_status(yahoo_provider)
    sectors = yahoo_provider.get_sector_indices()
    movers = yahoo_provider.get_nifty50_movers(top_n=5)

    return {
        "report_type": "eod_review",
        "report_date": day,
        "generated_at": report_timestamp_ist(),
        "title": "EOD Review",
        "session_tag": market_session_tag(),
        "market_status": status,
        "upstox_error": upstox_err or pulse_err,
        "sections": {
            "index_scorecard": scorecard,
            "option_chain_highlights": option_chain,
            "sector_performance": _sector_performance(sectors),
            "top_movers": movers,
            "fii_dii": fii_dii,
            "journal": journal,
        },
        "disclaimer": SEBI_DISCLAIMER,
    }
