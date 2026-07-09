"""Option chain analytics (max pain, PCR, OI highlights)."""
from __future__ import annotations

from typing import Any

import pandas as pd


def _oi_column(frame: pd.DataFrame) -> str:
    for name in ("openInterest", "openinterest", "oi"):
        if name in frame.columns:
            return name
    return "openInterest"


def compute_max_pain(calls: pd.DataFrame, puts: pd.DataFrame) -> float | None:
    if calls.empty and puts.empty:
        return None
    strikes = sorted(
        set(calls.get("strike", pd.Series(dtype=float)).tolist())
        | set(puts.get("strike", pd.Series(dtype=float)).tolist())
    )
    if not strikes:
        return None
    call_oi = calls.set_index("strike")[_oi_column(calls)] if not calls.empty else pd.Series(dtype=float)
    put_oi = puts.set_index("strike")[_oi_column(puts)] if not puts.empty else pd.Series(dtype=float)

    best_strike = None
    best_pain = None
    for settlement in strikes:
        pain = 0.0
        for strike, oi in call_oi.items():
            pain += max(0.0, settlement - strike) * float(oi or 0)
        for strike, oi in put_oi.items():
            pain += max(0.0, strike - settlement) * float(oi or 0)
        if best_pain is None or pain < best_pain:
            best_pain = pain
            best_strike = settlement
    return round(float(best_strike), 2) if best_strike is not None else None


def compute_pcr(calls: pd.DataFrame, puts: pd.DataFrame) -> float | None:
    if calls.empty or puts.empty:
        return None
    call_oi = float(calls[_oi_column(calls)].fillna(0).sum())
    put_oi = float(puts[_oi_column(puts)].fillna(0).sum())
    if call_oi <= 0:
        return None
    return round(put_oi / call_oi, 4)


def highest_oi_strike(frame: pd.DataFrame, side: str) -> dict[str, Any] | None:
    if frame.empty:
        return None
    col = _oi_column(frame)
    idx = frame[col].fillna(0).astype(float).idxmax()
    row = frame.loc[idx]
    return {
        "side": side,
        "strike": float(row.get("strike", 0)),
        "open_interest": float(row.get(col, 0) or 0),
    }


def strikes_snapshot(calls: pd.DataFrame, puts: pd.DataFrame, limit: int = 25) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not calls.empty:
        col = _oi_column(calls)
        for _, row in calls.nlargest(limit, col).iterrows():
            rows.append(
                {
                    "type": "CALL",
                    "strike": float(row["strike"]),
                    "open_interest": float(row.get(col, 0) or 0),
                    "last_price": float(row.get("lastPrice", row.get("last", 0)) or 0),
                }
            )
    if not puts.empty:
        col = _oi_column(puts)
        for _, row in puts.nlargest(limit, col).iterrows():
            rows.append(
                {
                    "type": "PUT",
                    "strike": float(row["strike"]),
                    "open_interest": float(row.get(col, 0) or 0),
                    "last_price": float(row.get("lastPrice", row.get("last", 0)) or 0),
                }
            )
    return rows