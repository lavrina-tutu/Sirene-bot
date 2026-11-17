"""Тесты typed query API (P3.RAG.1-4/6, R-023/R-026, AC-124/125/126/129)."""
from __future__ import annotations

import json

import pytest

from mofs_index.db import connect, initialize
from mofs_index.plan.migrate import ensure_plan_schema
from mofs_index.plan import writer as w
from mofs_index.plan import query as q


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "index.sqlite"
    c = connect(db_path, durable=True)
    initialize(c)
    ensure_plan_schema(c)
    yield c
    c.close()


def _publish_json(conn, plan_id, lineage_id, version, body, filename="gantt.json", tmp_path=None):
    import hashlib
    raw = json.dumps(body).encode("utf-8")
    sha = hashlib.sha256(raw).hexdigest()
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir(exist_ok=True)
    path = artifact_dir / f"{sha}.json"
    path.write_text(json.dumps(body), encoding="utf-8")
    artifact_id = w.record_artifact(conn, sha, "downloaded_json", str(path), size_bytes=len(raw))
    return w.record_publication(conn, w.PublicationSpec(
        plan_id=plan_id, lineage_id=lineage_id, artifact_id=artifact_id,
        source_namespace="confluence", attachment_id="att1", attachment_version=version,
        page_id="p1", filename=filename, raw_sha256=sha,
    ))


def test_resolve_plan_found_and_not_found(conn):
    plan_id = w.ensure_plan(conn, "zd", name="zd")
    res = q.resolve_plan(conn, "zd")
    assert res["plan_id"] == plan_id
    assert "receipt" in res

    missing = q.resolve_plan(conn, "nonexistent")
    assert missing["result_class"] == "insufficient_data"


def test_diff_versions_identical_content(conn, tmp_path):
    plan_id = w.ensure_plan(conn, "zd")
    lineage_id = w.ensure_lineage(conn, plan_id, "confluence", page_id="p1")
    body = {"eventsData": [{"id": 1, "startDate": "2026-01-01T09:00:00", "endDate": "2026-01-10T18:00:00", "duration": 9.0, "children": []}], "dependenciesData": []}
    pub1 = _publish_json(conn, plan_id, lineage_id, 1, body, tmp_path=tmp_path)
    pub2 = _publish_json(conn, plan_id, lineage_id, 2, body, tmp_path=tmp_path)

    d = q.diff_versions(conn, plan_id,
                         {"kind": "publication", "publication_id": pub1},
                         {"kind": "publication", "publication_id": pub2})
    assert d["content_identical"] is True
    assert d["receipt"]["hash_a"] == d["receipt"]["hash_b"]


def test_diff_versions_detects_removed_link_and_finish_shift(conn, tmp_path):
    plan_id = w.ensure_plan(conn, "zd")
    lineage_id = w.ensure_lineage(conn, plan_id, "confluence", page_id="p1")
    body_a = {
        "eventsData": [{"id": 1, "startDate": "2026-01-01T09:00:00", "endDate": "2026-01-10T18:00:00", "duration": 9.0, "children": [
            {"id": 2, "startDate": "2026-01-01T09:00:00", "endDate": "2026-01-05T18:00:00", "duration": 4.0, "children": []},
        ]}],
        "dependenciesData": [{"from": 1, "to": 2}],
    }
    body_b = {
        "eventsData": [{"id": 1, "startDate": "2026-01-01T09:00:00", "endDate": "2026-01-24T18:00:00", "duration": 23.0, "children": [
            {"id": 2, "startDate": "2026-01-01T09:00:00", "endDate": "2026-01-05T18:00:00", "duration": 4.0, "children": []},
        ]}],
        "dependenciesData": [],
    }
    pub1 = _publish_json(conn, plan_id, lineage_id, 1, body_a, tmp_path=tmp_path)
    pub2 = _publish_json(conn, plan_id, lineage_id, 2, body_b, tmp_path=tmp_path)

    d = q.diff_versions(conn, plan_id,
                         {"kind": "publication", "publication_id": pub1},
                         {"kind": "publication", "publication_id": pub2})
    assert d["content_identical"] is False
    assert d["links_removed"] == []  # No identity evidence for positional IDs.
    assert d["unmatched_entities"]["dependency"]["from"] == [{"from":1,"to":2}]
    assert d["root"]["finish_delta_calendar_days"] is None


