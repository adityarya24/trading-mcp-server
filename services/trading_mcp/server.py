"""Trading MCP server (stdio).

Market intelligence MCP server. Binds the tool registry to a real
Model Context Protocol stdio server. Schemas are declared explicitly
so the registry stays the single source of truth.

Run with::

    python -m services.trading_mcp
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Callable

import mcp.types as types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server

from .tools import TOOLS

SERVER_NAME = "trading-mcp"
SERVER_VERSION = "0.2.2"


def list_tool_names() -> list[str]:
    return sorted(TOOLS.keys())


def get_tool(name: str) -> Callable:
    try:
        return TOOLS[name]
    except KeyError as exc:
        raise KeyError(f"Unknown trading_mcp tool: {name}") from exc


# --- JSON Schemas for each tool ---------------------------------------------

TOOL_DEFINITIONS: list[types.Tool] = [
    types.Tool(
        name="get_quote",
        description="Get real-time/delayed quote for a symbol (Nifty, Sensex, stocks, crypto, XAUUSD). Returns LTP, OHLC, change%, volume.",
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Ticker symbol: 'NIFTY 50', 'SENSEX', 'RELIANCE.NS', 'XAUUSD' etc.",
                },
            },
            "required": ["symbol"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="get_market_status",
        description="Check if NSE is open, next holiday, today's expiry, current VIX.",
        inputSchema={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="log_trade",
        description="Log a new trade entry to the journal. Returns trade_id on success.",
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Ticker symbol, e.g. 'NIFTY 50', 'RELIANCE'"},
                "direction": {"type": "string", "enum": ["LONG", "SHORT"]},
                "entry_price": {"type": "number"},
                "quantity": {"type": "integer", "minimum": 1},
                "stop_loss": {"type": ["number", "null"], "description": "Stop loss price"},
                "target": {"type": ["number", "null"], "description": "Target price"},
                "strategy": {"type": ["string", "null"], "description": "Strategy tag, e.g. 'breakout', 'reversal'"},
                "tags": {"type": ["string", "null"], "description": "JSON array of tags, e.g. '[\"expiry\",\"scalping\"]'"},
                "notes": {"type": ["string", "null"], "description": "Trade rationale / entry notes"},
                "db_path": {"type": ["string", "null"], "description": "SQLite path override"},
            },
            "required": ["symbol", "direction", "entry_price", "quantity"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="get_journal",
        description="Query trade journal by date range and optional symbol filter.",
        inputSchema={
            "type": "object",
            "properties": {
                "from_date": {"type": "string", "description": "Start date YYYY-MM-DD"},
                "to_date": {"type": "string", "description": "End date YYYY-MM-DD"},
                "symbol": {"type": ["string", "null"], "description": "Filter by symbol"},
                "direction": {"type": ["string", "null"], "enum": ["LONG", "SHORT", None]},
                "db_path": {"type": ["string", "null"], "description": "SQLite path override"},
            },
            "required": ["from_date", "to_date"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="get_fii_dii_flow",
        description="Latest NSE provisional FII/FPI and DII cash-market net flows (₹ Cr). Analytics only.",
        inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
    ),
    types.Tool(
        name="get_option_chain",
        description="Option chain analytics: max pain, PCR, highest call/put OI (Yahoo). Data only.",
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "e.g. NIFTY 50"},
                "expiry": {"type": ["string", "null"], "description": "YYYY-MM-DD expiry"},
            },
            "required": ["symbol"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="generate_morning_brief",
        description="Build pre-market morning brief JSON (indices, globals, FII/DII, levels). Persists to SQLite.",
        inputSchema={
            "type": "object",
            "properties": {
                "report_date": {"type": ["string", "null"], "description": "YYYY-MM-DD (default today)"},
                "db_path": {"type": ["string", "null"]},
            },
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="generate_eod_review",
        description="Build end-of-day review JSON (indices, FII/DII, journal). Persists to SQLite.",
        inputSchema={
            "type": "object",
            "properties": {
                "report_date": {"type": ["string", "null"]},
                "db_path": {"type": ["string", "null"]},
            },
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="export_report_pdf",
        description="Render a stored brief as PDF (Chromium HTML pipeline with reportlab fallback).",
        inputSchema={
            "type": "object",
            "properties": {
                "brief_id": {"type": "string"},
                "output_path": {"type": ["string", "null"]},
                "renderer": {"type": ["string", "null"], "enum": ["html", "reportlab", None]},
                "db_path": {"type": ["string", "null"]},
            },
            "required": ["brief_id"],
            "additionalProperties": False,
        },
    ),
]


def _build_server() -> Server:
    server: Server = Server(SERVER_NAME)

    @server.list_tools()
    async def _handle_list_tools() -> list[types.Tool]:
        return TOOL_DEFINITIONS

    @server.call_tool()
    async def _handle_call_tool(
        name: str, arguments: dict[str, Any] | None
    ) -> list[types.TextContent]:
        fn = get_tool(name)
        kwargs = dict(arguments or {})
        result = await asyncio.to_thread(fn, **kwargs)
        payload = json.dumps(result, ensure_ascii=False, default=str)
        return [types.TextContent(type="text", text=payload)]

    return server


def build_initialization_options(server: Server) -> InitializationOptions:
    return InitializationOptions(
        server_name=SERVER_NAME,
        server_version=SERVER_VERSION,
        capabilities=server.get_capabilities(
            notification_options=NotificationOptions(),
            experimental_capabilities={},
        ),
    )


async def run_stdio() -> None:
    server = _build_server()
    options = build_initialization_options(server)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, options)


def main() -> None:
    asyncio.run(run_stdio())


if __name__ == "__main__":
    main()
