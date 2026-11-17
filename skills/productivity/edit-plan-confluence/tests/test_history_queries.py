"""Typed history semantics, time boundaries, cursor stability and CLI parity."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import pytest

from test_plan_batch import batch_case, fake_export
import plan_save as ps
from mofs_index.db import connect_durable
from mofs_index.plan import query as q, writer as w
from mofs_index.plan.history import HistoryRequest, HistoryQueryError, history

pytestmark = pytest.mark.archive_integration


@pytest.fixture
def history_case(batch_case, monkeypatch):
    context, sources = batch_case
    clock = ['2026-11-16T00:00:00Z']
    monkeypatch.setattr(w, '_now', lambda: clock[0])
    def export(path, **kwargs):
        clock[0] = '2026-11-17T00:00:00Z'
        return fake_export(path)
    monkeypatch.setattr(ps, 'run_export_full', export)
    receipts = []
    for i, (source, received, version) in enumerate([
        (sources[0], '2026-11-16T00:00:00Z', '2026-01-01'),
        (sources[1], '2026-11-16T03:00:00+03:00', '2026-02-01'),
        (sources[0], '2026-11-16T01:00:00Z', None),
        (sources[2], '2026-11-17T00:00:00Z', None),
    ]):
        clock[0] = received
        result = ps.save_snapshot(source, project_slug='history', source_version_date=version, context=context)
        assert result.exit_code == 0, result.to_dict()
        receipts.append(result.to_dict())
    c = connect_durable(context.db)
    snapshot = q.get_snapshot(c, receipts[0]['snapshot_id'])
    clock[0] = '2026-11-18T00:00:00Z'
    pub = w.record_publication(c, w.PublicationSpec(snapshot['plan_id'], 'fixture', 'attachment', 1,
        lineage_id=snapshot['lineage_id'], published_at='2026-10-01T00:00:00Z', observed_at='2026-11-15T00:00:00Z'))
    w.link_publication_snapshot(c, pub, snapshot['snapshot_id'], confidence='inferred', evidence='synthetic link, no trust promotion')
    # A legacy registration has an unknown publication time, even though its import is known.
    w.record_publication(c, w.PublicationSpec(snapshot['plan_id'], 'fixture', 'attachment', 2,
        lineage_id=snapshot['lineage_id'], observed_at='2026-11-16T00:00:00Z'))
    yield c, context, receipts
    c.close()


def test_history_views_and_defaults(history_case):
    c, context, receipts = history_case
    for view, field, count in [('files', 'received', 4), ('snapshots', 'recorded', 3), ('publications', 'published', 2)]:
        result = history(c, HistoryRequest('history', view=view))
        assert result['parameters']['time_field'] == field
        assert result['result']['total'] == count
    files = history(c, HistoryRequest('history'))['result']['records']
    assert {f['item_id'] for f in files} == {r['item_id'] for r in receipts}
    assert all(f['original_name'] and f['source_mpp_sha256'] and f['status'] for f in files)
    assert len({f['snapshot_id'] for f in files}) == 3
    snapshots = history(c, HistoryRequest('history', view='snapshots'))['result']['records']
    published = next(s for s in snapshots if s['snapshot_id'] == receipts[0]['snapshot_id'])
    assert published['published_at'] == '2026-10-01T00:00:00Z'
    assert published['publications'][0]['trust'] == 'legacy_unverified'
    assert q.get_snapshot(c, published['snapshot_id'])['published_at'] is None


def test_history_half_open_timezone_and_equal_timestamps(history_case):
    c, _, receipts = history_case
    request = HistoryRequest('history', since='2026-11-16T03:00:00+03:00', until='2026-11-17T00:00:00Z')
    result = history(c, request)['result']
    assert result['total'] == 3
    ids = {r['item_id'] for r in result['records']}
    assert ids == {r['item_id'] for r in receipts[:3]}
    assert receipts[3]['item_id'] not in ids


def test_history_filter_fields_are_distinct_order_source_does_not_change_filter(history_case):
    c, _, _ = history_case
    counts = {}
    for field in ('received', 'recorded', 'source', 'published'):
        result = history(c, HistoryRequest('history', time_field=field, since='2026-11-16T00:00:00Z', until='2026-11-17T00:00:00Z'))
        counts[field] = result['result']['total']
    assert counts == {'received': 3, 'recorded': 1, 'source': 0, 'published': 0}
    result = history(c, HistoryRequest('history', order='source', since='2026-11-16T00:00:00Z', until='2026-11-17T00:00:00Z'))
    assert result['parameters']['time_field'] == 'received'
    assert result['result']['total'] == 3 and len(result['result']['unknown_source_dates']) == 1
    assert len(result['result']['records']) == 2
    assert result['result']['unknown_source_date_count'] == 1


def test_history_unknown_time_separate_count(history_case):
    c, _, _ = history_case
    result = history(c, HistoryRequest('history', view='publications', since='2026-01-01T00:00:00Z'))
    assert result['result']['total'] == 1 and result['result']['unknown_time_count'] == 1
    assert result['result']['records'][0]['published_at'] == '2026-10-01T00:00:00Z'
    source = history(c, HistoryRequest('history', time_field='source', since='2026-01-01T00:00:00Z', until='2026-02-01T00:00:00Z'))
    assert source['result']['total'] == 1 and source['result']['unknown_time_count'] == 2
    assert source['result']['records'][0]['source_version_date'] == '2026-01-01'


@pytest.mark.parametrize('order', ['ingested', 'source'])
def test_history_cursor_stable_ties_unknowns_and_new_backdated_arrival(history_case, order):
    c, context, _ = history_case
    def records(result): return result['records'] + result['unknown_source_dates']
    all_rows = records(history(c, HistoryRequest('history', order=order))['result'])
    first = history(c, HistoryRequest('history', order=order, limit=1))['result']
    seen = records(first)
    cursor = first['next_cursor']
    # New backdated arrival would disturb offset pagination, but is beyond watermark.
    op = w.create_operation(c, w.OperationSpec('save', json.dumps({'save': {'project_slug': 'history'}})))
    w.create_import_item(c, w.ImportItemSpec(op, 'late.mpp', '/synthetic/late.mpp', received_at='2020-01-01T00:00:00Z'))
    while cursor:
        page = history(c, HistoryRequest('history', order=order, limit=1, cursor=cursor))['result']
        seen += records(page)
        cursor = page['next_cursor']
    assert [r['item_id'] for r in seen] == [r['item_id'] for r in all_rows]
    assert len({r['item_id'] for r in seen}) == 4
    assert history(c, HistoryRequest('history'))['result']['total'] == 5


@pytest.mark.parametrize('parameters', [
    {'since':'2026-11-16T00:00:00'}, {'until':'2026-11-17'},
    {'since':'2026-11-18T00:00:00Z','until':'2026-11-17T00:00:00Z'},
    {'since':'2026-11-17T00:00:00Z','until':'2026-11-17T00:00:00Z'},
    {'cursor':'garbage'}, {'limit':0}, {'limit':1001}, {'time_field':'status'},
])
def test_history_invalid_parameters_fail_closed(history_case, parameters):
    c, _, _ = history_case
    with pytest.raises(HistoryQueryError): history(c, HistoryRequest('history', **parameters))


def test_history_cursor_cannot_change_filter(history_case):
    c, _, _ = history_case
    cursor = history(c, HistoryRequest('history', limit=1))['result']['next_cursor']
    for changed in ({'project_slug':'other'}, {'view':'snapshots'}, {'time_field':'recorded'}, {'order':'source'}, {'lineage_id':'other'}):
        with pytest.raises(HistoryQueryError, match='cursor_context_mismatch'):
            history(c, HistoryRequest(**{'project_slug':'history', 'cursor':cursor, **changed}))


def test_history_project_lineage_scope_and_failed_arrivals(history_case):
    c, _, _ = history_case
    op = w.create_operation(c, w.OperationSpec('save', json.dumps({'save': {'project_slug':'history','lineage_id':'synthetic-line'}})))
    item = w.create_import_item(c, w.ImportItemSpec(op, 'failed.mpp', '/synthetic/failed.mpp', received_at='legacy unknown'))
    attempt = w.begin_operation_attempt(c, op, item)
    w.fail_import_item(c, item, attempt, 'mpp_unreadable')
    result = history(c, HistoryRequest('history', lineage_id='synthetic-line'))['result']
    assert result['total'] == 1 and result['records'][0]['status'] == 'failed'
    assert result['unknown_time_count'] == 1
    filtered = history(c, HistoryRequest('history', lineage_id='synthetic-line', since='2020-01-01T00:00:00Z'))['result']
    assert filtered['total'] == 0 and filtered['unknown_time_count'] == 1
    assert history(c, HistoryRequest('other'))['result']['total'] == 0


def test_history_cli_matches_typed_api(history_case):
    c, context, _ = history_case
    skill = Path(__file__).resolve().parents[1]
    command = ['/usr/bin/python3',str(skill/'scripts/cli.py'),'--db',str(context.db), '--workvault',str(context.workvault),
               '--cache-dir',str(context.cache_dir),'history','--project-slug','history','--limit','1']
    proc = subprocess.run(command,capture_output=True,text=True,timeout=30)
    assert proc.returncode == 0, proc.stderr
    actual = json.loads(proc.stdout)
    # The CLI adds current-plan selection from the persisted intake metadata;
    # the underlying typed history/cursor/trust contract remains byte-for-byte.
    current = actual['result'].pop('current_plan')
    assert current['basis']=='source_file_mtime_ns' and current['status'] in ('selected','ambiguous')
    for row in actual['result']['records']:
        assert type(row.pop('source_mtime_ns')) is int
    assert actual == history(c, HistoryRequest('history',limit=1))
    wrong = subprocess.run(command+['--since','2026-11-16'],capture_output=True,text=True,timeout=30)
    assert wrong.returncode == json.loads(wrong.stdout)['exit_code'] == 2


def test_q_history_integration_uses_same_api(history_case):
    root = Path('/home/tkachenkoav/hermes-workspace/skills/research/workvault-rag')
    skill = (root/'SKILL.md').read_text()
    reference = (root/'references/plan-queries.md').read_text()
    assert 'mofs_index.plan.history' in skill and 'HistoryRequest' in reference
    assert '[since, until)' in reference and 'unknown_time_count' in reference
    assert '--time-field received' in reference and 'unknown_source_dates' in reference
    import re
    snippet = next(block for block in re.findall(r'```python\n(.*?)```', reference, re.S) if 'HistoryRequest(' in block)
    # Execute Q's actual documented request against the same isolated fixture.
    namespace = {'conn': history_case[0]}
    exec(compile(snippet.replace("project_slug='trisigma'", "project_slug='history'"), 'Q/references/plan-queries.md', 'exec'), namespace)
    result = namespace['answer']
    assert result['result']['total'] == 3 and result['parameters']['time_field'] == 'received'



@pytest.mark.parametrize('view,identity', [('files','item_id'),('snapshots','snapshot_id'),('publications','publication_id')])
def test_history_all_views_paginate_without_duplicates(history_case, view, identity):
    c,_,_=history_case
    expected=history(c,HistoryRequest('history',view=view))['result']['records']
    seen=[];cursor=None
    while True:
        page=history(c,HistoryRequest('history',view=view,limit=1,cursor=cursor))['result']
        seen.extend(page['records'])
        cursor=page['next_cursor']
        if not cursor: break
    assert [row[identity] for row in seen]==[row[identity] for row in expected]
