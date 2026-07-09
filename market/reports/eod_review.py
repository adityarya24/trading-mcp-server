"""End-of-day review JSON builder."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from market.providers.nse import fetch_fii_dii_trade
from market.providers.yahoo import YahooFinanceProvider
from market.reports.common import (
    SEBI_DISCLAIMER,
    parse_report_date,
    quote_row,
    report_timestamp_ist,
)

from services.trading_mcp.storage import default_db_path, query_trades
from market.status import compute_market_status


def _sector_performance(sectors: list[dict[str, Any]]) -> dict[str, Any]:
    ranked = [s for s in sectors if s.get("change_pct") is not None]
    ranked.sort(key=lambda s: s["change_pct"], reverse=True)
    return {
        "top_3": ranked[:3],
        "bottom_3": list(reversed(ranked[-3:])) if len(ranked) >= 3 else ranked[:0],
        "all": sectors,
    }


def build_eod_review(
    report_date: str | None = None,
    db_path: Path | str | None = None,
) -> dict[str, Any]:
    d = parse_report_date(report_date)
    provider = YahooFinanceProvider()
    day = d.isoformat()

    indices = ["NIFTY 50", "SENSEX", "BANK NIFTY"]
    scorecard = [quote_row(provider.get_quote(sym).to_dict()) for sym in indices]

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

    status = compute_market_status(provider)
    sectors = provider.get_sector_indices()
    movers = provider.get_nifty50_movers(top_n=5)

    return {
        "report_type": "eod_review",
        "report_date": day,
        "generated_at": report_timestamp_ist(),
        "title": "EOD Review",
        "market_status": status,
        "sections": {
            "index_scorecard": scorecard,
            "sector_performance": _sector_performance(sectors),
            "top_movers": movers,
            "fii_dii": fii_dii,
            "journal": journal,
        },
        "disclaimer": SEBI_DISCLAIMER,
    }