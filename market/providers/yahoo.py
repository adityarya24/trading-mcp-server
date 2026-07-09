"""Yahoo Finance provider via yfinance."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yfinance as yf

from market.providers.option_analytics import (
    compute_max_pain,
    compute_pcr,
    highest_oi_strike,
    strikes_snapshot,
)
from services.trading_mcp.models import Candle, Quote

from .base import MarketDataProvider

_NIFTY50_PATH = Path(__file__).resolve().parent.parent / "data" / "nifty50_symbols.json"

SYMBOL_MAP: dict[str, str] = {
    "NIFTY 50": "^NSEI",
    "NIFTY": "^NSEI",
    "SENSEX": "^BSESN",
    "BANK NIFTY": "^NSEBANK",
    "BANKNIFTY": "^NSEBANK",
    "NIFTY IT": "^CNXIT",
    "NIFTY PHARMA": "^CNXPHARMA",
    "NIFTY AUTO": "^CNXAUTO",
    "NIFTY FMCG": "^CNXFMCG",
    "NIFTY METAL": "^CNXMETAL",
    "NIFTY ENERGY": "^CNXENERGY",
    "INDIA VIX": "^INDIAVIX",
    "GIFT NIFTY": "^NSEI",
    "S&P 500": "^GSPC",
    "SPX": "^GSPC",
    "NASDAQ": "^IXIC",
    "DOW JONES": "^DJI",
    "NIKKEI 225": "^N225",
    "HANG SENG": "^HSI",
    "XAUUSD": "GC=F",
    "GOLD": "GC=F",
    "SILVER": "SI=F",
    "BRENT CRUDE": "BZ=F",
    "CRUDE OIL": "CL=F",
    "WTI": "CL=F",
    "USDINR": "INR=X",
    "USD/INR": "INR=X",
}

SECTOR_INDICES: list[tuple[str, str]] = [
    ("Nifty Bank", "BANK NIFTY"),
    ("Nifty IT", "NIFTY IT"),
    ("Nifty Pharma", "NIFTY PHARMA"),
    ("Nifty Auto", "NIFTY AUTO"),
    ("Nifty FMCG", "NIFTY FMCG"),
    ("Nifty Metal", "NIFTY METAL"),
    ("Nifty Energy", "NIFTY ENERGY"),
]


class YahooFinanceProvider(MarketDataProvider):
    """yfinance-based market data provider."""

    def validate_symbol(self, symbol: str) -> str:
        upper = symbol.upper().strip()
        return SYMBOL_MAP.get(upper, symbol)

    def get_quote(self, symbol: str) -> Quote:
        ticker_str = self.validate_symbol(symbol)
        try:
            info = yf.Ticker(ticker_str).info
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
            return Quote(symbol=symbol, ltp=0.0, currency="N/A")

    def get_gift_nifty_quote(self) -> dict[str, Any]:
        """GIFT Nifty proxy: Yahoo has no SGXNIFTY; use Nifty pre-market/spot on ^NSEI."""
        ticker_str = "^NSEI"
        info = yf.Ticker(ticker_str).info
        ltp = (
            info.get("preMarketPrice")
            or info.get("regularMarketPrice")
            or info.get("previousClose")
            or 0.0
        )
        quote = Quote(
            symbol="GIFT NIFTY",
            ltp=round(float(ltp), 2) if ltp else 0.0,
            prev_close=info.get("previousClose"),
            change_pct=info.get("regularMarketChangePercent"),
            currency=info.get("currency", "INR"),
        )
        return {
            **quote.to_dict(),
            "yahoo_ticker": ticker_str,
            "is_proxy": True,
            "proxy_note": (
                "SGX GIFT Nifty unavailable on Yahoo free tier; using Nifty 50 "
                "pre-market/spot (^NSEI) as opening indicator."
            ),
        }

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

    def get_option_chain(self, symbol: str, expiry: str | None = None) -> dict[str, Any]:
        ticker_str = self.validate_symbol(symbol)
        ticker = yf.Ticker(ticker_str)
        expiries = list(ticker.options or [])
        if not expiries:
            return {
                "symbol": symbol,
                "ticker": ticker_str,
                "available": False,
                "message": "No option expiries returned by Yahoo for this symbol.",
                "max_pain": None,
                "pcr": None,
                "highest_call_oi": None,
                "highest_put_oi": None,
                "expiry": None,
                "strikes": [],
            }

        chosen = expiry if expiry in expiries else expiries[0]
        chain = ticker.option_chain(chosen)
        calls = chain.calls
        puts = chain.puts
        return {
            "symbol": symbol,
            "ticker": ticker_str,
            "available": True,
            "expiry": chosen,
            "expiries": expiries,
            "max_pain": compute_max_pain(calls, puts),
            "pcr": compute_pcr(calls, puts),
            "highest_call_oi": highest_oi_strike(calls, "CALL"),
            "highest_put_oi": highest_oi_strike(puts, "PUT"),
            "strikes": strikes_snapshot(calls, puts),
            "disclaimer": "OI/IV analytics only — not trading advice.",
        }

    def get_sector_indices(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for label, sym in SECTOR_INDICES:
            q = self.get_quote(sym)
            rows.append({"sector": label, **q.to_dict()})
        rows.sort(key=lambda r: (r.get("change_pct") is None, -(r.get("change_pct") or 0)))
        return rows

    def get_nifty50_movers(self, top_n: int = 5) -> dict[str, Any]:
        symbols = self._load_nifty50_symbols()
        if not symbols:
            return {"gainers": [], "losers": [], "count": 0}
        try:
            data = yf.download(
                " ".join(symbols),
                period="5d",
                group_by="ticker",
                progress=False,
                threads=True,
            )
        except Exception:
            return {"gainers": [], "losers": [], "count": 0, "error": "download_failed"}

        movers: list[dict[str, Any]] = []
        for sym in symbols:
            try:
                if len(symbols) == 1:
                    frame = data
                else:
                    frame = data[sym]
                if frame is None or frame.empty or len(frame) < 2:
                    continue
                prev_close = float(frame["Close"].iloc[-2])
                last_close = float(frame["Close"].iloc[-1])
                if prev_close <= 0:
                    continue
                change_pct = round(((last_close - prev_close) / prev_close) * 100, 4)
                movers.append(
                    {
                        "symbol": sym.replace(".NS", ""),
                        "ticker": sym,
                        "ltp": round(last_close, 2),
                        "change_pct": change_pct,
                    }
                )
            except Exception:
                continue

        movers.sort(key=lambda m: m["change_pct"], reverse=True)
        losers = sorted(movers, key=lambda m: m["change_pct"])[:top_n]
        return {
            "count": len(movers),
            "gainers": movers[:top_n],
            "losers": losers,
        }

    def _load_nifty50_symbols(self) -> list[str]:
        if not _NIFTY50_PATH.exists():
            return []
        return json.loads(_NIFTY50_PATH.read_text())