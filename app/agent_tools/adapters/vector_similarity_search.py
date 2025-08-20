from __future__ import annotations

from typing import Any, Optional

from app.agent_tools.adapters import registry
from app.agent_tools.adapters.base import AgentToolAdapter
from app.agent_tools.exceptions import AgentToolBindingInvalid, AgentToolConfigInvalid, AgentToolAdapterNotFound
from app.datasets.services import DatasetService
from app.ai_models.models import AIModel
from app.ai_models.utils import decrypt_config
from app.ai_models.adapters import registry as ai_model_registry


class VectorSimilaritySearchAdapter(AgentToolAdapter):
    kind = "vector.similarity_search"
    display_name = "Vector Similarity Search Tool"

    def validate_bindings(self, bindings: dict | None) -> None:
        resources = (bindings or {}).get("resources", [])
        idx = next((r for r in resources if r.get("role") == "vector_index" and r.get("type") == "dataset"), None)
        model = next((r for r in resources if r.get("role") == "embedding_model" and r.get("type") == "ai_model"), None)
        if not idx or not model:
            raise AgentToolBindingInvalid("vector.similarity_search requires bindings for dataset 'vector_index' and ai_model 'embedding_model'")

    def invoke(self, *, tool: dict, payload: dict, context: dict) -> Any:
        resources = (tool.get("bindings") or {}).get("resources", [])
        ds_binding = next(r for r in resources if r.get("role") == "vector_index" and r.get("type") == "dataset")
        model_binding = next(r for r in resources if r.get("role") == "embedding_model" and r.get("type") == "ai_model")

        config = tool.get("config") or {}
        top_k = int(payload.get("top_k") or config.get("top_k", 10))
        top_k = max(1, min(top_k, 1000))
        include_metadata = bool(payload.get("include_metadata") if payload.get("include_metadata") is not None else config.get("include_metadata", True))
        include_values = bool(payload.get("include_values") if payload.get("include_values") is not None else config.get("include_values", False))
        namespace = payload.get("namespace") or config.get("namespace")
        vector = payload.get("vector")
        text = payload.get("text")
        if vector is None and not text:
            raise AgentToolConfigInvalid("Either 'vector' or 'text' must be provided")

        # Validate filter keys if allowlist provided
        filter_obj = payload.get("filter")
        allowed_fields = set(config.get("allowed_metadata_fields") or [])
        if filter_obj and allowed_fields:
            for key in list(filter_obj.keys()):
                if key not in allowed_fields:
                    raise AgentToolConfigInvalid(f"Metadata filter key not allowed: {key}")

        # If text provided, embed using the bound embedding model
        if vector is None and isinstance(text, str):
            max_chars = int(config.get("embed_text_max_chars", 8000))
            text_to_embed = text.strip()[:max_chars]
            vector = self._embed_via_ai_model(context, model_binding["id"], text_to_embed)

        # Delegate to dataset vector query
        ds_service = DatasetService(context["db"], context["principal"])
        spec = {
            "vector": vector,
            "top_k": top_k,
            "filter": filter_obj,
            "include_values": include_values,
            "include_metadata": include_metadata,
            "namespace": namespace,
        }
        return ds_service.vector_query(ds_binding["id"], spec)

    def _embed_via_ai_model(self, context: dict, model_id: str, text: str) -> list[float]:
        # Load model
        db = context["db"]
        principal = context["principal"]
        model: Optional[AIModel] = (
            db.query(AIModel)
            .filter(AIModel.id == model_id, AIModel.tenant_id == principal.tenant_id, AIModel.deleted_at.is_(None))
            .one_or_none()
        )
        if model is None:
            raise AgentToolBindingInvalid("Referenced AI model not found in tenant")
        if not model.is_enabled:
            raise AgentToolBindingInvalid("Referenced AI model is disabled")
        if model.category != "embedding":
            raise AgentToolBindingInvalid("AI model category must be 'embedding'")

        cfg = decrypt_config(model.config.config_encrypted)
        connector = ai_model_registry.get(model.type)
        if connector is None:
            raise AgentToolAdapterNotFound("Embedding adapter not implemented for model type")
        vectors = connector.embed_texts(cfg, [text])
        if not vectors or not isinstance(vectors[0], list):
            raise AgentToolConfigInvalid("Embedding response malformed")
        return vectors[0]


registry.register(VectorSimilaritySearchAdapter.kind, VectorSimilaritySearchAdapter())


