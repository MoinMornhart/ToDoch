# syntax=docker/dockerfile:1
# App- und Worker-Image. Build-Kontext ist das Repository-Hauptverzeichnis.

FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY backend/app ./app
COPY VERSION ./VERSION
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim
RUN groupadd --system --gid 10001 todoch \
    && useradd --system --uid 10001 --gid todoch --home-dir /app --shell /usr/sbin/nologin todoch
WORKDIR /app
COPY --from=build /app /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
USER todoch
EXPOSE 8000
# Migrationen laufen bei jedem Start (idempotent); Zugriffslogs schreibt Caddy.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips '*' --no-server-header --no-access-log"]
