from __future__ import annotations

from typing import Any


def ensure_category_compatibility(dataset_category: str, datasource_type_slug: str) -> None:
    if dataset_category == "sql" and not datasource_type_slug.startswith("sql."):
        raise ValueError("Dataset category 'sql' requires a 'sql.*' datasource")
    if dataset_category == "vector" and not datasource_type_slug.startswith("vector."):
        raise ValueError("Dataset category 'vector' requires a 'vector.*' datasource")
    if dataset_category == "blob" and not datasource_type_slug.startswith("blob."):
        raise ValueError("Dataset category 'blob' requires a 'blob.*' datasource")


def normalize_limit(limit: int, default_limit: int, max_limit: int) -> int:
    if limit is None or limit <= 0:
        return default_limit
    return min(limit, max_limit)


def normalize_timeout(timeout_s: int | None, default_s: int, max_s: int) -> int:
    if timeout_s is None or timeout_s <= 0:
        return default_s
    return min(timeout_s, max_s)


def validate_sql_projection(columns: list[str] | None, allowed_columns: list[str]) -> list[str] | None:
    if columns is None:
        return None
    invalid = [c for c in columns if c not in allowed_columns]
    if invalid:
        raise ValueError(f"Invalid columns requested: {invalid}")
    return columns


def safe_order_by(order_by: list[dict] | None, allowed_columns: list[str]) -> list[dict] | None:
    if not order_by:
        return None
    cleaned: list[dict[str, Any]] = []
    for item in order_by:
        col = item.get("column")
        direction = (item.get("direction") or "asc").lower()
        if col not in allowed_columns:
            raise ValueError(f"Invalid order_by column: {col}")
        if direction not in ("asc", "desc"):
            raise ValueError("Invalid order_by direction")
        cleaned.append({"column": col, "direction": direction})
    return cleaned


