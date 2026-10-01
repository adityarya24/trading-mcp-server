from market.reports.common import pivot_levels, simple_moving_average


def test_pivot_levels():
    levels = pivot_levels(100, 90, 95)
    assert levels["pivot"] == 95.0
    assert levels["r1"] == 100.0
    assert levels["s1"] == 90.0


def test_sma():
    assert simple_moving_average([1, 2, 3, 4, 5], 3) == 4.0
    assert simple_moving_average([1, 2], 3) is None

def test_session_tag_follows_market_hours():
    from datetime import datetime
    from market.reports.common import IST, market_session_tag

    def thu(h, m):  # 1 Oct 2026 is a Thursday
        return datetime(2026, 10, 1, h, m, tzinfo=IST)

    assert market_session_tag(thu(9, 5)) == "Previous close"
    assert market_session_tag(thu(11, 0)) == "Live"
    assert market_session_tag(thu(15, 35)) == "Close"
    assert market_session_tag(datetime(2026, 10, 3, 11, 0, tzinfo=IST)) == "Previous close"  # Saturday
