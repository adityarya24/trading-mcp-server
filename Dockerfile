FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TRADING_PDF_RENDERER=html \
    TRADING_MCP_HOME=/app/data

RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    fonts-noto-core \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

ENV TRADING_CHROMIUM_EXECUTABLE=/usr/bin/chromium

WORKDIR /app
COPY pyproject.toml ./
COPY market ./market
COPY services ./services
COPY scripts ./scripts

RUN pip install --no-cache-dir -e ".[pdf]" \
    && playwright install-deps chromium || true

RUN mkdir -p /app/data/reports

CMD ["python", "-m", "services.trading_mcp"]