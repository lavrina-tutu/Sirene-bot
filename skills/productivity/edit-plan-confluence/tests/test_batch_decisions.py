"""AC-19: typed fixture -> CLI registration -> explicit batch consumption."""
from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import subprocess

import pytest

from test_plan_batch import batch_case, create, fake_export
import plan_batch as pb
import plan_save as ps
from plan_operation import show_operation
from plan_decision import register_decision
from plan_lock import batch_lock
from mofs_index.db import connect_durable
from mofs_index.plan import writer as w, query as q

pytestmark = pytest.mark.archive_integration
FIXTURE = Path(__file__).parent/'fixtures/synthetic/batch-decision-registration/provenance.json'


def add_evidence(context, path, *, project='other', lineage_id=None, quality='unconfirmed', label='initial'):
    fixture = json.loads(FIXTURE.read_text())
    manifest = json.loads((FIXTURE.parent/'manifest.json').read_text())
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == manifest['files']['provenance.json']['sha256']
    assert fixture['quality'] == manifest['quality'] == 'unconfirmed'
    c = connect_durable(context.db)
    try:
        return w.record_source_provenance(c, w.ProvenanceSpec(hashlib.sha256(path.read_bytes()).hexdigest(),
            project, json.dumps({**fixture['evidence'], 'label': label}), fixture['source'], fixture['reason'],
            lineage_id=lineage_id, quality=quality))
    finally:
        c.close()


def states(context, batch_id='test'):
    c = connect_durable(context.db)
    try:
        rows = q.get_batch_items(c, batch_id)
        return rows, [show_operation(r['operation_id'], db_path=context.db) for r in rows]
    finally:
        c.close()


def accept(context, shown, **kwargs):
    active = [p for p in shown['proposals'] if p['active']]
    return register_decision(shown['operation_id'], kwargs.pop('proposal_id', active[0]['proposal_id']),
                             db_path=context.db, reason=kwargs.pop('reason', 'Подтверждаю архивное размещение'), **kwargs)


def tables(context):
    c = connect_durable(context.db)
    try:
        return {table: [tuple(row) for row in c.execute('SELECT * FROM '+table+' ORDER BY 1')]
                for table in ('plan_baseline_selection', 'plan_snapshot_selection', 'plan_publication', 'plan_publication_snapshot', 'plan_identity_mapping', 'plan_mapping_revision')}
    finally:
        c.close()


@pytest.fixture
def decision_case(batch_case):
    context, sources = batch_case
    c = connect_durable(context.db)
    from mofs_index.plan.migrate import ensure_plan_schema
    ensure_plan_schema(c)
    plan = w.ensure_plan(c, 'batch-project')
    lineage = w.ensure_lineage(c, plan, 'local-archive-v1', basis='project_archive_v1')
    snapshot = w.ingest_snapshot(c, w.SnapshotSpec(plan_id=plan, lineage_id=lineage, representation='mpp'))
    w.select_snapshot_baseline(c, lineage, snapshot, is_explicit=True, basis='acceptance')
    w.select_plan_baseline(c, plan, snapshot, 0, is_explicit=True, basis='acceptance')
    c.close()
    before = tables(context)
    yield batch_case
    assert tables(context) == before


