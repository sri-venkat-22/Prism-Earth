"""MCP tool-logic tests (SRS §34.1, §16.18).

Drives the pure tool functions over a :class:`PrismClient` backed by
``httpx.MockTransport`` — no live server. Asserts each tool hits the right REST
endpoint, sends the bearer token only for the protected endpoints, and returns
the API JSON verbatim so citations + provenance reach the agent unchanged.
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.mcp import tools
from app.mcp.client import PrismApiError, PrismClient

_BASE = "http://api.test/api/v1"

_FETCH_RESPONSE = {
    "request_id": "REQ-1",
    "timestamp": "2026-07-02T00:00:00Z",
    "location": {"lat": 17.385, "lng": 78.486, "in_pilot_region": True},
    "fields": {"elevation": {"name": "elevation", "value": 542.16, "layer": "terrain"}},
    "provenance": {
        "elevation": {
            "field": "elevation",
            "dataset": "Copernicus DEM GLO-30",
            "source_url": "https://example.org/dem",
            "retrieved_at": "2026-07-02T00:00:00Z",
            "confidence": "high",
        }
    },
    "citations": [
        {
            "citation_id": "CIT-001",
            "dataset": "Copernicus DEM GLO-30",
            "retrieved_at": "2026-07-02T00:00:00Z",
            "field_names": ["elevation"],
        }
    ],
    "partial_failures": [],
    "summary": {
        "requested": 1,
        "resolved": 1,
        "null": 0,
        "datasets_used": ["Copernicus DEM GLO-30"],
    },
}

_ASK_RESPONSE = {
    "request_id": "REQ-2",
    "timestamp": "2026-07-02T00:00:00Z",
    "location": {"lat": 17.385, "lng": 78.486, "in_pilot_region": True},
    "answer": "The elevation here is about 542 m (Copernicus DEM GLO-30 [CIT-001]).",
    "citations": _FETCH_RESPONSE["citations"],
    "trace": {"planner": {}, "fetch": {}, "synthesizer": {}, "total_duration_ms": 1.0},
    "provenance": _FETCH_RESPONSE["provenance"],
}

_META_FIELDS = {"count": 1, "fields": [{"name": "elevation", "layer": "terrain"}]}


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    has_auth = "authorization" in request.headers
    if path.endswith("/fetch"):
        assert request.method == "POST"
        assert request.headers.get("authorization") == "Bearer test-token"
        assert json.loads(request.content)["lat"] == 17.385
        return httpx.Response(200, json=_FETCH_RESPONSE)
    if path.endswith("/ask"):
        assert request.headers.get("authorization") == "Bearer test-token"
        return httpx.Response(200, json=_ASK_RESPONSE)
    if path.endswith("/meta/fields"):
        assert not has_auth  # public discovery — no credential sent
        return httpx.Response(200, json=_META_FIELDS)
    if path.endswith("/meta/layers"):
        return httpx.Response(200, json={"count": 9, "layers": []})
    if path.endswith("/meta/presets"):
        return httpx.Response(200, json={"count": 18, "presets": []})
    return httpx.Response(404, json={"detail": "not found"})


def _client(token: str | None = "test-token") -> PrismClient:
    transport = httpx.MockTransport(_handler)
    return PrismClient(_BASE, token=token, client=httpx.AsyncClient(transport=transport))


async def test_fetch_tool_preserves_citations_and_provenance() -> None:
    client = _client()
    result = await tools.fetch_tool(client, lat=17.385, lng=78.486, fields=["elevation"])
    # Returned verbatim: provenance + citations intact (SRS §16.18).
    assert result["fields"]["elevation"]["value"] == 542.16
    assert result["citations"][0]["citation_id"] == "CIT-001"
    assert result["provenance"]["elevation"]["dataset"] == "Copernicus DEM GLO-30"


async def test_fetch_tool_sends_preset() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json=_FETCH_RESPONSE)

    client = PrismClient(
        _BASE, token="test-token", client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    await tools.fetch_tool(client, lat=17.385, lng=78.486, preset="terrain")
    assert captured == {"lat": 17.385, "lng": 78.486, "preset": "terrain"}


async def test_ask_tool_returns_cited_answer() -> None:
    client = _client()
    result = await tools.ask_tool(client, lat=17.385, lng=78.486, question="How high?")
    assert "CIT-001" in result["answer"]
    assert result["citations"]


async def test_meta_tools_are_unauthenticated() -> None:
    client = _client()
    fields = await tools.meta_fields_tool(client)
    assert fields["count"] == 1
    layers = await tools.meta_layers_tool(client)
    assert layers["count"] == 9
    presets = await tools.meta_presets_tool(client)
    assert presets["count"] == 18


async def test_client_raises_on_error_response() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"code": "AUTHENTICATION_ERROR"}})

    client = PrismClient(
        _BASE, token=None, client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(PrismApiError) as excinfo:
        await tools.fetch_tool(client, lat=1.0, lng=2.0, fields=["elevation"])
    assert excinfo.value.status_code == 401


def test_server_builds_and_registers_srs_tools() -> None:
    """The FastMCP server exposes the §34.1 tools (skipped if mcp is absent)."""
    import asyncio

    pytest.importorskip("mcp")
    from app.mcp.config import McpConfig
    from app.mcp.server import build_server

    server = build_server(
        McpConfig(
            base_url=_BASE,
            token=None,
            timeout=5,
            transport="stdio",
            host="127.0.0.1",
            port=8765,
        )
    )
    names = {t.name for t in asyncio.run(server.list_tools())}
    assert {"prism_earth_fetch", "prism_earth_ask"} <= names
    assert {
        "prism_earth_meta_fields",
        "prism_earth_meta_layers",
        "prism_earth_meta_presets",
    } <= names
