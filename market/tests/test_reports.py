from __future__ import annotations

from datetime import date

from market.reports import morning_brief as mb_mod
from market.reports import eod_review as eod_mod
from market.tests.conftest import FakeProvider


def test_build_morning_brief_structure(monkeypatch, fake_provider, sample_fii_dii_payload):
    monkeypatch.setattr(mb_mod, "YahooFinanceProvider", lambda: fake_provider)
    monkeypatch.setattr(
        mb_mod,
        "fetch_fii_dii_trade",
        lambda **kwargs: {
            "session_date": "08-Jul-2026",
            "fii": {"date": "08-Jul-2026", "net_value_cr": 1.0},
            "dii": {"date": "08-Jul-2026", "net_value_cr": 2.0},
        },
    )
    report = mb_mod.build_morning_brief("2026-07-09")
    assert report["report_type"] == "morning_brief"
    assert report["report_date"] == "2026-07-09"
    assert len(report["sections"]["market_pulse"]) == 4
    assert report["sections"]["technical_levels"]["levels"] is not None
    assert "disclaimer" in report
    assert "opening_outlook" in report["sections"]


def test_build_eod_review_includes_journal(monkeypatch, fake_provider, tmp_path):
    class EodProvider(FakeProvider):
        def get_sector_indices(self):
            return [{"sector": "Nifty IT", "change_pct": 1.2, "ltp": 100}]

        def get_nifty50_movers(self, top_n=5):
            return {"gainers": [{"symbol": "TCS", "ltp": 1, "change_pct": 2}], "losers": [], "count": 1}

    monkeypatch.setattr(eod_mod, "YahooFinanceProvider", EodProvider)
    monkeypatch.setattr(
        eod_mod,
        "fetch_fii_dii_trade",
        lambda **kwargs: {"fii": {"net_value_cr": 0}, "dii": {"net_value_cr": 0}},
    )
    db = tmp_path / "test.sqlite3"
    from services.trading_mcp.tools import log_trade_tool

    log_trade_tool(
        symbol="NIFTY 50",
        direction="LONG",
        entry_price=24000,
        quantity=25,
        db_path=db,
    )
    report = eod_mod.build_eod_review(date.today().isoformat(), db_path=db)
    assert report["report_type"] == "eod_review"
    assert report["sections"]["journal"]["count"] == 1
    assert "sector_performance" in report["sections"]
    assert "top_movers" in report["sections"]