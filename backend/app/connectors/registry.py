"""The Connector Registry (SRS §18.10, §15.9).

Maintains the mapping between catalog fields and the connector that owns each,
and the connector instances themselves. The Fetch Engine consults the registry
before every execution (SRS §18.10): routing is **catalog-driven** — a field's
owning connector is resolved through its layer (SRS §11.5), never hardcoded — so
new connectors integrate by registering an instance whose ``name`` matches the
layer's connector key, with no change to the orchestrator (SRS §18.14).

A deployment need not register every connector: in Phase 3 only Terrain and
Administrative are wired. Fields whose owning connector is not registered are
reported by :meth:`route` as *unrouted* so the orchestrator can surface them as
partial failures rather than crashing (SRS §15.16).
"""

from __future__ import annotations

from app.connectors.base import BaseConnector, ConnectorHealth
from app.core.logging import get_logger
from app.metadata.catalog import Catalog

logger = get_logger(__name__)


class ConnectorRegistry:
    """Catalog-driven field → connector routing (SRS §18.10)."""

    def __init__(self, catalog: Catalog, connectors: list[BaseConnector]) -> None:
        self._catalog = catalog
        self._by_name: dict[str, BaseConnector] = {}
        for connector in connectors:
            self._by_name[connector.name] = connector

    # --- Discovery --------------------------------------------------------- #
    def connectors(self) -> list[BaseConnector]:
        return list(self._by_name.values())

    def has(self, name: str) -> bool:
        return name in self._by_name

    def get(self, name: str) -> BaseConnector | None:
        return self._by_name.get(name)

    def connector_key_for_field(self, field_name: str) -> str:
        """The connector key that owns ``field_name`` (via its layer, SRS §11.5)."""
        return self._catalog.connector_for_field(field_name)

    def connector_for_field(self, field_name: str) -> BaseConnector | None:
        """The registered connector instance owning ``field_name``, if any."""
        return self._by_name.get(self.connector_key_for_field(field_name))

    # --- Routing ----------------------------------------------------------- #
    def route(self, fields: list[str]) -> tuple[dict[BaseConnector, list[str]], dict[str, str]]:
        """Group ``fields`` by owning connector (SRS §18.10).

        Returns ``(grouped, unrouted)`` where ``grouped`` maps each registered
        connector to its assigned fields (input order preserved) and ``unrouted``
        maps each field whose owning connector is *not* registered to that
        connector key. The orchestrator turns unrouted fields into partial
        failures (SRS §15.16).
        """
        grouped: dict[BaseConnector, list[str]] = {}
        unrouted: dict[str, str] = {}
        for field in fields:
            key = self.connector_key_for_field(field)
            connector = self._by_name.get(key)
            if connector is None:
                unrouted[field] = key
                continue
            grouped.setdefault(connector, []).append(field)
        return grouped, unrouted

    # --- Lifecycle (SRS §18.2, §18.12) ------------------------------------- #
    async def initialize_all(self) -> None:
        for connector in self._by_name.values():
            await connector.initialize()
        logger.info("connector_registry.initialized", connectors=list(self._by_name))

    async def shutdown_all(self) -> None:
        for connector in self._by_name.values():
            await connector.shutdown()

    async def health_all(self) -> list[ConnectorHealth]:
        return [await connector.health() for connector in self._by_name.values()]