def test_diff_versions_representation_mismatch_is_explicit(conn, tmp_path):
    plan_id = w.ensure_plan(conn, "zd")
    line = w.ensure_lineage(conn, plan_id, 'test', page_id='p1')
    pub1 = _publish_json(conn,plan_id,line,1,{'eventsData':[]},tmp_path=tmp_path)
    snap = w.ingest_snapshot(conn,w.SnapshotSpec(plan_id=plan_id,representation='mpp'))
    d = q.diff_versions(conn,plan_id,{'kind':'publication','publication_id':pub1}, {'kind':'snapshot','snapshot_id':snap})
    assert d['result_class']=='representation_mismatch' and d['exit_code']==4


def test_task_history_by_uid_and_caveat(conn):
    plan_id = w.ensure_plan(conn, "zd")
    lineage_id = w.ensure_lineage(conn, plan_id, "mpp_archive")
    spec_a = w.SnapshotSpec(
        plan_id=plan_id, lineage_id=lineage_id, representation="mpp",
        tasks=(w.TaskVersionSpec(task_key="t744", uid="744", name="Task", finish_raw="2026-11-12T18:00"),),
    )
    spec_b = w.SnapshotSpec(
        plan_id=plan_id, lineage_id=lineage_id, representation="mpp",
        tasks=(w.TaskVersionSpec(task_key="t744", uid="744", name="Task", finish_raw="2026-11-16T18:00"),),
    )
    w.ingest_snapshot(conn, spec_a)
    w.ingest_snapshot(conn, spec_b)

    hist = q.task_history(conn, plan_id, "744")
    assert hist["finish_delta_calendar_days"] is None
    assert hist["history"] == []
    assert len(hist["unmatched_tasks"]) == 2
    assert "caveat" in hist
    assert hist["receipt"]["mapping"] == "unknown"


def test_task_history_unknown_uid_is_insufficient_data(conn):
    plan_id = w.ensure_plan(conn, "zd")
    hist = q.task_history(conn, plan_id, "999999")
    assert hist["result_class"] == "insufficient_data"


def test_diff_snapshots_working_drift_unavailable_without_timezone(conn):
    plan_id = w.ensure_plan(conn, "zd")
    lineage_id = w.ensure_lineage(conn, plan_id, "mpp_archive")
    snap_a = w.ingest_snapshot(conn, w.SnapshotSpec(
        plan_id=plan_id, lineage_id=lineage_id, representation="mpp", timezone_hint=None,
        tasks=(w.TaskVersionSpec(task_key="t1", uid="1", outline_level=1, finish_raw="2026-01-10"),),
    ))
    snap_b = w.ingest_snapshot(conn, w.SnapshotSpec(
        plan_id=plan_id, lineage_id=lineage_id, representation="mpp", timezone_hint=None,
        tasks=(w.TaskVersionSpec(task_key="t1", uid="1", outline_level=1, finish_raw="2026-01-14"),),
    ))
    d = q.diff_versions(conn, plan_id, {"kind": "snapshot", "snapshot_id": snap_a}, {"kind": "snapshot", "snapshot_id": snap_b})
    assert d["working_drift"] == "unavailable"


def test_compare_baseline_missing_slot_not_fabricated(conn):
    plan_id = w.ensure_plan(conn, "zd")
    lineage_id = w.ensure_lineage(conn, plan_id, "mpp_archive")
    snap = w.ingest_snapshot(conn, w.SnapshotSpec(
        plan_id=plan_id, lineage_id=lineage_id, representation="mpp",
        tasks=(w.TaskVersionSpec(task_key="t1", uid="1", finish_raw="2026-01-10"),),
    ))
    result = q.compare_baseline(conn, plan_id, snap, baseline_slot=0)
    assert result["missing_baseline_count"] == 1
    assert result["comparisons"][0]["status"] == "baseline_missing"


