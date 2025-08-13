from __future__ import annotations

import importlib.metadata
from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional


class ConnectorProtocol:
    # Metadata
    type_slug: str
    display_name: str
    category: str
    version: str

    # Core methods
    def validate_config(self, config: dict) -> None: ...
    def redact_config(self, config: dict) -> dict: ...
    def test_connection(self, config: dict, timeout_s: int = 10) -> dict: ...
    def get_json_schema(self) -> dict: ...


@dataclass(frozen=True)
class ConnectorMeta:
    type_slug: str
    display_name: str
    category: str
    version: str
    source: str  # builtin | plugin
    json_schema: dict


class ConnectorRegistry:
    def __init__(self) -> None:
        self._connectors: dict[str, ConnectorProtocol] = {}

    def register(self, connector: ConnectorProtocol, source: str = "builtin") -> None:
        self._connectors[connector.type_slug] = connector

    def get(self, type_slug: str) -> Optional[ConnectorProtocol]:
        return self._connectors.get(type_slug)

    def list(self) -> list[ConnectorMeta]:
        items: list[ConnectorMeta] = []
        for c in self._connectors.values():
            items.append(
                ConnectorMeta(
                    type_slug=c.type_slug,
                    display_name=c.display_name,
                    category=c.category,
                    version=c.version,
                    source="builtin",  # core stage: all would be builtin if present
                    json_schema=c.get_json_schema(),
                )
            )
        return items

    def load_plugins(self) -> None:
        # Discover external connectors via entry points group 'orion.datasources'
        try:
            eps = importlib.metadata.entry_points(group="orion.datasources")
        except Exception:
            eps = []  # type: ignore[assignment]
        for ep in eps:
            try:
                factory: Callable[[], ConnectorProtocol] = ep.load()
                connector = factory()
                self._connectors[connector.type_slug] = connector
            except Exception:
                # Silently skip bad plugins at core stage; logging can be added later
                continue


registry = ConnectorRegistry()

try:
    from app.datasources.adapters.postgres import PostgresConnector

    registry.register(PostgresConnector())
except Exception:
    # Postgres is optional; if import fails, skip built-in registration
    pass


