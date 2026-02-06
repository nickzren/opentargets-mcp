FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --system appuser \
    && useradd --system --gid appuser --create-home appuser

COPY pyproject.toml uv.lock README.md ./

RUN pip install --no-cache-dir uv --upgrade \
    && uv sync --frozen --no-dev --no-install-project \
    && rm -rf /root/.cache/pip

COPY . .

RUN uv sync --frozen --no-dev \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import os,sys,urllib.request; transport=os.getenv('MCP_TRANSPORT','http'); port=os.getenv('FASTMCP_SERVER_PORT','8000'); url=f'http://127.0.0.1:{port}/'; code=200 if transport=='stdio' else urllib.request.urlopen(url, timeout=3).getcode(); sys.exit(0 if 200 <= code < 500 else 1)"

CMD ["uv","run","python","-m","opentargets_mcp.server"]