def test_explain_finish_change_on_publications_gives_observed_diff_not_validated(conn, tmp_path):
    """AC-139: вопрос про историческую пару публикаций (без UID) не выдаёт
    validated_attribution — честный observed_diff с блокерами."""
    plan_id = w.ensure_plan(conn, "zd")
    lineage_id = w.ensure_lineage(conn, plan_id, "confluence", page_id="p1")
    body_a = {"eventsData": [{"id": 1, "startDate": "2026-01-01T09:00:00", "endDate": "2026-01-10T18:00:00", "duration": 9.0, "children": []}], "dependenciesData": []}
    body_b = {"eventsData": [{"id": 1, "startDate": "2026-01-01T09:00:00", "endDate": "2026-01-24T18:00:00", "duration": 23.0, "children": []}], "dependenciesData": []}
    pub4 = _publish_json(conn, plan_id, lineage_id, 4, body_a, tmp_path=tmp_path)
    pub5 = _publish_json(conn, plan_id, lineage_id, 5, body_b, tmp_path=tmp_path)

    result = q.explain_finish_change(
        conn, plan_id,
        {"kind": "publication", "publication_id": pub4},
        {"kind": "publication", "publication_id": pub5},
    )
    assert result["result_class"] == "observed_diff"
    assert result["blockers"]


def test_legacy_registration_is_not_new_verified_confirmation(conn, tmp_path):
    plan = w.ensure_plan(conn,"legacy")
    lineage = w.ensure_lineage(conn,plan,"test",page_id="p1")
    pub = _publish_json(conn,plan,lineage,1,{"eventsData":[]},tmp_path=tmp_path)
    versions = q.list_versions(conn,plan)["versions"]
    assert versions[0]["publication_id"] == pub
    assert versions[0]["trust"] == "legacy_unverified"
    assert versions[0]["publication_verified"] is False
    loaded = q._load_publication(conn,plan,pub)
    assert loaded["trust"] == "legacy_unverified"
    assert loaded["publication_verified"] is False
    from mofs_index.plan.render import _build_markdown
    meta = q.resolve_plan(conn,"legacy")
    md = _build_markdown(conn,plan,meta,1)
    assert "legacy_unverified" in md
    assert "Последняя регистрация" in md
    assert "подтверждение полным конвейером: False" in md


def semantic_pair(conn, tmp_path, *, task_changes=None, dep_changes=None, cal_changes=None, assignment_changes=None, source_b='b', timezone='Europe/Moscow'):
    from dataclasses import replace
    plan = w.ensure_plan(conn,'semantic')
    tasks = (w.TaskVersionSpec(task_key='t1',uid='1',outline_level=1,name='Root',finish_raw='2026-11-01T09:00:00',
                 calendar_key='c1',summary=True), w.TaskVersionSpec(task_key='t2',uid='2',name='Child',parent_task_key='t1'))
    dep = w.DependencyVersionSpec('t1','t2',link_type='FS',lag_raw='1 day',lag_amount='1',lag_units='DAYS',lag_elapsed=False,calendar_basis='predecessor')
    cal = w.CalendarVersionSpec('c1',minutes_per_day_decimal='480',intervals=(w.CalendarIntervalSpec('weekday','MONDAY',True,'09:00','12:00'),))
    assignment = w.AssignmentVersionSpec('t1','r1',assignment_key='a1',uid='1',units_decimal='100',work_amount='8',work_units='HOURS',effective_calendar_key='c1')
    snapshots=[]
    for tag in ('a',source_b):
        modified = tag != 'a'
        spec = w.SnapshotSpec(plan_id=plan,representation='mpp',source_mpp_sha256=tag*64,
            resolved_timezone=timezone,
            tasks=(replace(tasks[0],**(task_changes or {})),tasks[1]) if modified else tasks,
            dependencies=(replace(dep,**(dep_changes or {})),dep) if modified else (dep,dep),
            calendars=(replace(cal,**(cal_changes or {})),) if modified else (cal,),
            resources=(w.ResourceVersionSpec('r1',uid='1'),w.ResourceVersionSpec('r2',uid='2')),
            assignments=(replace(assignment,**(assignment_changes or {})),) if modified else (assignment,))
        snapshots.append(w.ingest_snapshot(conn,spec))
    return plan,*snapshots


