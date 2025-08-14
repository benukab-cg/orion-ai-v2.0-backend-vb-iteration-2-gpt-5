from __future__ import annotations

from typing import Any
import builtins as _builtins

from app.core.config import get_settings

try:  # pragma: no cover - optional dependency import
    from pinecone import Pinecone  # type: ignore
except Exception:
    Pinecone = None  # type: ignore[assignment]

# Fallback generic exception type; we will catch broadly
PineconeApiException = Exception  # type: ignore[assignment]


class PineconeDatasetConnector:
    type_slug = "vector.pinecone"
    display_name = "Pinecone Dataset"
    category = "vector"
    version = "1.0.0"

    def __init__(self) -> None:
        self.settings = get_settings()

    # Config validation at dataset level
    def validate_dataset_config(self, config: dict) -> None:
        index = config.get("index")
        if not index or not isinstance(index, str):
            raise ValueError("'index' is required and must be a string")
        ns = config.get("namespace")
        if ns is not None and not isinstance(ns, str):
            raise ValueError("'namespace' must be a string when provided")

    def describe_schema(self, dataset: dict, limit_fields: int | None = None) -> dict:
        pc = self._client(dataset)
        cfg = dataset["config"]
        index_name = cfg["index"]
        try:
            desc = pc.describe_index(index_name)
        except Exception:
            raise ValueError("Index not found")
        stats = self.stats(dataset)
        return {"dimension": getattr(desc, "dimension", None) or desc.get("dimension"), "namespaces": list((stats.get("namespaces") or {}).keys())}

    def query(self, dataset: dict, vector: list[float], top_k: int, filter: dict | None, options: dict | None = None) -> dict:
        if not isinstance(vector, list) or not vector:
            raise ValueError("'vector' must be a non-empty list of floats")
        top_k = max(1, min(int(top_k or 10), 1000))

        cfg = dataset["config"]
        ns = (options or {}).get("namespace") or cfg.get("namespace")
        include_values = bool((options or {}).get("include_values", False))
        include_metadata = bool((options or {}).get("include_metadata", True))

        pc = self._client(dataset)
        index = pc.Index(cfg["index"])  # host auto-resolved by SDK
        try:
            res = index.query(
                vector=vector,
                top_k=top_k,
                filter=filter,
                namespace=ns,
                include_values=include_values,
                include_metadata=include_metadata,
            )
        except Exception as e:
            # Map common not found
            msg = str(e)
            if "not found" in msg.lower():
                raise ValueError("Index not found")
            raise ValueError(f"Pinecone query failed: {msg}")
        # res.matches is list of Match objects; coerce to plain dicts
        matches: list[dict] = []
        for m in (getattr(res, "matches", None) or []):
            d = None
            if hasattr(m, "model_dump") and callable(getattr(m, "model_dump")):
                try:
                    d = m.model_dump()
                except Exception:
                    d = None
            if d is None:
                try:
                    d = _builtins.dict(m)
                except Exception:
                    try:
                        d = getattr(m, "to_dict")()  # type: ignore[call-arg]
                    except Exception:
                        d = {k: getattr(m, k) for k in dir(m) if not k.startswith("_")}
            matches.append(d)
        ns_out = getattr(res, "namespace", None)
        if ns_out is None:
            ns_out = ns
        return {"matches": matches, "namespace": ns_out}

    def stats(self, dataset: dict) -> dict:
        cfg = dataset["config"]
        pc = self._client(dataset)
        index = pc.Index(cfg["index"])  # host auto-resolved
        try:
            data = index.describe_index_stats()
        except Exception:
            raise ValueError("Index not found")
        # data is dict-like { namespaces: {...}, total_vector_count: int }
        # Normalize to plain dict
        if isinstance(data, dict):
            return data
        if hasattr(data, "model_dump") and callable(getattr(data, "model_dump")):
            try:
                return data.model_dump()
            except Exception:
                pass
        if hasattr(data, "to_dict") and callable(getattr(data, "to_dict")):
            try:
                return data.to_dict()
            except Exception:
                pass
        try:
            return _builtins.dict(data)
        except Exception:
            # Last resort reflective extraction
            return {k: getattr(data, k) for k in dir(data) if not k.startswith("_")}

    def get(self, dataset: dict, range_spec: dict | None = None) -> dict:
        raise NotImplementedError("Blob get not supported for Pinecone connector")

    def presign_get(self, dataset: dict, ttl_s: int) -> dict:
        raise NotImplementedError("Blob presign not supported for Pinecone connector")

    def apply_rls(self, context: dict, operation: str, spec: dict) -> dict:
        return spec

    def limits(self) -> dict:
        return {"default_limit": 10, "max_limit": 1000}

    # Helpers
    def _client(self, dataset: dict):
        if Pinecone is None:
            raise ValueError("Pinecone SDK not installed")
        ds_cfg = dataset["datasource"]["config"]
        api_key = ds_cfg.get("api_key")
        if not api_key:
            raise ValueError("Missing Pinecone api_key in datasource config")
        return Pinecone(api_key=api_key)


