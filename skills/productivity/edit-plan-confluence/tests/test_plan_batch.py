"""Batch API and CLI: freeze-all, sequential processing, policy, counts, identity."""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
import os
import subprocess
from pathlib import Path

import pytest

import plan_batch as pb
import plan_save as ps
from env import MpxjRuntime
from plan_context import PlanContext
from plan_receipt import batch_counts, batch_exit_code, validate_batch_receipt
from mofs_index.db import connect_durable
from mofs_index.plan import query as q, writer as w

pytestmark = pytest.mark.archive_integration
FIXTURES = Path(__file__).parent / "fixtures"
VERSIONS = {"reader": "read-mpp-v2", "mpxj": "16.4.0", "jpype": "1.7.1"}


def fake_runtime(**kwargs):
    return MpxjRuntime("/usr/bin/python3.9", VERSIONS)


def fake_export(source, **kwargs):
    if Path(source).read_bytes().startswith(b"broken"):
        raise ps.PlanSaveError("mpp_unreadable")
    export = json.loads((FIXTURES/"synthetic/relations-all-types.json").read_text())
    export["provenance"].update(sha256=hashlib.sha256(Path(source).read_bytes()).hexdigest(), size_bytes=Path(source).stat().st_size)
    return export


@pytest.fixture
def batch_case(tmp_path, monkeypatch):
    context = PlanContext.resolve(db=tmp_path/"state/index.sqlite", workvault=tmp_path/"WorkVault", cache_dir=tmp_path/"cache")
    sources = []
    for number in range(3):
        path = tmp_path/(str(number)+".mpp")
        path.write_bytes(b"different fixture bytes " + str(number).encode())
        sources.append(path)
    monkeypatch.setattr(pb, "select_mpxj_python", fake_runtime)
    monkeypatch.setattr(ps, "select_mpxj_python", fake_runtime)
    monkeypatch.setattr(ps, "run_export_full", fake_export)
    return context, sources


def create(case, **kwargs):
    context, sources = case
    result = pb.create_batch(context=context, **{"mpp": sources, "project_slug":"batch-project", "batch_id":"test", **kwargs})
    validate_batch_receipt(result)
    return result


def test_freeze_all_before_first_reader_and_mutated_second_source(batch_case, monkeypatch):
    context, sources = batch_case
    old = [p.read_bytes() for p in sources]
    calls = []
    def reader(source, **kwargs):
        c = connect_durable(context.db)
        try:
            assert q.get_import_batch(c, "test")["inputs_frozen_at"]
            rows = q.get_batch_items(c, "test")
            assert len(rows) == 3 and all(row["frozen_locator"] for row in rows)
            assert sum(row["status"] == "processing" for row in rows) == 1
        finally:
            c.close()
        calls.append(Path(source).read_bytes())
        if len(calls) == 1:
            sources[1].write_bytes(b"changed while first reader runs")
            sources[2].unlink()
        return fake_export(source)
    monkeypatch.setattr(ps, "run_export_full", reader)
    result = create(batch_case)
    assert result["exit_code"] == 0, result
    assert calls == old
    assert result["counts"]["saved"] == result["counts"]["total"] == 3
    assert result["counts"]["saved_with_warnings"] == 3
    assert len({item["snapshot_id"] for item in result["items"]}) == 3


@pytest.mark.parametrize("policy,expected", [("continue", ["saved_with_warnings", "failed", "saved_with_warnings"]),
                                             ("stop", ["saved_with_warnings", "failed", "not_started"])])
def test_corrupt_middle_continue_stop_freeze_whole_list(batch_case, policy, expected):
    context, sources = batch_case
    sources[1].write_bytes(b"broken MPP")
    result = create(batch_case, on_error=policy)
    assert result["exit_code"] == 6 and [i["status"] for i in result["items"]] == expected, result
    assert result["inputs_frozen_at"]
    c = connect_durable(context.db)
    assert all(r["frozen_locator"] for r in q.get_batch_items(c, "test"))
    c.close()
    errors = pb.show_batch("test", context=context, view="errors")
    assert [i["item_id"] for i in errors["result"]["items"]] == (["2"] if policy == "continue" else ["2", "3"])


