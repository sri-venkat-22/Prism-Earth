"""Export the generated OpenAPI schema to a file (SRS §13.22, §36.4).

Usage (from the backend directory, with the venv active)::

    python -m scripts.export_openapi            # writes openapi.json
    python -m scripts.export_openapi docs/openapi.json

The schema is produced by the FastAPI app itself, so it always matches the live
API contract — there is nothing to hand-maintain.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure the backend package is importable when run from the repo root.
_BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.main import app  # noqa: E402


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("openapi.json")
    schema = app.openapi()
    out.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    paths = len(schema.get("paths", {}))
    print(f"Wrote {out} ({paths} paths, OpenAPI {schema.get('openapi')})")


if __name__ == "__main__":
    main()