def test_ac19_continue_registration_and_explicit_consumption(decision_case, monkeypatch):
    context, sources = decision_case
    add_evidence(context, sources[1])
    reads = []
    def export(path, **kw):
        reads.append(str(path)); return fake_export(path)
    monkeypatch.setattr(ps, 'run_export_full', export)
    result = create(decision_case)
    assert result['exit_code'] == 6
    assert [i['status'] for i in result['items']] == ['saved_with_warnings', 'needs_decision', 'saved_with_warnings']
    assert result['items'][1]['error']['code'] == q.BATCH_REASONS[0]
    rows, shown = states(context)
    operation = shown[1]
    assert operation['identity_requirements'] == [] and len(operation['proposals']) == 1
    proposal = operation['proposals'][0]
    assert hashlib.sha256(w._json(proposal['content']).encode()).hexdigest() == proposal['proposal_sha256']
    assert hashlib.sha256(w._json(proposal['content']['policy']).encode()).hexdigest() == proposal['content']['policy_sha256']
    retry = pb.resume_batch('test', context=context, retry_decisions=True)
    assert retry['counts']['needs_decision'] == 1 and len(reads) == 2
    registered = accept(context, operation)
    import jsonschema
    jsonschema.validate(registered, json.loads((Path(__file__).resolve().parents[1]/'references/schemas/batch-decision-result.schema.json').read_text()))
    assert registered['action'] == 'register_batch_decision' and registered['status'] == 'decision_registered'
    assert registered['decision_ready'] and registered['exit_code'] == 0 and not registered['published']
    assert registered['manifest_sha256'] == result['manifest_sha256']
    assert states(context)[0][1]['status'] == 'needs_decision' and len(reads) == 2
    duplicate = accept(context, operation)
    assert duplicate['decision_id'] == registered['decision_id']
    changed = accept(context, operation, reason='Иное основание')
    assert changed['exit_code'] == 4 and changed['error']['code'] == 'decision_conflict'
    assert pb.resume_batch('test', context=context)['exit_code'] == 6 and len(reads) == 2
    c = connect_durable(context.db)
    assert len([e for e in q.get_operation_events(c, operation['operation_id']) if e['event_kind'] == 'decision_registered']) == 1
    c.close()
    errors = pb.show_batch('test', context=context, view='errors')['result']['items']
    assert len(errors) == 1 and errors[0]['decision_ready'] and errors[0]['decisions']
    done = pb.resume_batch('test', context=context, retry_decisions=True)
    assert done['exit_code'] == 0 and len(reads) == 3
    assert done['manifest_sha256'] == result['manifest_sha256']
    assert [i['operation_id'] for i in done['items']] == [i['operation_id'] for i in result['items']]


@pytest.mark.parametrize('both', [False, True])
@pytest.mark.parametrize('policy', ['continue', 'stop'])
def test_ac19_lineage_two_reasons_and_stop(decision_case, both, policy):
    context, sources = decision_case
    c = connect_durable(context.db)
    plan = w.ensure_plan(c, 'batch-project')
    other = w.ensure_lineage(c, plan, 'other-local', basis='unverified fixture')
    c.close()
    add_evidence(context, sources[1], project='batch-project', lineage_id=other)
    if both:
        add_evidence(context, sources[1])
    first = create(decision_case, on_error=policy)
    assert first['counts']['not_started'] == int(policy == 'stop')
    rows, shown = states(context)
    active = [p for p in shown[1]['proposals'] if p['active']]
    assert len(active) == 1 + int(both)
    one = accept(context, shown[1])
    assert one['decision_ready'] == (not both)
    if both:
        assert pb.show_batch('test', context=context)['items'][1]['error']['code'] == q.BATCH_REASONS[1]
        partial = pb.resume_batch('test', context=context, retry_decisions=True)
        assert partial['counts']['needs_decision'] == 1
        assert partial['counts']['not_started'] == int(policy == 'stop')
        second = accept(context, states(context)[1][1], proposal_id=active[1]['proposal_id'])
        assert second['decision_ready']
    assert pb.resume_batch('test', context=context, retry_decisions=True)['exit_code'] == 0


def test_ac19_foreign_stale_and_changed_grounds(decision_case):
    context, sources = decision_case
    add_evidence(context, sources[1])
    first = create(decision_case)
    _, shown = states(context)
    original = shown[1]
    old = accept(context, original)
    add_evidence(context, sources[1], label='new contradictory evidence')
    stale = accept(context, original)
    assert stale['exit_code'] == 4 and stale['error']['code'] == 'proposal_context_mismatch'
    assert pb.resume_batch('test', context=context, retry_decisions=True)['counts']['needs_decision'] == 1
    updated = states(context)[1][1]
    assert len(updated['proposals']) == 2 and len(updated['decisions']) == 1 and not updated['decision_ready']
    assert old['decision_id'] == updated['decisions'][0]['decision_id']
    assert accept(context, updated, proposal_id='proposal-'+'0'*64)['exit_code'] == 4
    # Another batch with the same source has a different immutable proposal.
    other = create((context, [sources[1]]), batch_id='foreign')
    foreign = states(context, 'foreign')[1][0]
    assert accept(context, foreign, proposal_id=updated['proposals'][-1]['proposal_id'])['exit_code'] == 4
    assert accept(context, updated)['exit_code'] == 0
    assert pb.resume_batch('test', context=context, retry_decisions=True)['exit_code'] == 0
    assert pb.show_batch('test', context=context)['manifest_sha256'] == first['manifest_sha256']