def test_infrastructure_after_success_has_priority_and_retains_counts(batch_case, monkeypatch):
    calls = []
    def reader(source, **kwargs):
        calls.append(str(source))
        if len(calls) == 2:
            raise OSError("shared archive is unavailable")
        return fake_export(source)
    monkeypatch.setattr(ps, "run_export_full", reader)
    result = create(batch_case)
    assert result["exit_code"] == 5 and result["status"] == "infrastructure_stopped", result
    assert result["counts"]["saved"] == 1 and result["counts"]["not_started"] == 1
    assert len(calls) == 2


def test_duplicates_within_across_batches_and_same_names_different_bytes(batch_case):
    context, sources = batch_case
    sources[1].write_bytes(sources[0].read_bytes())
    same_name = sources[2].parent/"nested"/sources[0].name
    same_name.parent.mkdir(); same_name.write_bytes(b"other content same name")
    first = create((context, [sources[0], sources[1], same_name]))
    assert first["exit_code"] == 0, first
    assert first["counts"]["saved"] == 2 and first["counts"]["unchanged"] == 1
    second = create((context, [sources[0]]), batch_id="another")
    assert second["counts"]["unchanged"] == 1
    c = connect_durable(context.db)
    assert c.execute("SELECT count(*) FROM plan_snapshot").fetchone()[0] == 2
    assert c.execute("SELECT count(*) FROM plan_import_item").fetchone()[0] == 4
    assert len({i["item_id"] for name in ("test", "another") for i in q.get_batch_items(c, name)}) == 4
    c.close()


def test_structural_errors_precede_arrivals(batch_case, tmp_path):
    context, sources = batch_case
    path = tmp_path/"bad.json"
    path.write_text(json.dumps({"schema_version":1, "items":[{"item_id":"a", "path":str(sources[0]), "project_slug":"p", "bad":True}]}))
    result = pb.create_batch(context=context, manifest=path)
    assert result["exit_code"] == 2 and result["batch_id"] is None
    assert not context.db.exists()
    assert pb.create_batch(context=context, manifest=path, project_slug="forbidden")["exit_code"] == 2
    assert pb.create_batch(context=context, mpp=sources, inbox=tmp_path, project_slug="p")["exit_code"] == 2


def test_existing_batch_same_request_only_state_changed_manifest_conflicts(batch_case, tmp_path, monkeypatch):
    context, sources = batch_case
    path = tmp_path/"manifest.json"
    doc = {"schema_version":1, "label":"Label", "items":[{"item_id":str(i), "path":p.name, "project_slug":"batch-project"} for i,p in enumerate(sources)]}
    path.write_text(json.dumps(doc))
    first = pb.create_batch(context=context, manifest=path, batch_id="test")
    assert first["exit_code"] == 0, first
    before = {p.name:p.read_bytes() for p in (context.workvault/"_plan-receipts").rglob("*.json")}
    monkeypatch.setattr(pb, "_effective_context", lambda *a: pytest.fail("new defaults on repeat"))
    monkeypatch.setattr(pb, "_project_defaults", lambda *a: pytest.fail("new lineage on repeat"))
    path.write_text(json.dumps(doc, sort_keys=True, indent=4))
    for p in sources: p.unlink()
    assert pb.create_batch(context=context, manifest=path, batch_id="test") == first
    assert before == {p.name:p.read_bytes() for p in (context.workvault/"_plan-receipts").rglob("*.json")}
    doc["label"] = "Changed"
    path.write_text(json.dumps(doc))
    conflict = pb.create_batch(context=context, manifest=path, batch_id="test")
    assert conflict["exit_code"] == 4 and conflict["error"]["code"] == "batch_manifest_conflict"


