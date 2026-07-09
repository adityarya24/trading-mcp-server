from __future__ import annotations


import pandas as pd

from market.providers.yahoo import SYMBOL_MAP, YahooFinanceProvider


def test_validate_symbol_maps_nifty():
    p = YahooFinanceProvider()
    assert p.validate_symbol("nifty 50") == "^NSEI"
    assert SYMBOL_MAP["XAUUSD"] == "GC=F"


def test_get_quote_from_info(monkeypatch):
    class FakeTicker:
        def __init__(self, _ticker: str):
            self.info = {
                "regularMarketPrice": 23962.8,
                "previousClose": 23880.0,
                "regularMarketChange": 82.8,
                "regularMarketChangePercent": 0.34,
                "regularMarketOpen": 23900.0,
                "dayHigh": 24010.0,
                "dayLow": 23890.0,
                "volume": 999,
                "currency": "INR",
            }

    monkeypatch.setattr("market.providers.yahoo.yf.Ticker", FakeTicker)
    q = YahooFinanceProvider().get_quote("NIFTY 50")
    assert q.ltp == 23962.8
    assert q.symbol == "NIFTY 50"
    assert q.change_pct == 0.34


def test_get_ohlc_from_history(monkeypatch):
    idx = pd.to_datetime(["2026-07-08", "2026-07-09"])
    frame = pd.DataFrame(
        {
            "Open": [23880.0, 23920.0],
            "High": [24050.0, 24100.0],
            "Low": [23800.0, 23900.0],
            "Close": [23920.0, 24000.0],
            "Volume": [100, 200],
        },
        index=idx,
    )

    class FakeTicker:
        def history(self, period: str, interval: str):
            return frame

    monkeypatch.setattr("market.providers.yahoo.yf.Ticker", lambda _s: FakeTicker())
    candles = YahooFinanceProvider().get_ohlc("NIFTY 50", count=2)
    assert len(candles) == 2
    assert candles[-1].close == 24000.0