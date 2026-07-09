"""MCP tool logic (SRS §34.1).

Pure async functions over a :class:`TerraClient` — deliberately free of any
``mcp`` import so they can be unit-tested with ``httpx.MockTransport`` and reused
regardless of transport. Each returns the REST API's JSON **verbatim**, so the
``citations`` and ``provenance`` an AI agent needs (§16.18) are passed through
untouched.

The §34.1 tools are ``terra_fetch`` and ``terra_ask``; the ``meta_*``
tools expose the public discovery catalog (SRS §13.6–13.8) so an agent can learn
which fields/presets exist before calling fetch.
"""

from __future__ import annotations

from typing import Any

from app.mcp.client import TerraClient


async def fetch_tool(
    client: TerraClient,
    *,
    lat: float,
    lng: float,
    fields: list[str] | None = None,
    preset: str | None = None,
) -> dict[str, Any]:
    """Deterministic field retrieval with provenance + citations (SRS §13.9)."""
    body: dict[str, Any] = {"lat": lat, "lng": lng}
    if fields:
        body["fields"] = fields
    if preset:
        body["preset"] = preset
    return await client.post("/fetch", json=body, auth=True)


async def ask_tool(client: TerraClient, *, lat: float, lng: float, question: str) -> dict[str, Any]:
    """Natural-language answer with a cited execution trace (SRS §13.13)."""
    return await client.post("/ask", json={"lat": lat, "lng": lng, "question": question}, auth=True)


async def meta_fields_tool(
    client: TerraClient,
    *,
    layer: str | None = None,
    lifecycle: str | None = None,
    available: bool | None = None,
) -> dict[str, Any]:
    """The field catalog (SRS §13.6)."""
    params: dict[str, Any] = {}
    if layer is not None:
        params["layer"] = layer
    if lifecycle is not None:
        params["lifecycle"] = lifecycle
    if available is not None:
        params["available"] = available
    return await client.get("/meta/fields", params=params or None)


async def meta_layers_tool(client: TerraClient) -> dict[str, Any]:
    """The domain layers (SRS §13.7)."""
    return await client.get("/meta/layers")


async def meta_presets_tool(client: TerraClient) -> dict[str, Any]:
    """The predefined presets (SRS §13.8)."""
    return await client.get("/meta/presets")