def confirm_pair(conn,tmp_path,a,b,*,mode='mapping',partial=False,reason='fixture explicit assertion'):
    import hashlib
    from mofs_index.plan.identity import MappingPair
    raw=b'Explicit synthetic test assertion of pair identity'
    path=tmp_path/'assertion.txt';path.write_bytes(raw)
    digest=hashlib.sha256(raw).hexdigest()
    evidence=w.record_artifact(conn,digest,'other',str(path),size_bytes=len(raw))
    pairs=tuple(MappingPair(kind,key,key,kind+':'+key) for kind,keys in (
        ('task',('t1',) if partial else ('t1','t2')),('resource',() if partial else ('r1','r2')),
        ('calendar',() if partial else ('c1',)),('assignment',() if partial else ('a1',))) for key in keys)
    return w.register_identity_confirmation(conn,w.IdentityConfirmationSpec('semantic',a,b,mode,evidence,digest,
        reason,'test','pytest',pairs=() if mode=='continuity' else pairs))['mapping_revision_id']


def diff_pair(conn,plan,a,b,revision=None):
    return q.diff_versions(conn,plan,{'kind':'snapshot','snapshot_id':a},{'kind':'snapshot','snapshot_id':b},mapping_revision_id=revision)


@pytest.mark.parametrize('changes', [
    {'link_type':'SS'},{'link_type':'FF'},{'link_type':'SF'}, {'lag_amount':'-1'},{'lag_amount':'2'},
    {'lag_units':'HOURS'},{'lag_elapsed':True},{'calendar_basis':'successor'},{'lag_calendar':'resource'}])
def test_full_dependency_multiset_semantics(conn,tmp_path,changes):
    plan,a,b=semantic_pair(conn,tmp_path,dep_changes=changes)
    revision=confirm_pair(conn,tmp_path,a,b)
    d=diff_pair(conn,plan,a,b,revision)
    assert len(d['links_added'])==len(d['links_removed'])==1
    assert all(d['links_added'][0][key]==value for key,value in changes.items())
    assert d['receipt']['mapping_revision_id']==revision


@pytest.mark.parametrize('changes', [
    {'name':'Rename'}, {'wbs':'1.2'}, {'source_id':'77'}, {'milestone':True},{'summary':False}, {'task_mode':'manual'},
    {'actual_start':'2026-10-01T09:00'}, {'actual_finish':'2026-10-02T09:00'}, {'actual_duration_raw':'2 days'},
    {'remaining_duration_raw':'3 days'},{'percent_complete_decimal':'52.125'}, {'work_amount':'8.5'},
    {'duration_units':'HOURS'},{'duration_elapsed':True}, {'notes':'saved notes'}, {'calendar_key':None},
    {'effective_calendar_key':'c1'}, {'parent_task_key':'t2'}, {'constraint_date':'2026-11-12'},
    {'early_start':'2026-01-01'}, {'late_finish':'2026-11-02'},
    {'segments':(w.TaskSegmentSpec('2026-01-01T09:00','2026-01-01T10:00'),)},
    {'baseline_values':(w.BaselineValueSpec(0,baseline_start='2026-01-01'),)},
    {'extensions':'{"mode":"custom"}'}, {'source_json':'{"extra_saved_field":"value"}'}])
def test_every_saved_task_field_is_compared(conn,tmp_path,changes):
    plan,a,b=semantic_pair(conn,tmp_path,task_changes=changes)
    confirm_pair(conn,tmp_path,a,b)
    d=diff_pair(conn,plan,a,b)
    assert len(d['changed_tasks'])==1
    key=next(iter(changes)); key={'segments':'segments','baseline_values':'baseline_values'}.get(key,key)
    assert key in d['changed_tasks'][0]['changes']


