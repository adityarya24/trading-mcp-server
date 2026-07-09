"""SQLite-backed storage for the trading MCP service."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import Trade

DEFAULT_DB_PATH = Path("data/trading_mcp.sqlite3")


def default_db_path() -> Path:
    return DEFAULT_DB_PATH


SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    trade_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL CHECK(direction IN ('LONG','SHORT')),
    entry_price REAL NOT NULL,
    entry_time TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    stop_loss REAL,
    target REAL,
    exit_price REAL,
    exit_time TEXT,
    pnl REAL,
    strategy TEXT,
    tags TEXT DEFAULT '[]',
    notes TEXT,
    review TEXT,
    status TEXT NOT NULL DEFAULT 'OPEN' CHECK(status IN ('OPEN','CLOSED','CANCELLED')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_trades_date ON trades(entry_time);
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);

CREATE TABLE IF NOT EXISTS briefs (
    brief_id TEXT PRIMARY KEY,
    report_type TEXT NOT NULL,
    report_date TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    pdf_path TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_briefs_type_date ON briefs(report_type, report_date);
"""


def _connect(db_path: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init_db(db_path: Path | str) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(path) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def insert_trade(db_path: Path | str, trade: Trade) -> Trade:
    init_db(db_path)
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO trades (
                trade_id, symbol, direction, entry_price, entry_time,
                quantity, stop_loss, target, strategy, tags, notes,
                status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trade.trade_id,
                trade.symbol,
                trade.direction,
                trade.entry_price,
                trade.entry_time,
                trade.quantity,
                trade.stop_loss,
                trade.target,
                trade.strategy,
                trade.tags or "[]",
                trade.notes,
                trade.status,
                trade.created_at,
                trade.updated_at,
            ),
        )
        conn.commit()
    return trade


def _row_to_trade(row: sqlite3.Row) -> Trade:
    return Trade(
        trade_id=row["trade_id"],
        symbol=row["symbol"],
        direction=row["direction"],
        entry_price=row["entry_price"],
        entry_time=row["entry_time"],
        quantity=row["quantity"],
        stop_loss=row["stop_loss"],
        target=row["target"],
        exit_price=row["exit_price"],
        exit_time=row["exit_time"],
        pnl=row["pnl"],
        strategy=row["strategy"],
        tags=row["tags"],
        notes=row["notes"],
        review=row["review"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def query_trades(
    db_path: Path | str,
    from_date: str,
    to_date: str,
    symbol: str | None = None,
    direction: str | None = None,
) -> list[Trade]:
    init_db(db_path)
    query = "SELECT * FROM trades WHERE entry_time >= ? AND entry_time <= ?"
    params: list[str | None] = [from_date + "T00:00:00", to_date + "T23:59:59"]

    if symbol:
        query += " AND symbol = ?"
        params.append(symbol)
    if direction:
        query += " AND direction = ?"
        params.append(direction)

    query += " ORDER BY entry_time DESC"
    with _connect(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_trade(row) for row in rows]
