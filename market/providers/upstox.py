"""Upstox market data provider (quotes + option chain).

Token is never logged. HTTP goes through one helper with a 20s timeout and an
injectable session so unit tests can fake responses with no network.
"""
from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests

from market.providers.option_analytics import (
    analyze_chain_rows,
)

IST = ZoneInfo("Asia/Kolkata")
API = "https://api.upstox.com"
TIMEOUT = 20
DEFAULT_TOKEN_FILE = "/home/aditya/.hermes/profiles/arjun/.env.upstox"

# Display name -> instrument_key
INDEX_KEYS: dict[str, str] = {
    "NIFTY 50": "NSE_INDEX|Nifty 50",
    "NIFTY": "NSE_INDEX|Nifty 50",
    "BANK NIFTY": "NSE_INDEX|Nifty Bank",
    "BANKNIFTY": "NSE_INDEX|Nifty Bank",
    "FIN NIFTY": "NSE_INDEX|Nifty Fin Service",
    "FINNIFTY": "NSE_INDEX|Nifty Fin Service",
    "SENSEX": "BSE_INDEX|SENSEX",
    "INDIA VIX": "NSE_INDEX|India VIX",
}

CHAIN_UNDERLYINGS: dict[str, str] = {
    "NIFTY": "NSE_INDEX|Nifty 50",
    "NIFTY 50": "NSE_INDEX|Nifty 50",
    "BANKNIFTY": "NSE_INDEX|Nifty Bank",
    "BANK NIFTY": "NSE_INDEX|Nifty Bank",
    "SENSEX": "BSE_INDEX|SENSEX",
}


class UpstoxError(RuntimeError):
    """Upstox call failed or token missing."""


def load_access_token(
    env: dict[str, str] | None = None,
    token_file: str | Path | None = None,
) -> str:
    """Resolve UPSTOX_ANALYTICS_TOKEN from env or token file. Never log the value."""
    environ = env if env is not None else os.environ
    direct = (environ.get("UPSTOX_ANALYTICS_TOKEN") or "").strip()
    if direct:
        return direct

    path = Path(
        token_file
        if token_file is not None
        else (environ.get("UPSTOX_TOKEN_FILE") or DEFAULT_TOKEN_FILE)
    )
    if not path.is_file():
        raise UpstoxError(
            f"UPSTOX_ANALYTICS_TOKEN missing and token file not found: {path}"
        )
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() == "UPSTOX_ANALYTICS_TOKEN":
            token = value.strip().strip('"').strip("'")
            if token:
                return token
    raise UpstoxError(f"UPSTOX_ANALYTICS_TOKEN not set in {path}")


def _match_quote(data: dict[str, Any], instrument_key: str, name: str = "") -> dict[str, Any]:
    """Locate one instrument in a quotes payload (keys may use | or :)."""
    if instrument_key in data:
        return data[instrument_key]
    candidates = {
        instrument_key.replace("|", ":").lower(),
        instrument_key.split("|")[-1].lower(),
    }
    if name:
        segment = instrument_key.split("|")[0]
        candidates |= {name.lower(), f"{segment}:{name}".lower()}
    for key, value in data.items():
        if not isinstance(value, dict):
            continue
        if key.lower() in candidates or key.split(":")[-1].lower() in candidates:
            return value
        if str(value.get("instrument_token", "")).lower() == instrument_key.lower():
            return value
    return {}


def _normalize_quote(raw: dict[str, Any], name: str) -> dict[str, Any]:
    """Map Upstox quote blob to {ltp, open, high, low, prev_close, change, change_pct}.

    Prefer net_change: prev_close = ltp - net_change. Fallback to ohlc.close.
    """
    if not raw:
        return {
            "ltp": None,
            "open": None,
            "high": None,
            "low": None,
            "prev_close": None,
            "change": None,
            "change_pct": None,
            "error": "not in response",
        }
    ohlc = raw.get("ohlc") or {}
    ltp_raw = raw.get("last_price")
    ltp = float(ltp_raw) if isinstance(ltp_raw, (int, float)) else None
    open_ = ohlc.get("open")
    high = ohlc.get("high")
    low = ohlc.get("low")
    net_change = raw.get("net_change")
    prev_close: float | None = None
    change: float | None = None

    if isinstance(ltp, (int, float)) and isinstance(net_change, (int, float)):
        change = float(net_change)
        prev_close = round(float(ltp) - change, 2)
    else:
        close = ohlc.get("close")
        if isinstance(close, (int, float)):
            prev_close = float(close)
            if isinstance(ltp, (int, float)):
                change = float(ltp) - prev_close

    change_pct: float | None = None
    if change is not None and prev_close and prev_close != 0:
        change_pct = round(change / prev_close * 100, 2)

    return {
        "ltp": round(ltp, 2) if ltp is not None else None,
        "open": round(float(open_), 2) if isinstance(open_, (int, float)) else None,
        "high": round(float(high), 2) if isinstance(high, (int, float)) else None,
        "low": round(float(low), 2) if isinstance(low, (int, float)) else None,
        "prev_close": round(prev_close, 2) if prev_close is not None else None,
        "change": round(change, 2) if change is not None else None,
        "change_pct": change_pct,
    }


