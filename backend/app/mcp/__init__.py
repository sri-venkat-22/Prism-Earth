"""Prism Earth MCP server package (SRS §34).

Exposes the platform to AI clients over the Model Context Protocol as a thin
client over the REST API. The FastMCP server (:func:`app.mcp.server.build_server`)
is built lazily so the ``mcp`` SDK is only required when actually running the
server — importing this package does not pull it in.
"""

from __future__ import annotations
