from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import Principal
from app.ai_models.adapters import registry
from app.ai_models.exceptions import (
    AIModelConflict,
    AIModelNotFound,
    AIModelNotImplemented,
    AIModelUnknownType,
)
from app.ai_models.models import AIModel, AIModelConfig
from app.ai_models.utils import (
    apply_redaction,
    collect_redacted_paths,
    decrypt_config,
    encrypt_config,
    REDACTED,
    merge_partial_config,
)


class AIModelService:
    def __init__(self, db: Session, principal: Principal) -> None:
        self.db = db
        self.principal = principal
        self.settings = get_settings()

    # CRUD
    def create(self, payload: dict) -> dict:
        type_slug: str = payload["type"]
        connector = registry.get(type_slug)
        if connector is None:
            raise AIModelUnknownType(f"Unknown AI model type: {type_slug}")

        connector.validate_config(payload["config"])  # may raise

        model_id = str(uuid.uuid4())
        model = AIModel(
            id=model_id,
            tenant_id=self.principal.tenant_id,
            owner_id=self.principal.user_id,
            name=payload["name"].strip(),
            type=type_slug,
            category=payload["category"].strip(),
            description=(payload.get("description") or None),
            tags=payload.get("tags") or None,
            is_enabled=bool(payload.get("is_enabled", True)),
            created_by=self.principal.user_id,
            updated_by=self.principal.user_id,
        )

        redacted_config = connector.redact_config(payload["config"])
        encrypted = encrypt_config(payload["config"])  # store raw encrypted
        cfg = AIModelConfig(
            ai_model_id=model_id,
            config_encrypted=encrypted,
            config_schema_version=payload.get("config_schema_version"),
            redaction_map={"secret_paths": collect_redacted_paths(redacted_config)},
        )
        model.config = cfg

        self.db.add(model)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise AIModelConflict("An AI model with this name already exists in the tenant")
        self.db.refresh(model)
        return self._to_response_dict(model)

    def get(self, model_id: str) -> dict:
        model = self._get_owned(model_id)
        return self._to_response_dict(model)

    def list(self, *, type: Optional[str] = None, category: Optional[str] = None, enabled: Optional[bool] = None, limit: int = 20, offset: int = 0) -> tuple[list[dict], int]:
        stmt = select(AIModel).where(
            and_(
                AIModel.tenant_id == self.principal.tenant_id,
                AIModel.deleted_at.is_(None),
            )
        )
        if type:
            stmt = stmt.where(AIModel.type == type)
        if category:
            stmt = stmt.where(AIModel.category == category)
        if enabled is not None:
            stmt = stmt.where(AIModel.is_enabled == enabled)

        total = self.db.execute(stmt).scalars().unique().all()
        items = total[offset : offset + limit]
        return [self._to_response_dict(m) for m in items], len(total)

    def update(self, model_id: str, payload: dict) -> dict:
        model = self._get_owned(model_id)
        connector = registry.get(model.type)
        if connector is None:
            raise AIModelUnknownType(f"Unknown AI model type: {model.type}")

        if "name" in payload and payload["name"]:
            model.name = payload["name"].strip()
        if "description" in payload:
            model.description = payload["description"]
        if "tags" in payload:
            model.tags = payload["tags"]
        if "is_enabled" in payload and payload["is_enabled"] is not None:
            model.is_enabled = bool(payload["is_enabled"])
        model.updated_by = self.principal.user_id

        if "config" in payload and payload["config"] is not None:
            current = decrypt_config(model.config.config_encrypted)
            merged = merge_partial_config(current, payload["config"], model.config.redaction_map)
            connector.validate_config(merged)
            redacted = connector.redact_config(merged)
            model.config.config_encrypted = encrypt_config(merged)
            model.config.config_schema_version = payload.get("config_schema_version") or model.config.config_schema_version
            model.config.redaction_map = {"secret_paths": collect_redacted_paths(redacted)}

        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise AIModelConflict("An AI model with this name already exists in the tenant")
        self.db.refresh(model)
        return self._to_response_dict(model)

    def delete(self, model_id: str) -> None:
        model = self._get_owned(model_id)
        from datetime import datetime as _dt

        model.deleted_at = _dt.utcnow()
        self.db.commit()

    def set_enabled(self, model_id: str, enabled: bool) -> dict:
        model = self._get_owned(model_id)
        model.is_enabled = enabled
        model.updated_by = self.principal.user_id
        self.db.commit()
        self.db.refresh(model)
        return self._to_response_dict(model)

    # Types listing
    def list_types(self) -> list[dict]:
        items = registry.list()
        return [
            {
                "type": m.type_slug,
                "display_name": m.display_name,
                "category": m.category,
                "version": m.version,
                "json_schema": m.json_schema,
                "source": m.source,
            }
            for m in items
        ]

    # Test connection (non-billable by default)
    def test_connection(self, model_id: str, *, timeout_s: Optional[int] = None, smoke_inference: bool = False) -> dict:
        model = self._get_owned(model_id)
        connector = registry.get(model.type)
        if connector is None:
            raise AIModelNotImplemented("No connector implemented for this AI model type")

        ts = timeout_s or 10
        ts = min(ts, 30)
        config = decrypt_config(model.config.config_encrypted)
        result = connector.test_connection(config, timeout_s=ts, allow_smoke_inference=bool(smoke_inference))
        return result

    # Helpers
    def _get_owned(self, model_id: str) -> AIModel:
        stmt = select(AIModel).where(
            and_(
                AIModel.id == model_id,
                AIModel.tenant_id == self.principal.tenant_id,
                AIModel.deleted_at.is_(None),
            )
        )
        obj = self.db.execute(stmt).scalar_one_or_none()
        if obj is None:
            raise AIModelNotFound()
        return obj

    def _to_response_dict(self, obj: AIModel) -> dict:
        cfg_plain = decrypt_config(obj.config.config_encrypted)
        redacted = apply_redaction(cfg_plain, obj.config.redaction_map)
        return {
            "id": obj.id,
            "tenant_id": obj.tenant_id,
            "owner_id": obj.owner_id,
            "name": obj.name,
            "type": obj.type,
            "category": obj.category,
            "description": obj.description,
            "tags": obj.tags,
            "is_enabled": obj.is_enabled,
            "created_at": obj.created_at,
            "updated_at": obj.updated_at,
            "created_by": obj.created_by,
            "updated_by": obj.updated_by,
            "config": redacted,
            "config_schema_version": obj.config.config_schema_version,
        }