def test_inbox_late_file_excluded_diagnostics_and_sources_preserved(batch_case, tmp_path, monkeypatch):
    context, sources = batch_case
    inbox = tmp_path/"Inbox"; inbox.mkdir()
    for name in ("Я.mpp", "A.mpp"):
        shutil.copy2(sources[0], inbox/name)
    (inbox/"~$open.mpp").write_bytes(b"open")
    (inbox/"link.mpp").symlink_to(sources[0])
    def reader(source, **kwargs):
        (inbox/"later.mpp").write_bytes(b"late")
        return fake_export(source)
    monkeypatch.setattr(ps, "run_export_full", reader)
    result = pb.create_batch(context=context, inbox=inbox, project_slug="batch-project", batch_id="inbox")
    assert result["exit_code"] == 0 and result["counts"]["total"] == 2, result
    c = connect_durable(context.db)
    rows = q.get_batch_items(c, "inbox")
    assert [r["original_name"] for r in rows] == ["A.mpp", "Я.mpp"]
    assert len(json.loads(q.get_import_batch(c, "inbox")["context_json"])["diagnostics"]) == 2
    c.close()
    assert (inbox/"A.mpp").read_bytes() == sources[0].read_bytes()
    assert (inbox/"Я.mpp").exists() and (inbox/"later.mpp").exists()


def test_receipt_balance_and_priority():
    items = [{"status":s} for s in ("saved", "saved_with_warnings", "unchanged", "failed", "needs_decision", "not_started")]
    counts = batch_counts(items)
    assert counts == {"total":6,"saved":2,"saved_with_warnings":1,"unchanged":1,"failed":1,"needs_decision":1,"not_started":1}
    assert batch_exit_code(counts) == 6
    assert batch_exit_code(counts, infrastructure=True) == 5
    assert batch_exit_code(counts, infrastructure=True, conflict=True) == 4
    assert batch_exit_code(counts, infrastructure=True, conflict=True, argument_error=True) == 2
    assert batch_exit_code(batch_counts(items[:3])) == 0


def test_missing_input_and_expected_hash_known_before_first_parse(batch_case, tmp_path, monkeypatch):
    context, sources = batch_case
    sources[1].unlink()
    doc={"schema_version":1,"items":[{"item_id":str(i),"path":str(p),"project_slug":"batch-project"} for i,p in enumerate(sources)]}
    doc["items"][2]["expected_sha256"]="0"*64
    path=tmp_path/"hash.json"; path.write_text(json.dumps(doc))
    calls=[]
    def reader(source,**kwargs):
        c=connect_durable(context.db)
        batch=q.get_import_batch(c,"hash"); rows=q.get_batch_items(c,"hash"); c.close()
        assert batch["inputs_frozen_at"] and rows[1]["error_code"]=="input_missing" and rows[2]["error_code"]=="source_hash_mismatch"
        calls.append(source)
        return fake_export(source)
    monkeypatch.setattr(ps,"run_export_full",reader)
    result=pb.create_batch(context=context,manifest=path,batch_id="hash")
    assert result["exit_code"] == 6 and result["counts"]["saved"]==1 and result["counts"]["failed"]==2, result
    assert len(calls)==1


def test_foreign_lineage_is_local_failure_and_new_mpp_needs_no_decision(batch_case, tmp_path):
    context,sources=batch_case
    from plan_archive import resolve_plan_binding
    c=connect_durable(context.db)
    from mofs_index.plan.migrate import ensure_plan_schema
    ensure_plan_schema(c)
    foreign=resolve_plan_binding(None,"other-project",conn=c)["lineage_id"]; c.close()
    doc={"schema_version":1,"items":[{"item_id":str(i),"path":str(p),"project_slug":"batch-project"} for i,p in enumerate(sources)]}
    doc["items"][1]["lineage_id"]=foreign
    path=tmp_path/"foreign.json"; path.write_text(json.dumps(doc))
    result=pb.create_batch(context=context,manifest=path)
    assert result["exit_code"]==6 and result["counts"]["saved"]==2 and result["counts"]["needs_decision"]==0, result
    assert result["items"][1]["error"]["code"]=="binding_conflict"


