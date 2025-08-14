from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import Principal
from app.datasources.models import DataSource
from app.datasources.utils import decrypt_config
from app.datasets.adapters import registry as dataset_registry
from app.datasets.exceptions import (
    DatasetConflict,
    DatasetDisabled,
    DatasetNotFound,
    DatasetNotImplemented,
    DatasetUnknownType,
    DatasetValidationError,
)
from app.datasets.models import (
    Dataset,
    DatasetCachedSchema,
    DatasetConfig,
    DatasetMetadataProfile,
)


class DatasetService:
    def __init__(self, db: Session, principal: Principal) -> None:
        self.db = db
        self.principal = principal
        self.settings = get_settings()

    # CRUD
    def create(self, payload: dict) -> dict:
        ds_id = str(uuid.uuid4())
        dataset = Dataset(
            id=ds_id,
            tenant_id=self.principal.tenant_id,
            owner_id=self.principal.user_id,
            name=payload["name"].strip(),
            category=payload["category"].strip(),
            data_source_id=payload["data_source_id"],
            description=(payload.get("description") or None),
            tags=payload.get("tags") or None,
            is_enabled=bool(payload.get("is_enabled", True)),
            created_by=self.principal.user_id,
            updated_by=self.principal.user_id,
        )

        # Validate datasource existence and basic compatibility (category check left to connectors at runtime)
        ds_stmt = select(DataSource).where(and_(
            DataSource.id == dataset.data_source_id,
            DataSource.tenant_id == self.principal.tenant_id,
            DataSource.deleted_at.is_(None),
        ))
        data_source = self.db.execute(ds_stmt).scalar_one_or_none()
        if data_source is None:
            raise DatasetValidationError("Referenced datasource not found")

        # Validate config shape via connector JSON schema when available
        connector = dataset_registry.get(data_source.type)  # type: ignore[attr-defined]
        if connector is None:
            # Allow creation without a registered connector; runtime operations will raise not implemented
            pass
        else:
            try:
                connector.validate_dataset_config(payload["config"])
            except Exception as ex:  # narrow later
                raise DatasetValidationError(str(ex))

        cfg = DatasetConfig(
            dataset_id=ds_id,
            config_json=payload["config"],
            config_schema_version=payload.get("config_schema_version"),
        )
        dataset.config = cfg

        self.db.add(dataset)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise DatasetConflict("A dataset with this name already exists in the tenant")
        self.db.refresh(dataset)
        return self._to_response_dict(dataset)

    def get(self, dataset_id: str) -> dict:
        dataset = self._get_owned(dataset_id)
        return self._to_response_dict(dataset)

    def list(self, *, category: Optional[str] = None, enabled: Optional[bool] = None, limit: int = 20, offset: int = 0) -> tuple[list[dict], int]:
        stmt = select(Dataset).where(
            and_(
                Dataset.tenant_id == self.principal.tenant_id,
                Dataset.deleted_at.is_(None),
            )
        )
        if category:
            stmt = stmt.where(Dataset.category == category)
        if enabled is not None:
            stmt = stmt.where(Dataset.is_enabled == enabled)

        total = self.db.execute(stmt).scalars().unique().all()
        items = total[offset : offset + limit]
        return [self._to_response_dict(d) for d in items], len(total)

    def update(self, dataset_id: str, payload: dict) -> dict:
        dataset = self._get_owned(dataset_id)
        if "name" in payload and payload["name"]:
            dataset.name = payload["name"].strip()
        if "description" in payload:
            dataset.description = payload["description"]
        if "tags" in payload:
            dataset.tags = payload["tags"]
        if "is_enabled" in payload and payload["is_enabled"] is not None:
            dataset.is_enabled = bool(payload["is_enabled"])
        dataset.updated_by = self.principal.user_id

        if "config" in payload and payload["config"] is not None:
            dataset.config.config_json = payload["config"]
            dataset.config.config_schema_version = payload.get("config_schema_version") or dataset.config.config_schema_version

        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise DatasetConflict("A dataset with this name already exists in the tenant")
        self.db.refresh(dataset)
        return self._to_response_dict(dataset)

    def delete(self, dataset_id: str) -> None:
        dataset = self._get_owned(dataset_id)
        from datetime import datetime as _dt

        dataset.deleted_at = _dt.utcnow()
        self.db.commit()

    def set_enabled(self, dataset_id: str, enabled: bool) -> dict:
        dataset = self._get_owned(dataset_id)
        dataset.is_enabled = enabled
        dataset.updated_by = self.principal.user_id
        self.db.commit()
        self.db.refresh(dataset)
        return self._to_response_dict(dataset)

    # Read-only Operations (stubs; require connectors)
    def sql_select(self, dataset_id: str, query_spec: dict) -> dict:
        dataset, connector, data_source = self._resolve_for_ops(dataset_id, expected_category="sql")
        if connector is None:
            raise DatasetNotImplemented("No connector for dataset datasource type")
        return connector.select(self._dataset_binding(dataset, data_source), query_spec)

    def sql_schema(self, dataset_id: str) -> dict:
        dataset, connector, data_source = self._resolve_for_ops(dataset_id, expected_category="sql")
        if connector is None:
            raise DatasetNotImplemented("No connector for dataset datasource type")
        schema = connector.describe_schema(self._dataset_binding(dataset, data_source))
        # Persist cached schema
        if dataset.cached_schema is None:
            dataset.cached_schema = DatasetCachedSchema(dataset_id=dataset.id, category=dataset.category, schema_json=schema)
        else:
            dataset.cached_schema.schema_json = schema
        self.db.commit()
        return schema

    def sql_count(self, dataset_id: str) -> dict:
        # Optional utility; leave to connector with a safe strategy
        dataset, connector, data_source = self._resolve_for_ops(dataset_id, expected_category="sql")
        if connector is None:
            raise DatasetNotImplemented("No connector for dataset datasource type")
        # Reuse select with COUNT(*) abstraction if connector exposes count; otherwise raise
        if hasattr(connector, "count"):
            return connector.count(self._dataset_binding(dataset, data_source))  # type: ignore[attr-defined]
        raise DatasetNotImplemented("Count operation not provided by connector")

    def vector_query(self, dataset_id: str, spec: dict) -> dict:
        dataset, connector, data_source = self._resolve_for_ops(dataset_id, expected_category="vector")
        if connector is None:
            raise DatasetNotImplemented("No connector for dataset datasource type")
        return connector.query(self._dataset_binding(dataset, data_source), spec.get("vector"), spec.get("top_k"), spec.get("filter"), {"include_values": spec.get("include_values"), "include_metadata": spec.get("include_metadata"), "namespace": spec.get("namespace")})

    def vector_stats(self, dataset_id: str) -> dict:
        dataset, connector, data_source = self._resolve_for_ops(dataset_id, expected_category="vector")
        if connector is None:
            raise DatasetNotImplemented("No connector for dataset datasource type")
        return connector.stats(self._dataset_binding(dataset, data_source))

    def blob_get(self, dataset_id: str, range_spec: Optional[dict]) -> dict:
        dataset, connector, data_source = self._resolve_for_ops(dataset_id, expected_category="blob")
        if connector is None:
            raise DatasetNotImplemented("No connector for dataset datasource type")
        return connector.get(self._dataset_binding(dataset, data_source), range_spec)

    def blob_presign(self, dataset_id: str, ttl_s: int) -> dict:
        dataset, connector, data_source = self._resolve_for_ops(dataset_id, expected_category="blob")
        if connector is None:
            raise DatasetNotImplemented("No connector for dataset datasource type")
        return connector.presign_get(self._dataset_binding(dataset, data_source), ttl_s)

    # Helpers
    def _dataset_binding(self, dataset: Dataset, data_source: DataSource) -> dict:
        ds_cfg_plain = decrypt_config(data_source.config.config_encrypted)
        return {
            "id": dataset.id,
            "category": dataset.category,
            "data_source_id": dataset.data_source_id,
            "config": dataset.config.config_json,
            "datasource": {
                "type": data_source.type,
                "category": data_source.category,
                "config": ds_cfg_plain,
            },
        }

    def _resolve_for_ops(self, dataset_id: str, expected_category: str) -> tuple[Dataset, Any, DataSource]:
        dataset = self._get_owned(dataset_id)
        if not dataset.is_enabled:
            raise DatasetDisabled()
        # lookup datasource
        ds_stmt = select(DataSource).where(and_(
            DataSource.id == dataset.data_source_id,
            DataSource.tenant_id == self.principal.tenant_id,
            DataSource.deleted_at.is_(None),
        ))
        data_source = self.db.execute(ds_stmt).scalar_one_or_none()
        if data_source is None or not data_source.is_enabled:
            raise DatasetDisabled("Datasource disabled or not found")
        if dataset.category != expected_category:
            raise DatasetValidationError("Dataset category mismatch for operation")
        connector = dataset_registry.get(data_source.type)  # type: ignore[attr-defined]
        return dataset, connector, data_source

    def _get_owned(self, dataset_id: str) -> Dataset:
        stmt = select(Dataset).where(
            and_(
                Dataset.id == dataset_id,
                Dataset.tenant_id == self.principal.tenant_id,
                Dataset.deleted_at.is_(None),
            )
        )
        obj = self.db.execute(stmt).scalar_one_or_none()
        if obj is None:
            raise DatasetNotFound()
        return obj

    def _to_response_dict(self, d: Dataset) -> dict:
        return {
            "id": d.id,
            "tenant_id": d.tenant_id,
            "owner_id": d.owner_id,
            "name": d.name,
            "category": d.category,
            "description": d.description,
            "tags": d.tags,
            "is_enabled": d.is_enabled,
            "created_at": d.created_at,
            "updated_at": d.updated_at,
            "created_by": d.created_by,
            "updated_by": d.updated_by,
            "data_source_id": d.data_source_id,
            "config": d.config.config_json,
            "config_schema_version": d.config.config_schema_version,
        }


