"""Run the Prism Earth MCP server (SRS §34).

    python -m app.mcp                         # stdio (Claude Desktop / Cursor)
    python -m app.mcp --transport streamable-http --port 8765

Configuration defaults come from the ``PRISM_MCP_*`` settings; CLI flags override
them. The server talks to the REST API at ``--base-url`` and uses ``--token`` as
the bearer credential for the protected ``/fetch`` and ``/ask`` endpoints.
"""

from __future__ import annotations

import argparse
from dataclasses import replace

from app.mcp.config import load_mcp_config
from app.mcp.server import build_server


def main() -> None:
    defaults = load_mcp_config()
    parser = argparse.ArgumentParser(prog="app.mcp", description="Prism Earth MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default=defaults.transport,
        help="Transport to expose (default: %(default)s)",
    )
    parser.add_argument("--host", default=defaults.host, help="HTTP host (streamable-http)")
    parser.add_argument("--port", type=int, default=defaults.port, help="HTTP port")
    parser.add_argument("--base-url", default=defaults.base_url, help="REST API base URL")
    parser.add_argument("--token", default=defaults.token, help="Bearer token for fetch/ask")
    args = parser.parse_args()

    config = replace(
        defaults,
        transport=args.transport,
        host=args.host,
        port=args.port,
        base_url=args.base_url,
        token=args.token,
    )
    server = build_server(config)
    server.run(transport=config.transport)  # type: ignore[arg-type]


if __name__ == "__main__":
    main()