@pytest.mark.parametrize('parameters', [{}, {'timezone_hint':'Europe/Moscow'}, {'mapping_revision':'other'}, {'rule_scope':'project'}])
def test_ac19_context_immutable(decision_case, parameters):
    context, sources = decision_case
    add_evidence(context, sources[1]); first = create(decision_case)
    shown = states(context)[1][1]
    options = {'reason':'reason', **parameters}
    result = register_decision(shown['operation_id'], None if not parameters else shown['proposals'][0]['proposal_id'], db_path=context.db, **options)
    assert result['exit_code'] == 4 and result['error']['code'] == 'batch_context_immutable'
    conflict = create(decision_case, timezone_hint='Europe/Moscow')
    assert conflict['exit_code'] == 4 and conflict['error']['code'] == 'batch_manifest_conflict'
    changed = create(decision_case, batch_id='new-zone', timezone_hint='Europe/Moscow')
    assert changed['counts']['needs_decision'] == 1
    assert states(context, 'new-zone')[1][1]['proposals'][0]['content']['resolved_timezone'] == 'Europe/Moscow'
    assert pb.show_batch('test', context=context)['manifest_sha256'] == first['manifest_sha256']


def test_ac19_registration_batch_busy(decision_case):
    context, sources = decision_case
    add_evidence(context, sources[1]); create(decision_case)
    shown = states(context)[1][1]
    mp = multiprocessing.get_context('fork')
    acquired, release = mp.Event(), mp.Event()
    def handler():
        with batch_lock(context.db, 'test'):
            acquired.set()
            assert release.wait(30)
    process = mp.Process(target=handler)
    process.start()
    try:
        assert acquired.wait(10)
        result = accept(context, shown)
        assert result['exit_code'] == 4 and result['error']['code'] == 'batch_busy'
        assert not states(context)[1][1]['decisions']
    finally:
        release.set(); process.join(10)
    assert process.exitcode == 0


def test_ac19_proved_conflict_is_item_failure(decision_case):
    context, sources = decision_case
    add_evidence(context, sources[1], quality='confirmed')
    result = create(decision_case)
    assert result['exit_code'] == 6 and result['counts']['failed'] == 1
    assert result['items'][1]['error']['code'] == 'binding_conflict'
    assert not states(context)[1][1]['proposals']


def test_ac19_no_artificial_decisions(decision_case):
    context, _ = decision_case
    result = create(decision_case)
    assert result['counts']['needs_decision'] == 0 and result['exit_code'] == 0
    assert all(not state['proposals'] for state in states(context)[1])


@pytest.mark.parametrize('boundary', ['registered', 'snapshot_committed'])
def test_ac19_process_death_after_registration_and_commit(decision_case, monkeypatch, boundary):
    context, sources = decision_case
    add_evidence(context, sources[1]); create(decision_case)
    shown = states(context)[1][1]
    if boundary == 'snapshot_committed':
        assert accept(context, shown)['exit_code'] == 0
    def crash():
        if boundary == 'registered':
            assert accept(context, shown)['exit_code'] == 0
            os._exit(86)
        original = w.commit_import_snapshot
        def commit(*a, **kw):
            result = original(*a, **kw)
            os._exit(86)
        w.commit_import_snapshot = commit
        pb.resume_batch('test', context=context, retry_decisions=True)
        os._exit(87)
    process = multiprocessing.get_context('fork').Process(target=crash)
    process.start(); process.join(30)
    assert process.exitcode == 86
    current = states(context)[1][1]
    assert len(current['decisions']) == 1
    if boundary == 'snapshot_committed':
        assert current['snapshot_id']
        def no_reader(*a, **kw): raise AssertionError('reader after commit')
        monkeypatch.setattr(ps, 'run_export_full', no_reader)
    done = pb.resume_batch('test', context=context, retry_decisions=True)
    assert done['exit_code'] == 0
    c = connect_durable(context.db)
    assert len(q.get_batch_items(c, 'test')) == 3
    assert len(q.get_batch_decisions(c, shown['operation_id'])) == 1
    assert len([e for e in q.get_operation_events(c, shown['operation_id']) if e['event_kind'] == 'snapshot_committed']) == 1
    c.close()


