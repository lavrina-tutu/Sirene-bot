"""Stage-02 normalization and non-secret execution context contracts."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from prepared_plan import NormalizationProfile, PreparedPlan, validate_export

pytestmark = pytest.mark.unit
SYNTHETIC = Path(__file__).parent / "fixtures/synthetic"


@pytest.fixture
def full_export():
    return json.loads((SYNTHETIC / "relations-all-types.json").read_text())


def test_semantic_hash_excludes_execution_provenance(full_export):
    first = PreparedPlan.from_export(full_export)
    changed = copy.deepcopy(full_export)
    changed.update(source="/other/dir/new-name.mpp", operation_id="other", work_dir="/new-workdir", telemetry={"MPXJ_read": 99})
    changed["provenance"].update(source_path="/other/dir/new-name.mpp", original_name="new-name.mpp", read_at="tomorrow", operation_id="other")
    second = PreparedPlan.from_export(changed)
    assert first.semantic_hash == second.semantic_hash
    assert first.semantic_bytes() == second.semantic_bytes()
    assert first.to_dict()["provenance"] != second.to_dict()["provenance"]


def test_normalization_profile_and_timezone_change_identity(full_export):
    original = PreparedPlan.from_export(full_export)
    assert original.normalized_data["resolved_timezone"] is None
    assert original.to_dict()["provenance"]["timezone_origin"] == "unknown"
    assert original.normalized_data["diagnose_graph"]["schedule_status"] == "not_verified"
    assert PreparedPlan.from_export(full_export, timezone_hint="Europe/Moscow").semantic_hash != original.semantic_hash
    profile = copy.deepcopy(NormalizationProfile.load().document)
    profile["version"] = "1.0.1"
    assert PreparedPlan.from_export(full_export, profile=NormalizationProfile(profile)).semantic_hash != original.semantic_hash
    with pytest.raises(Exception, match="No time zone|Unknown|not found"):
        PreparedPlan.from_export(full_export, timezone_hint="Not/AZone")


def test_relations_keep_signed_elapsed_and_known_zero(full_export):
    data = PreparedPlan.from_export(full_export).normalized_data
    assert {r["link_type"] for r in data["dependencies"]} == {"FS", "SS", "FF", "SF"}
    lag = next(r["lag_value"] for r in data["dependencies"] if r["link_type"] == "SS")
    assert lag == {"value": {"amount": "-1", "units": "ELAPSED_DAYS", "source_units": "ed", "elapsed": True}, "quality": "ok", "reason": None}
    zero = next(r["lag_value"] for r in data["dependencies"] if r["link_type"] == "FF")
    assert zero["value"]["amount"] == "0" and zero["quality"] == "ok"


def test_calendar_intervals_exceptions_inheritance_and_bindings():
    data = json.loads((SYNTHETIC / "calendar-intervals.json").read_text())
    prepared = PreparedPlan.from_export(data).normalized_data
    assert any(len(d["intervals"]["value"] or []) > 1 for c in prepared["calendars"] for d in c["weekdays"])
    assert any(c["parent_key"]["value"] for c in prepared["calendars"])
    # Exception intervals on real AB are also checked by R's binary-reader tests.
    bindings = json.loads((SYNTHETIC / "calendar-bindings.json").read_text())
    value = PreparedPlan.from_export(bindings).normalized_data
    assert value["tasks"][-1]["calendar_key"]["value"] != value["project"]["default_calendar_key"]["value"]
    assert any(r["calendar_key"]["value"] for r in value["resources"])


def test_quality_missing_getter_errors_are_preserved():
    data = json.loads((SYNTHETIC / "missing-getter-errors.json").read_text())
    value = PreparedPlan.from_export(data).normalized_data
    assert value["collections"]["tasks"]["status"] == "partial"
    t = value["tasks"][1]
    assert t["actual_start"] == {"value": None, "quality": "missing", "reason": "not_set"}
    assert t["duration"]["reason"].startswith("getter_failed:")
    assert t["task_mode"]["quality"] == "unsupported"


@pytest.mark.parametrize("corrupt", ["task_key", "count", "collection", "version", "field_reason", "nan", "null_zero"])
def test_invalid_export_is_rejected(full_export, corrupt):
    if corrupt == "task_key":
        full_export["tasks"][0]["task_key"] = "obj:0x12345"
    elif corrupt == "count":
        full_export["collections"]["tasks"]["count"] += 1
    elif corrupt == "collection":
        del full_export["assignments"]
    elif corrupt == "version":
        full_export["export_version"] = "v0"
    elif corrupt == "field_reason":
        full_export["tasks"][0]["start"] = {"value": None, "quality": "missing"}
    elif corrupt == "null_zero":
        full_export["tasks"][0]["start"] = {"value": None, "quality": "ok", "reason": None}
    else:
        full_export["project"]["bad"] = float("nan")
    with pytest.raises((ValueError, TypeError)):
        validate_export(full_export)


def test_prepared_load_rejects_changed_data(full_export):
    plan = PreparedPlan.from_export(full_export).to_dict()
    plan["normalized_data"]["tasks"][1]["name"] = "tampered"
    with pytest.raises(ValueError, match="prepared_hash_mismatch"):
        PreparedPlan(plan).validate()


def test_fixtures_manifest_integrity():
    manifest = json.loads((SYNTHETIC / "manifest.json").read_text())
    assert {"relations-all-types", "calendar-intervals", "calendar-bindings", "graph-invalid", "missing-getter-errors", "same-bytes-diff-names"} <= {r["id"] for r in manifest["fixtures"]}
    for row in manifest["fixtures"]:
        if "path" in row:
            raw = (SYNTHETIC / row["path"]).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == row["sha256"]
            assert len(raw) == row["size_bytes"]


def test_context_unified_settings_cli_overrides_and_no_secrets(tmp_path, monkeypatch):
    import env
    from plan_context import PlanContext
    # Credentials must never be consulted by the archive context.
    monkeypatch.setattr(env, "load_confluence_env", lambda *a, **k: pytest.fail("credentials requested"))
    monkeypatch.delenv("CONFLUENCE_TOKEN", raising=False)
    settings = env.load_settings()
    context = PlanContext.resolve(settings=settings, db=tmp_path / "state/test.sqlite", workvault=tmp_path / "vault", cache_dir=tmp_path / "cache")
    snapshot = context.snapshot()
    assert snapshot["sources"]["CACHE_DIR"] == "cli_override"
    assert snapshot["paths"]["db"] == str(tmp_path / "state/test.sqlite")
    assert snapshot["profiles"]["SUMMARY_PROFILE"]["status"] == "not_installed"  # stage 08
    assert "TOKEN" not in json.dumps(snapshot)
    assert context.mpp_reader == Path.home() / "USERTOOLS/MppReader"
    for kind in ("mpp", "zip"):
        limit = context.settings[{"mpp": "MPP_MAX_BYTES", "zip": "ZIP_MAX_BYTES"}[kind]]
        context.check_input_size(limit, kind=kind)
        with pytest.raises(ValueError, match="size_limit"):
            context.check_input_size(limit + 1, kind=kind)


@pytest.mark.parametrize("key,value", [("MPP_READ_TIMEOUT_SECONDS", "0"), ("HTTP_TIMEOUT_SECONDS", "86401"), ("HTTP_RETRY_LIMIT", "11"),
                                      ("MPP_MAX_BYTES", "-1"), ("ZIP_MAX_RATIO", "0"), ("ZIP_MAX_ENTRIES", "1.2"), ("NORMALIZATION_PROFILE", "../../bad")])
def test_settings_reject_invalid_ranges(key, value):
    from env import Settings, load_settings
    from plan_context import PlanContext
    import jsonschema
    settings = load_settings()
    with pytest.raises((ValueError, jsonschema.ValidationError)):
        PlanContext.resolve(settings=Settings({**settings.values, key: value}, settings.sources))


@pytest.mark.parametrize("key", ["MPP_READ_TIMEOUT_SECONDS", "HTTP_TIMEOUT_SECONDS", "HTTP_RETRY_LIMIT", "MPP_MAX_BYTES",
                                  "ZIP_MAX_BYTES", "ZIP_MAX_ENTRIES", "ZIP_MAX_UNPACKED_BYTES", "ZIP_MAX_RATIO"])
def test_settings_numeric_contract_boundaries(key):
    import jsonschema
    from env import Settings, load_settings
    from plan_context import PlanContext, SETTINGS_CONTRACT
    contract = json.loads(SETTINGS_CONTRACT.read_text())["properties"][key]
    settings = load_settings()
    for value in [contract["minimum"], contract["maximum"]]:
        resolved = PlanContext.resolve(settings=Settings({**settings.values, key: str(value)}, settings.sources))
        assert resolved.settings[key] == value
    for value in [contract["minimum"] - 1, contract["maximum"] + 1]:
        with pytest.raises((ValueError, jsonschema.ValidationError)):
            PlanContext.resolve(settings=Settings({**settings.values, key: str(value)}, settings.sources))
