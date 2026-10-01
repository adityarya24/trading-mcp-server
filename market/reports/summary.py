"""Plain-text Telegram summaries for morning / EOD briefs (max 5 lines)."""
from __future__ import annotations

from typing import Any

from market.reports.common import fmt_pct, fmt_price, fmt_signed_cr


def _find_index(rows: list[dict[str, Any]] | None, *names: str) -> dict[str, Any] | None:
    if not rows:
        return None
    wanted = {n.upper() for n in names}
    for row in rows:
        sym = str(row.get("symbol") or "").upper()
        if sym in wanted:
            return row
    return None


def _idx_bit(row: dict[str, Any] | None, label: str) -> str | None:
    if not row or row.get("ltp") is None:
        return None
    pct = row.get("change_pct")
    if pct is None:
        return f"{label} {fmt_price(row['ltp'])}"
    return f"{label} {fmt_price(row['ltp'])} ({fmt_pct(pct)})"


def _oi_line(block: dict[str, Any] | None, label: str) -> str | None:
    if not block:
        return None
    if not block.get("available"):
        msg = block.get("message") or "unavailable"
        # Keep short — no multi-line dump
        short = str(msg).split(":")[-1].strip() if msg else "unavailable"
        return f"{label} OI: {short[:40]}"
    support = block.get("support") or []
    resist = block.get("resistance") or []
    sup = fmt_price(support[0]["strike"], 0) if support else "—"
    res = fmt_price(resist[0]["strike"], 0) if resist else "—"
    pcr = block.get("pcr")
    pcr_s = f"{pcr:.2f}" if isinstance(pcr, (int, float)) else "—"
    parts = [f"{label} OI: support {sup} / resistance {res}", f"PCR {pcr_s}"]
    mp = block.get("max_pain")
    if mp is not None and label.startswith("Nifty") and not label.startswith("Bank"):
        parts.append(f"max pain {fmt_price(mp, 0)}")
        exp = block.get("expiry")
        if exp:
            # "2026-10-06" -> "6 Oct"
            try:
                from datetime import date

                d = date.fromisoformat(str(exp)[:10])
                parts.append(f"expiry {d.day} {d.strftime('%b')}")
            except ValueError:
                parts.append(f"expiry {exp}")
    return " · ".join(parts)


def _global_line(cues: list[dict[str, Any]] | None) -> str | None:
    if not cues:
        return None
    by_label = {str(c.get("label") or "").upper(): c for c in cues}

    def bit(label: str, short: str, price: bool = False) -> str | None:
        row = by_label.get(label.upper())
        if not row:
            # try fuzzy
            for k, v in by_label.items():
                if label.upper() in k:
                    row = v
                    break
        if not row or row.get("ltp") is None:
            return None
        if price and "BRENT" in label.upper():
            return f"{short} ${fmt_price(row['ltp'])} ({fmt_pct(row.get('change_pct'))})"
        if "USD" in label.upper() or "INR" in short:
            return f"{short} {fmt_price(row['ltp'])}"
        return f"{short} {fmt_pct(row.get('change_pct'))}"

    parts = [
        p
        for p in (
            bit("S&P 500", "S&P"),
            bit("NASDAQ", "Nasdaq"),
            bit("Brent Crude", "Brent", price=True),
            bit("USD/INR", "USD/INR"),
        )
        if p
    ]
    if not parts:
        return None
    return "Global: " + " · ".join(parts)


def _fii_line(fii_dii: dict[str, Any] | None) -> str | None:
    if not fii_dii or fii_dii.get("error"):
        return None
    fii = fii_dii.get("fii") or {}
    dii = fii_dii.get("dii") or {}
    if fii.get("net_value_cr") is None and dii.get("net_value_cr") is None:
        return None
    date_s = fii.get("date") or dii.get("date") or fii_dii.get("session_date") or ""
    # Try compact date "30 Sep"
    date_bit = ""
    if date_s:
        date_bit = f" ({date_s})"
    parts = []
    if fii.get("net_value_cr") is not None:
        parts.append(f"FII {fmt_signed_cr(fii['net_value_cr'])}")
    if dii.get("net_value_cr") is not None:
        parts.append(f"DII {fmt_signed_cr(dii['net_value_cr'])}")
    return " · ".join(parts) + date_bit


def telegram_summary(report: dict[str, Any]) -> str:
    """At most 5 plain-text lines; no Markdown tables; never 'None'."""
    sections = report.get("sections") or {}
    rtype = report.get("report_type")

    if rtype == "eod_review":
        indices = sections.get("index_scorecard") or []
    else:
        indices = sections.get("market_pulse") or []

    nifty = _find_index(indices, "NIFTY 50", "NIFTY")
    sensex = _find_index(indices, "SENSEX")
    bank = _find_index(indices, "BANK NIFTY", "BANKNIFTY")
    vix = _find_index(indices, "INDIA VIX", "INDIAVIX")

    line1_parts = [
        p
        for p in (
            _idx_bit(nifty, "Nifty"),
            _idx_bit(sensex, "Sensex"),
            _idx_bit(bank, "Bank Nifty"),
        )
        if p
    ]
    if vix and vix.get("ltp") is not None:
        line1_parts.append(f"VIX {fmt_price(vix['ltp'])}")
    if report.get("upstox_error") and not line1_parts:
        line1_parts.append("Indices: Upstox unavailable")

    oc = sections.get("option_chain_highlights") or {}
    # Support both dict-of-underlyings and legacy single block
    if isinstance(oc, dict) and ("NIFTY" in oc or "BANKNIFTY" in oc):
        nifty_oc = oc.get("NIFTY")
        bank_oc = oc.get("BANKNIFTY")
    else:
        nifty_oc = oc if isinstance(oc, dict) else None
        bank_oc = None

    lines: list[str] = []
    if line1_parts:
        lines.append(" · ".join(line1_parts))

    for block, label in ((nifty_oc, "Nifty"), (bank_oc, "Bank Nifty")):
        line = _oi_line(block, label)
        if line:
            lines.append(line)

    g = _global_line(sections.get("global_cues"))
    if g:
        lines.append(g)

    f = _fii_line(sections.get("fii_dii"))
    if f:
        lines.append(f)

    # Cap at 5; drop least critical from the end of middle if needed
    cleaned = [ln.replace("None", "—") for ln in lines if ln and str(ln).strip()]
    return "\n".join(cleaned[:5])
