# Trading MCP (stdio)

Market intelligence MCP server — JSON tools + optional PDF reports.

## Run

```bash
pip install -e ".[pdf]"
python -m services.trading_mcp
```

## Tools (v0.2)

| Tool | Purpose |
|------|---------|
| `get_quote` | Yahoo quote |
| `get_market_status` | NSE open/holiday/expiry/VIX |
| `get_fii_dii_flow` | NSE provisional FII/DII |
| `log_trade` / `get_journal` | SQLite journal |
| `generate_morning_brief` | Pre-market JSON + `brief_id` |
| `generate_eod_review` | EOD JSON + `brief_id` |
| `export_report_pdf` | PDF from `brief_id` |

## PDF

- Default: HTML + Chromium (`TRADING_PDF_RENDERER=html`)
- Fallback: `reportlab` (`TRADING_PDF_RENDERER=reportlab` or auto on Chromium failure)

## Docker

```bash
docker build -t trading-mcp .
docker run -i trading-mcp
```

Stdio MCP — attach with your MCP client over `-i`.