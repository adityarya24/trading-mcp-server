#!/usr/bin/env python3
"""Smoke-test the Trading MCP server via stdio.

Spawns the server as a child process, initialises the MCP session,
and exercises the registered MCP tools (quotes, journal, briefs, PDF).

Usage::

    python scripts/smoke_mcp_client.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def run_smoke() -> None:
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "services.trading_mcp"],
        cwd=str(REPO_ROOT),
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # 1. List tools
            tools_result = await session.list_tools()
            tool_names = [t.name for t in tools_result.tools]
            assert len(tool_names) >= 9, tool_names
            print(f"✓ list_tools: {len(tool_names)} tools registered — {tool_names}")

            # 2. get_market_status
            result = await session.call_tool("get_market_status", {})
            status = json.loads(result.content[0].text)
            print(f"\n✓ get_market_status: is_open={status['is_open']}, vix={status.get('vix')}, expiry={status.get('today_expiry')}")

            # 3. get_quote — Nifty
            result = await session.call_tool("get_quote", {"symbol": "NIFTY 50"})
            quote = json.loads(result.content[0].text)
            print(f"✓ get_quote(NIFTY): LTP={quote.get('ltp')}, change_pct={quote.get('change_pct')}")

            # 4. get_quote — Sensex
            result = await session.call_tool("get_quote", {"symbol": "SENSEX"})
            quote = json.loads(result.content[0].text)
            print(f"✓ get_quote(SENSEX): LTP={quote.get('ltp')}, change_pct={quote.get('change_pct')}")

            # 5. get_quote — XAUUSD
            result = await session.call_tool("get_quote", {"symbol": "XAUUSD"})
            quote = json.loads(result.content[0].text)
            print(f"✓ get_quote(XAUUSD): LTP={quote.get('ltp')}")

            # 6. log_trade
            result = await session.call_tool("log_trade", {
                "symbol": "NIFTY 50",
                "direction": "LONG",
                "entry_price": 23960,
                "quantity": 50,
                "stop_loss": 23900,
                "target": 24100,
                "strategy": "bounce",
                "notes": "Smoke test trade",
            })
            trade_result = json.loads(result.content[0].text)
            trade_id = trade_result["trade_id"]
            print(f"\n✓ log_trade: id={trade_id}, status={trade_result['status']}")

            # 7. get_journal — today's trades
            from datetime import date
            today = date.today().isoformat()
            result = await session.call_tool("get_journal", {
                "from_date": today,
                "to_date": today,
            })
            journal = json.loads(result.content[0].text)
            trades = journal.get("trades", [])
            print(f"✓ get_journal({today}): {journal['count']} trade(s) found")

            # Verify the trade we just logged is in the journal
            logged_ids = [t["trade_id"] for t in trades]
            assert trade_id in logged_ids, f"Logged trade {trade_id} not found in journal!"
            print(f"  ↳ verified: trade {trade_id} appears in journal")

            # 8. GIFT Nifty quote
            result = await session.call_tool("get_quote", {"symbol": "GIFT NIFTY"})
            gift = json.loads(result.content[0].text)
            print(f"✓ get_quote(GIFT NIFTY): LTP={gift.get('ltp')}")

            result = await session.call_tool("get_option_chain", {"symbol": "NIFTY 50"})
            chain = json.loads(result.content[0].text)
            print(f"✓ get_option_chain(NIFTY): available={chain.get('available')}")

            # 9. FII/DII
            result = await session.call_tool("get_fii_dii_flow", {})
            fii = json.loads(result.content[0].text)
            assert "participants" in fii or "error" not in fii
            print(f"\n✓ get_fii_dii_flow: session={fii.get('session_date')}")

            # 10. Morning brief + PDF (reportlab — no Chromium required in CI)
            result = await session.call_tool("generate_morning_brief", {})
            brief = json.loads(result.content[0].text)
            brief_id = brief["brief_id"]
            print(f"✓ generate_morning_brief: brief_id={brief_id}")

            result = await session.call_tool(
                "export_report_pdf",
                {"brief_id": brief_id, "renderer": "reportlab"},
            )
            pdf_meta = json.loads(result.content[0].text)
            print(f"✓ export_report_pdf: {pdf_meta.get('pdf_path')} ({pdf_meta.get('renderer')})")

            print("\n" + "=" * 50)
            print("🎯 ALL SMOKE TESTS PASSED")
            print("=" * 50)


def main() -> None:
    asyncio.run(run_smoke())


if __name__ == "__main__":
    main()
