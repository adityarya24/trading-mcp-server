"""Yahoo Finance provider via yfinance.

Free tier — delayed 15 min. Suitable for EOD analysis and swing trading.
No auth required. Zero setup.
"""
from __future__ import annotations

import yfinance as yf

from services.trading_mcp.models import Candle, Quote

from .base import MarketDataProvider

# Symbol mapping: MCP tool names → Yahoo Finance tickers
SYMBOL_MAP: dict[str, str] = {
    # Indian indices
    "NIFTY 50": "^NSEI",
    "NIFTY": "^NSEI",
    "SENSEX": "^BSESN",
    "BANK NIFTY": "^NSEBANK",
    "BANKNIFTY": "^NSEBANK",
    "NIFTY IT": "^CNXIT",
    "INDIA VIX": "^INDIAVIX",
    # Global indices
    "S&P 500": "^GSPC",
    "SPX": "^GSPC",
    "NASDAQ": "^IXIC",
    "DOW JONES": "^DJI",
    "NIKKEI 225": "^N225",
    "HANG SENG": "^HSI",
    # Commodities
    "XAUUSD": "GC=F",
    "GOLD": "GC=F",
    "SILVER": "SI=F",
    "BRENT CRUDE": "BZ=F",
    "CRUDE OIL": "CL=F",
    "WTI": "CL=F",
    # FX
    "USDINR": "INR=X",
    "USD/INR": "INR=X",
}


class YahooFinanceProvider(MarketDataProvider):
    """yfinance-based market data provider."""

    def validate_symbol(self, symbol: str) -> str:
        """Map friendly names to Yahoo tickers."""
        upper = symbol.upper().strip()
        return SYMBOL_MAP.get(upper, symbol)

    def get_quote(self, symbol: str) -> Quote:
        ticker_str = self.validate_symbol(symbol)
        try:
            t = yf.Ticker(ticker_str)
            info = t.info

            ltp = info.get("regularMarketPrice") or info.get("previousClose")
            prev_close = info.get("previousClose")
            change = info.get("regularMarketChange")
            change_pct = info.get("regularMarketChangePercent")

            return Quote(
                symbol=symbol,
                ltp=round(ltp, 2) if ltp else 0.0,
                open=info.get("regularMarketOpen"),
                high=info.get("dayHigh"),
                low=info.get("dayLow"),
                prev_close=round(prev_close, 2) if prev_close else None,
                change=round(change, 2) if change else None,
                change_pct=round(change_pct, 4) if change_pct else None,
                volume=info.get("volume"),
                currency=info.get("currency", "INR"),
            )
        except Exception:
            return Quote(
                symbol=symbol,
                ltp=0.0,
                currency="N/A",
            )

    def get_ohlc(self, symbol: str, interval: str = "1d", count: int = 30) -> list[Candle]:
        ticker_str = self.validate_symbol(symbol)
        period = "3mo" if count > 60 else "2mo" if count > 30 else "1mo"
        try:
            hist = yf.Ticker(ticker_str).history(period=period, interval=interval)
        except Exception:
            return []
        if hist is None or hist.empty:
            return []
        candles: list[Candle] = []
        for ts, row in hist.tail(count).iterrows():
            vol = row.get("Volume")
            volume = int(vol) if vol == vol else None
            candles.append(
                Candle(
                    symbol=symbol,
                    timestamp=ts.to_pydatetime().isoformat(),
                    open=round(float(row["Open"]), 2),
                    high=round(float(row["High"]), 2),
                    low=round(float(row["Low"]), 2),
                    close=round(float(row["Close"]), 2),
                    volume=volume,
                    interval=interval,
                )
            )
        return candles