@pytest.mark.parametrize('changes',[
    {'intervals':(w.CalendarIntervalSpec('weekday','MONDAY',True,'09:30','12:00'),)},
    {'intervals':(w.CalendarIntervalSpec('exception','2026-11-01',False),)},
    {'parent_key':'other'}, {'base_calendar_key':'other'}, {'minutes_per_day_decimal':'420'}])
def test_calendar_intervals_exceptions_inheritance_parameters(conn,tmp_path,changes):
    plan,a,b=semantic_pair(conn,tmp_path,cal_changes=changes)
    confirm_pair(conn,tmp_path,a,b)
    assert diff_pair(conn,plan,a,b)['changed_calendars']


@pytest.mark.parametrize('changes',[{'resource_key':'r2'},{'task_key':'t2'},{'units_decimal':'50'},
    {'work_amount':'9'},{'work_units':'DAYS'},{'start_raw':'2026-11-02T09:00'}, {'finish_raw':'2026-11-03T09:00'},
    {'effective_calendar_key':None},{'actual_work_raw':'2 hours'},{'remaining_work_raw':'6 hours'},
    {'timephased':(w.TimephasedSpec('2026-11-01T09:00','2026-11-01T10:00',work_amount='1',work_units='HOURS'),)}])
def test_assignment_full_semantics(conn,tmp_path,changes):
    plan,a,b=semantic_pair(conn,tmp_path,assignment_changes=changes)
    confirm_pair(conn,tmp_path,a,b)
    assert diff_pair(conn,plan,a,b)['changed_assignments']


def test_same_source_unknown_identity_partial_and_exact_revision(conn,tmp_path):
    plan,a,b=semantic_pair(conn,tmp_path)
    unknown=diff_pair(conn,plan,a,b)
    assert unknown['receipt']['mapping']=='unknown' and not unknown['links_added']
    assert all(unknown['unmatched_entities'][kind]['from'] for kind in ('task','calendar','assignment'))
    partial=confirm_pair(conn,tmp_path,a,b,partial=True)
    d=diff_pair(conn,plan,a,b,partial)
    assert d['unmatched_entities']['calendar']['from'] and d['unmatched_entities']['assignment']['to']
    assert len(d['unmatched_entities']['task']['to'])==1
    assert d['receipt']['completeness']=='partial' and d['receipt']['calendar']=='unknown'
    assert diff_pair(conn,plan,a,a)['receipt']['mapping']=='same_source'


def test_selector_owner_checked_before_diff_or_representation(conn,tmp_path,monkeypatch):
    plan,a,b=semantic_pair(conn,tmp_path)
    other=w.ensure_plan(conn,'foreign')
    foreign=w.ingest_snapshot(conn,w.SnapshotSpec(plan_id=other,representation='gantt_json'))
    def forbidden(*args,**kwargs):
        raise AssertionError('diff must not start')
    monkeypatch.setattr(q,'_diff_snapshots',forbidden)
    for x,y in ((a,foreign),(foreign,a)):
        with pytest.raises(q.PlanQueryError,match='selector_project_mismatch'):
            diff_pair(conn,plan,x,y)
    with pytest.raises(q.PlanQueryError,match='selector_project_mismatch'):
        q.compare_baseline(conn,plan,foreign)
    from mofs_index.plan.identity import IdentityError
    with pytest.raises(IdentityError,match='selector_project_mismatch'):
        q.task_history(conn,plan,'1',from_snapshot_id=foreign)


def test_time_precision_unknown_timezone_not_completeness(conn,tmp_path):
    plan,a,b=semantic_pair(conn,tmp_path,task_changes={'finish_raw':'2026-11-01T09:00:30'},timezone='Europe/Moscow')
    confirm_pair(conn,tmp_path,a,b)
    d=diff_pair(conn,plan,a,b)
    assert d['root']['finish_delta_seconds']==30
    assert d['receipt']['completeness']=='partial' and d['receipt']['calendar']=='unknown'
    assert q._absolute_delta('2026-11-01T09:00','2026-11-01T10:00',None,None) is None
    assert q._absolute_delta('2026-11-01','2026-11-02','UTC','UTC') is None
    assert q._absolute_delta('2026-11-01T01:30','2026-11-01T02:00','America/New_York','America/New_York') is None


