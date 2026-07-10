# Terra backend image (SRS §32). Python 3.12 + uv.
#
# Build context is the REPO ROOT (not backend/) so this can also COPY the
# top-level configs/ directory into the image — required on PaaS targets like
# Render that run a plain container with no Compose volume mounts. Locally,
# docker-compose's `./configs:/configs:ro` mount simply overlays this baked-in
# copy, so live-edited configs still work unchanged in dev.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Install uv (dependency manager). Pinned: an unpinned install picks up
# whatever uv released today, and a newer uv can enforce stricter lockfile
# checks than the one that generated uv.lock, breaking `--frozen` builds
# without any change on our side.
RUN pip install --no-cache-dir uv==0.11.25

# ---- Dependency layer (cached unless manifests change) ----
# The base image already provides Python 3.12. `--frozen` installs exactly what
# the committed uv.lock pins (fully reproducible); `--no-install-project` skips
# the app itself (it is a runnable, not a package — see pyproject [tool.uv]).
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# ---- Application layer ----
COPY backend/app ./app
COPY backend/alembic.ini ./
COPY backend/migrations ./migrations
COPY configs /configs
COPY backend/docker-entrypoint.sh ./
RUN chmod +x ./docker-entrypoint.sh

ENV PATH="/app/.venv/bin:$PATH" \
    TERRA_CONFIG_DIR=/configs

# Create a non-root user.
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Liveness for orchestrators (SRS §7.3). Uses the readiness-independent /health
# endpoint, which returns 200 while the process is serving.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/v1/health').status==200 else 1)"

# Applies pending migrations, then execs into CMD (see docker-entrypoint.sh).
# Every deploy target (dev compose, self-hosted VM, Render) gets migrations
# for free with no separate job/dashboard field to configure or typo.
ENTRYPOINT ["./docker-entrypoint.sh"]

# Production default: multiple Uvicorn workers behind Nginx (SRS §33). Override
# the worker count via the compose command for horizontal tuning.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
