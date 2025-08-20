from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import Principal
from app.agent_tools.adapters import registry
from app.agent_tools.exceptions import (
    AgentToolAdapterNotFound,
    AgentToolBindingInvalid,
    AgentToolConfigInvalid,
    AgentToolConflict,
    AgentToolDisabled,
    AgentToolInvokeNotImplemented,
    AgentToolNotFound,
)
from app.agent_tools.models import AgentTool, AgentToolConfig
from app.datasets.models import Dataset
from app.ai_models.models import AIModel


class AgentToolService:
    def __init__(self, db: Session, principal: Principal) -> None:
        self.db = db
        self.principal = principal
        self.settings = get_settings()

    # CRUD
    def create(self, payload: dict) -> dict:
        kind: str = payload["kind"].strip()
        provider: Optional[str] = (payload.get("provider") or None)
        adapter = registry.get(kind, provider)
        if adapter is None:
            raise AgentToolAdapterNotFound(f"No adapter registered for kind={kind} provider={provider}")

        try:
            adapter.validate_config(payload.get("config") or {})
            adapter.validate_bindings((payload.get("bindings") or None))
            self._validate_bindings_semantics(kind, payload.get("bindings") or None)
        except AgentToolBindingInvalid:
            raise
        except Exception as ex:
            raise AgentToolConfigInvalid(str(ex))

        tool_id = str(uuid.uuid4())
        tool = AgentTool(
            id=tool_id,
            tenant_id=self.principal.tenant_id,
            owner_id=self.principal.user_id,
            name=payload["name"].strip(),
            kind=kind,
            provider=provider,
            description=(payload.get("description") or None),
            tags=payload.get("tags") or None,
            is_enabled=bool(payload.get("is_enabled", True)),
            bindings=self._normalize_bindings(payload.get("bindings") or None),
            created_by=self.principal.user_id,
            updated_by=self.principal.user_id,
        )
        cfg = AgentToolConfig(
            tool_id=tool_id,
            config_json=payload.get("config") or {},
            config_schema_version=payload.get("config_schema_version"),
        )
        tool.config = cfg

        self.db.add(tool)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise AgentToolConflict("A tool with this name already exists in the tenant")
        self.db.refresh(tool)
        return self._to_response_dict(tool)

    def get(self, tool_id: str) -> dict:
        obj = self._get_owned(tool_id)
        return self._to_response_dict(obj)

    def list(self, *, kind: Optional[str] = None, enabled: Optional[bool] = None, limit: int = 20, offset: int = 0) -> tuple[list[dict], int]:
        stmt = select(AgentTool).where(
            and_(
                AgentTool.tenant_id == self.principal.tenant_id,
                AgentTool.deleted_at.is_(None),
            )
        )
        if kind:
            stmt = stmt.where(AgentTool.kind == kind)
        if enabled is not None:
            stmt = stmt.where(AgentTool.is_enabled == enabled)

        total = self.db.execute(stmt).scalars().unique().all()
        items = total[offset : offset + limit]
        return [self._to_response_dict(m) for m in items], len(total)

    def update(self, tool_id: str, payload: dict) -> dict:
        obj = self._get_owned(tool_id)

        if "name" in payload and payload["name"]:
            obj.name = payload["name"].strip()
        if "description" in payload:
            obj.description = payload["description"]
        if "tags" in payload:
            obj.tags = payload["tags"]
        if "is_enabled" in payload and payload["is_enabled"] is not None:
            obj.is_enabled = bool(payload["is_enabled"])
        if "bindings" in payload:
            adapter = registry.get(obj.kind, obj.provider)
            if adapter is None:
                raise AgentToolAdapterNotFound(f"No adapter registered for kind={obj.kind} provider={obj.provider}")
            try:
                adapter.validate_bindings(payload.get("bindings") or None)
                self._validate_bindings_semantics(obj.kind, payload.get("bindings") or None)
            except AgentToolBindingInvalid:
                raise
            except Exception as ex:
                raise AgentToolConfigInvalid(str(ex))
            obj.bindings = self._normalize_bindings(payload.get("bindings") or None)
        obj.updated_by = self.principal.user_id

        if "config" in payload and payload["config"] is not None:
            adapter = registry.get(obj.kind, obj.provider)
            if adapter is None:
                raise AgentToolAdapterNotFound(f"No adapter registered for kind={obj.kind} provider={obj.provider}")
            adapter.validate_config(payload["config"])
            obj.config.config_json = payload["config"]
            obj.config.config_schema_version = payload.get("config_schema_version") or obj.config.config_schema_version

        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise AgentToolConflict("A tool with this name already exists in the tenant")
        self.db.refresh(obj)
        return self._to_response_dict(obj)

    def delete(self, tool_id: str) -> None:
        obj = self._get_owned(tool_id)
        from datetime import datetime as _dt

        obj.deleted_at = _dt.utcnow()
        self.db.commit()

    def set_enabled(self, tool_id: str, enabled: bool) -> dict:
        obj = self._get_owned(tool_id)
        obj.is_enabled = enabled
        obj.updated_by = self.principal.user_id
        self.db.commit()
        self.db.refresh(obj)
        return self._to_response_dict(obj)

    def list_kinds(self) -> list[dict]:
        return registry.list()

    # Invocation dispatch (no execution logic in this phase)
    def invoke(self, tool_id: str, payload: dict) -> dict:
        obj = self._get_owned(tool_id)
        if not obj.is_enabled:
            raise AgentToolDisabled()

        adapter = registry.get(obj.kind, obj.provider)
        if adapter is None:
            raise AgentToolAdapterNotFound(f"No adapter registered for kind={obj.kind} provider={obj.provider}")

        # Validate bindings prior to invoke
        adapter.validate_bindings(obj.bindings or None)

        context = {"db": self.db, "principal": self.principal, "settings": self.settings}
        result = adapter.invoke(tool=self._to_response_dict(obj), payload=payload, context=context)
        return result

    # Helpers
    def _get_owned(self, tool_id: str) -> AgentTool:
        stmt = select(AgentTool).where(
            and_(
                AgentTool.id == tool_id,
                AgentTool.tenant_id == self.principal.tenant_id,
                AgentTool.deleted_at.is_(None),
            )
        )
        obj = self.db.execute(stmt).scalar_one_or_none()
        if obj is None:
            raise AgentToolNotFound()
        return obj

    def _to_response_dict(self, obj: AgentTool) -> dict:
        return {
            "id": obj.id,
            "tenant_id": obj.tenant_id,
            "owner_id": obj.owner_id,
            "name": obj.name,
            "kind": obj.kind,
            "provider": obj.provider,
            "description": obj.description,
            "tags": obj.tags,
            "is_enabled": obj.is_enabled,
            "bindings": obj.bindings,
            "created_at": obj.created_at,
            "updated_at": obj.updated_at,
            "created_by": obj.created_by,
            "updated_by": obj.updated_by,
            "config": obj.config.config_json,
            "config_schema_version": obj.config.config_schema_version,
        }

    def _normalize_bindings(self, bindings: dict | None) -> dict | None:
        if not bindings:
            return None
        resources = []
        for r in bindings.get("resources", []):
            new_r = dict(r)
            if "id" in new_r:
                new_r["id"] = str(new_r["id"])
            resources.append(new_r)
        return {"resources": resources}

    def _validate_bindings_semantics(self, kind: str, bindings: dict | None) -> None:
        resources = (bindings or {}).get("resources", [])
        if kind == "sql.select":
            primary = next((r for r in resources if r.get("role") == "primary" and r.get("type") == "dataset"), None)
            if not primary:
                raise AgentToolBindingInvalid("sql.select requires a dataset binding with role 'primary'")
            self._ensure_dataset_category(primary["id"], required_category="sql")
        elif kind == "vector.similarity_search":
            idx = next((r for r in resources if r.get("role") == "vector_index" and r.get("type") == "dataset"), None)
            mdl = next((r for r in resources if r.get("role") == "embedding_model" and r.get("type") == "ai_model"), None)
            if not idx or not mdl:
                raise AgentToolBindingInvalid("vector.similarity_search requires 'vector_index' dataset and 'embedding_model' ai_model bindings")
            self._ensure_dataset_category(idx["id"], required_category="vector")
            self._ensure_ai_model_category(mdl["id"], required_category="embedding")
        else:
            # For unknown kinds at this phase, no semantic checks beyond adapter-level
            return

    def _ensure_dataset_category(self, dataset_id: str | uuid.UUID, *, required_category: str) -> None:
        dataset_id = str(dataset_id)
        stmt = select(Dataset).where(
            and_(
                Dataset.id == dataset_id,
                Dataset.tenant_id == self.principal.tenant_id,
                Dataset.deleted_at.is_(None),
            )
        )
        ds = self.db.execute(stmt).scalar_one_or_none()
        if ds is None:
            raise AgentToolBindingInvalid("Referenced dataset not found in tenant")
        if ds.category != required_category:
            raise AgentToolBindingInvalid(f"Dataset category mismatch; required '{required_category}'")

    def _ensure_ai_model_category(self, model_id: str | uuid.UUID, *, required_category: str) -> None:
        model_id = str(model_id)
        stmt = select(AIModel).where(
            and_(
                AIModel.id == model_id,
                AIModel.tenant_id == self.principal.tenant_id,
                AIModel.deleted_at.is_(None),
            )
        )
        mdl = self.db.execute(stmt).scalar_one_or_none()
        if mdl is None:
            raise AgentToolBindingInvalid("Referenced AI model not found in tenant")
        if mdl.category != required_category:
            raise AgentToolBindingInvalid(f"AI model category mismatch; required '{required_category}'")


