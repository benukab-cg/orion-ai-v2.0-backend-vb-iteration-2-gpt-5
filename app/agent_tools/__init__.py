from __future__ import annotations

# Ensure built-in adapters register on import
from .adapters import registry as _registry  # noqa: F401
from .adapters import sql_select as _sql  # noqa: F401
from .adapters import vector_similarity_search as _vec  # noqa: F401