def test_same_bytes_different_timezone_and_profile_new_scope(batch_case, monkeypatch, tmp_path):
    from dataclasses import replace
    context,sources=batch_case
    first=create((context,sources[:1]))
    second=create((context,sources[:1]),batch_id="zone",timezone_hint="Europe/Moscow")
    assert first["exit_code"]==second["exit_code"]==0 and first["items"][0]["snapshot_id"] != second["items"][0]["snapshot_id"]
    profiles=tmp_path/"profiles"; profiles.mkdir()
    profile=json.loads((pb.PROFILES/"normalization-v1.json").read_text());profile["version"]="1.0.1"
    (profiles/"normalization-v1.json").write_text(json.dumps(profile))
    monkeypatch.setattr(pb,"PROFILES",profiles);monkeypatch.setattr(ps,"PROFILES",profiles)
    import plan_context
    monkeypatch.setattr(plan_context,"PROFILES",profiles)
    third=create((context,sources[:1]),batch_id="profile")
    assert third["exit_code"]==0 and third["items"][0]["snapshot_id"] not in (first["items"][0]["snapshot_id"],second["items"][0]["snapshot_id"]), third


def test_fixtures_batch_hashes_and_manifest_cases(fixtures_dir):
    from plan_manifest import ManifestError, load_manifest, scan_inbox
    root=fixtures_dir/"batch"
    manifest=json.loads((root/"fixtures-manifest.json").read_text())
    for name,info in manifest["files"].items():
        assert hashlib.sha256((root/name).read_bytes()).hexdigest()==info["sha256"]
    assert len(load_manifest(root/"continue.json")["items"])==3
    assert load_manifest(root/"stop.json")["on_error"]=="stop"
    for name in ("invalid-null.json","duplicate-ids.json"):
        with pytest.raises(ManifestError): load_manifest(root/name)
    assert [Path(p).name for p in scan_inbox(root/"Inbox")[0]]==["A.mpp"]


