from __future__ import annotations

from typing import Any, Optional


class AgentToolAdapter:
    kind: str
    provider: Optional[str] = None
    display_name: str = ""
    version: str = "1.0"

    def validate_config(self, config: dict) -> None:
        return None

    def validate_bindings(self, bindings: dict | None) -> None:
        return None

    def invoke(self, *, tool: dict, payload: dict, context: dict) -> Any:  # pragma: no cover - implemented by concrete adapters
        raise NotImplementedError


