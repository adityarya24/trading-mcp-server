"""Shared pytest fixtures."""
from __future__ import annotations

from typing import Any

import pytest

from market.providers.base import MarketDataProvider
from services.trading_mcp.models import Candle, Quote


class FakeProvider(MarketDataProvider):
    def get_quote(self, symbol: str) -> Quote:
        return Quote(
            symbol=symbol,
            ltp=24000.0,
            open=23900.0,
            high=24100.0,
            low=23850.0,
            prev_close=23950.0,
            change=50.0,
            change_pct=0.21,
            volume=1_000_000,
            currency="INR",
        )

    def get_ohlc(self, symbol: str, interval: str = "1d", count: int = 30) -> list[Candle]:
        base = [
            ("2026-07-07T00:00:00", 23800, 23950, 23750, 23880),
            ("2026-07-08T00:00:00", 23880, 24050, 23800, 23920),
            ("2026-07-09T00:00:00", 23920, 24100, 23900, 24000),
        ]
        candles: list[Candle] = []
        for ts, o, h, low, c in base[-count:]:
            candles.append(
                Candle(
                    symbol=symbol,
                    timestamp=ts,
                    open=float(o),
                    high=float(h),
                    low=float(low),
                    close=float(c),
                    volume=100,
                    interval=interval,
                )
            )
        return candles


@pytest.fixture
def fake_provider() -> FakeProvider:
    return FakeProvider()


@pytest.fixture
def sample_fii_dii_payload() -> list[dict[str, Any]]:
    return [
        {
            "buyValue": "19165.13",
            "category": "DII",
            "date": "08-Jul-2026",
            "netValue": "790.16",
            "sellValue": "18374.97",
        },
        {
            "buyValue": "17463.95",
            "category": "FII/FPI",
            "date": "08-Jul-2026",
            "netValue": "1962.8",
            "sellValue": "15501.15",
        },
    ]