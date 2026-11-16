"""Independent cache invalidation, corruption and actual single-read evidence."""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from plan_cache import ParseCache, RepresentationCache
from prepared_plan import PreparedPlan

pytestmark = pytest.mark.unit
FIXTURES = Path(__file__).parent / "fixtures/synthetic"


@pytest.fixture
def cached_input(tmp_path):
    source = tmp_path / "durable/input.mpp"
    source.parent.mkdir()
    shutil.copy2(FIXTURES / "relations-all-types.mpp", source)
    export = json.loads((FIXTURES / "relations-all-types.json").read_text())
    p = export["provenance"]
    material = ParseCache.material(p["sha256"], reader={k:p[k] for k in ("reader", "mpxj", "jpype")}, export_version=export["export_version"])
    assert hashlib.sha256(source.read_bytes()).hexdigest() == p["sha256"]
    return source, export, material


def test_independent_cache_keys(cached_input, tmp_path):
    source, export, material = cached_input
    parse = ParseCache(tmp_path / "cache")
    calls = []
    def reader(path):
        calls.append(path)
        return copy.deepcopy(export)
    parsed = parse.get_or_parse(source, material, parser=reader)
    plan = PreparedPlan.from_export(parsed)
    rep = RepresentationCache(tmp_path / "cache")
    key = rep.material(plan.semantic_hash, converter_version="converter-1", rules_revision="rules-1", plugin_profile={"id":"test", "sha":"1"}, template_parameters={"title":"test"})
    assert rep.get_or_build(plan, key, lambda p: {"tasks": [1]}) == {"tasks": [1]}
    assert rep.get_or_build(plan, key, lambda p: pytest.fail("rebuilt on cache hit")) == {"tasks": [1]}
    for field, value in [("converter_version", "converter-2"), ("rules_revision", "rules-2"), ("plugin_profile", {"id":"v2"}), ("template_parameters", {"title":"changed"})]:
        changed = {**key, field: value}
        assert rep.key(changed) != rep.key(key)
        assert rep.load(changed) is None
        assert parse.get_or_parse(source, material, parser=reader)
    assert len(calls) == 1
    for field,value in [("reader", {"reader":"new"}), ("export_version", "new"), ("parameters", {"option":"changed"})]:
        changed = {**material, field:value}
        assert parse.key(changed) != parse.key(material)
        assert parse.load(changed) is None


@pytest.mark.parametrize("kind", ["truncated", "checksum", "complete", "version", "payload_missing_field", "count", "reader"])
def test_corrupt_cache_rebuilds_from_verified_source(cached_input, tmp_path, kind):
    source, export, material = cached_input
    cache = ParseCache(tmp_path / "cache")
    cache.store(material, export)
    path = cache.path(material)
    if kind == "truncated":
        path.write_text('{"cache_version":1')
    else:
        doc = json.loads(path.read_text())
        if kind == "checksum":
            doc["payload"]["tasks"][0]["name"] = "corrupt"
        elif kind == "complete":
            doc["complete"] = False
        elif kind == "version":
            doc["cache_version"] += 1
        else:
            if kind == "payload_missing_field":
                del doc["payload"]["assignments"]
            elif kind == "count":
                doc["payload"]["collections"]["tasks"]["count"] += 10
            else:
                doc["payload"]["provenance"]["reader"] = "other"
            from prepared_plan import canonical_bytes, fingerprint
            doc["payload_sha256"] = fingerprint(doc["payload"])
            doc["payload_bytes"] = len(canonical_bytes(doc["payload"]))
        path.write_text(json.dumps(doc))
    called = []
    assert cache.get_or_parse(source, material, parser=lambda p: called.append(p) or export) == export
    assert called == [source]
    assert cache.load(material) == export


def test_corrupt_source_is_not_read_or_reused(cached_input, tmp_path):
    source, export, material = cached_input
    cache = ParseCache(tmp_path / "cache")
    cache.store(material, export)
    source.write_bytes(b"changed durable source")
    with pytest.raises(ValueError, match="source_integrity_failed"):
        cache.get_or_parse(source, material, parser=lambda p: pytest.fail("reader must not run"))


def test_cache_deletion_does_not_delete_durable_data(cached_input, tmp_path):
    source, export, material = cached_input
    durable = source.parent / "prepared.json"
    durable.write_text(json.dumps(PreparedPlan.from_export(export).to_dict()))
    cache = ParseCache(tmp_path / "cache")
    cache.store(material, export)
    shutil.rmtree(tmp_path / "cache")
    PreparedPlan(json.loads(durable.read_text())).validate()
    assert hashlib.sha256(source.read_bytes()).hexdigest() == material["source_sha256"]
    assert cache.load(material) is None


def test_atomic_failure_preserves_previous_entry(cached_input, tmp_path, monkeypatch):
    source, export, material = cached_input
    cache = ParseCache(tmp_path / "cache")
    cache.store(material, export)
    import plan_cache
    def fail(*a, **k):
        raise OSError("simulated write failure before rename")
    with monkeypatch.context() as patch:
        patch.setattr(plan_cache.os, "replace", fail)
        with pytest.raises(OSError):
            cache.store(material, export)
    assert cache.load(material) == export
    assert not list(cache.root.glob(".pending-*"))


def test_concurrent_atomic_writes(cached_input, tmp_path):
    _, export, material = cached_input
    cache = ParseCache(tmp_path / "cache")
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(lambda _: cache.store(material, export), range(9)))
    assert cache.load(material) == export
    assert not list(cache.root.glob(".pending-*"))


