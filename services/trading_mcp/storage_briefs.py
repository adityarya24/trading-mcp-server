"""Brief persistence helpers (kept separate to limit storage.py churn)."""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from market.models import now_iso_utc

from .storage import _connect, init_db


def insert_brief(
    db_path: Path | str,
    report: dict[str, Any],
    *,
    pdf_path: str | None = None,
) -> str:
    init_db(db_path)
    brief_id = f"brf-{uuid.uuid4().hex[:12]}"
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO briefs (brief_id, report_type, report_date, payload_json, pdf_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                brief_id,
                report["report_type"],
                report["report_date"],
                json.dumps(report, ensure_ascii=False),
                pdf_path,
                now_iso_utc(),
            ),
        )
        conn.commit()
    return brief_id


def get_brief(db_path: Path | str, brief_id: str) -> dict[str, Any] | None:
    init_db(db_path)
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT brief_id, report_type, report_date, payload_json, pdf_path, created_at FROM briefs WHERE brief_id = ?",
            (brief_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "brief_id": row["brief_id"],
        "report_type": row["report_type"],
        "report_date": row["report_date"],
        "report": json.loads(row["payload_json"]),
        "pdf_path": row["pdf_path"],
        "created_at": row["created_at"],
    }


def update_brief_pdf_path(db_path: Path | str, brief_id: str, pdf_path: str) -> None:
    init_db(db_path)
    with _connect(db_path) as conn:
        conn.execute("UPDATE briefs SET pdf_path = ? WHERE brief_id = ?", (pdf_path, brief_id))
        conn.commit()