def test_ac19_registration_transaction_rollback(decision_case, monkeypatch):
    context, sources = decision_case
    add_evidence(context, sources[1]); create(decision_case)
    shown = states(context)[1][1]
    original = w._operation_event
    def fail(conn, attempt, kind, *a, **kw):
        if kind == 'decision_registered': raise OSError('journal unavailable')
        return original(conn, attempt, kind, *a, **kw)
    monkeypatch.setattr(w, '_operation_event', fail)
    assert accept(context, shown)['exit_code'] == 5
    assert not states(context)[1][1]['decisions']


def test_ac19_real_cli_registration_and_retry(tmp_path, request):
    """Full gate path, actual MPP; no SQL or test monkeypatch in product process."""
    from plan_context import PlanContext
    context = PlanContext.resolve(db=tmp_path/'state/index.sqlite', workvault=tmp_path/'WorkVault', cache_dir=tmp_path/'cache')
    skill = Path(__file__).resolve().parents[1]
    real = json.loads((skill/'tests/fixtures/real/manifest.json').read_text())['fixtures']
    fixture = next(f for f in real if f['id'] == 'E')
    source = tmp_path/'E.mpp'; source.write_bytes((skill/'tests/fixtures/real'/ (fixture['sha256']+'.mpp')).read_bytes())
    c = connect_durable(context.db)
    from mofs_index.plan.migrate import ensure_plan_schema
    ensure_plan_schema(c); c.close()
    add_evidence(context, source)
    guard = tmp_path/'guard'; guard.mkdir()
    (guard/'sitecustomize.py').write_text('''import socket,sqlite3,os,sys,importlib.abc
from pathlib import Path
class Guard(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname.split('.')[0] in ('conf_client','pipeline'): raise AssertionError('client forbidden')
sys.meta_path.insert(0,Guard())
def denied(*a,**k): raise AssertionError('network forbidden')
socket.socket.connect=denied
socket.create_connection=denied
original=sqlite3.connect
def connect(path,*a,**k):
 if str(path) != ':memory:': assert Path(os.environ['DECISION_TEST_ROOT']) in Path(str(path)).resolve().parents
 return original(path,*a,**k)
sqlite3.connect=connect
''')
    env = dict(os.environ, DECISION_TEST_ROOT=str(tmp_path))
    env['PYTHONPATH'] = str(guard)+os.pathsep+env.get('PYTHONPATH','')
    base = ['/usr/bin/python3',str(skill/'scripts/cli.py'),'--db',str(context.db),'--workvault',str(context.workvault),'--cache-dir',str(context.cache_dir)]
    evidence=[]
    def cli(*args):
        command=base+list(args)
        proc=subprocess.run(command,env=env,capture_output=True,text=True,timeout=150)
        assert proc.stdout, proc.stderr
        result=json.loads(proc.stdout)
        evidence.append({'command':command,'rc':proc.returncode,'result':result,'stderr':proc.stderr})
        assert proc.returncode == result['exit_code']
        return result
    first=cli('batch','save','--batch-id','cli','--project-slug','batch-project','--mpp',str(source))
    assert first['exit_code'] == 6 and first['counts']['needs_decision'] == 1
    operation=cli('operation','show','--operation-id',first['items'][0]['operation_id'])
    proposal=operation['proposals'][0]['proposal_id']
    args=('resume','--operation-id',operation['operation_id'],'--accept-proposal',proposal,'--reason','Подтверждаю')
    registered=cli(*args)
    assert registered['exit_code']==0 and registered['decision_ready']
    c=connect_durable(context.db)
    assert not q.get_operation_item(c,operation['operation_id'])['snapshot_id']
    assert not any(e['event_kind']=='save_metrics' for e in q.get_operation_events(c,operation['operation_id']))
    c.close()
    assert cli(*args)['decision_id']==registered['decision_id']
    assert cli('batch','resume','--batch-id','cli')['exit_code']==6
    done=cli('batch','resume','--batch-id','cli','--retry-decisions')
    assert done['exit_code']==0 and done['manifest_sha256']==first['manifest_sha256']
    c=connect_durable(context.db)
    metric=[json.loads(e['detail']) for e in q.get_operation_events(c,operation['operation_id']) if e['event_kind']=='save_metrics'][-1]
    assert metric['counters']['MPXJ_read']==1
    c.close()
    root=getattr(request.config,'_acceptance_root',tmp_path)/'reports'
    root.mkdir(exist_ok=True)
    (root/'batch-decisions-cli.json').write_text(json.dumps({'calls':evidence,'metrics':metric,'POST':0,'PUT':0},ensure_ascii=False,indent=2))
