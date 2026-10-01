#!/usr/bin/env python3
"""Build morning/EOD brief PDF and print Telegram summary + MEDIA path."""
from __future__ import annotations

import argparse
import sys
import traceback
from datetime import datetime
from pathlib import Path

# Repo root on sys.path
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from market.reports.eod_review import build_eod_review  # noqa: E402
from market.reports.morning_brief import build_morning_brief  # noqa: E402
from market.reports.pdf_export import export_report_pdf  # noqa: E402
from market.reports.summary import telegram_summary  # noqa: E402
from zoneinfo import ZoneInfo  # noqa: E402

IST = ZoneInfo("Asia/Kolkata")


def _default_pdf_path(mode: str, report_date: str) -> Path:
    out_dir = Path.home() / ".hermes" / "shared" / "briefs"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(IST).strftime("%H%M%S")
    return out_dir / f"{mode}_{report_date}_{stamp}.pdf"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Arjun morning/EOD brief runner")
    parser.add_argument("--mode", choices=("morning", "eod"), required=True)
    parser.add_argument("--date", default=None, help="YYYY-MM-DD (default: today)")
    parser.add_argument("--pdf", default=None, help="Output PDF path")
    args = parser.parse_args(argv)

    pdf_path: Path | None = None
    reason = None
    report = None

    try:
        if args.mode == "morning":
            report = build_morning_brief(args.date)
        else:
            report = build_eod_review(args.date)
    except Exception as exc:  # noqa: BLE001
        reason = f"report build failed: {exc}"
        print(f"DATA_UNAVAILABLE: {reason}", file=sys.stdout)
        traceback.print_exc(file=sys.stderr)
        return 0

    try:
        pdf_path = Path(args.pdf) if args.pdf else _default_pdf_path(args.mode, report["report_date"])
        export_report_pdf(report, pdf_path)
    except Exception as exc:  # noqa: BLE001
        reason = f"pdf export failed: {exc}"
        pdf_path = None
        traceback.print_exc(file=sys.stderr)

    try:
        summary = telegram_summary(report)
    except Exception as exc:  # noqa: BLE001
        summary = ""
        reason = reason or f"summary failed: {exc}"

    if not summary.strip():
        print(f"DATA_UNAVAILABLE: {reason or 'empty summary'}")
    else:
        # Strip accidental None
        print(summary.replace("None", "—"))

    if pdf_path and pdf_path.exists():
        print()
        print(f"MEDIA:{pdf_path.resolve()}")
    elif reason:
        print(f"DATA_UNAVAILABLE: {reason}")
        return 0

    # Exit 0 unless nothing at all could be produced
    if not summary.strip() and not (pdf_path and pdf_path.exists()):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
