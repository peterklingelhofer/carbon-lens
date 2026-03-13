# --- Build stage ---
FROM python:3.12-slim AS builder

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev --no-install-project

COPY src/ src/
COPY data/ data/
RUN uv sync --no-dev

# --- Runtime stage ---
FROM python:3.12-slim

# curl needed for health checks
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/data /app/data

# Alembic files for auto-migration
COPY alembic.ini ./
COPY alembic/ alembic/

RUN chown -R appuser:appuser /app

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

USER appuser
EXPOSE 8000

# Use PORT env var for PaaS compatibility (Fly.io, Heroku, Railway)
CMD ["sh", "-c", "uvicorn carbon_mesh.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
