from market.reports.common import pivot_levels, simple_moving_average


def test_pivot_levels():
    levels = pivot_levels(100, 90, 95)
    assert levels["pivot"] == 95.0
    assert levels["r1"] == 100.0
    assert levels["s1"] == 90.0


def test_sma():
    assert simple_moving_average([1, 2, 3, 4, 5], 3) == 4.0
    assert simple_moving_average([1, 2], 3) is None