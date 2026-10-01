"""Option chain analytics (max pain, PCR, OI highlights)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd


def _oi_column(frame: pd.DataFrame) -> str:
    for name in ("openInterest", "openinterest", "oi", "ce_oi", "pe_oi"):
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


# --- Pure helpers for Upstox-shaped chain rows ---------------------------------


def compute_pcr_from_rows(rows: list[dict[str, Any]]) -> float | None:
    """PCR = total PE OI / total CE OI, 2 decimals."""
    ce = sum(float(r.get("ce_oi") or 0) for r in rows)
    pe = sum(float(r.get("pe_oi") or 0) for r in rows)
    if ce <= 0:
        return None
    return round(pe / ce, 2)


def compute_max_pain_from_rows(rows: list[dict[str, Any]]) -> float | None:
    """Strike that minimises total payout to option buyers."""
    if not rows:
        return None
    strikes = sorted({float(r["strike"]) for r in rows if r.get("strike") is not None})
    if not strikes:
        return None
    best_strike = None
    best_pain = None
    for settlement in strikes:
        pain = 0.0
        for r in rows:
            k = float(r["strike"])
            ce_oi = float(r.get("ce_oi") or 0)
            pe_oi = float(r.get("pe_oi") or 0)
            pain += max(0.0, settlement - k) * ce_oi
            pain += max(0.0, k - settlement) * pe_oi
        if best_pain is None or pain < best_pain:
            best_pain = pain
            best_strike = settlement
    return round(float(best_strike), 2) if best_strike is not None else None


def top_oi_strikes(rows: list[dict[str, Any]], side: str, n: int = 3) -> list[dict[str, Any]]:
    """Top N strikes by CE or PE open interest.

    side: 'CE' (resistance) or 'PE' (support).
    """
    key = "ce_oi" if side.upper() == "CE" else "pe_oi"
    ranked = sorted(
        rows,
        key=lambda r: float(r.get(key) or 0),
        reverse=True,
    )
    out: list[dict[str, Any]] = []
    for r in ranked[:n]:
        oi = float(r.get(key) or 0)
        if oi <= 0:
            continue
        out.append(
            {
                "strike": float(r["strike"]),
                "open_interest": oi,
                "ltp": r.get("ce_ltp") if side.upper() == "CE" else r.get("pe_ltp"),
            }
        )
    return out


def days_to_expiry(expiry: str | None, as_of: date | None = None) -> int | None:
    if not expiry:
        return None
    try:
        exp_d = date.fromisoformat(str(expiry)[:10])
    except ValueError:
        return None
    base = as_of or date.today()
    return (exp_d - base).days


def _side_of_spot(rows: list[dict[str, Any]], spot: float | None, *, above: bool) -> list[dict[str, Any]]:
    """Strikes at or above spot (above=True) or at or below it; all rows when spot is unknown."""
    if spot is None:
        return rows
    return [r for r in rows if (float(r["strike"]) >= spot if above else float(r["strike"]) <= spot)]


def analyze_chain_rows(
    rows: list[dict[str, Any]],
    *,
    spot: float | None = None,
    expiry: str | None = None,
    as_of: date | None = None,
) -> dict[str, Any]:
    """Bundle PCR, max pain, support/resistance OI for report sections."""
    exp = expiry or (rows[0].get("expiry") if rows else None)
    day = as_of
    if day is None and isinstance(as_of, datetime):
        day = as_of.date()
    return {
        "expiry": exp,
        "days_to_expiry": days_to_expiry(exp, as_of=day),
        "spot": spot,
        "pcr": compute_pcr_from_rows(rows),
        "max_pain": compute_max_pain_from_rows(rows),
        # Walls only count on their side of spot: a call wall below spot or a
        # put wall above it is in the money and says nothing about the next level.
        "resistance": top_oi_strikes(_side_of_spot(rows, spot, above=True), "CE", 3),
        "support": top_oi_strikes(_side_of_spot(rows, spot, above=False), "PE", 3),
        "total_ce_oi": sum(float(r.get("ce_oi") or 0) for r in rows),
        "total_pe_oi": sum(float(r.get("pe_oi") or 0) for r in rows),
        "strikes": rows,
    }
