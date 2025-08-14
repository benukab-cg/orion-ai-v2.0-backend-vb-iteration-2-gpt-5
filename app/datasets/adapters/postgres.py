from __future__ import annotations

import re
from contextlib import contextmanager
from typing import Any, Optional

from sqlalchemy import create_engine, text

from app.core.config import get_settings


_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_identifier(name: str) -> None:
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(f"Invalid identifier: {name}")


def _quote_ident(name: str) -> str:
    _validate_identifier(name)
    return f'"{name}"'


def _has_forbidden_tokens(expr: str) -> bool:
    lowered = expr.lower()
    forbidden = [";", "--", "/*", " union ", " join ", " select ", " with ", " return", " insert ", " update ", " delete ", " drop ", " alter "]
    return any(tok in lowered for tok in forbidden)


class PostgresDatasetConnector:
    type_slug = "sql.postgres"
    display_name = "PostgreSQL Dataset"
    category = "sql"
    version = "1.0.0"

    def __init__(self) -> None:
        self.settings = get_settings()

    # Protocol methods
    def validate_dataset_config(self, config: dict) -> None:
        table = config.get("table")
        if not table or not isinstance(table, str):
            raise ValueError("'table' is required and must be a string")
        _validate_identifier(table)
        schema = config.get("schema")
        if schema is not None:
            if not isinstance(schema, str):
                raise ValueError("'schema' must be a string when provided")
            _validate_identifier(schema)
        qts = config.get("query_timeout_s")
        if qts is not None and (not isinstance(qts, int) or qts <= 0):
            raise ValueError("'query_timeout_s' must be a positive integer when provided")

    def describe_schema(self, dataset: dict, limit_fields: int | None = None) -> dict:
        ds_cfg = dataset["config"]
        table = ds_cfg["table"]
        schema = ds_cfg.get("schema") or "public"
        with self._pg_conn(dataset) as conn:
            sql = text(
                """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = :schema AND table_name = :table
                ORDER BY ordinal_position
                """
            )
            rows = conn.execute(sql, {"schema": schema, "table": table}).mappings().all()
        if not rows:
            raise ValueError(f"Table not found: {schema}.{table}")
        columns = [
            {"name": r["column_name"], "type": r["data_type"], "nullable": (r["is_nullable"] == "YES")}
            for r in rows
        ]
        if limit_fields is not None:
            columns = columns[:limit_fields]
        return {"schema": schema, "table": table, "columns": columns}

    def select(self, dataset: dict, query_spec: dict) -> dict:
        ds_cfg = dataset["config"]
        table = ds_cfg["table"]
        schema = ds_cfg.get("schema") or "public"
        # Timeout: default 15s, cap at 60s (avoid binding in SET to prevent syntax issues)
        timeout_s = ds_cfg.get("query_timeout_s") or 15
        try:
            timeout_s = int(timeout_s)
        except Exception:
            timeout_s = 15
        timeout_s = max(1, min(timeout_s, 60))

        # Schema discovery for whitelist
        schema_info = self.describe_schema(dataset)
        allowed_columns = [c["name"] for c in schema_info["columns"]]

        # Build projection
        cols_req = query_spec.get("columns")
        if cols_req:
            for c in cols_req:
                if c not in allowed_columns:
                    raise ValueError(f"Invalid column requested: {c}")
            projection = ", ".join(_quote_ident(c) for c in cols_req)
        else:
            projection = ", ".join(_quote_ident(c) for c in allowed_columns)

        # WHERE
        where_expr = query_spec.get("where")
        params = query_spec.get("params") or {}
        if where_expr:
            if _has_forbidden_tokens(where_expr):
                raise ValueError("Disallowed tokens in WHERE expression")
            where_sql = f" WHERE {where_expr}"
        else:
            where_sql = ""

        # ORDER BY
        order_sql = ""
        order_by = query_spec.get("order_by") or []
        if order_by:
            parts = []
            for item in order_by:
                col = item.get("column")
                direction = (item.get("direction") or "asc").upper()
                if col not in allowed_columns:
                    raise ValueError(f"Invalid order_by column: {col}")
                if direction not in ("ASC", "DESC"):
                    raise ValueError("Invalid order_by direction")
                parts.append(f"{_quote_ident(col)} {direction}")
            order_sql = " ORDER BY " + ", ".join(parts)

        # LIMIT/OFFSET
        limits = self.limits()
        limit = query_spec.get("limit") or limits["default_limit"]
        limit = min(max(1, int(limit)), limits["max_limit"])
        offset = int(query_spec.get("offset") or 0)
        offset = max(0, offset)

        fq_table = f"{_quote_ident(schema)}.{_quote_ident(table)}"
        sql_txt = f"SELECT {projection} FROM {fq_table}{where_sql}{order_sql} LIMIT :_limit OFFSET :_offset"

        with self._pg_conn(dataset) as conn:
            # Set statement timeout in milliseconds (inline literal; Postgres doesn't support bind here)
            conn.execute(text(f"SET LOCAL statement_timeout = {int(timeout_s * 1000)}"))
            result = conn.execute(text(sql_txt), {**params, "_limit": limit, "_offset": offset})
            rows = result.mappings().all()
        return {"rows": [dict(r) for r in rows], "limit": limit, "offset": offset}

    def stats(self, dataset: dict) -> dict:
        # Provide a simple row count as stats (and validate table exists)
        ds_cfg = dataset["config"]
        table = ds_cfg["table"]
        schema = ds_cfg.get("schema") or "public"
        # Validate existence via describe_schema (will raise if missing)
        _ = self.describe_schema(dataset)
        fq_table = f"{_quote_ident(schema)}.{_quote_ident(table)}"
        with self._pg_conn(dataset) as conn:
            result = conn.execute(text(f"SELECT COUNT(*) AS cnt FROM {fq_table}"))
            cnt = int(result.scalar_one())
        return {"count": cnt}

    # Optional explicit count method used by the service if present
    def count(self, dataset: dict) -> dict:
        return self.stats(dataset)

    def get(self, dataset: dict, range_spec: dict | None = None) -> dict:  # not applicable
        raise NotImplementedError("Blob get not supported for Postgres connector")

    def presign_get(self, dataset: dict, ttl_s: int) -> dict:  # not applicable
        raise NotImplementedError("Blob presign not supported for Postgres connector")

    def apply_rls(self, context: dict, operation: str, spec: dict) -> dict:
        # Service is responsible for RLS merge; keep as no-op
        return spec

    def limits(self) -> dict:
        s = self.settings
        return {"default_limit": getattr(s, "default_page_size", 20), "max_limit": getattr(s, "max_page_size", 100), "max_timeout_s": getattr(s, "datasource_test_timeout_max_s", 30)}

    @contextmanager
    def _pg_conn(self, dataset: dict):
        datasource = dataset["datasource"]
        cfg = datasource["config"]
        user = cfg.get("username")
        password = cfg.get("password")
        host = cfg.get("host")
        port = cfg.get("port", 5432)
        database = cfg.get("database")
        ssl_mode = cfg.get("ssl_mode", "require")
        url = f"postgresql+psycopg://{user}:{password}@{host}:{port}/{database}?sslmode={ssl_mode}"
        engine = create_engine(url, pool_pre_ping=True, future=True)
        conn = engine.connect()
        try:
            yield conn
        finally:
            conn.close()
            engine.dispose()



