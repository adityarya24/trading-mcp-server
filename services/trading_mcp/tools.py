"""Tool functions exposed by the trading MCP service."""
from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from market.providers.nse import fetch_fii_dii_trade
from market.reports.eod_review import build_eod_review
from market.reports.morning_brief import build_morning_brief
from market.reports.pdf_export import export_report_pdf
from market.status import compute_market_status

from .models import Quote, Trade
from .storage import default_db_path, insert_trade, query_trades
from .storage_briefs import get_brief, insert_brief, update_brief_pdf_path

from market.providers.base import MarketDataProvider
from market.providers.yahoo import YahooFinanceProvider

_default_provider: MarketDataProvider | None = None


def _resolve_provider() -> MarketDataProvider:
    global _default_provider
    if _default_provider is None:
        _default_provider = YahooFinanceProvider()
    return _default_provider


def get_quote_tool(symbol: str) -> dict[str, Any]:
    provider = _resolve_provider()
    quote: Quote = provider.get_quote(symbol)
    return quote.to_dict()


def get_market_status_tool() -> dict[str, Any]:
    return compute_market_status(_resolve_provider())


def get_fii_dii_flow_tool() -> dict[str, Any]:
    return fetch_fii_dii_trade()


def log_trade_tool(
    symbol: str,
    direction: str,
    entry_price: float,
    quantity: int,
    stop_loss: float | None = None,
    target: float | None = None,
    strategy: str | None = None,
    tags: str | None = None,
    notes: str | None = None,
    db_path: Path | str | None = None,
) -> dict[str, Any]:
    db = Path(db_path) if db_path else default_db_path()
    trade_id = f"trd-{uuid.uuid4().hex[:12]}"
    now = datetime.now().isoformat(timespec="seconds")

    trade = Trade(
        trade_id=trade_id,
        symbol=symbol,
        direction=direction.upper(),
        entry_price=entry_price,
        entry_time=now,
        quantity=quantity,
        stop_loss=stop_loss,
        target=target,
        strategy=strategy,
        tags=tags,
        notes=notes,
        created_at=now,
        updated_at=now,
        status="OPEN",
    )
    insert_trade(db, trade)
    return {"trade_id": trade_id, "status": "logged", "trade": trade.to_dict()}


def get_journal_tool(
    from_date: str,
    to_date: str,
    symbol: str | None = None,
    direction: str | None = None,
    db_path: Path | str | None = None,
) -> dict[str, Any]:
    db = Path(db_path) if db_path else default_db_path()
    trades = query_trades(db, from_date, to_date, symbol, direction)
    return {
        "count": len(trades),
        "trades": [t.to_dict() for t in trades],
        "from": from_date,
        "to": to_date,
    }


def generate_morning_brief_tool(
    report_date: str | None = None,
    db_path: Path | str | None = None,
) -> dict[str, Any]:
    db = Path(db_path) if db_path else default_db_path()
    report = build_morning_brief(report_date)
    brief_id = insert_brief(db, report)
    return {"brief_id": brief_id, "status": "generated", "report": report}


def generate_eod_review_tool(
    report_date: str | None = None,
    db_path: Path | str | None = None,
) -> dict[str, Any]:
    db = Path(db_path) if db_path else default_db_path()
    report = build_eod_review(report_date, db_path=db)
    brief_id = insert_brief(db, report)
    return {"brief_id": brief_id, "status": "generated", "report": report}


def export_report_pdf_tool(
    brief_id: str | None = None,
    output_path: str | None = None,
    renderer: str | None = None,
    db_path: Path | str | None = None,
) -> dict[str, Any]:
    if not brief_id:
        raise ValueError("brief_id is required — generate a brief first")
    db = Path(db_path) if db_path else default_db_path()
    stored = get_brief(db, brief_id)
    if not stored:
        raise ValueError(f"Unknown brief_id: {brief_id}")
    report = stored["report"]
    out = Path(output_path) if output_path else Path("data/reports") / f"{brief_id}.pdf"
    meta = export_report_pdf(report, out, renderer=renderer)
    update_brief_pdf_path(db, brief_id, meta["pdf_path"])
    return {"brief_id": brief_id, "status": "exported", **meta}


TOOLS: dict[str, Any] = {
    "get_quote": get_quote_tool,
    "get_market_status": get_market_status_tool,
    "get_fii_dii_flow": get_fii_dii_flow_tool,
    "log_trade": log_trade_tool,
    "get_journal": get_journal_tool,
    "generate_morning_brief": generate_morning_brief_tool,
    "generate_eod_review": generate_eod_review_tool,
    "export_report_pdf": export_report_pdf_tool,
}