def test_exact_publications_same_v2_two_pages_and_untrusted_link(conn,tmp_path):
    import hashlib
    plan=w.ensure_plan(conn,'pages')
    raw=b'{"eventsData":[{"id":1,"name":"root"}]}'
    digest=hashlib.sha256(raw).hexdigest();path=tmp_path/'gantt.json';path.write_bytes(raw)
    artifact=w.record_artifact(conn,digest,'downloaded_json',str(path))
    pubs=[]
    for page in ('p1','p2'):
        line=w.ensure_lineage(conn,plan,'test',page_id=page)
        pubs.append(w.record_publication(conn,w.PublicationSpec(plan,'test','attachment-'+page,2,
            lineage_id=line,artifact_id=artifact,page_id=page,filename='gantt.json',raw_sha256=digest)))
    with pytest.raises(q.PlanQueryError,match='exact_publication_id_required'):
        q.diff_versions(conn,plan,{'kind':'publication','attachment_version':2},{'kind':'publication','publication_id':pubs[0]})
    d=q.diff_versions(conn,plan,*[{'kind':'publication','publication_id':p} for p in pubs])
    assert d['content_identical'] and d['receipt']['mapping']=='unknown'
    assert d['publications']['from']['page_id']=='p1' and d['publications']['to']['page_id']=='p2'
    from mofs_index.plan.selectors import resolve_selector
    with pytest.raises(q.PlanQueryError,match='publication_page_id_mismatch'):
        resolve_selector(conn,plan,{'kind':'publication','publication_id':pubs[0],'page_id':'p2'})
    foreign=w.ensure_plan(conn,'foreign-publication')
    sid=w.ingest_snapshot(conn,w.SnapshotSpec(plan_id=foreign,representation='mpp'))
    # Typed writer rejects cross-project links before any query can use them.
    with pytest.raises(w.PlanWriterError):
        w.link_publication_snapshot(conn,pubs[0],sid,confidence='confirmed',evidence='test')


def test_mixed_representation_requires_actual_gantt_snapshot_mapping(conn,tmp_path):
    import hashlib
    from mofs_index.plan.identity import MappingPair
    plan,a,_=semantic_pair(conn,tmp_path)
    raw=b'{"eventsData":[{"id":1,"name":"Gantt root"}]}'
    digest=hashlib.sha256(raw).hexdigest();path=tmp_path/'published.json';path.write_bytes(raw)
    artifact=w.record_artifact(conn,digest,'published_json',str(path))
    b=w.ingest_snapshot(conn,w.SnapshotSpec(plan_id=plan,representation='gantt_json',source_artifact_id=artifact,
        source_mpp_sha256=digest,tasks=(w.TaskVersionSpec('gantt:1',name='Gantt root'),)))
    pub=w.record_publication(conn,w.PublicationSpec(plan,'test','mixed-att',1,page_id='p1',filename='gantt.json',artifact_id=artifact,raw_sha256=digest))
    w.link_publication_snapshot(conn,pub,b,confidence='confirmed',evidence='synthetic exact Gantt bytes')
    selectors=({'kind':'snapshot','snapshot_id':a},{'kind':'publication','publication_id':pub})
    assert q.diff_versions(conn,plan,*selectors)['result_class']=='representation_mismatch'
    eid=w.record_artifact(conn,digest,'other',str(path))
    rev=w.register_identity_confirmation(conn,w.IdentityConfirmationSpec('semantic',a,b,'mapping',eid,digest,
        'explicit mixed representation mapping fixture','test','pytest',pairs=(MappingPair('task','t1','gantt:1','root'),)))
    result=q.diff_versions(conn,plan,*selectors,mapping_revision_id=rev['mapping_revision_id'])
    assert result['receipt']['mapping']=='confirmed_mapping'
    assert result['changed_tasks'][0]['to_key']=='gantt:1'
    assert result['unmatched_entities']['task']['from'][0]['task_key']=='t2'


