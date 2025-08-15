from __future__ import annotations

from importlib.metadata import entry_points
from typing import Dict, Iterable, List, Optional

from .base import AIModelConnector, ConnectorMetadata


class Registry:
    """Registry of AI Model connectors (builtin + plugins).

    Initially empty for core; providers are added by plugin packages via entry points.
    """

    def __init__(self) -> None:
        self._connectors: Dict[str, AIModelConnector] = {}
        self._loaded_plugins: bool = False

    def register(self, connector: AIModelConnector) -> None:
        slug = connector.meta.type_slug
        self._connectors[slug] = connector

    def get(self, type_slug: str) -> Optional[AIModelConnector]:
        self._ensure_plugins_loaded()
        return self._connectors.get(type_slug)

    def list(self) -> List[ConnectorMetadata]:
        self._ensure_plugins_loaded()
        return [c.meta for c in self._connectors.values()]

    def _ensure_plugins_loaded(self) -> None:
        if self._loaded_plugins:
            return
        # Load entry points once
        try:
            eps = entry_points(group="orion.ai_models")
        except Exception:
            eps = []  # type: ignore[assignment]
        for ep in eps:  # type: ignore[assignment]
            try:
                connector: AIModelConnector = ep.load()()  # entry point returns connector class
                self.register(connector)
            except Exception:
                # Swallow to avoid breaking core if a plugin is broken
                continue
        self._loaded_plugins = True



