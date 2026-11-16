"""Strict batch intake descriptions. No SQL, reader, or source-file mutations."""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo


class ManifestError(ValueError):
    def __init__(self, code="invalid_manifest"):
        self.code = code
        super().__init__(code)


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def manifest_hash(value):
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def absolute_path(value, base=None):
    # Normalize spelling without following a final symlink: intake must reject it.
    path = Path(value).expanduser()
    return os.path.abspath((Path(base) / path) if base and not path.is_absolute() else path)


def _string(value):
    return isinstance(value, str) and bool(value.strip()) and "\x00" not in value


def validate_manifest(document):
    """Validate all structure before any arrival is registered; optional != null."""
    if not isinstance(document, dict) or set(document) - {"schema_version", "items", "label", "on_error"}:
        raise ManifestError()
    if type(document.get("schema_version")) is not int or document["schema_version"] != 1:
        raise ManifestError()
    if not isinstance(document.get("items"), list) or not document["items"]:
        raise ManifestError()
    if "label" in document and not _string(document["label"]):
        raise ManifestError()
    if "on_error" in document and document["on_error"] not in ("continue", "stop"):
        raise ManifestError()
    ids = set()
    required = {"item_id", "path", "project_slug"}
    allowed = required | {"lineage_id", "source_version_date", "expected_sha256", "timezone_hint"}
    for item in document["items"]:
        if not isinstance(item, dict) or not required <= set(item) or set(item) - allowed:
            raise ManifestError()
        if not all(_string(value) for value in item.values()):
            raise ManifestError()
        if item["item_id"] in ids:
            raise ManifestError("duplicate_item_id")
        ids.add(item["item_id"])
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", item["project_slug"]) or ".." in item["project_slug"]:
            raise ManifestError("invalid_project_slug")
        if "expected_sha256" in item and not re.fullmatch(r"[0-9a-fA-F]{64}", item["expected_sha256"]):
            raise ManifestError("invalid_expected_sha256")
        if "source_version_date" in item:
            try:
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", item["source_version_date"]):
                    raise ValueError()
                date.fromisoformat(item["source_version_date"])
            except ValueError as exc:
                raise ManifestError("invalid_source_version_date") from exc
        if "timezone_hint" in item:
            try:
                ZoneInfo(item["timezone_hint"])
            except (ValueError, KeyError) as exc:
                raise ManifestError("invalid_timezone") from exc
    return document


def load_manifest(path):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ManifestError("duplicate_json_key")
            result[key] = value
        return result
    try:
        return validate_manifest(json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=pairs))
    except (OSError, UnicodeError, ValueError) as exc:
        if isinstance(exc, ManifestError):
            raise
        raise ManifestError() from exc


def canonicalize_request(document, *, base_dir=None, on_error=None, defaults=None, source=None):
    """Canonical fields/order/paths plus *persisted* implicit values on repeats.

    defaults is an item-ID map resolved once by the batch owner. Never reads
    config, a project profile or input bytes while comparing an existing ID.
    """
    validate_manifest(document)
    policy = on_error if on_error is not None else document.get("on_error", "continue")
    if policy not in ("continue", "stop"):
        raise ManifestError("invalid_on_error")
    items = []
    for entry in document["items"]:
        item = dict(entry)
        item["path"] = absolute_path(item["path"], base_dir)
        if "expected_sha256" in item:
            item["expected_sha256"] = item["expected_sha256"].lower()
        implicit = (defaults or {}).get(item["item_id"], {})
        for key in ("lineage_id", "timezone_hint"):
            item[key] = item.get(key, implicit.get(key))
        item["normalization"] = implicit.get("normalization")
        items.append(item)
    return {"schema_version": 1, "items": items, "label": document.get("label"),
            "on_error": policy, "source": source or {"kind": "manifest"}}


def scan_inbox(folder):
    """One explicitly selected directory, Unicode code-point order, no recursion.

    Completion means a stable regular non-temporary .mpp; the actual consistent
    byte copy is checked by freeze_input, rather than guessed from file age.
    """
    root = Path(absolute_path(folder))
    if not root.is_dir() or root.is_symlink():
        raise ManifestError("invalid_inbox")
    paths, diagnostics = [], []
    try:
        entries = sorted(root.iterdir(), key=lambda p: p.name)
        for path in entries:
            mode = path.lstat().st_mode
            reason = None
            name = path.name.lower()
            if stat.S_ISLNK(mode):
                reason = "inbox_symlink_excluded"
            elif name.startswith((".", "~", "#$")) or name.endswith((".tmp", ".part", ".partial", ".download", ".crdownload", "~")):
                reason = "inbox_temporary_excluded"
            elif not stat.S_ISREG(mode):
                reason = "inbox_nonregular_excluded"
            elif path.suffix.lower() == ".mpp":
                paths.append(str(path))
            if reason:
                diagnostics.append({"name": path.name, "code": reason})
    except OSError as exc:
        raise ManifestError("inbox_unreadable") from exc
    return paths, diagnostics
