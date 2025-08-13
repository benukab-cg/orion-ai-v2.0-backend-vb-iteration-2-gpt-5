from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import Principal
from app.datasources.adapters import registry
from app.datasources.exceptions import (
    DataSourceConflict,
    DataSourceNotFound,
    DataSourceNotImplemented,
    DataSourceUnknownType,
    DataSourceValidationError,
)
from app.datasources.models import DataSource, DataSourceConfig
from app.datasources.utils import (
    REDACTED,
    apply_redaction,
    decrypt_config,
    encrypt_config,
    merge_partial_config,
)


class DataSourceService:
    def __init__(self, db: Session, principal: Principal) -> None:
        self.db = db
        self.principal = principal
        self.settings = get_settings()

    # CRUD
    def create(self, payload: dict) -> dict:
        type_slug: str = payload["type"]
        connector = registry.get(type_slug)
        if connector is None:
            raise DataSourceUnknownType(f"Unknown datasource type: {type_slug}")

        connector.validate_config(payload["config"])  # may raise its own exception or return None

        ds_id = str(uuid.uuid4())
        data_source = DataSource(
            id=ds_id,
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

        # Secrets and config
        redacted_config = connector.redact_config(payload["config"])  # should mark secrets with REDACTED
        encrypted = encrypt_config(payload["config"])  # store raw encrypted
        config = DataSourceConfig(
            data_source_id=ds_id,
            config_encrypted=encrypted,
            config_schema_version=payload.get("config_schema_version"),
            redaction_map={"secret_paths": _collect_redacted_paths(redacted_config)},
        )
        data_source.config = config

        self.db.add(data_source)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise DataSourceConflict("A datasource with this name already exists in the tenant")
        self.db.refresh(data_source)

        return self._to_response_dict(data_source)

    def get(self, ds_id: str) -> dict:
        data_source = self._get_owned(ds_id)
        return self._to_response_dict(data_source)

    def list(self, *, type: Optional[str] = None, enabled: Optional[bool] = None, tag: Optional[str] = None, limit: int = 20, offset: int = 0) -> tuple[list[dict], int]:
        stmt = select(DataSource).where(
            and_(
                DataSource.tenant_id == self.principal.tenant_id,
                DataSource.deleted_at.is_(None),
            )
        )
        if type:
            stmt = stmt.where(DataSource.type == type)
        if enabled is not None:
            stmt = stmt.where(DataSource.is_enabled == enabled)
        if tag:
            # naive filter: tag present key or value equals; kept simple for core stage
            stmt = stmt.where(DataSource.tags.is_not(None))

        total = self.db.execute(stmt).scalars().unique().all()
        items = total[offset : offset + limit]
        return [self._to_response_dict(ds) for ds in items], len(total)

    def update(self, ds_id: str, payload: dict) -> dict:
        data_source = self._get_owned(ds_id)
        connector = registry.get(data_source.type)
        if connector is None:
            raise DataSourceUnknownType(f"Unknown datasource type: {data_source.type}")

        if "name" in payload and payload["name"]:
            data_source.name = payload["name"].strip()
        if "description" in payload:
            data_source.description = payload["description"]
        if "tags" in payload:
            data_source.tags = payload["tags"]
        if "is_enabled" in payload and payload["is_enabled"] is not None:
            data_source.is_enabled = bool(payload["is_enabled"])
        data_source.updated_by = self.principal.user_id

        # Config rotation/partial update
        if "config" in payload and payload["config"] is not None:
            current = decrypt_config(data_source.config.config_encrypted)
            merged = merge_partial_config(current, payload["config"], data_source.config.redaction_map)
            connector.validate_config(merged)

            redacted = connector.redact_config(merged)
            data_source.config.config_encrypted = encrypt_config(merged)
            data_source.config.config_schema_version = payload.get("config_schema_version") or data_source.config.config_schema_version
            data_source.config.redaction_map = {"secret_paths": _collect_redacted_paths(redacted)}

        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise DataSourceConflict("A datasource with this name already exists in the tenant")
        self.db.refresh(data_source)
        return self._to_response_dict(data_source)

    def delete(self, ds_id: str) -> None:
        data_source = self._get_owned(ds_id)
        # Soft delete
        from datetime import datetime as _dt

        data_source.deleted_at = _dt.utcnow()
        self.db.commit()

    def set_enabled(self, ds_id: str, enabled: bool) -> dict:
        data_source = self._get_owned(ds_id)
        data_source.is_enabled = enabled
        data_source.updated_by = self.principal.user_id
        self.db.commit()
        self.db.refresh(data_source)
        return self._to_response_dict(data_source)

    # Types listing
    def list_types(self) -> list[dict]:
        items = registry.list()  # empty in core stage unless plugins installed
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

    # Test connection stub
    def test_connection(self, ds_id: str, timeout_s: Optional[int] = None) -> dict:
        data_source = self._get_owned(ds_id)
        connector = registry.get(data_source.type)
        if connector is None:
            raise DataSourceNotImplemented("No connector implemented for this datasource type")

        ts = timeout_s or self.settings.datasource_test_timeout_s
        ts = min(ts, self.settings.datasource_test_timeout_max_s)
        config = decrypt_config(data_source.config.config_encrypted)
        result = connector.test_connection(config, timeout_s=ts)
        return result

    # Helpers
    def _get_owned(self, ds_id: str) -> DataSource:
        stmt = select(DataSource).where(
            and_(
                DataSource.id == ds_id,
                DataSource.tenant_id == self.principal.tenant_id,
                DataSource.deleted_at.is_(None),
            )
        )
        obj = self.db.execute(stmt).scalar_one_or_none()
        if obj is None:
            raise DataSourceNotFound()
        return obj

    def _to_response_dict(self, ds: DataSource) -> dict:
        cfg_plain = decrypt_config(ds.config.config_encrypted)
        redacted = apply_redaction(cfg_plain, ds.config.redaction_map)
        return {
            "id": ds.id,
            "tenant_id": ds.tenant_id,
            "owner_id": ds.owner_id,
            "name": ds.name,
            "type": ds.type,
            "category": ds.category,
            "description": ds.description,
            "tags": ds.tags,
            "is_enabled": ds.is_enabled,
            "created_at": ds.created_at,
            "updated_at": ds.updated_at,
            "created_by": ds.created_by,
            "updated_by": ds.updated_by,
            "config": redacted,
            "config_schema_version": ds.config.config_schema_version,
        }


def _collect_redacted_paths(redacted_config: dict) -> list[str]:
    paths: list[str] = []

    def walk(node: Any, prefix: list[str]):
        if isinstance(node, dict):
            for k, v in node.items():
                if v == REDACTED:
                    paths.append(".".join(prefix + [k]))
                else:
                    walk(v, prefix + [k])

    walk(redacted_config, [])
    return paths


