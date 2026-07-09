from __future__ import annotations

import services.trading_mcp.tools as tools_mod
from services.trading_mcp.server import list_tool_names

from market.tests.conftest import FakeProvider


def _reset_provider():
    tools_mod._default_provider = None


def test_tool_registry_count():
    names = list_tool_names()
    assert len(names) == 9
    assert "generate_morning_brief" in names
    assert "export_report_pdf" in names
    assert "get_option_chain" in names


def test_log_and_journal_roundtrip(tmp_path, monkeypatch):
    _reset_provider()
    monkeypatch.setattr(tools_mod, "_resolve_provider", lambda: FakeProvider())
    db = tmp_path / "journal.sqlite3"

    logged = tools_mod.log_trade_tool(
        symbol="NIFTY 50",
        direction="LONG",
        entry_price=23960,
        quantity=50,
        db_path=db,
    )
    assert logged["status"] == "logged"
    trade_id = logged["trade_id"]

    journal = tools_mod.get_journal_tool("2026-07-09", "2026-07-09", db_path=db)
    assert journal["count"] == 1
    assert journal["trades"][0]["trade_id"] == trade_id


def test_morning_brief_and_pdf_export(tmp_path, monkeypatch):
    _reset_provider()
    monkeypatch.setattr(tools_mod, "_resolve_provider", lambda: FakeProvider())
    monkeypatch.setattr(
        tools_mod,
        "fetch_fii_dii_trade",
        lambda: {"fii": {"net_value_cr": 1}, "dii": {"net_value_cr": 2}},
    )
    monkeypatch.setattr(
        "market.reports.morning_brief.YahooFinanceProvider",
        lambda: FakeProvider(),
    )
    monkeypatch.setattr(
        "market.reports.morning_brief.fetch_fii_dii_trade",
        lambda **k: {"fii": {"net_value_cr": 1}, "dii": {"net_value_cr": 2}},
    )

    db = tmp_path / "briefs.sqlite3"
    gen = tools_mod.generate_morning_brief_tool(db_path=db)
    brief_id = gen["brief_id"]
    assert gen["report"]["report_type"] == "morning_brief"

    out = tmp_path / "out.pdf"
    exported = tools_mod.export_report_pdf_tool(
        brief_id=brief_id,
        output_path=str(out),
        renderer="reportlab",
        db_path=db,
    )
    assert exported["renderer"] == "reportlab"
    assert out.exists()