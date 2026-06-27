"""Time helpers."""

from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Timezone-aware current UTC time."""
    return datetime.now(timezone.utc)


def utcnow_iso() -> str:
    """ISO 8601 UTC timestamp with a trailing ``Z`` (e.g. ``2026-06-27T10:30:00Z``)."""
    return utcnow().isoformat(timespec="seconds").replace("+00:00", "Z")
