# Prism Earth backend image (SRS §32). Python 3.12 + uv.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Install uv (dependency manager).
RUN pip install --no-cache-dir uv

# ---- Dependency layer (cached unless manifests change) ----
# The base image already provides Python 3.12. `--frozen` installs exactly what
# the committed uv.lock pins (fully reproducible); `--no-install-project` skips
# the app itself (it is a runnable, not a package — see pyproject [tool.uv]).
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# ---- Application layer ----
COPY app ./app
COPY alembic.ini ./
COPY migrations ./migrations

ENV PATH="/app/.venv/bin:$PATH" \
    PRISM_CONFIG_DIR=/configs

# Create a non-root user.
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
