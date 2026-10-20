# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:0.12.22-python3.14-trixie-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    FASTPRIZE_DB_PATH=/data/fastprize.sqlite3 \
    FASTPRIZE_COOKIE_SECURE=true \
    FORWARDED_ALLOW_IPS=""

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY src/ ./src/
COPY assets/ ./assets/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev \
    && groupadd --gid 10001 fastprize \
    && useradd --uid 10001 --gid fastprize --create-home fastprize \
    && mkdir /data \
    && chown fastprize:fastprize /data

USER fastprize
EXPOSE 5001
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "from urllib.request import urlopen; assert urlopen('http://127.0.0.1:5001/login', timeout=3).status == 200"

CMD ["uvicorn", "fastprize.app:app", "--host", "0.0.0.0", "--port", "5001", "--workers", "1", "--proxy-headers"]