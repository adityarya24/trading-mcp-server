from market.status import compute_market_status

from market.tests.conftest import FakeProvider


def test_market_status_has_core_fields(fake_provider):
    status = compute_market_status(fake_provider)
    assert status["market"] == "NSE"
    assert "is_open" in status
    assert "current_time" in status
    assert status["vix"] is not None