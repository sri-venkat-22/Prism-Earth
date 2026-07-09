"""Terra MCP server (SRS §34).

Exposes the platform to AI clients via the Model Context Protocol. The server is
a thin client over the REST API (§34.2 workflow), so it inherits determinism,
provenance, and citations unchanged (§16.18).

Tools (SRS §34.1):

- ``terra_fetch`` — deterministic geospatial data.
- ``terra_ask``   — natural-language answer via Planner → Fetch →
  Synthesizer.
- ``terra_meta_fields`` / ``terra_meta_layers`` /
  ``terra_meta_presets`` — the public discovery catalog (SRS §13.6–13.8).

The ``mcp`` SDK is imported lazily (the litellm precedent) so importing this
module — and the rest of the app — never requires the SDK to be installed.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from app.mcp import tools
from app.mcp.client import TerraClient
from app.mcp.config import McpConfig, load_mcp_config

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

_INSTRUCTIONS = (
    "Terra provides deterministic, citation-backed geospatial intelligence "
    "for India (pilot region: Telangana). Every value carries its source, dataset "
    "version, retrieval time, and confidence; the platform never fabricates data. "
    "Use terra_meta_fields/layers/presets to discover what is available, "
    "terra_fetch for raw cited values at a coordinate, and terra_ask "
    "for a natural-language answer with an execution trace. Always surface the "
    "returned citations to the user."
)


def build_server(config: McpConfig | None = None) -> FastMCP:
    """Construct the FastMCP server with the Terra tools registered."""
    from mcp.server.fastmcp import FastMCP  # lazy: only needed to run the server

    config = config or load_mcp_config()
    client = TerraClient(config.base_url, token=config.token, timeout=config.timeout)

    @asynccontextmanager
    async def lifespan(_server: FastMCP) -> AsyncIterator[dict[str, Any]]:
        try:
            yield {}
        finally:
            await client.aclose()

    mcp = FastMCP(
        "terra",
        instructions=_INSTRUCTIONS,
        host=config.host,
        port=config.port,
        lifespan=lifespan,
    )

    @mcp.tool(
        name="terra_fetch",
        description=(
            "Retrieve deterministic geospatial field values at a WGS84 coordinate, "
            "each with source, dataset version, retrieval time, confidence, and "
            "citations. Provide either an explicit list of field names or a preset "
            "id (discover both via the meta tools). No AI is involved."
        ),
    )
    async def terra_fetch(
        lat: float,
        lng: float,
        fields: list[str] | None = None,
        preset: str | None = None,
    ) -> dict[str, Any]:
        return await tools.fetch_tool(client, lat=lat, lng=lng, fields=fields, preset=preset)

    @mcp.tool(
        name="terra_ask",
        description=(
            "Answer a natural-language question about a WGS84 coordinate using the "
            "Planner -> Fetch -> Synthesizer pipeline. Returns a cited answer, the "
            "citations, an execution trace, and per-field provenance. The answer is "
            "synthesized only from fetched values and never fabricates data."
        ),
    )
    async def terra_ask(lat: float, lng: float, question: str) -> dict[str, Any]:
        return await tools.ask_tool(client, lat=lat, lng=lng, question=question)

    @mcp.tool(
        name="terra_meta_fields",
        description=(
            "List the field catalog: every supported field with its layer, "
            "lifecycle, availability, unit, source, and supported presets. "
            "Optionally filter by layer, lifecycle, or availability. Public."
        ),
    )
    async def terra_meta_fields(
        layer: str | None = None,
        lifecycle: str | None = None,
        available: bool | None = None,
    ) -> dict[str, Any]:
        return await tools.meta_fields_tool(
            client, layer=layer, lifecycle=lifecycle, available=available
        )

    @mcp.tool(
        name="terra_meta_layers",
        description="List the domain layers (Terrain, Climate, ... ). Public.",
    )
    async def terra_meta_layers() -> dict[str, Any]:
        return await tools.meta_layers_tool(client)

    @mcp.tool(
        name="terra_meta_presets",
        description="List the predefined presets, each expanding to catalog fields. Public.",
    )
    async def terra_meta_presets() -> dict[str, Any]:
        return await tools.meta_presets_tool(client)

    return mcp
