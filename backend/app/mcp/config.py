"""MCP server configuration (SRS §34, §9).

Reads the ``PRISM_MCP_*`` settings into a small value object. Kept separate from
the FastMCP server so it can be constructed and overridden (CLI flags, tests)
without importing the ``mcp`` SDK.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings, get_settings


@dataclass(slots=True)
class McpConfig:
    base_url: str
    token: str | None
    timeout: float
    transport: str
    host: str
    port: int


def load_mcp_config(settings: Settings | None = None) -> McpConfig:
    settings = settings or get_settings()
    return McpConfig(
        base_url=settings.mcp_api_base_url,
        token=settings.mcp_api_token,
        timeout=settings.mcp_request_timeout,
        transport=settings.mcp_transport,
        host=settings.mcp_http_host,
        port=settings.mcp_http_port,
    )
