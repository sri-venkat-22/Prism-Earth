"""HTTP client for the Terra REST API (SRS §34.2, §11.2).

The MCP server does not touch the platform internals — it consumes the same
public REST API as the browser and any other integration (§11.2 API-first). This
thin ``httpx`` wrapper adds the bearer token (for the protected ``/fetch`` and
``/ask`` endpoints) and returns the API's JSON verbatim, so provenance and
citations are preserved end-to-end (§16.18).
"""

from __future__ import annotations

from typing import Any

import httpx


class TerraApiError(RuntimeError):
    """A non-2xx response from the REST API, surfaced to the MCP tool caller."""

    def __init__(self, status_code: int, body: Any) -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(f"Terra API returned HTTP {status_code}: {body}")


class TerraClient:
    """Async client over the Terra REST API."""

    def __init__(
        self,
        base_url: str,
        *,
        token: str | None = None,
        timeout: float = 60.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout
        # An injected client (e.g. with httpx.MockTransport) is used as-is; this
        # is how the tools are unit-tested without a live server.
        self._client = client
        self._owns_client = client is None

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            # Full URLs are built explicitly in ``_request`` (see below), so no
            # ``base_url`` is set here — httpx would otherwise drop the API path
            # prefix when joining a leading-slash request path.
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        auth: bool = False,
    ) -> dict[str, Any]:
        headers: dict[str, str] = {}
        if auth and self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        client = self._ensure_client()
        url = f"{self._base_url}{path}"
        response = await client.request(method, url, json=json, params=params, headers=headers)
        try:
            payload = response.json()
        except ValueError:
            payload = {"detail": response.text}
        if response.status_code >= 400:
            raise TerraApiError(response.status_code, payload)
        assert isinstance(payload, dict)  # noqa: S101 - narrows the decoded JSON type
        return payload

    async def get(
        self, path: str, *, params: dict[str, Any] | None = None, auth: bool = False
    ) -> dict[str, Any]:
        return await self._request("GET", path, params=params, auth=auth)

    async def post(
        self, path: str, *, json: dict[str, Any] | None = None, auth: bool = False
    ) -> dict[str, Any]:
        return await self._request("POST", path, json=json, auth=auth)