@pytest.mark.mpp_fixtures
@pytest.mark.parametrize("input_mode", ["mpp", "manifest", "inbox", "named-risks"])
def test_real_batch_cli_native_copies(tmp_path, request, input_mode):
    skill = Path(__file__).resolve().parents[1]
    sources = json.loads((FIXTURES/"real/manifest.json").read_text())["fixtures"]
    ids = ("D-risks", "E") if input_mode == "named-risks" else ("E", "F")
    copies = []
    provenance = []
    inbox = tmp_path/"Inbox"; inbox.mkdir()
    for case in ids:
        fixture = next(f for f in sources if f["id"] == case)
        origin = Path(fixture["origin"])
        assert hashlib.sha256(origin.read_bytes()).hexdigest() == fixture["sha256"]
        assert origin.stat().st_size == fixture["size_bytes"]
        target = inbox/(case+".mpp"); shutil.copy2(origin, target)
        assert hashlib.sha256(target.read_bytes()).hexdigest() == fixture["sha256"]
        copies.append(target)
        provenance.append({**fixture, "copy": str(target)})
    guard = tmp_path/"guard"; guard.mkdir()
    (guard/"sitecustomize.py").write_text('''import sys,socket,sqlite3,os,importlib.abc
from pathlib import Path
class DenyConfluence(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname.split('.')[0] in ('conf_client','pipeline'):
   raise NotImplementedError('Confluence import forbidden on batch')
sys.meta_path.insert(0,DenyConfluence())
def denied(*a,**k): raise AssertionError('network forbidden on batch')
socket.socket.connect=denied
socket.create_connection=denied
original=sqlite3.connect
def connect(path,*a,**k):
 if str(path) != ':memory:':
  candidate=Path(str(path).removeprefix('file:').split('?')[0]).resolve()
  assert Path(os.environ['BATCH_TEST_ROOT']) in candidate.parents
 return original(path,*a,**k)
sqlite3.connect=connect
''')
    env = dict(os.environ)
    env.pop("CONFLUENCE_TOKEN", None)
    env["PYTHONPATH"] = str(guard)+os.pathsep+env.get("PYTHONPATH", "")
    env["BATCH_TEST_ROOT"] = str(tmp_path)
    env["MPXJ_PYTHON"] = "/usr/bin/python3.9"
    cli = ["/usr/bin/python3", str(skill/"scripts/cli.py"), "--db", str(tmp_path/"state/index.sqlite"),
           "--workvault", str(tmp_path/"WorkVault"), "--cache-dir", str(tmp_path/"cache")]
    command = [*cli,"batch","save","--batch-id","real"]
    if input_mode == "manifest":
        manifest=tmp_path/"batch.json"
        manifest.write_text(json.dumps({"schema_version":1,"items":[{"item_id":case,"path":str(path),"project_slug":"batch-project"} for case,path in zip(ids,copies)]}))
        command += ["--manifest",str(manifest)]
    elif input_mode == "inbox":
        command += ["--inbox",str(inbox),"--project-slug","batch-project"]
    else:
        command += ["--project-slug","batch-project"]
        for path in copies: command += ["--mpp",str(path)]
    proc = subprocess.run(command,capture_output=True,text=True,env=env,timeout=180)
    result = json.loads(proc.stdout)
    assert proc.returncode == 0, (result,proc.stderr)
    validate_batch_receipt(result)
    assert result["counts"]["saved"] == 2 and result["published"] is False
    assert len({item["snapshot_id"] for item in result["items"]}) == 2
    context = PlanContext.resolve(db=tmp_path/"state/index.sqlite",workvault=tmp_path/"WorkVault",cache_dir=tmp_path/"cache")
    c = connect_durable(context.db)
    rows = q.get_batch_items(c,"real")
    evidence=[]
    for case,row in zip(ids,rows):
        saved = json.loads((context.workvault/"_plan-receipts"/row["operation_id"]/"save.json").read_text())
        if case in ("E","F"):
            assert (saved["task_count"],saved["dependency_count"]) == ({"E":(78,84),"F":(86,93)}[case])
            assert saved["display_task_count"] == saved["task_count"]-1
        w.verify_snapshot(c,saved["snapshot_id"])
        snapshot=q.get_snapshot(c,saved["snapshot_id"])
        artifact=q.get_artifact(c,snapshot["source_artifact_id"])
        assert hashlib.sha256(Path(artifact["path"]).read_bytes()).hexdigest() == saved["source"]["sha256"]
        normalized=q.find_artifact_by_hash(c,snapshot["normalized_data_sha256"])
        assert Path(w.verify_artifact(c,normalized["artifact_id"])).read_bytes() == snapshot["source_json"].encode()
        events=q.get_operation_events(c,row["operation_id"])
        metrics=[json.loads(e["detail"]) for e in events if e["event_kind"] == "save_metrics"][-1]
        assert metrics["counters"]["MPXJ_read"] == 1
        started=next(e["created_at"] for e in events if e["event_kind"] == "batch_processing")
        assert started >= result["inputs_frozen_at"]
        evidence.append({"case":case,"receipt":saved,"metrics":metrics,
            "versions":json.loads(snapshot["source_json"])["source_identity"],"events":events})
    # Persist a populated baseline, then a new batch with identical bytes. This
    # verifies both deduplication and exact preservation of preexisting selection.
    snapshot=q.get_snapshot(c,result["items"][0]["snapshot_id"])
    w.select_snapshot_baseline(c,snapshot["lineage_id"],snapshot["snapshot_id"],is_explicit=True,basis="acceptance")
    w.select_plan_baseline(c,snapshot["plan_id"],snapshot["snapshot_id"],0,is_explicit=True,basis="acceptance")
    tables=("plan_baseline_selection","plan_snapshot_selection","plan_publication","plan_publication_snapshot")
    before={table:[tuple(row) for row in c.execute("SELECT * FROM "+table+" ORDER BY 1")] for table in tables}
    c.close()
    repeat = command.copy(); repeat[repeat.index("real")] = "new-arrival"
    warm = subprocess.run(repeat,capture_output=True,text=True,env=env,timeout=180)
    warm_result=json.loads(warm.stdout)
    assert warm.returncode == 0 and warm_result["counts"]["unchanged"] == 2, (warm_result,warm.stderr)
    c=connect_durable(context.db)
    after={table:[tuple(row) for row in c.execute("SELECT * FROM "+table+" ORDER BY 1")] for table in tables}
    assert after == before
    warm_metrics=[]
    for row in q.get_batch_items(c,"new-arrival"):
        metric=[json.loads(e["detail"]) for e in q.get_operation_events(c,row["operation_id"]) if e["event_kind"]=="save_metrics"][-1]
        assert metric["counters"]["MPXJ_read"] == 0 and metric["counters"]["cache_hit"] == 1
        warm_metrics.append(metric)
    c.close()
    corrupt_batches=[]
    if input_mode == "mpp":
        broken=tmp_path/"corrupt.mpp"; shutil.copy2(FIXTURES/"batch/corrupt.mpp",broken)
        for policy in ("continue","stop"):
            failure_command=[*cli,"batch","save","--batch-id","real-"+policy,"--on-error",policy,
                "--project-slug","batch-project","--mpp",str(copies[0]),"--mpp",str(broken),"--mpp",str(copies[1])]
            failed=subprocess.run(failure_command,capture_output=True,text=True,env=env,timeout=180)
            failed_result=json.loads(failed.stdout)
            validate_batch_receipt(failed_result)
            assert failed.returncode==6 and failed_result["counts"]["failed"]==1, (failed_result,failed.stderr)
            assert failed_result["counts"]["unchanged"]==(2 if policy=="continue" else 1)
            assert failed_result["counts"]["not_started"]==(0 if policy=="continue" else 1)
            c=connect_durable(context.db)
            assert all(row["frozen_locator"] for row in q.get_batch_items(c,"real-"+policy)); c.close()
            corrupt_batches.append({"command":failure_command,"rc":failed.returncode,"receipt":failed_result})
        show_command=[*cli,"batch","show","--batch-id","real-stop","--view","errors"]
        shown=subprocess.run(show_command,capture_output=True,text=True,env=env,timeout=30)
        query=json.loads(shown.stdout)
        assert shown.returncode==0 and [item["status"] for item in query["result"]["items"]]==["failed","not_started"]
        for path in copies:path.unlink()
        resume_command=[*cli,"batch","resume","--batch-id","real"]
        resumed=subprocess.run(resume_command,capture_output=True,text=True,env=env,timeout=30)
        resumed_result=json.loads(resumed.stdout)
        assert resumed.returncode==0 and resumed_result["items"]==result["items"], (resumed_result,resumed.stderr)
        same=subprocess.run(command,capture_output=True,text=True,env=env,timeout=30)
        assert same.returncode==0 and json.loads(same.stdout)["items"]==result["items"]
    report_root=getattr(request.config,"_acceptance_root",tmp_path)/"reports"
    report_root.mkdir(exist_ok=True)
    (report_root/("batch-real-"+input_mode+".json")).write_text(json.dumps({"input_mode":input_mode,
        "command":command,"rc":proc.returncode,"receipt":result,"fixtures":provenance,"cases":evidence,
        "repeat_command":repeat,"repeat_rc":warm.returncode,"repeat_receipt":warm_result,"repeat_metrics":warm_metrics,
        "corrupt_batches":corrupt_batches,
        "baseline_before":before,"baseline_after":after,"client_import":"forbidden","network":"forbidden","POST":0,"PUT":0},ensure_ascii=False,indent=2))


@pytest.mark.parametrize("arguments", [[], ["--mpp","a","--manifest","b"], ["--inbox","x"],
    ["--manifest","x","--project-slug","forbidden"], ["--mpp","x","--project-slug","p","--on-error","bad"]])
def test_batch_cli_argument_errors_single_json(tmp_path, arguments):
    skill=Path(__file__).resolve().parents[1]
    command=["/usr/bin/python3",str(skill/"scripts/cli.py"),"--db",str(tmp_path/"state/index.sqlite"),
        "--workvault",str(tmp_path/"WorkVault"),"--cache-dir",str(tmp_path/"cache"),"batch","save",*arguments]
    proc=subprocess.run(command,capture_output=True,text=True,timeout=20)
    result=json.loads(proc.stdout)
    assert proc.returncode == result["exit_code"] == 2
    validate_batch_receipt(result)
    assert not (tmp_path/"state/index.sqlite").exists()
