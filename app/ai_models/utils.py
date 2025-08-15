from __future__ import annotations

import base64
import json
from typing import Any

from cryptography.fernet import Fernet

from app.core.config import get_settings


REDACTED = "__REDACTED__"


def _get_fernet() -> Fernet:
    settings = get_settings()
    key = settings.secret_key
    normalized = base64.urlsafe_b64encode(key.encode("utf-8").ljust(32, b"0")[:32])
    return Fernet(normalized)


def encrypt_config(config: dict) -> bytes:
    f = _get_fernet()
    payload = json.dumps(config).encode("utf-8")
    return f.encrypt(payload)


def decrypt_config(token: bytes) -> dict:
    f = _get_fernet()
    data = f.decrypt(token)
    return json.loads(data.decode("utf-8"))


def apply_redaction(config: dict, redaction_map: dict | None) -> dict:
    if not redaction_map:
        return config
    redacted = json.loads(json.dumps(config))
    for path_str in redaction_map.get("secret_paths", []):
        parts = path_str.split(".") if path_str else []
        cursor: Any = redacted
        for i, part in enumerate(parts):
            if isinstance(cursor, dict) and part in cursor:
                if i == len(parts) - 1:
                    cursor[part] = REDACTED
                else:
                    cursor = cursor[part]
            else:
                break
    return redacted


def merge_partial_config(existing_config: dict, patch_config: dict, redaction_map: dict | None) -> dict:
    def _merge(dst: dict, src: dict):
        for k, v in src.items():
            if isinstance(v, dict) and isinstance(dst.get(k), dict):
                _merge(dst[k], v)
            else:
                if v == REDACTED:
                    dst_value = dst.get(k)
                    if dst_value is not None:
                        continue
                dst[k] = v

    result = json.loads(json.dumps(existing_config))
    _merge(result, patch_config)
    return result


def collect_redacted_paths(redacted_config: dict) -> list[str]:
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