def test_representation_corruption_rebuilds(cached_input, tmp_path):
    _, export, _ = cached_input
    plan = PreparedPlan.from_export(export)
    cache = RepresentationCache(tmp_path / "cache")
    key = cache.material(plan.semantic_hash, converter_version="1", rules_revision="1", plugin_profile="fixture-profile-sha", template_parameters={})
    cache.get_or_build(plan, key, lambda p: ["expected"])
    cache.path(key).write_text('{"unfinished":true}')
    assert cache.get_or_build(plan, key, lambda p: ["expected"]) == ["expected"]
    with pytest.raises(ValueError, match="source_mismatch"):
        cache.get_or_build(plan, {**key, "normalized_sha256": "a" * 64}, lambda p: pytest.fail())


@pytest.mark.mpp_fixtures
def test_real_parse_cache_one_read_same_bytes_different_names(tmp_path, request):
    from env import select_mpxj_python
    import subprocess
    from plan_context import PlanContext
    context = PlanContext.resolve(db=tmp_path / "state/index.sqlite", workvault=tmp_path / "WorkVault", cache_dir=tmp_path / "cache")
    runtime = select_mpxj_python()
    original = FIXTURES / "relations-all-types.mpp"
    source = tmp_path / "one.mpp";other = tmp_path / "other/renamed.mpp";other.parent.mkdir()
    shutil.copy2(original, source);shutil.copy2(original, other)
    cache = ParseCache(context.cache_dir, counters=request.config._acceptance_counters)
    key = cache.material(hashlib.sha256(source.read_bytes()).hexdigest(), reader=runtime.versions, export_version="full-export-v2")
    actual_read_events = []
    def parse(path):
        # Instrument the actual MPXJ boundary in a separate interpreter; the
        # fixture is not a mock/project XML and the counter comes from reader.read.
        code = "import sys,json;sys.path.insert(0,sys.argv[1]);from plan_export import export_full;print(json.dumps(export_full(sys.argv[2])))"
        result = subprocess.run([runtime.python, "-c", code, str(context.mpp_reader), str(path)], capture_output=True, text=True, timeout=180)
        assert result.returncode == 0, result.stderr
        value = json.loads(result.stdout[result.stdout.index("{"):])
        actual_read_events.append(value["telemetry"]["MPXJ_read"])
        return value
    before = dict(cache.counters)
    first = PreparedPlan.from_export(cache.get_or_parse(source, key, parser=parse))
    second = PreparedPlan.from_export(cache.get_or_parse(other, key, parser=parse))
    assert actual_read_events == [1]
    assert cache.counters["MPXJ_read"] - before["MPXJ_read"] == 1
    assert cache.counters["cache_hit"] - before["cache_hit"] == 1
    assert first.semantic_bytes() == second.semantic_bytes()
    assert second.to_dict()["provenance"]["original_name"] == "renamed.mpp"
    cache.path(key).write_bytes(b"corruption")
    third = PreparedPlan.from_export(cache.get_or_parse(other, key, parser=parse))
    assert actual_read_events == [1, 1]
    assert first.semantic_hash == third.semantic_hash
    root = getattr(request.config, "_acceptance_root", None)
    if root is not None:
        evidence = {"cold_MPXJ_read": 1, "repeat_MPXJ_read": 0,
                    "corruption_rebuild_MPXJ_read": 1, "boundary_counts": actual_read_events,
                    "python": runtime.python, "versions": runtime.versions,
                    "source_sha256": key["source_sha256"], "semantic_sha256": first.semantic_hash,
                    "scope": "new prepared branch only; legacy calendar/CSV paths are stage 08"}
        (root / "reports/cache-read-evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")


def test_derived_representation_cache_profile_template_root_and_corruption(stage08_export,stage08_profile,tmp_path,monkeypatch,request):
    from prepared_plan import PreparedPlan
    from mpp_convert import representation_bytes
    import mpp_convert
    p=PreparedPlan.from_export(stage08_export,timezone_hint='Europe/Moscow')
    counters={}
    cache=RepresentationCache(tmp_path/'cache',counters=counters)
    first=cache.convert_prepared(p,plugin_profile=stage08_profile)
    assert counters=={'cache_miss':1}
    builder=mpp_convert.convert_prepared_plan
    def no_build(*a,**k):raise AssertionError('derived cache hit must not rebuild')
    monkeypatch.setattr(mpp_convert,'convert_prepared_plan',no_build)
    again=cache.convert_prepared(p,plugin_profile=stage08_profile)
    assert representation_bytes(first)==representation_bytes(again) and counters['cache_hit']==1
    monkeypatch.setattr(mpp_convert,'convert_prepared_plan',builder)
    path=next(cache.root.glob('*.json'));path.write_bytes(b'truncated')
    assert representation_bytes(cache.convert_prepared(p,plugin_profile=stage08_profile))==representation_bytes(first)
    assert counters['cache_miss']==2
    stage08_profile.document['version']='unit-v2'
    cache.convert_prepared(p,plugin_profile=stage08_profile)
    assert counters['cache_miss']==3
    cache.convert_prepared(p,plugin_profile=stage08_profile,root_task_key='root')
    assert counters['cache_miss']==4
    cache.convert_prepared(p,plugin_profile=stage08_profile,template_json={'eventsData':[],'macroConfig':{'x':1}})
    assert counters['cache_miss']==5
    root=getattr(request.config,'_acceptance_root',tmp_path)
    (root/'reports/stage08-cache.json').write_text(json.dumps({'counters':counters,'MPXJ_read':0,'source':'pure prepared conversion; reader forbidden by separate instrumentation test'},indent=2))
