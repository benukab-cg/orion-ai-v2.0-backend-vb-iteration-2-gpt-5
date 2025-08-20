from __future__ import annotations

from .base import AgentToolAdapter


class Registry:
    def __init__(self) -> None:
        self._adapters: dict[tuple[str, str | None], AgentToolAdapter] = {}

    def register(self, kind: str, adapter: AgentToolAdapter, provider: str | None = None) -> None:
        self._adapters[(kind, provider)] = adapter

    def get(self, kind: str, provider: str | None = None) -> AgentToolAdapter | None:
        return self._adapters.get((kind, provider)) or self._adapters.get((kind, None))

    def list(self) -> list[dict]:
        return [
            {"kind": k[0], "provider": k[1], "adapter": type(v).__name__}
            for k, v in self._adapters.items()
        ]


registry = Registry()


