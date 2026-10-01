from pathlib import Path

import pytest

from market.reports.pdf_export import export_report_pdf, render_html


SAMPLE = {
    "report_type": "morning_brief",
    "report_date": "2026-07-09",
    "generated_at": "2026-07-09 08:45:00 IST",
    "title": "Morning Brief",
    "session_tag": "Previous close",
    "market_status": {"today_expiry": False, "expiry_instrument": None},
    "upstox_error": None,
    "sections": {
        "market_pulse": [
            {
                "symbol": "NIFTY 50",
                "ltp": 24000.0,
                "change": 50.0,
                "change_pct": 0.21,
                "prev_close": 23950.0,
                "open": 23900.0,
                "high": 24100.0,
                "low": 23850.0,
            }
        ],
        "global_cues": [{"label": "S&P 500", "ltp": 5000.0, "change_pct": -0.25}],
        "fii_dii": {
            "fii": {"date": "08-Jul-2026", "net_value_cr": 1.0},
            "dii": {"date": "08-Jul-2026", "net_value_cr": 2.0},
        },
        "technical_levels": {"levels": {"pivot": 24000}, "dma_20": 24100, "dma_50": 23800},
        "opening_outlook": {
            "gift_nifty": {"ltp": None, "available": False, "message": "GIFT Nifty: unavailable"},
            "nifty_spot_reference": None,
            "premium_discount_pts": None,
            "expected_open_range": {"low": None, "high": None},
            "gap_assessment": "unavailable",
            "note": "GIFT Nifty: unavailable",
        },
        "option_chain_highlights": {
            "NIFTY": {
                "available": True,
                "spot": 24000,
                "expiry": "2026-07-10",
                "days_to_expiry": 1,
                "pcr": 0.85,
                "max_pain": 24000,
                "support": [{"strike": 23800}],
                "resistance": [{"strike": 24200}],
            },
            "BANKNIFTY": {"available": False, "message": "Upstox unavailable"},
        },
    },
    "disclaimer": "For informational purposes only.",
}


def test_render_html_contains_title():
    html = render_html(SAMPLE)
    assert "Morning Brief" in html
    assert "NIFTY 50" in html


def test_reportlab_pdf_fallback(tmp_path: Path):
    out = tmp_path / "brief.pdf"
    meta = export_report_pdf(SAMPLE, out, renderer="reportlab")
    assert meta["renderer"] == "reportlab"
    assert out.exists() and out.stat().st_size > 500


def test_explicit_html_renderer_raises_without_chromium(tmp_path: Path, monkeypatch):
    def _boom(*args, **kwargs):
        raise RuntimeError("no chromium")

    monkeypatch.setattr("market.reports.pdf_export._html_to_chromium_pdf", _boom)
    with pytest.raises(RuntimeError, match="no chromium"):
        export_report_pdf(SAMPLE, tmp_path / "x.pdf", renderer="html")

def test_find_chromium_env_var_wins(monkeypatch):
    from market.reports.pdf_export import find_chromium_executable

    monkeypatch.setenv("TRADING_CHROMIUM_EXECUTABLE", "/custom/chrome")
    assert find_chromium_executable() == "/custom/chrome"


def test_find_chromium_probe_returns_existing_or_none(monkeypatch):
    import os

    from market.reports.pdf_export import find_chromium_executable

    monkeypatch.delenv("TRADING_CHROMIUM_EXECUTABLE", raising=False)
    found = find_chromium_executable()
    assert found is None or os.path.exists(found)


def test_pdf_one_page_when_renderer_available(tmp_path: Path):
    """Render sample morning brief and assert single page if pypdf is present."""
    pytest.importorskip("pypdf")
    from pypdf import PdfReader

    out = tmp_path / "onepage.pdf"
    try:
        meta = export_report_pdf(SAMPLE, out, renderer="html")
    except Exception as exc:  # chromium missing etc.
        pytest.skip(f"html renderer unavailable: {exc}")
    assert out.exists()
    reader = PdfReader(str(out))
    assert len(reader.pages) == 1, f"expected 1 page, got {len(reader.pages)} ({meta})"
