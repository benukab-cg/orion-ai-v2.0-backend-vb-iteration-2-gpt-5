from __future__ import annotations

import importlib.metadata
from dataclasses import dataclass
from typing import Any, Callable, Optional


class DatasetConnectorProtocol:
    # Metadata
    type_slug: str
    display_name: str
    category: str  # sql | vector | blob
    version: str

    # Config and schema
    def validate_dataset_config(self, config: dict) -> None: ...
    def describe_schema(self, dataset: dict, limit_fields: int | None = None) -> dict: ...

    # Read-only operations
    # SQL
    def select(self, dataset: dict, query_spec: dict) -> dict: ...
    # Vector
    def query(self, dataset: dict, vector: list[float], top_k: int, filter: dict | None, options: dict | None = None) -> dict: ...
    def stats(self, dataset: dict) -> dict: ...
    # Blob
    def get(self, dataset: dict, range_spec: dict | None = None) -> dict: ...
    def presign_get(self, dataset: dict, ttl_s: int) -> dict: ...

    # RLS and limits
    def apply_rls(self, context: dict, operation: str, spec: dict) -> dict: ...
    def limits(self) -> dict: ...


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
        self._connectors: dict[str, DatasetConnectorProtocol] = {}

    def register(self, connector: DatasetConnectorProtocol, source: str = "builtin") -> None:
        self._connectors[connector.type_slug] = connector

    def get(self, type_slug: str) -> Optional[DatasetConnectorProtocol]:
        return self._connectors.get(type_slug)

    def list(self) -> list[ConnectorMeta]:
        items: list[ConnectorMeta] = []
        for c in self._connectors.values():
            try:
                schema = getattr(c, "get_json_schema", None)
                json_schema = schema() if callable(schema) else {}
            except Exception:
                json_schema = {}
            items.append(
                ConnectorMeta(
                    type_slug=c.type_slug,
                    display_name=c.display_name,
                    category=c.category,
                    version=c.version,
                    source="builtin",
                    json_schema=json_schema,
                )
            )
        return items

    def load_plugins(self) -> None:
        # Discover external dataset connectors via entry points group 'orion.datasets'
        try:
            eps = importlib.metadata.entry_points(group="orion.datasets")
        except Exception:
            eps = []  # type: ignore[assignment]
        for ep in eps:
            try:
                factory: Callable[[], DatasetConnectorProtocol] = ep.load()
                connector = factory()
                self._connectors[connector.type_slug] = connector
            except Exception:
                continue


registry = ConnectorRegistry()

try:
    from app.datasets.adapters.postgres import PostgresDatasetConnector

    registry.register(PostgresDatasetConnector())
except Exception:
    # Optional; if import fails (missing driver), skip registration
    pass


