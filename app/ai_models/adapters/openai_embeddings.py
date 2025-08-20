from __future__ import annotations

import time
from typing import Any, Dict, Optional

import httpx

from app.ai_models.adapters.base import AIModelConnector, ConnectorMetadata
from app.ai_models.exceptions import AIModelValidationError
from app.ai_models.utils import REDACTED


class OpenAIEmbeddingsConnector(AIModelConnector):
    def __init__(self) -> None:
        self.meta = ConnectorMetadata(
            type_slug="embedding.openai",
            display_name="OpenAI Embeddings",
            category="embedding",
            version="1.0.0",
            json_schema=_OPENAI_EMBEDDINGS_JSON_SCHEMA,
            source="builtin",
        )

    def validate_config(self, config: dict) -> None:
        api_key = config.get("api_key")
        if not api_key or not isinstance(api_key, str):
            raise AIModelValidationError("'api_key' is required and must be a string")
        base_url = config.get("base_url")
        if base_url is not None and not isinstance(base_url, str):
            raise AIModelValidationError("'base_url' must be a string if provided")
        default_model = config.get("default_model")
        if default_model is not None and not isinstance(default_model, str):
            raise AIModelValidationError("'default_model' must be a string if provided")
        expected_dimension = config.get("expected_dimension")
        if expected_dimension is not None and (not isinstance(expected_dimension, int) or expected_dimension <= 0):
            raise AIModelValidationError("'expected_dimension' must be a positive integer if provided")
        api_version = config.get("api_version")
        if base_url and "azure.com" in base_url and not api_version:
            raise AIModelValidationError("'api_version' is required when using Azure OpenAI base_url")

    def redact_config(self, config: dict) -> dict:
        def _redact(d: dict) -> dict:
            out: dict[str, Any] = {}
            for k, v in d.items():
                if k.lower() in {"api_key", "authorization"}:
                    out[k] = REDACTED
                elif isinstance(v, dict):
                    out[k] = _redact(v)
                else:
                    out[k] = v
            return out

        return _redact(config)

    def test_connection(self, config: dict, *, timeout_s: int = 10, allow_smoke_inference: bool = False) -> dict:
        base_url: str = (config.get("base_url") or "https://api.openai.com/v1").rstrip("/")
        api_key: str = config["api_key"]
        org: Optional[str] = config.get("organization")
        api_version: Optional[str] = config.get("api_version")
        extra_headers: dict[str, str] = config.get("extra_headers") or {}
        extra_query: dict[str, str] = config.get("extra_query_params") or {}

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        if org:
            headers["OpenAI-Organization"] = org
        headers.update({k: v for k, v in extra_headers.items() if k.lower() != "authorization"})

        client = httpx.Client(timeout=timeout_s)
        started = time.time()
        billable = False
        try:
            if "azure.com" in base_url:
                url = f"{base_url}/deployments"
                params = {"api-version": api_version} | extra_query
                r = client.get(url, headers=headers, params=params)
            else:
                url = f"{base_url}/models"
                r = client.get(url, headers=headers, params=extra_query)

            latency_ms = int((time.time() - started) * 1000)
            if r.status_code == 200:
                return {"status": "ok", "latency_ms": latency_ms, "billable": False, "details": {"endpoint": url}}
            if r.status_code in (401, 403):
                return {"status": "failed", "latency_ms": latency_ms, "billable": False, "details": {"error": "auth_failed", "status_code": r.status_code}}
            if r.status_code == 429:
                return {"status": "failed", "latency_ms": latency_ms, "billable": False, "details": {"error": "rate_limited", "status_code": r.status_code}}

            if allow_smoke_inference:
                billable = True
                model = config.get("default_model") or "text-embedding-3-small"
                body = {
                    "model": model,
                    "input": ["ping"],
                }
                if "azure.com" in base_url:
                    # Azure embeddings path: /deployments/{model}/embeddings
                    url = f"{base_url}/deployments/{model}/embeddings"
                    params = {"api-version": api_version} | extra_query
                    r2 = client.post(url, headers=headers, params=params, json=body)
                else:
                    url = f"{base_url}/embeddings"
                    r2 = client.post(url, headers=headers, params=extra_query, json=body)
                latency_ms = int((time.time() - started) * 1000)
                if 200 <= r2.status_code < 300:
                    return {"status": "ok", "latency_ms": latency_ms, "billable": True, "details": {"endpoint": url}}
                else:
                    return {"status": "failed", "latency_ms": latency_ms, "billable": True, "details": {"error": f"status_{r2.status_code}", "endpoint": url}}

            return {"status": "failed", "latency_ms": latency_ms, "billable": False, "details": {"error": f"status_{r.status_code}", "endpoint": url}}
        except httpx.TimeoutException:
            latency_ms = int((time.time() - started) * 1000)
            return {"status": "failed", "latency_ms": latency_ms, "billable": billable, "details": {"error": "timeout"}}
        except httpx.RequestError as e:
            latency_ms = int((time.time() - started) * 1000)
            return {"status": "failed", "latency_ms": latency_ms, "billable": billable, "details": {"error": "request_error", "message": str(e)}}
        finally:
            client.close()

    def get_capabilities(self, config: dict) -> dict:
        base_url: str = (config.get("base_url") or "https://api.openai.com/v1").rstrip("/")
        api_key: str = config.get("api_key", "")
        api_version: Optional[str] = config.get("api_version")
        extra_headers: dict[str, str] = config.get("extra_headers") or {}
        extra_query: dict[str, str] = config.get("extra_query_params") or {}

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        headers.update({k: v for k, v in extra_headers.items() if k.lower() != "authorization"})

        client = httpx.Client(timeout=10)
        try:
            if "azure.com" in base_url:
                url = f"{base_url}/deployments"
                params = {"api-version": api_version} | extra_query
                r = client.get(url, headers=headers, params=params)
                models: list[str] = []
                if r.status_code == 200:
                    data = r.json()
                    for item in data.get("data", []):
                        name = item.get("id") or item.get("name")
                        if isinstance(name, str):
                            models.append(name)
                return {"models": models, "api_style": "azure"}
            else:
                url = f"{base_url}/models"
                r = client.get(url, headers=headers, params=extra_query)
                models = []
                if r.status_code == 200:
                    data = r.json()
                    for item in data.get("data", []):
                        mid = item.get("id")
                        if isinstance(mid, str) and ("embedding" in mid or mid.startswith("text-embedding-")):
                            models.append(mid)
                # Provide known dimensions where applicable (best-effort hints)
                dims: Dict[str, int] = {}
                for m in models:
                    if m == "text-embedding-3-large":
                        dims[m] = 3072
                    elif m == "text-embedding-3-small":
                        dims[m] = 1536
                return {"models": models, "embedding_dimensions": dims, "api_style": "openai"}
        except Exception:
            return {"models": [], "api_style": "unknown"}
        finally:
            client.close()

    def embed_texts(self, config: dict, texts: list[str]) -> list[list[float]]:
        base_url: str = (config.get("base_url") or "https://api.openai.com/v1").rstrip("/")
        api_key: str = config["api_key"]
        model: str = config.get("default_model") or "text-embedding-3-small"
        api_version: Optional[str] = config.get("api_version")
        extra_headers: dict[str, str] = config.get("extra_headers") or {}
        extra_query: dict[str, str] = config.get("extra_query_params") or {}

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        headers.update({k: v for k, v in extra_headers.items() if k.lower() != "authorization"})

        client = httpx.Client(timeout=30)
        try:
            body = {"model": model, "input": texts}
            if "azure.com" in base_url:
                url = f"{base_url}/deployments/{model}/embeddings"
                params = {"api-version": api_version} | extra_query
                resp = client.post(url, headers=headers, params=params, json=body)
            else:
                url = f"{base_url}/embeddings"
                resp = client.post(url, headers=headers, params=extra_query, json=body)
            if not (200 <= resp.status_code < 300):
                raise AIModelValidationError(f"OpenAI embeddings failed with status {resp.status_code}")
            data = resp.json()
            arr = [item.get("embedding") for item in data.get("data", [])]
            if not arr or not isinstance(arr[0], list):
                raise AIModelValidationError("Malformed embeddings response")
            return arr
        finally:
            client.close()


_OPENAI_EMBEDDINGS_JSON_SCHEMA: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "OpenAI Embeddings Connector Configuration",
    "type": "object",
    "properties": {
        "api_key": {"type": "string", "title": "API Key", "secret": True},
        "base_url": {"type": "string", "title": "Base URL", "default": "https://api.openai.com/v1"},
        "organization": {"type": "string", "title": "Organization", "nullable": True},
        "default_model": {"type": "string", "title": "Default Model", "nullable": True},
        "api_version": {"type": "string", "title": "API Version (Azure only)", "nullable": True},
        "expected_dimension": {"type": "integer", "title": "Expected Dimension", "nullable": True},
        "extra_headers": {"type": "object", "title": "Extra Headers", "additionalProperties": {"type": "string"}},
        "extra_query_params": {"type": "object", "title": "Extra Query Params", "additionalProperties": {"type": "string"}},
    },
    "required": ["api_key"],
}



