"""Upstox provider tests — fake session only, no network."""
from __future__ import annotations

import json
from datetime import date
from typing import Any

import pytest

from market.providers.option_analytics import (
    analyze_chain_rows,
    compute_max_pain_from_rows,
    compute_pcr_from_rows,
    top_oi_strikes,
)
from market.providers.upstox import UpstoxError, UpstoxProvider, _normalize_quote, load_access_token


class FakeResponse:
    def __init__(self, payload: Any, status_code: int = 200, text: str = ""):
        self._payload = payload
        self.status_code = status_code
        self.text = text or json.dumps(payload)

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeSession:
    """routes: (path_substring or full) -> payload or callable(params)->payload"""

    def __init__(self, routes: dict[str, Any]):
        self.routes = routes
        self.calls: list[tuple[str, dict]] = []

    def get(self, url: str, params=None, timeout=None, headers=None):
        self.calls.append((url, params or {}))
        path = url.split("api.upstox.com")[-1] if "api.upstox.com" in url else url
        for key, value in self.routes.items():
            if key in path or key in url:
                payload = value(params or {}) if callable(value) else value
                if isinstance(payload, tuple):
                    body, code = payload
                    return FakeResponse(body, status_code=code)
                return FakeResponse(payload)
        return FakeResponse({"status": "error", "errors": [{"message": f"no route {path}"}]}, 404)


QUOTES_PAYLOAD = {
    "status": "success",
    "data": {
        "NSE_INDEX:Nifty 50": {
            "last_price": 22421.95,
            "net_change": -198.50,
            "ohlc": {"open": 22600.0, "high": 22650.0, "low": 22380.0, "close": 22620.45},
            "instrument_token": "NSE_INDEX|Nifty 50",
        },
        "NSE_INDEX:Nifty Bank": {
            "last_price": 54450.75,
            "net_change": -180.25,
            "ohlc": {"open": 54600.0, "high": 54700.0, "low": 54300.0, "close": 54631.0},
        },
    },
}

CONTRACTS_PAYLOAD = {
    "status": "success",
    "data": [
        {"expiry": "2026-09-30"},
        {"expiry": "2026-10-06"},
        {"expiry": "2026-10-13"},
    ],
}

CHAIN_PAYLOAD = {
    "status": "success",
    "data": [
        {
            "strike_price": 22000,
            "call_options": {"market_data": {"ltp": 500, "oi": 1_000_000}},
            "put_options": {"market_data": {"ltp": 80, "oi": 3_000_000}},
        },
        {
            "strike_price": 22500,
            "call_options": {"market_data": {"ltp": 200, "oi": 2_500_000}},
            "put_options": {"market_data": {"ltp": 150, "oi": 2_000_000}},
        },
        {
            "strike_price": 23000,
            "call_options": {"market_data": {"ltp": 50, "oi": 4_000_000}},
            "put_options": {"market_data": {"ltp": 400, "oi": 1_200_000}},
        },
    ],
}


def test_load_token_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("UPSTOX_ANALYTICS_TOKEN", "env-token-value")
    assert load_access_token() == "env-token-value"


def test_load_token_from_file(monkeypatch, tmp_path):
    monkeypatch.delenv("UPSTOX_ANALYTICS_TOKEN", raising=False)
    f = tmp_path / "tok.env"
    f.write_text("UPSTOX_ANALYTICS_TOKEN=file-token-value\n", encoding="utf-8")
    monkeypatch.setenv("UPSTOX_TOKEN_FILE", str(f))
    assert load_access_token() == "file-token-value"


def test_load_token_missing_raises(monkeypatch, tmp_path):
    monkeypatch.delenv("UPSTOX_ANALYTICS_TOKEN", raising=False)
    monkeypatch.setenv("UPSTOX_TOKEN_FILE", str(tmp_path / "nope"))
    with pytest.raises(UpstoxError, match="missing"):
        load_access_token()


def test_normalize_prev_close_from_net_change():
    raw = {
        "last_price": 22421.95,
        "net_change": -198.50,
        "ohlc": {"open": 1, "high": 2, "low": 3, "close": 99999},  # must not win
    }
    q = _normalize_quote(raw, "NIFTY 50")
    assert q["ltp"] == 22421.95
    assert q["change"] == -198.50
    assert q["prev_close"] == round(22421.95 - (-198.50), 2)
    assert q["change_pct"] == round(-198.50 / q["prev_close"] * 100, 2)


def test_get_quotes_prev_close_change():
    session = FakeSession({"/v2/market-quote/quotes": QUOTES_PAYLOAD})
    p = UpstoxProvider(token="t", session=session)
    out = p.get_quotes(
        {
            "NIFTY 50": "NSE_INDEX|Nifty 50",
            "BANK NIFTY": "NSE_INDEX|Nifty Bank",
        }
    )
    n = out["NIFTY 50"]
    assert n["ltp"] == 22421.95
    assert n["change"] == -198.50
    assert n["prev_close"] == pytest.approx(22620.45)
    assert n["change_pct"] == pytest.approx(-0.88, abs=0.01)


def test_nearest_expiry():
    session = FakeSession({"/v2/option/contract": CONTRACTS_PAYLOAD})
    p = UpstoxProvider(token="t", session=session)
    assert p.nearest_expiry("NSE_INDEX|Nifty 50", today=date(2026, 10, 1)) == "2026-10-06"


def test_option_chain_and_analytics():
    session = FakeSession(
        {
            "/v2/option/contract": CONTRACTS_PAYLOAD,
            "/v2/option/chain": CHAIN_PAYLOAD,
        }
    )
    p = UpstoxProvider(token="t", session=session)
    rows = p.get_option_chain("NSE_INDEX|Nifty 50", today=date(2026, 10, 1))
    assert len(rows) == 3
    assert rows[0]["strike"] == 22000
    pcr = compute_pcr_from_rows(rows)
    assert pcr == round((3_000_000 + 2_000_000 + 1_200_000) / (1_000_000 + 2_500_000 + 4_000_000), 2)
    mp = compute_max_pain_from_rows(rows)
    assert mp in {22000.0, 22500.0, 23000.0}
    res = top_oi_strikes(rows, "CE", 3)
    assert res[0]["strike"] == 23000
    sup = top_oi_strikes(rows, "PE", 3)
    assert sup[0]["strike"] == 22000
    analytics = analyze_chain_rows(rows, spot=22400, expiry="2026-10-06", as_of=date(2026, 10, 1))
    assert analytics["pcr"] == pcr
    assert analytics["days_to_expiry"] == 5


def test_option_chain_highlights_bundle():
    session = FakeSession(
        {
            "/v2/option/contract": CONTRACTS_PAYLOAD,
            "/v2/option/chain": CHAIN_PAYLOAD,
        }
    )
    p = UpstoxProvider(token="t", session=session)
    h = p.option_chain_highlights("NIFTY", spot=22400, today=date(2026, 10, 1))
    assert h["available"] is True
    assert h["pcr"] is not None
    assert h["resistance"][0]["strike"] == 23000
