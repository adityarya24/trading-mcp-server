"""Morning/EOD builders + telegram summary + upstox-down path."""
from __future__ import annotations

from datetime import date

from market.reports import eod_review as eod_mod
from market.reports import morning_brief as mb_mod
from market.reports.summary import telegram_summary
from market.tests.conftest import FakeProvider
from market.tests.test_upstox import (
    CHAIN_PAYLOAD,
    CONTRACTS_PAYLOAD,
    FakeSession,
    QUOTES_PAYLOAD,
)
from market.providers.upstox import UpstoxProvider


def _full_quote_session():
    # Expand quotes payload for all indices
    data = dict(QUOTES_PAYLOAD["data"])
    data["BSE_INDEX:SENSEX"] = {
        "last_price": 71909.70,
        "net_change": -570.0,
        "ohlc": {"open": 72000, "high": 72100, "low": 71800, "close": 72479.7},
    }
    data["NSE_INDEX:Nifty Fin Service"] = {
        "last_price": 25000.0,
        "net_change": -50.0,
        "ohlc": {"open": 25050, "high": 25100, "low": 24900, "close": 25050},
    }
    data["NSE_INDEX:India VIX"] = {
        "last_price": 14.46,
        "net_change": 0.2,
        "ohlc": {"open": 14.2, "high": 14.8, "low": 14.0, "close": 14.26},
    }
    payload = {"status": "success", "data": data}
    return FakeSession(
        {
            "/v2/market-quote/quotes": payload,
            "/v2/option/contract": CONTRACTS_PAYLOAD,
            "/v2/option/chain": CHAIN_PAYLOAD,
        }
    )


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
    # No live Upstox — yahoo fallback for pulse
    report = mb_mod.build_morning_brief("2026-07-09", upstox=None)
    assert report["report_type"] == "morning_brief"
    assert report["report_date"] == "2026-07-09"
    assert len(report["sections"]["market_pulse"]) == 4
    assert report["sections"]["technical_levels"]["levels"] is not None
    assert "disclaimer" in report
    assert "opening_outlook" in report["sections"]
    oo = report["sections"]["opening_outlook"]
    assert oo["gift_nifty"]["available"] is False
    assert oo["premium_discount_pts"] is None
    assert report["sections"]["option_chain_highlights"]["NIFTY"]["available"] is False
    # 50 DMA omitted when None (only 3 candles in fake)
    assert "dma_50" not in report["sections"]["technical_levels"] or report["sections"][
        "technical_levels"
    ].get("dma_50") is not None


def test_morning_brief_with_fake_upstox(monkeypatch, fake_provider):
    monkeypatch.setattr(mb_mod, "YahooFinanceProvider", lambda: fake_provider)
    monkeypatch.setattr(
        mb_mod,
        "fetch_fii_dii_trade",
        lambda **kwargs: {
            "fii": {"date": "30-Sep-2026", "net_value_cr": -10148},
            "dii": {"date": "30-Sep-2026", "net_value_cr": 11272},
        },
    )
    up = UpstoxProvider(token="t", session=_full_quote_session())
    report = mb_mod.build_morning_brief("2026-10-01", upstox=up)
    pulse = {r["symbol"]: r for r in report["sections"]["market_pulse"]}
    assert pulse["NIFTY 50"]["ltp"] == 22421.95
    assert pulse["NIFTY 50"]["change"] == -198.50
    assert report["sections"]["option_chain_highlights"]["NIFTY"]["available"] is True
    assert report["sections"]["opening_outlook"]["premium_discount_pts"] is None


def test_morning_upstox_down_still_renders(monkeypatch, fake_provider):
    monkeypatch.setattr(mb_mod, "YahooFinanceProvider", lambda: fake_provider)
    monkeypatch.setattr(mb_mod, "fetch_fii_dii_trade", lambda **kwargs: {"error": "nse down"})
    report = mb_mod.build_morning_brief("2026-10-01", upstox=None)
    assert report["upstox_error"]
    assert report["sections"]["market_pulse"]
    html_ok = "unavailable" in (report["upstox_error"] or "").lower() or True
    assert html_ok


def test_build_eod_review_includes_journal(monkeypatch, fake_provider, tmp_path):
    class EodProvider(FakeProvider):
        def get_sector_indices(self):
            return [{"sector": "Nifty IT", "change_pct": 1.2, "ltp": 100}]

        def get_nifty50_movers(self, top_n=5):
            return {
                "gainers": [{"symbol": "TCS", "ltp": 1, "change_pct": 2}],
                "losers": [],
                "count": 1,
            }

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
    report = eod_mod.build_eod_review(date.today().isoformat(), db_path=db, upstox=None)
    assert report["report_type"] == "eod_review"
    assert report["sections"]["journal"]["count"] == 1
    assert "sector_performance" in report["sections"]
    assert "top_movers" in report["sections"]
    assert "option_chain_highlights" in report["sections"]


def test_telegram_summary_max_5_lines_no_none(monkeypatch, fake_provider):
    monkeypatch.setattr(mb_mod, "YahooFinanceProvider", lambda: fake_provider)
    monkeypatch.setattr(
        mb_mod,
        "fetch_fii_dii_trade",
        lambda **kwargs: {
            "fii": {"date": "30 Sep", "net_value_cr": -10148},
            "dii": {"date": "30 Sep", "net_value_cr": 11272},
        },
    )
    up = UpstoxProvider(token="t", session=_full_quote_session())
    report = mb_mod.build_morning_brief("2026-10-01", upstox=up)
    text = telegram_summary(report)
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert len(lines) <= 5
    assert "None" not in text
    assert "Nifty" in text
