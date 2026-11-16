"""Strict manifest, canonical identity and nonrecursive Inbox intake."""
import copy
import json
from pathlib import Path

import pytest

from plan_manifest import ManifestError, canonicalize_request, load_manifest, manifest_hash, scan_inbox, validate_manifest

pytestmark = pytest.mark.unit


def document():
    return {"schema_version": 1, "items": [{"item_id": "e", "path": "one.mpp", "project_slug": "project"}]}


@pytest.mark.parametrize("field,value", [("mode", "publish"), ("page_id", "1"), ("batch_id", "x"),
    ("project_slug", "p"), ("lineage_id", "l"), ("timezone_hint", "UTC"), ("label", None), ("on_error", None),
    ("schema_version", True), ("items", []), ("items", None)])
def test_manifest_rejects_unknown_null_and_common_fields(field, value):
    doc = document(); doc[field] = value
    with pytest.raises(ManifestError):
        validate_manifest(doc)


@pytest.mark.parametrize("field,value", [("mode", "save"), ("page_id", "1"), ("lineage_id", None),
    ("source_version_date", "2026-02-30"), ("source_version_date", "20261116"),
    ("expected_sha256", "z"*64), ("timezone_hint", "Not/AZone"), ("project_slug", "../bad"), ("item_id", " ")])
def test_manifest_item_validation(field, value):
    doc = document(); doc["items"][0][field] = value
    with pytest.raises(ManifestError):
        validate_manifest(doc)


def test_manifest_duplicate_ids_and_json_keys(tmp_path):
    doc = document(); doc["items"] *= 2
    with pytest.raises(ManifestError, match="duplicate_item_id"):
        validate_manifest(doc)
    path = tmp_path/"duplicate.json"
    path.write_text('{"schema_version":1,"schema_version":1,"items":[]}')
    with pytest.raises(ManifestError, match="duplicate_json_key"):
        load_manifest(path)


def test_canonical_order_paths_fields_label_policy_and_saved_defaults(tmp_path):
    doc = document()
    doc.update(label="Label", on_error="stop")
    doc["items"][0].update(expected_sha256="A"*64, source_version_date="2026-11-16", timezone_hint="Europe/Moscow")
    defaults = {"e": {"lineage_id": "frozen-lineage", "timezone_hint": "UTC", "normalization": {"sha256": "pinned"}}}
    first = canonicalize_request(doc, base_dir=tmp_path, defaults=defaults)
    second = canonicalize_request(json.loads(json.dumps(doc, sort_keys=True, indent=4)), base_dir=tmp_path, defaults=defaults)
    assert first == second and manifest_hash(first) == manifest_hash(second)
    assert first["items"][0]["path"] == str(tmp_path/"one.mpp")
    assert first["items"][0]["expected_sha256"] == "a"*64
    assert first["items"][0]["lineage_id"] == "frozen-lineage"
    assert first["items"][0]["timezone_hint"] == "Europe/Moscow"
    assert canonicalize_request(doc, on_error="continue")["on_error"] == "continue"
    assert canonicalize_request(document())["on_error"] == "continue"
    for change in ("label", "policy", "path", "date", "lineage", "timezone", "hash", "order"):
        other = copy.deepcopy(doc)
        if change == "label": other["label"] = "Other"
        elif change == "policy": other["on_error"] = "continue"
        elif change == "order": other["items"].insert(0, {**other["items"][0], "item_id": "other"})
        else:
            key = {"date":"source_version_date", "lineage":"lineage_id", "timezone":"timezone_hint", "hash":"expected_sha256"}.get(change, change)
            other["items"][0][key] = {"path":"two.mpp", "date":"2026-11-15", "lineage":"other", "timezone":"UTC", "hash":"b"*64}[change]
        assert manifest_hash(canonicalize_request(other, base_dir=tmp_path, defaults=defaults)) != manifest_hash(first)


def test_inbox_unicode_regular_complete_nonrecursive_diagnostics(tmp_path):
    for name in ("Я.mpp", "A.mpp", "а.MPP", ".hidden.mpp", "~$open.mpp", "copy.mpp.part", "note.txt"):
        (tmp_path/name).write_bytes(b"fixture")
    (tmp_path/"nested").mkdir(); (tmp_path/"nested/deeper.mpp").touch()
    (tmp_path/"link.mpp").symlink_to(tmp_path/"A.mpp")
    before = {str(p):p.lstat().st_mode for p in tmp_path.rglob("*")}
    paths, diagnostics = scan_inbox(tmp_path)
    assert [Path(p).name for p in paths] == ["A.mpp", "Я.mpp", "а.MPP"]
    assert {d["code"] for d in diagnostics} == {"inbox_temporary_excluded", "inbox_symlink_excluded", "inbox_nonregular_excluded"}
    assert {str(p):p.lstat().st_mode for p in tmp_path.rglob("*")} == before