class UpstoxProvider:
    """Thin Upstox client. Pass session= for tests."""

    def __init__(
        self,
        token: str | None = None,
        session: requests.Session | None = None,
        *,
        base_url: str = API,
        timeout: float = TIMEOUT,
    ) -> None:
        self._token = token if token is not None else load_access_token()
        self._session = session or requests.Session()
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def _get(self, path: str, **params: Any) -> Any:
        url = f"{self._base_url}{path}"
        response = self._session.get(
            url,
            params=params or None,
            timeout=self._timeout,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self._token}",
            },
        )
        try:
            payload = response.json()
        except ValueError as exc:
            raise UpstoxError(f"{path}: HTTP {response.status_code}, non-JSON body") from exc
        if response.status_code >= 400 or payload.get("status") == "error":
            errors = payload.get("errors") or [{"message": str(response.text)[:200]}]
            detail = "; ".join(str(e.get("message") or e) for e in errors if isinstance(e, dict))
            if not detail:
                detail = str(errors)[:200]
            raise UpstoxError(f"{path}: HTTP {response.status_code}: {detail}")
        return payload.get("data")

    def get_quotes(self, keys: dict[str, str]) -> dict[str, dict[str, Any]]:
        """name -> instrument_key map → normalized quote dicts."""
        if not keys:
            return {}
        data = self._get(
            "/v2/market-quote/quotes",
            instrument_key=",".join(keys.values()),
        )
        if not isinstance(data, dict):
            data = {}
        out: dict[str, dict[str, Any]] = {}
        for name, key in keys.items():
            raw = _match_quote(data, key, name)
            out[name] = _normalize_quote(raw, name)
        return out

    def nearest_expiry(self, underlying_key: str, today: date | None = None) -> str:
        """Earliest contract expiry >= today (IST calendar date)."""
        contracts = self._get("/v2/option/contract", instrument_key=underlying_key) or []
        if not isinstance(contracts, list):
            contracts = []
        day = (today or datetime.now(IST).date()).isoformat()
        upcoming = sorted(
            {c["expiry"] for c in contracts if isinstance(c, dict) and c.get("expiry") and c["expiry"] >= day}
        )
        if not upcoming:
            raise UpstoxError("no upcoming option expiry found")
        return upcoming[0]

    def get_option_chain(
        self,
        underlying_key: str,
        expiry: str | None = None,
        *,
        today: date | None = None,
    ) -> list[dict[str, Any]]:
        """Return per-strike rows: strike, ce_ltp, ce_oi, pe_ltp, pe_oi."""
        exp = expiry or self.nearest_expiry(underlying_key, today=today)
        rows = self._get(
            "/v2/option/chain",
            instrument_key=underlying_key,
            expiry_date=exp,
        ) or []
        if not isinstance(rows, list):
            rows = []
        out: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            call = (row.get("call_options") or {}).get("market_data") or {}
            put = (row.get("put_options") or {}).get("market_data") or {}
            strike = row.get("strike_price")
            if strike is None:
                continue
            out.append(
                {
                    "strike": float(strike),
                    "ce_ltp": _num(call.get("ltp")),
                    "ce_oi": _num(call.get("oi")),
                    "pe_ltp": _num(put.get("ltp")),
                    "pe_oi": _num(put.get("oi")),
                    "expiry": exp,
                }
            )
        return out

    def option_chain_highlights(
        self,
        name: str,
        *,
        spot: float | None = None,
        expiry: str | None = None,
        today: date | None = None,
    ) -> dict[str, Any]:
        """Full analytics block for one underlying (NIFTY / BANKNIFTY / SENSEX)."""
        key = CHAIN_UNDERLYINGS.get(name.upper()) or CHAIN_UNDERLYINGS.get(name)
        if not key:
            return {
                "symbol": name,
                "available": False,
                "message": f"unknown underlying: {name}",
            }
        try:
            day = today or datetime.now(IST).date()
            exp = expiry or self.nearest_expiry(key, today=day)
            rows = self.get_option_chain(key, expiry=exp, today=day)
        except UpstoxError as exc:
            return {
                "symbol": name,
                "available": False,
                "message": f"Upstox unavailable: {exc}",
            }
        if not rows:
            return {
                "symbol": name,
                "available": False,
                "message": "empty option chain",
                "expiry": exp,
            }
        analytics = analyze_chain_rows(rows, spot=spot, expiry=exp, as_of=day)
        return {
            "symbol": name,
            "available": True,
            "underlying_key": key,
            "spot": spot,
            **analytics,
        }


def _num(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def index_keys_for(names: list[str]) -> dict[str, str]:
    """Resolve display names to instrument keys; skip unknown."""
    out: dict[str, str] = {}
    for name in names:
        key = INDEX_KEYS.get(name) or INDEX_KEYS.get(name.upper())
        if key:
            out[name] = key
    return out


def quotes_as_rows(quotes: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert get_quotes result to report table rows."""
    rows = []
    for symbol, q in quotes.items():
        rows.append(
            {
                "symbol": symbol,
                "ltp": q.get("ltp"),
                "open": q.get("open"),
                "high": q.get("high"),
                "low": q.get("low"),
                "prev_close": q.get("prev_close"),
                "change": q.get("change"),
                "change_pct": q.get("change_pct"),
                "volume": None,
                "currency": "INR",
                "error": q.get("error"),
            }
        )
    return rows
