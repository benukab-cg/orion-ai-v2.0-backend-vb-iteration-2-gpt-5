from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Literal

import psycopg
from pydantic import BaseModel, Field, ValidationError, field_validator

from app.datasources.utils import REDACTED


SslMode = Literal["disable", "prefer", "require", "verify-ca", "verify-full"]


class PostgresConfig(BaseModel):
    host: str
    port: int = Field(default=5432, ge=1, le=65535)
    database: str
    username: str
    password: str
    ssl_mode: SslMode = Field(default="require")

    @field_validator("host", "database", "username", "password")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v


@dataclass
class PostgresConnector:
    type_slug: str = "sql.postgres"
    display_name: str = "PostgreSQL"
    category: str = "sql"
    version: str = "1.0.0"

    def validate_config(self, config: dict) -> None:
        try:
            PostgresConfig(**config)
        except ValidationError as ve:
            # Re-raise with a simple message list; the service will wrap appropriately
            raise ValueError(ve.errors())

    def redact_config(self, config: dict) -> dict:
        redacted = {**config}
        if "password" in redacted and redacted["password"]:
            redacted["password"] = REDACTED
        return redacted

    def get_json_schema(self) -> dict:
        schema = PostgresConfig.model_json_schema()
        # UI hints
        props = schema.get("properties", {})
        if "password" in props:
            props["password"]["format"] = "password"
            props["password"]["secret"] = True
            props["password"]["title"] = "Password"
        if "username" in props:
            props["username"]["title"] = "Username"
        if "database" in props:
            props["database"]["title"] = "Database"
        if "ssl_mode" in props:
            props["ssl_mode"]["title"] = "SSL Mode"
        return {
            "type": "object",
            "title": "PostgreSQL",
            **schema,
        }

    def test_connection(self, config: dict, timeout_s: int = 10) -> dict:
        # Validate and normalize
        pg = PostgresConfig(**config)
        start = time.perf_counter()
        try:
            conn = psycopg.connect(
                host=pg.host,
                port=pg.port,
                dbname=pg.database,
                user=pg.username,
                password=pg.password,
                sslmode=pg.ssl_mode,
                connect_timeout=timeout_s,
            )
            try:
                # Fetch server version without exposing or mutating data
                server_version = conn.info.parameter_status("server_version")
            finally:
                conn.close()
            latency_ms = int((time.perf_counter() - start) * 1000)
            return {"status": "ok", "latency_ms": latency_ms, "details": {"server_version": server_version}}
        except psycopg.OperationalError as e:  # network/auth issues
            latency_ms = int((time.perf_counter() - start) * 1000)
            detail_text = str(e).lower()
            code = "DS_UNREACHABLE"
            if "password authentication failed" in detail_text or "authentication failed" in detail_text:
                code = "DS_AUTH_FAILED"
            elif "timeout" in detail_text:
                code = "DS_TIMEOUT"
            return {"status": "failed", "latency_ms": latency_ms, "details": {"error": str(e), "code": code}}
        except Exception as e:
            latency_ms = int((time.perf_counter() - start) * 1000)
            return {"status": "failed", "latency_ms": latency_ms, "details": {"error": str(e), "code": "DS_VALIDATION_ERROR"}}


