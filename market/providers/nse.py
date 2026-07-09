"""NSE public endpoints (FII/DII provisional flows).

Requires a one-shot homepage visit to obtain cookies — same pattern as
browser clients. Returns structured JSON only; no investment advice.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

NSE_HOME = "https://www.nseindia.com"
FII_DII_URL = f"{NSE_HOME}/api/fiidiiTradeReact"

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": f"{NSE_HOME}/",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fetch_fii_dii_trade(*, timeout: float = 20.0) -> dict[str, Any]:
    """Fetch latest FII/FPI and DII cash-market provisional net flows (₹ Cr)."""
    with httpx.Client(
        headers=_DEFAULT_HEADERS,
        follow_redirects=True,
        timeout=timeout,
    ) as client:
        client.get(NSE_HOME)
        response = client.get(FII_DII_URL)
        response.raise_for_status()
        raw = response.json()

    participants: list[dict[str, Any]] = []
    for row in raw:
        category = str(row.get("category", "")).strip()
        participants.append(
            {
                "category": category,
                "date": row.get("date"),
                "buy_value_cr": _to_float(row.get("buyValue")),
                "sell_value_cr": _to_float(row.get("sellValue")),
                "net_value_cr": _to_float(row.get("netValue")),
            }
        )

    fii = next((p for p in participants if "FII" in p["category"].upper()), None)
    dii = next((p for p in participants if p["category"].upper() == "DII"), None)
    session_date = fii.get("date") if fii else (dii.get("date") if dii else None)

    return {
        "source": "nse_fiidiiTradeReact",
        "fetched_at": _now_iso(),
        "session_date": session_date,
        "fii": fii,
        "dii": dii,
        "participants": participants,
        "disclaimer": (
            "Provisional NSE cash-market FII/DII data. For analytics only; "
            "not investment advice."
        ),
    }


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None