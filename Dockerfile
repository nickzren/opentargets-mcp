FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MCP_TRANSPORT=http \
    FASTMCP_SERVER_HOST=0.0.0.0

WORKDIR /app

RUN groupadd --system appuser \
    && useradd --system --gid appuser --create-home appuser

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN pip install --no-cache-dir .

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import os,sys,urllib.request; transport=os.getenv('MCP_TRANSPORT','http'); port=os.getenv('FASTMCP_SERVER_PORT','8000'); url=f'http://127.0.0.1:{port}/'; code=200 if transport=='stdio' else urllib.request.urlopen(url, timeout=3).getcode(); sys.exit(0 if 200 <= code < 500 else 1)"

CMD ["opentargets-mcp"]
