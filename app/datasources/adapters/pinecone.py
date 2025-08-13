from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator

from app.datasources.utils import REDACTED


class PineconeConfig(BaseModel):
    api_key: str
    environment: str
    project_name: Optional[str] = None

    @field_validator("api_key", "environment")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v


@dataclass
class PineconeConnector:
    type_slug: str = "vector.pinecone"
    display_name: str = "Pinecone"
    category: str = "vector"
    version: str = "1.0.0"

    def validate_config(self, config: dict) -> None:
        try:
            PineconeConfig(**config)
        except ValidationError as ve:
            raise ValueError(ve.errors())

    def redact_config(self, config: dict) -> dict:
        redacted = {**config}
        if "api_key" in redacted and redacted["api_key"]:
            redacted["api_key"] = REDACTED
        return redacted

    def get_json_schema(self) -> dict:
        schema = PineconeConfig.model_json_schema()
        props = schema.get("properties", {})
        if "api_key" in props:
            props["api_key"]["format"] = "password"
            props["api_key"]["secret"] = True
            props["api_key"]["title"] = "API Key"
        if "environment" in props:
            props["environment"]["title"] = "Environment"
            props["environment"]["examples"] = ["us-west1-gcp", "us-east1-aws"]
        if "project_name" in props:
            props["project_name"]["title"] = "Project Name"
        return {
            "type": "object",
            "title": "Pinecone",
            **schema,
        }

    def test_connection(self, config: dict, timeout_s: int = 10) -> dict:
        pc = PineconeConfig(**config)
        start = time.perf_counter()
        headers = {"Api-Key": pc.api_key}

        # Try global endpoint first (serverless/new API), then classic controller endpoint
        candidates = [
            "https://api.pinecone.io/actions/whoami",
            f"https://controller.{pc.environment}.pinecone.io/actions/whoami",
        ]

        last_error: dict | None = None
        for url in candidates:
            try:
                with httpx.Client(timeout=timeout_s) as client:
                    resp = client.get(url, headers=headers)
                latency_ms = int((time.perf_counter() - start) * 1000)
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                    except Exception:
                        data = {}
                    return {"status": "ok", "latency_ms": latency_ms, "details": data}
                if resp.status_code in (401, 403):
                    return {"status": "failed", "latency_ms": latency_ms, "details": {"error": resp.text, "code": "DS_AUTH_FAILED"}}
                # For 404/5xx or other unexpected codes, record and try next candidate
                last_error = {"status": "failed", "latency_ms": latency_ms, "details": {"error": resp.text, "code": "DS_VALIDATION_ERROR"}}
            except httpx.ConnectTimeout:
                latency_ms = int((time.perf_counter() - start) * 1000)
                # Try next candidate if available; otherwise return timeout
                last_error = {"status": "failed", "latency_ms": latency_ms, "details": {"error": "timeout", "code": "DS_TIMEOUT"}}
            except httpx.HTTPError as e:
                latency_ms = int((time.perf_counter() - start) * 1000)
                last_error = {"status": "failed", "latency_ms": latency_ms, "details": {"error": str(e), "code": "DS_UNREACHABLE"}}

        # If none succeeded, return the last captured error
        return last_error or {"status": "failed", "latency_ms": int((time.perf_counter() - start) * 1000), "details": {"error": "unknown", "code": "DS_UNREACHABLE"}}


