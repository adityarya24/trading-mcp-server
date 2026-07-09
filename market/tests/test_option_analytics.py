import pandas as pd

from market.providers.option_analytics import compute_max_pain, compute_pcr, highest_oi_strike


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