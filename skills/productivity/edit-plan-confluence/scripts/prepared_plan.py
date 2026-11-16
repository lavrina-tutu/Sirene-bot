"""Pure prepared-plan normalization. No JVM, SQL, network or executable CLI."""
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
COLLECTIONS = ("tasks", "dependencies", "external_dependencies", "resources", "assignments", "calendars")
NORMALIZER_VERSION = "prepared-v1"


def canonical_bytes(value: Any) -> bytes:
    def exact(obj):
        if isinstance(obj, Decimal):
            if not obj.is_finite():
                raise ValueError("non_finite_number")
            return format(obj.normalize(), "f")
        raise TypeError(f"not JSON serializable: {type(obj).__name__}")
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False, default=exact).encode("utf-8")


def fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


@dataclass(frozen=True)
class NormalizationProfile:
    document: dict[str, Any]

    @classmethod
    def load(cls, path=None):
        profile = cls(json.loads(Path(path or ROOT / "references/profiles/normalization-v1.json").read_text()))
        profile.validate()
        return profile

    def validate(self):
        d = self.document
        if (d.get("id") != "normalization-v1" or d.get("normalizer_version") != NORMALIZER_VERSION
                or d.get("export_version") != "full-export-v2"
                or d.get("dates", {}).get("policy") != "preserve_source_local_precision"
                or d.get("dates", {}).get("unknown_timezone") is not None
                or d.get("numbers") != {"quantities": "decimal_strings", "rounding": "none"}
                or d.get("ordering") != "preserve_source_rows_and_parallel_relations"):
            raise ValueError("unsupported_normalization_profile")

    @property
    def fingerprint(self):
        return fingerprint(self.document)


def validate_export(data):
    """Reject malformed/truncated exports, retain honestly marked partial ones."""
    if not isinstance(data, dict) or data.get("export_version") != "full-export-v2":
        raise ValueError("unsupported_export_version")
    p = data.get("provenance", {})
    if not re.fullmatch(r"[0-9a-f]{64}", str(p.get("sha256", ""))):
        raise ValueError("invalid_source_hash")
    if type(p.get("size_bytes")) is not int or p["size_bytes"] <= 0:
        raise ValueError("invalid_source_size")
    if any(not isinstance(p.get(k), str) or not p[k] for k in ("reader", "mpxj", "jpype")):
        raise ValueError("missing_reader_versions")
    if not isinstance(data.get("project"), dict) or not isinstance(data.get("diagnose_graph"), dict):
        raise ValueError("missing_project_or_graph")
    for name in COLLECTIONS:
        items = data.get(name)
        if not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
            raise ValueError(f"missing_or_invalid_collection:{name}")
        quality = data.get("collections", {}).get(name, {})
        if quality.get("status") not in ("complete", "partial", "missing", "unsupported"):
            raise ValueError(f"invalid_collection_quality:{name}")
        count = sum("error" not in r for r in items)
        if quality.get("count") != count:
            raise ValueError(f"collection_count_mismatch:{name}")
        if quality["status"] != "complete" and not quality.get("reason"):
            raise ValueError(f"quality_reason_required:{name}")
    if not any("error" not in t and t.get("task_key") for t in data["tasks"]):
        raise ValueError("no_readable_tasks")
    for name, key in [("tasks", "task_key"), ("resources", "resource_key"), ("assignments", "assignment_key"), ("calendars", "calendar_key")]:
        ids = [row.get(key) for row in data[name] if "error" not in row]
        if any(not isinstance(k, str) or not k for k in ids) or len(ids) != len(set(ids)):
            raise ValueError(f"invalid_local_identity:{name}")
    def walk(obj):
        if isinstance(obj, dict):
            if "quality" in obj and isinstance(obj["quality"], str) and obj["quality"] in ("ok", "missing", "unsupported", "partial"):
                if obj["quality"] != "ok" and not obj.get("reason"):
                    raise ValueError("field_quality_reason_required")
                if obj["quality"] == "ok" and "value" in obj and obj["value"] is None:
                    raise ValueError("null_is_not_known_zero")
            for key, val in obj.items():
                if key.endswith(("_key", "_keys")) or key == "task_key":
                    if re.search(r"obj:|object at 0x|@[0-9a-fA-F]{5,}", str(val)):
                        raise ValueError("unstable_identity")
                walk(val)
        elif isinstance(obj, list):
            for val in obj:
                walk(val)
    walk(data)
    canonical_bytes(data)  # NaN/nonserializable objects fail before persistence.


@dataclass(frozen=True)
class PreparedPlan:
    document: dict[str, Any]

    @classmethod
    def from_export(cls, export, *, profile=None, timezone_hint=None, provenance=None):
        validate_export(export)
        profile = profile or NormalizationProfile.load()
        profile.validate()
        resolved = timezone_hint if timezone_hint is not None else export.get("timezone_hint")
        if resolved is not None:
            ZoneInfo(resolved)  # Unknown remains null; no machine-local/ZD fallback.
        origin = "explicit_hint" if timezone_hint is not None else "source" if resolved is not None else "unknown"
        source = export["provenance"]
        normalized = {key: deepcopy(export[key]) for key in (*COLLECTIONS, "project", "collections", "diagnose_graph")}
        normalized["summary_inputs"] = deepcopy(export.get("summary_inputs", {}))
        normalized["export_version"] = export["export_version"]
        normalized["source_identity"] = {k: source[k] for k in ("sha256", "size_bytes", "reader", "mpxj", "jpype")}
        normalized["normalization"] = {"id": profile.document["id"], "version": profile.document["version"],
                                       "normalizer_version": NORMALIZER_VERSION, "fingerprint": profile.fingerprint}
        # The origin of a timezone decision is provenance, not semantic identity.
        normalized["resolved_timezone"] = resolved
        doc = {"schema_version": 1, "normalized_data": normalized,
               "semantic_sha256": fingerprint(normalized), "provenance": {**deepcopy(source), **(provenance or {}), "timezone_origin": origin}}
        prepared = cls(doc)
        prepared.validate()
        return prepared

    @property
    def semantic_hash(self):
        return self.document["semantic_sha256"]

    @property
    def normalized_data(self):
        return deepcopy(self.document["normalized_data"])

    def semantic_bytes(self):
        return canonical_bytes(self.document["normalized_data"])

    def to_dict(self):
        return deepcopy(self.document)

    def validate(self):
        import jsonschema
        schema = json.loads((ROOT / "references/schemas/prepared-plan.schema.json").read_text())
        jsonschema.validate(self.document, schema)
        normalized = self.document["normalized_data"]
        if fingerprint(normalized) != self.semantic_hash:
            raise ValueError("prepared_hash_mismatch")
        # Reapply exporter invariants when loading a prepared document from disk.
        validate_export({**normalized, "provenance": normalized["source_identity"]})
        if normalized["resolved_timezone"] is not None:
            ZoneInfo(normalized["resolved_timezone"])
        return self
