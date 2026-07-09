"""Abstract base for market data providers.

All providers MUST implement this interface. This keeps the MCP tools layer
completely independent of which data source is wired in (yfinance, Zerodha,
Angel, Upstox, etc.).
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from market.models import Candle, Quote


class MarketDataProvider(ABC):
    """Standardized interface for any market data source."""

    @abstractmethod
    def get_quote(self, symbol: str) -> Quote:
        """Get current quote: LTP, change, change%, volume, OHLC."""
        ...

    def get_ohlc(self, symbol: str, interval: str = "1d", count: int = 30) -> list[Candle]:
        """Get OHLCV candles. Override for provider-specific implementation."""
        return []

    def validate_symbol(self, symbol: str) -> str:
        """Normalize symbol to provider-specific format. Override if needed."""
        return symbol
