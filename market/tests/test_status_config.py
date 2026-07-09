from market.status import _load_holidays, compute_market_status



def test_holidays_loaded_from_defaults_yaml():
    holidays = _load_holidays()
    assert any(h.get("date") == "2026-01-26" and "Republic" in h.get("reason", "") for h in holidays)


def test_market_status_exposes_next_holiday(fake_provider):
    status = compute_market_status(fake_provider)
    assert "next_holiday" in status
    # Future holiday from 2026 calendar should be present when config loads.
    if status["next_holiday"]:
        assert "2026-" in status["next_holiday"]