# Cliplift backend — production image for Railway
FROM python:3.12-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency files first for caching
COPY pyproject.toml uv.lock* ./

# Install dependencies (no project install)
RUN uv sync --frozen --no-install-project --no-dev || uv sync --no-install-project --no-dev

# Copy application code
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# --- Runtime stage ---
FROM python:3.12-slim AS runtime

WORKDIR /app

# Copy from builder
COPY --from=builder /app /app
COPY --from=builder /bin/uv /bin/uv

# Non-root user
RUN useradd -m -u 1000 cliplift && chown -R cliplift:cliplift /app
USER cliplift

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# No HEALTHCHECK in Dockerfile — Railway handles health checks natively
# via the /health endpoint (configured in Railway dashboard). Spawning a
# Python interpreter every 30s for the check adds ~200ms overhead per probe.

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
