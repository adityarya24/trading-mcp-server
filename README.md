# trading-mcp-server

[![CI](https://github.com/adityarya24/trading-mcp-server/actions/workflows/ci.yml/badge.svg)](https://github.com/adityarya24/trading-mcp-server/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![MCP](https://img.shields.io/badge/MCP-stdio-6f42c1)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

Market intelligence **Model Context Protocol (stdio)** server for Indian and global markets. Plug into OpenClaw, Claude Desktop, or any MCP client — quotes, journal, FII/DII, morning brief / EOD JSON, PDF export.

**Outputs are analytics only** (SEBI-safe by design): no buy/sell signals in report schemas.

## Quick start

```bash
git clone https://github.com/adityarya24/trading-mcp-server.git
cd trading-mcp-server
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[pdf,dev]"
python -m services.trading_mcp          # stdio MCP server
python scripts/smoke_mcp_client.py      # integration smoke (network)
```

## MCP tools (v0.2)

| Tool | Description |
|------|-------------|
| `get_quote` | LTP / OHLC / change% (Yahoo Finance) |
| `get_market_status` | NSE open, holiday, expiry, VIX |
| `get_fii_dii_flow` | NSE provisional FII/DII (₹ Cr) |
| `log_trade` / `get_journal` | SQLite trade journal |
| `generate_morning_brief` | Pre-market JSON + `brief_id` |
| `generate_eod_review` | EOD JSON + `brief_id` |
| `export_report_pdf` | PDF via HTML/Chromium or reportlab fallback |

## PDF rendering

| Env | Purpose |
|-----|---------|
| `TRADING_PDF_RENDERER=html` | Playwright + Chromium (default in Docker) |
| `TRADING_PDF_RENDERER=reportlab` | In-process fallback (CI / minimal installs) |
| `TRADING_CHROMIUM_EXECUTABLE` | Path to Chromium binary |

```bash
docker build -t trading-mcp .
docker run -i trading-mcp
```

## Development

```bash
pytest -q
ruff check market services
```

Unit tests mock **providers**, **NSE**, and **reports** — no live market calls in CI.

## Layout

```
market/           # data providers, reports, templates
services/trading_mcp/   # MCP server + tools + SQLite
scripts/          # smoke_mcp_client.py
```

## License

MIT — see [LICENSE](LICENSE) (add if not yet committed).