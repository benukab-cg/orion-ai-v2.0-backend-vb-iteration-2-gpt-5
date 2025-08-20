from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class ConnectorMetadata:
    type_slug: str
    display_name: str
    category: str  # "llm" | "embedding"
    version: str
    json_schema: dict
    source: str  # "builtin" | "plugin"


class AIModelConnector:
    """Abstract interface for AI Model connectors.

    Implementations should not perform billable inference in test_connection unless explicitly allowed.
    """

    meta: ConnectorMetadata

    def validate_config(self, config: dict) -> None:
        """Validate provider-specific configuration. Raise exceptions on failure."""
        raise NotImplementedError

    def redact_config(self, config: dict) -> dict:
        """Return a copy of config with secret fields replaced by redacted placeholders."""
        raise NotImplementedError

    def test_connection(self, config: dict, *, timeout_s: int = 10, allow_smoke_inference: bool = False) -> dict:
        """Short-lived connectivity/auth check. Avoid billable inference by default."""
        raise NotImplementedError

    def get_json_schema(self) -> dict:
        """Return JSON Schema describing the provider configuration for UI/validation."""
        return self.meta.json_schema

    def get_capabilities(self, config: dict) -> dict:
        """Return static/dynamic capability metadata where available.

        Example keys: models, max_input_tokens, max_output_tokens, embedding_dimensions, api_style.
        """
        return {}

    # Optional inference interfaces (implemented by specific categories)
    def embed_texts(self, config: dict, texts: list[str]) -> list[list[float]]:
        """Return embeddings for the given texts. Implemented by embedding model connectors.

        Default behavior is to raise NotImplementedError.
        """
        raise NotImplementedError



