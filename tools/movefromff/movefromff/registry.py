"""`_registry.json` reader/writer — минимальная схема v2.0.

ТЗ §4: только `status` ∈ {pending, completed, error}. Никаких sha256/integrity/
errors/audio_url/last_checked_at/source/processing_status.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from .filename import utc_now_iso

SCHEMA_VERSION = "2.0"

Status = Literal["pending", "completed", "error"]

FILE_KINDS = ("transcript", "summary", "actions")

# Поля v1.x, которые при чтении просто отбрасываются (миграция → v2.0).
_LEGACY_FIELDS = {
    "sha256",
    "transfer_status",
    "integrity",
    "source",
    "processing_status",
    "moved_by",
    "moved_at",
    "moved_to",
    "errors",
    "audio_url",
    "last_checked_at",
    "keywords",
    "size_bytes",
    "written_at",
}


class MeetingRecord(BaseModel):
    """Запись о скачанной встрече (минимум полей, v2.0)."""

    model_config = ConfigDict(extra="ignore")

    title: str = "Untitled meeting"
    meeting_date: Optional[str] = None  # ISO-8601 Z UTC
    duration_minutes: Optional[float] = None
    participants: List[str] = Field(default_factory=list)
    files: Dict[str, str] = Field(default_factory=dict)  # kind → filename
    status: Status = "pending"
    fetched_at: Optional[str] = None


class Registry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schema_version: str = SCHEMA_VERSION
    updated_at: str = Field(default_factory=utc_now_iso)
    meetings: Dict[str, MeetingRecord] = Field(default_factory=dict)


def _migrate_record(raw: dict, meeting_id: str, new_meetings_dir: Optional[Path] = None) -> dict:
    """Привести запись v1.x → v2.0.

    Согласно ТЗ §13:
    - Оставить только нужные поля.
    - status=completed, если все файлы реально лежат на диске; иначе error.
    - files: dict[str, FileMeta] → dict[str, str] (только имя файла).
    """
    out: dict = {
        "title": raw.get("title", "Untitled meeting"),
        "meeting_date": raw.get("meeting_date"),
        "duration_minutes": raw.get("duration_minutes"),
        "participants": list(raw.get("participants") or []),
        "fetched_at": raw.get("fetched_at"),
    }

    # files: может быть либо dict[str, str] (v2.0), либо dict[str, FileMeta-like] (v1.x)
    files_raw = raw.get("files") or {}
    files: Dict[str, str] = {}
    if isinstance(files_raw, dict):
        for kind, meta in files_raw.items():
            if isinstance(meta, str):
                files[kind] = meta
            elif isinstance(meta, dict):
                fn = meta.get("filename") or ""
                if fn:
                    files[kind] = fn
    out["files"] = files

    # status: если уже есть в новом формате — берём; иначе мигрируем
    if raw.get("status") in ("pending", "completed", "error"):
        out["status"] = raw["status"]
    else:
        # legacy: проставить completed если все файлы есть на диске
        legacy_transfer = raw.get("transfer_status")
        if legacy_transfer == "completed" and files and new_meetings_dir is not None:
            all_present = all(
                (new_meetings_dir / fn).exists() for fn in files.values() if fn
            )
            out["status"] = "completed" if all_present else "error"
        elif legacy_transfer == "completed" and files:
            # без проверки диска (не передан) — оставим completed
            out["status"] = "completed"
        else:
            out["status"] = "error" if files else "pending"
    return out


def load_registry(path: Path, new_meetings_dir: Optional[Path] = None) -> Registry:
    """Прочитать реестр. Поддерживает миграцию v1.0/v1.1 → v2.0.

    Если файла нет → пустой реестр с актуальной схемой.
    """
    if not path.exists():
        return Registry()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Registry not valid JSON: {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise RuntimeError(f"Registry root is not an object: {path}")

    schema = str(raw.get("schema_version") or "1.0")
    meetings_raw = raw.get("meetings") or {}

    if schema == SCHEMA_VERSION:
        # Чистое чтение, но всё равно пропускаем через модель.
        return Registry.model_validate({
            "schema_version": SCHEMA_VERSION,
            "updated_at": raw.get("updated_at") or utc_now_iso(),
            "meetings": meetings_raw,
        })

    # Миграция v1.0 / v1.1 → v2.0
    if new_meetings_dir is None:
        # Попробуем понять путь к директории из расположения registry.json
        new_meetings_dir = path.parent

    migrated_meetings: Dict[str, dict] = {}
    for mid, rec_raw in meetings_raw.items():
        if not isinstance(rec_raw, dict):
            continue
        migrated_meetings[mid] = _migrate_record(rec_raw, mid, new_meetings_dir)

    return Registry.model_validate({
        "schema_version": SCHEMA_VERSION,
        "updated_at": utc_now_iso(),
        "meetings": migrated_meetings,
    })


def save_registry(reg: Registry, path: Path) -> None:
    """Атомарная запись реестра (tmp + os.replace)."""
    reg.schema_version = SCHEMA_VERSION
    reg.updated_at = utc_now_iso()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = reg.model_dump(mode="json", exclude_none=False)
    blob = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False)
    fd, tmp_path = tempfile.mkstemp(
        prefix="_registry-", suffix=".json.tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(blob)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
        os.replace(tmp_path, path)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except OSError:
            pass


def make_empty_record() -> MeetingRecord:
    """Пустая заготовка с status=pending."""
    return MeetingRecord()
