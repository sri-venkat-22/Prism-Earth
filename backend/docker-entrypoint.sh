#!/bin/sh
# Apply pending migrations, then hand off to the container's CMD (uvicorn).
#
# ponytail: runs on every container boot rather than as a separate one-shot
# job. `alembic upgrade head` is idempotent (a no-op once at head), so this is
# safe for a single instance — the topology every target here runs (dev,
# self-hosted VM, Render free tier). If this ever scales to multiple backend
# replicas racing the same migration on cold boot, split this back out into a
# dedicated migrate step that gates replica startup.
set -e
alembic upgrade head
exec "$@"
