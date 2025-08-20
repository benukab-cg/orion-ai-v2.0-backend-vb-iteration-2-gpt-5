from __future__ import annotations

from app.agent_tools.adapters import registry
from app.agent_tools.adapters.base import AgentToolAdapter
from app.agent_tools.exceptions import AgentToolBindingInvalid, AgentToolInvokeNotImplemented


class VectorSimilaritySearchAdapter(AgentToolAdapter):
    kind = "vector.similarity_search"
    display_name = "Vector Similarity Search Tool"

    def validate_bindings(self, bindings: dict | None) -> None:
        resources = (bindings or {}).get("resources", [])
        idx = next((r for r in resources if r.get("role") == "vector_index" and r.get("type") == "dataset"), None)
        model = next((r for r in resources if r.get("role") == "embedding_model" and r.get("type") == "ai_model"), None)
        if not idx or not model:
            raise AgentToolBindingInvalid("vector.similarity_search requires bindings for dataset 'vector_index' and ai_model 'embedding_model'")

    def invoke(self, *, tool: dict, payload: dict, context: dict):  # no execution in this phase
        raise AgentToolInvokeNotImplemented("Execution not implemented for vector.similarity_search in this phase")


registry.register(VectorSimilaritySearchAdapter.kind, VectorSimilaritySearchAdapter())


