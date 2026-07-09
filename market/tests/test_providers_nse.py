from __future__ import annotations

from market.providers import nse as nse_mod


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, *args, **kwargs):
        self.calls: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url: str):
        self.calls.append(url)
        if url.endswith("nseindia.com"):
            return _FakeResponse("<html></html>")
        return _FakeResponse(
            [
                {
                    "buyValue": "100",
                    "category": "DII",
                    "date": "08-Jul-2026",
                    "netValue": "10",
                    "sellValue": "90",
                },
                {
                    "buyValue": "200",
                    "category": "FII/FPI",
                    "date": "08-Jul-2026",
                    "netValue": "-5",
                    "sellValue": "205",
                },
            ]
        )


def test_fetch_fii_dii_trade_parses_categories(monkeypatch, sample_fii_dii_payload):
    class ClientWithPayload(_FakeClient):
        def get(self, url: str):
            self.calls.append(url)
            if "fiidii" in url:
                return _FakeResponse(sample_fii_dii_payload)
            return _FakeResponse("")

    monkeypatch.setattr(nse_mod.httpx, "Client", ClientWithPayload)
    out = nse_mod.fetch_fii_dii_trade()
    assert out["session_date"] == "08-Jul-2026"
    assert out["fii"]["net_value_cr"] == 1962.8
    assert out["dii"]["net_value_cr"] == 790.16
    assert "disclaimer" in out