from __future__ import annotations

from .base import AIModelConnector
from .registry import Registry
from .openai_gpt import OpenAIConnector
from .openai_embeddings import OpenAIEmbeddingsConnector

# Public registry instance for the module
registry = Registry()

__all__ = [
    "AIModelConnector",
    "registry",
]

# Register builtin connectors
try:
    registry.register(OpenAIConnector())
    registry.register(OpenAIEmbeddingsConnector())
except Exception:
    # Do not fail module import if connector init raises
    pass


