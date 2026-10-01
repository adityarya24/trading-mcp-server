import pandas as pd

from market.providers.option_analytics import (
    compute_max_pain,
    compute_max_pain_from_rows,
    compute_pcr,
    compute_pcr_from_rows,
    highest_oi_strike,
    top_oi_strikes,
)


def test_max_pain_and_pcr():
    calls = pd.DataFrame(
        {"strike": [100, 101], "openInterest": [1000, 500]},
    )
    puts = pd.DataFrame(
        {"strike": [100, 99], "openInterest": [800, 1200]},
    )
    assert compute_pcr(calls, puts) == round(2000 / 1500, 4)
    assert compute_max_pain(calls, puts) is not None
    hi_call = highest_oi_strike(calls, "CALL")
    assert hi_call and hi_call["strike"] == 100.0


def test_row_helpers_pcr_max_pain_top():
    rows = [
        {"strike": 100, "ce_oi": 1000, "pe_oi": 800, "ce_ltp": 1, "pe_ltp": 2},
        {"strike": 101, "ce_oi": 500, "pe_oi": 1200, "ce_ltp": 1, "pe_ltp": 2},
    ]
    assert compute_pcr_from_rows(rows) == round(2000 / 1500, 2)
    assert compute_max_pain_from_rows(rows) is not None
    assert top_oi_strikes(rows, "CE", 1)[0]["strike"] == 100
    assert top_oi_strikes(rows, "PE", 1)[0]["strike"] == 101

def test_walls_stay_on_their_side_of_spot():
    from market.providers.option_analytics import analyze_chain_rows

    rows = [
        {"strike": 53000, "ce_oi": 10, "pe_oi": 500},
        {"strike": 54000, "ce_oi": 50, "pe_oi": 900},
        {"strike": 55000, "ce_oi": 800, "pe_oi": 300},
        {"strike": 58000, "ce_oi": 1400, "pe_oi": 1300},  # biggest on both sides, but far above spot
    ]
    out = analyze_chain_rows(rows, spot=54450)
    assert out["support"][0]["strike"] == 54000
    assert all(s["strike"] <= 54450 for s in out["support"])
    assert out["resistance"][0]["strike"] == 58000
    assert all(r["strike"] >= 54450 for r in out["resistance"])
