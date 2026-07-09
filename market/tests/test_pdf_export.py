from pathlib import Path

from market.reports.pdf_export import export_report_pdf, render_html


SAMPLE = {
    "report_type": "morning_brief",
    "report_date": "2026-07-09",
    "generated_at": "2026-07-09 08:45:00 IST",
    "title": "Morning Brief",
    "market_status": {"today_expiry": False, "expiry_instrument": None},
    "sections": {
        "market_pulse": [{"symbol": "NIFTY 50", "ltp": 24000, "change_pct": 0.1, "prev_close": 23900}],
        "global_cues": [],
        "fii_dii": {"fii": {"date": "08-Jul-2026", "net_value_cr": 1.0}, "dii": {"net_value_cr": 2.0}},
        "technical_levels": {"levels": {"pivot": 24000}, "dma_20": 24100, "dma_50": 23800},
        "opening_outlook": {
            "gift_nifty": {"ltp": 24010, "proxy_note": "proxy"},
            "nifty_spot_reference": 23900,
            "premium_discount_pts": 110,
            "expected_open_range": {"low": 23950, "high": 24050},
            "gap_assessment": "mild_positive_gap",
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