def test_calendar_project_task_resource_assignment_bindings(conn,tmp_path):
    plan,a,b=semantic_pair(conn,tmp_path,task_changes={'calendar_key':None})
    confirm_pair(conn,tmp_path,a,b)
    d=diff_pair(conn,plan,a,b)
    assert 'calendar_key' in d['changed_tasks'][0]['changes']
    c=w.ingest_snapshot(conn,w.SnapshotSpec(plan_id=plan,representation='mpp',source_mpp_sha256='c'*64,
        source_json='{"project":{"default_calendar_key":{"value":"c1","quality":"known"}}}',
        tasks=(w.TaskVersionSpec('t1',uid='1'),)))
    e=w.ingest_snapshot(conn,w.SnapshotSpec(plan_id=plan,representation='mpp',source_mpp_sha256='d'*64,
        source_json='{"project":{"default_calendar_key":{"value":null,"quality":"known"}}}',
        tasks=(w.TaskVersionSpec('t1',uid='1'),)))
    confirm_pair(conn,tmp_path,c,e,partial=True)
    assert diff_pair(conn,plan,c,e)['project_changes']['default_calendar_key']


def test_same_source_distinct_snapshots_same_profile_not_uid_inference(conn,tmp_path):
    import hashlib
    raw=b'Identical synthetic bytes';digest=hashlib.sha256(raw).hexdigest();path=tmp_path/'source.mpp';path.write_bytes(raw)
    artifact=w.record_artifact(conn,digest,'mpp',str(path));plan=w.ensure_plan(conn,'same-source')
    snapshots=[]
    for name in ('one','two'):
        line=w.ensure_lineage(conn,plan,'local:'+name)
        snapshots.append(w.ingest_snapshot(conn,w.SnapshotSpec(plan_id=plan,lineage_id=line,representation='mpp',
            source_artifact_id=artifact,source_mpp_sha256=digest,normalization_profile_fingerprint='f'*64,resolved_timezone='unknown',
            tasks=(w.TaskVersionSpec('t1',uid='1'),))))
    result=diff_pair(conn,plan,*snapshots)
    assert result['receipt']['mapping']=='same_source' and not result['changed_tasks']
    assert result['receipt']['mapping_revision_id'] is None


def test_dependency_source_endpoint_ids_follow_confirmed_mapping(conn,tmp_path):
    import hashlib
    from mofs_index.plan.identity import MappingPair
    plan=w.ensure_plan(conn,'renumbered')
    snapshots=[]
    for tag,first,last in (('a','1','2'),('b','101','102')):
        snapshots.append(w.ingest_snapshot(conn,w.SnapshotSpec(plan_id=plan,representation='mpp',source_mpp_sha256=tag*64,
            tasks=(w.TaskVersionSpec('t'+first,uid=first),w.TaskVersionSpec('t'+last,uid=last)),
            dependencies=(w.DependencyVersionSpec('t'+first,'t'+last,link_type='FS',lag_amount='-1',lag_units='HOURS',lag_elapsed=True,
                source_json=json.dumps({'predecessor_uid':first,'successor_uid':last,'predecessor_id':int(first),
                    'successor_id':int(last),'uid':'local-'+tag,'dependency_key':'local-'+tag,
                    'predecessor_task_key':'t'+first,'successor_task_key':'t'+last,'driving':True})),))))
    raw=b'Explicit synthetic renumbering mapping';path=tmp_path/'renumbering.txt';path.write_bytes(raw)
    digest=hashlib.sha256(raw).hexdigest();eid=w.record_artifact(conn,digest,'other',str(path))
    rev=w.register_identity_confirmation(conn,w.IdentityConfirmationSpec('renumbered',*snapshots,'mapping',eid,digest,
        'Confirmed synthetic endpoints only','test','pytest',pairs=(MappingPair('task','t1','t101','first'),MappingPair('task','t2','t102','last'))))
    result=diff_pair(conn,plan,*snapshots,rev['mapping_revision_id'])
    assert result['links_added']==result['links_removed']==[]
    assert result['receipt']['mapping']=='confirmed_mapping'
