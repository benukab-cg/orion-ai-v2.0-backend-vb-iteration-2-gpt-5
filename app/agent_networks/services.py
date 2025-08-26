from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import Principal
from app.agent_networks.exceptions import AgentNetworkConflict, AgentNetworkInvalid, AgentNetworkNotFound
from app.agent_networks.models import (
    AgentNetwork,
    AgentNetworkNode,
    AgentNetworkEdge,
    AgentNetworkInterface,
)
from app.agent_networks.schemas import AgentNetworkSpec
from app.agents.models import Agent


class AgentNetworkService:
    def __init__(self, db: Session, principal: Principal) -> None:
        self.db = db
        self.principal = principal

    # CRUD & versioning
    def create(self, payload: dict) -> dict:
        self._validate_create_payload(payload)

        network_id = str(uuid.uuid4())
        obj = AgentNetwork(
            id=network_id,
            tenant_id=self.principal.tenant_id,
            owner_id=self.principal.user_id,
            name=payload["name"].strip(),
            slug=payload["slug"].strip(),
            type=payload["type"],
            description=payload.get("description") or None,
            tags=payload.get("tags") or None,
            version=payload["version"].strip(),
            status=payload.get("status") or "draft",
            spec_json=self._spec_to_dict(payload["spec"]),
            is_enabled=bool(payload.get("is_enabled", True)),
            created_by=self.principal.user_id,
            updated_by=self.principal.user_id,
        )

        # Persist nodes and edges for queryability
        spec = AgentNetworkSpec.model_validate(payload["spec"]) if not isinstance(payload["spec"], AgentNetworkSpec) else payload["spec"]
        for n in spec.nodes:
            self._ensure_node_reference_exists(n)
            node = AgentNetworkNode(
                id=str(uuid.uuid4()),
                network_id=network_id,
                node_key=n.node_key,
                agent_id=(str(n.agent_id) if n.agent_id else None),
                child_network_id=(str(n.child_network_id) if n.child_network_id else None),
                child_network_version=n.child_network_version,
                role=n.role,
                config_json=n.config,
            )
            self.db.add(node)
        for e in spec.edges:
            edge = AgentNetworkEdge(
                id=str(uuid.uuid4()),
                network_id=network_id,
                source_node_key=e.source_node_key,
                target_node_key=e.target_node_key,
                condition=e.condition,
            )
            self.db.add(edge)

        # Optional interface descriptor
        if spec.interface and isinstance(spec.interface, dict):
            iface = AgentNetworkInterface(
                network_id=network_id,
                version=obj.version,
                inputs_schema=spec.interface.get("inputs_schema") or {},
                outputs_schema=spec.interface.get("outputs_schema") or {},
                streaming=bool(spec.interface.get("streaming", False)),
                capabilities=spec.interface.get("capabilities") or None,
            )
            self.db.add(iface)

        try:
            self.db.add(obj)
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise AgentNetworkConflict("A network with this slug and version already exists in the tenant")
        self.db.refresh(obj)
        return self._to_response_dict(obj)

    def get(self, network_id: str) -> dict:
        obj = self._get_owned(network_id)
        return self._to_response_dict(obj)

    def list(self, *, type: Optional[str] = None, status: Optional[str] = None, enabled: Optional[bool] = None, limit: int = 20, offset: int = 0) -> tuple[list[dict], int]:
        stmt = select(AgentNetwork).where(
            and_(
                AgentNetwork.tenant_id == self.principal.tenant_id,
                AgentNetwork.deleted_at.is_(None),
            )
        )
        if type:
            stmt = stmt.where(AgentNetwork.type == type)
        if status:
            stmt = stmt.where(AgentNetwork.status == status)
        if enabled is not None:
            stmt = stmt.where(AgentNetwork.is_enabled == enabled)
        all_items = self.db.execute(stmt).scalars().unique().all()
        items = all_items[offset : offset + limit]
        return [self._to_response_dict(m) for m in items], len(all_items)

    def update(self, network_id: str, payload: dict) -> dict:
        obj = self._get_owned(network_id)

        if "name" in payload and payload["name"]:
            obj.name = payload["name"].strip()
        if "description" in payload:
            obj.description = payload["description"]
        if "tags" in payload:
            obj.tags = payload["tags"]
        if "status" in payload and payload["status"]:
            obj.status = payload["status"]
        if "is_enabled" in payload and payload["is_enabled"] is not None:
            obj.is_enabled = bool(payload["is_enabled"])

        if "spec" in payload and payload["spec"] is not None:
            spec = AgentNetworkSpec.model_validate(payload["spec"]) if not isinstance(payload["spec"], AgentNetworkSpec) else payload["spec"]
            # Basic validation: references exist; defer DAG checks to validate()
            for n in spec.nodes:
                self._ensure_node_reference_exists(n)
            obj.spec_json = self._spec_to_dict(spec)

        obj.updated_by = self.principal.user_id
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise AgentNetworkConflict("Update caused a conflict")
        self.db.refresh(obj)
        return self._to_response_dict(obj)

    def delete(self, network_id: str) -> None:
        obj = self._get_owned(network_id)
        from datetime import datetime as _dt

        obj.deleted_at = _dt.utcnow()
        self.db.commit()

    # Validation
    def validate(self, network_id: str) -> dict:
        obj = self._get_owned(network_id)
        spec = AgentNetworkSpec.model_validate(obj.spec_json)
        # Node keys unique enforced by DB; validate edges reference existing nodes
        node_keys = {n.node_key for n in spec.nodes}
        for e in spec.edges:
            if e.source_node_key not in node_keys or e.target_node_key not in node_keys:
                raise AgentNetworkInvalid("Edge references unknown node key")
        # Acyclic check only for non-swarm; swarm may include cycles due to handoffs
        if spec.type != "swarm":
            self._assert_acyclic(spec)
        # Ensure node references exist
        for n in spec.nodes:
            self._ensure_node_reference_exists(n)

        if spec.type == "swarm":
            self._validate_swarm_spec(spec)
        return {"status": "ok"}

    # Execution stubs
    def invoke(self, network_id: str, payload: dict) -> dict:
        obj = self._get_owned(network_id)
        if not obj.is_enabled:
            raise AgentNetworkInvalid("Network is disabled")
        spec = AgentNetworkSpec.model_validate(obj.spec_json)
        if spec.type == "standalone":
            from app.agent_networks.runtime.standalone import invoke_standalone
            return invoke_standalone(self.db, self.principal, spec, payload)
        elif spec.type == "swarm":
            from app.agent_networks.runtime.swarm import invoke_swarm
            return invoke_swarm(self.db, self.principal, spec, payload)
        else:
            raise AgentNetworkInvalid("Network type not supported in this iteration")

    # Helpers
    def _get_owned(self, network_id: str) -> AgentNetwork:
        stmt = select(AgentNetwork).where(
            and_(
                AgentNetwork.id == network_id,
                AgentNetwork.tenant_id == self.principal.tenant_id,
                AgentNetwork.deleted_at.is_(None),
            )
        )
        obj = self.db.execute(stmt).scalar_one_or_none()
        if obj is None:
            raise AgentNetworkNotFound()
        return obj

    def _to_response_dict(self, obj: AgentNetwork) -> dict:
        # Ensure spec is JSON-serializable (UUIDs -> strings)
        try:
            spec_json_safe = AgentNetworkSpec.model_validate(obj.spec_json).model_dump(mode="json")
        except Exception:
            spec_json_safe = obj.spec_json
        return {
            "id": obj.id,
            "tenant_id": obj.tenant_id,
            "owner_id": obj.owner_id,
            "name": obj.name,
            "slug": obj.slug,
            "type": obj.type,
            "description": obj.description,
            "tags": obj.tags,
            "version": obj.version,
            "status": obj.status,
            "is_enabled": obj.is_enabled,
            "created_at": obj.created_at.isoformat(),
            "updated_at": obj.updated_at.isoformat(),
            "spec": spec_json_safe,
        }

    def _validate_create_payload(self, payload: dict) -> None:
        spec = payload.get("spec")
        if spec is None:
            raise AgentNetworkInvalid("spec is required")
        spec_obj = AgentNetworkSpec.model_validate(spec) if not isinstance(spec, AgentNetworkSpec) else spec
        # Basic reference checks
        for n in spec_obj.nodes:
            self._ensure_node_reference_exists(n)

    def _spec_to_dict(self, spec: AgentNetworkSpec | dict) -> dict:
        if isinstance(spec, AgentNetworkSpec):
            return spec.model_dump(mode="json")
        # If it's already a dict (from request body), coerce through Pydantic for safety
        try:
            return AgentNetworkSpec.model_validate(spec).model_dump(mode="json")
        except Exception:
            return spec

    def _ensure_node_reference_exists(self, node) -> None:
        if node.agent_id:
            stmt = select(Agent).where(
                and_(
                    Agent.id == str(node.agent_id),
                    Agent.tenant_id == self.principal.tenant_id,
                    Agent.deleted_at.is_(None),
                )
            )
            if self.db.execute(stmt).scalar_one_or_none() is None:
                raise AgentNetworkInvalid(f"Referenced agent not found: {node.agent_id}")
        if node.child_network_id:
            stmt = select(AgentNetwork).where(
                and_(
                    AgentNetwork.id == str(node.child_network_id),
                    AgentNetwork.tenant_id == self.principal.tenant_id,
                    AgentNetwork.deleted_at.is_(None),
                )
            )
            if self.db.execute(stmt).scalar_one_or_none() is None:
                raise AgentNetworkInvalid(f"Referenced child network not found: {node.child_network_id}")
        if bool(node.agent_id) == bool(node.child_network_id):
            # Exactly one of agent or child network must be set
            raise AgentNetworkInvalid("Node must reference exactly one of agent_id or child_network_id")

    def _assert_acyclic(self, spec: AgentNetworkSpec) -> None:
        graph: dict[str, list[str]] = {}
        for n in spec.nodes:
            graph[n.node_key] = []
        for e in spec.edges:
            graph.setdefault(e.source_node_key, []).append(e.target_node_key)

        visited: dict[str, int] = {}

        def dfs(node: str) -> None:
            state = visited.get(node, 0)
            if state == 1:
                raise AgentNetworkInvalid("Cycle detected in network edges")
            if state == 2:
                return
            visited[node] = 1
            for nxt in graph.get(node, []):
                dfs(nxt)
            visited[node] = 2

        for key in graph.keys():
            if visited.get(key, 0) == 0:
                dfs(key)

    # Swarm helpers
    def _validate_swarm_spec(self, spec: AgentNetworkSpec) -> None:
        # Require agents only (no child networks in first iteration)
        for n in spec.nodes:
            if not n.agent_id or n.child_network_id:
                raise AgentNetworkInvalid("Swarm nodes must reference agents only in this iteration")
        # Optional default_active_agent must match a node_key or name
        cfg = spec.swarm or {}
        default_active = (cfg.get("default_active_agent") or "").strip()
        if default_active:
            names = {n.node_key for n in spec.nodes}
            if default_active not in names:
                raise AgentNetworkInvalid("default_active_agent must match a node_key")
        # Handoff policy: allow_all or edges
        policy = (cfg.get("handoff_policy") or "edges").strip()
        if policy not in ("edges", "allow_all"):
            raise AgentNetworkInvalid("handoff_policy must be 'edges' or 'allow_all'")


    # (no agent/LLM helpers here; delegated to app/agents)


