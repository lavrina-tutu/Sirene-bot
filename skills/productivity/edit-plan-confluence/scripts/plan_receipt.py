"""Квитанции шагов попытки — файловое зеркало ``plan_attempt_event`` (P1.W1.3).

Маскирует ``CONFLUENCE_TOKEN``/``Authorization`` при сериализации (R-022,
AC-123). Квитанции пишутся до и после каждого сетевого эффекта.
"""
from __future__ import annotations

import os
import tempfile
import json
import re
from pathlib import Path
from typing import Any

from env import get_workvault_path

_SECRET_KEY_RE = re.compile(r"(token|authorization|bearer)", re.IGNORECASE)
_BEARER_VALUE_RE = re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE)


def _mask_value(value: Any) -> Any:
    if isinstance(value, str):
        return _BEARER_VALUE_RE.sub("Bearer ***MASKED***", value)
    return value


def mask_secrets(payload: Any) -> Any:
    """Рекурсивно маскировать значения по ключам, похожим на токен/заголовок
    авторизации, и строки вида ``Bearer <token>`` в произвольном месте."""
    if isinstance(payload, dict):
        out: dict[str, Any] = {}
        for k, v in payload.items():
            if _SECRET_KEY_RE.search(str(k)):
                out[k] = "***MASKED***"
            else:
                out[k] = mask_secrets(v)
        return out
    if isinstance(payload, list):
        return [mask_secrets(v) for v in payload]
    return _mask_value(payload)


def receipts_dir(attempt_id: str) -> Path:
    return get_workvault_path() / "_plan-receipts" / attempt_id


def write_receipt(attempt_id: str, event_id: str, payload: dict[str, Any]) -> Path:
    """Записать квитанцию ``receipts/<attempt-id>/<event-id>.json``, маскируя
    секреты. Идемпотентна: повторный вызов перезаписывает тем же содержимым
    (не накапливает дубликаты файлов)."""
    masked = mask_secrets(payload)
    d = receipts_dir(attempt_id)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{event_id}.json"
    # A crash must not turn a receipt into truncated JSON.
    fd, temporary = tempfile.mkstemp(prefix=".receipt-", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(masked, stream, ensure_ascii=False, indent=2, default=str)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return path


def read_receipt(attempt_id: str, event_id: str) -> dict[str, Any] | None:
    path = receipts_dir(attempt_id) / f"{event_id}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_failure_receipt(attempt_id: str, stage: str, error: Exception, *, external_effect: str) -> Path:
    """Unknown/partial remote writes never become published:false or success."""
    return write_receipt(attempt_id, "failure-" + stage, {
        "stage": stage, "status": "failed", "published": None,
        "external_effect": external_effect, "error": str(error),
        "schedule": "not_verified",
    })
