"""Public CLI journeys with real E/F, populated baseline and durable receipts."""
import hashlib
import json
from pathlib import Path

import pytest
from mofs_index.db import connect_durable
from mofs_index.plan import query as q, writer as w

pytestmark = [pytest.mark.acceptance, pytest.mark.mpp_fixtures]


@pytest.mark.parametrize('policy', ['continue', 'stop'])
def test_inbox_errors_resume_and_history(policy, stage13_input, stage13_cli, stage13_record, tmp_path):
    context, run = stage13_cli
    inbox = context.workvault/'Inbox'/'isolated-upload'
    inbox.mkdir(parents=True)
    for case, name in [('E', '01-E.mpp'), ('F', '03-F.mpp')]:
        source, _ = stage13_input(case)
        (inbox/name).write_bytes(source.read_bytes())
    (inbox/'02-corrupt.mpp').write_bytes(b'Intentional acceptance corrupt MPP')
    (inbox/'04-duplicate.mpp').write_bytes((inbox/'01-E.mpp').read_bytes())
    (inbox/'~$unfinished.mpp').write_bytes(b'ignored unfinished')
    first = run('batch', 'save', '--inbox', str(inbox), '--project-slug', 'stage13-trisigma',
                '--batch-id', 'G-'+policy, '--on-error', policy)
    stage13_record('G-'+policy+'-first', {'case': 'G', 'receipt': first,
        'baseline_before': context.baseline_before, 'baseline_after': context.baseline(),
        'transport_limitation': 'Telegram rejects before skill; folder plus one text command is the supported route'})
    assert first['exit_code'] == 6 and first['published'] is False
    assert first['inputs_frozen_at'] and first['counts']['total'] == 4
    assert first['counts']['failed'] == 1
    assert first['counts']['saved'] == (2 if policy == 'continue' else 1)
    errors = run('batch', 'show', '--batch-id', first['batch_id'], '--view', 'errors')
    stage13_record('G-'+policy+'-errors', {'case': 'G', 'result': errors})
    # Originals are deliberately deleted after freeze; resume must not reopen them.
    for path in inbox.glob('*.mpp'):
        path.unlink()
    (inbox/'99-late.mpp').write_bytes(b'not in the frozen request')
    resumed = run('batch', 'resume', '--batch-id', first['batch_id'])
    stage13_record('G-'+policy+'-resume', {'case': 'G', 'receipt': resumed,
        'baseline_before': context.baseline_before, 'baseline_after': context.baseline()})
    assert resumed['manifest_sha256'] == first['manifest_sha256']
    assert resumed['counts']['total'] == 4 and resumed['exit_code'] == 6
    if policy == 'continue':
        assert resumed['counts']['saved'] == 2 and resumed['counts']['unchanged'] == 1
    else:
        # A nonretryable corrupt item still enforces the frozen stop policy.
        # Retryable-stop recovery is covered separately in the failure matrix.
        assert resumed['counts']['saved'] == 1 and resumed['counts']['not_started'] == 2
    assert {i['item_id'] for i in resumed['items']} == {i['item_id'] for i in first['items']}
    history = run('history', '--project-slug', 'stage13-trisigma', '--view', 'files')
    stage13_record('G-'+policy+'-history', {'case': 'G', 'result': history})
    records = history['result']['records']
    assert len(records) == 4
    assert all(row['source_mpp_sha256'] and row['original_name'] and row['received_at'] for row in records)
    assert len({i['snapshot_id'] for i in resumed['items'] if i['snapshot_id']}) == (2 if policy == 'continue' else 1)
    assert context.baseline() == context.baseline_before


def test_real_ef_batch_and_exact_compare(stage13_input, stage13_cli, stage13_record):
    context, run = stage13_cli
    e, _ = stage13_input('E'); f, _ = stage13_input('F')
    batch = run('batch', 'save', '--mpp', str(e), '--mpp', str(f),
                '--project-slug', 'stage13-trisigma', '--batch-id', 'real-EF')
    stage13_record('EF-batch', {'cases': ['E', 'F', 'G'], 'receipt': batch,
        'baseline_before': context.baseline_before, 'baseline_after': context.baseline()})
    assert batch['exit_code'] == 0 and batch['counts']['saved'] == 2
    snapshots = [i['snapshot_id'] for i in batch['items']]
    assert len(set(snapshots)) == 2
    conn = connect_durable(context.db)
    try:
        evidence = []
        for item, expected in zip(batch['items'], [(78, 84), (86, 93)]):
            snapshot = q.get_snapshot(conn, item['snapshot_id'])
            normalized = json.loads(snapshot['source_json'])
            assert (len(normalized['tasks']), len(normalized['dependencies'])) == expected
            w.verify_snapshot(conn, item['snapshot_id'])
            metrics = [json.loads(e['detail']) for e in q.get_operation_events(conn, item['operation_id'])
                       if e['event_kind'] == 'save_metrics'][-1]
            assert metrics['counters']['MPXJ_read'] == 1
            evidence.append({'snapshot_id': item['snapshot_id'], 'metrics': metrics,
                             'collections': normalized['collections']})
    finally:
        conn.close()
    compared = run('compare', '--project-slug', 'stage13-trisigma', '--from', 'snapshot:'+snapshots[0],
                   '--to', 'snapshot:'+snapshots[1])
    stage13_record('EF-readback-compare', {'cases': ['E', 'F', 'G'], 'items': evidence, 'result': compared})
    assert compared['exit_code'] == 0
    assert compared['result']['receipt']['mapping'] == 'unknown'
    assert compared['result']['unmatched_entities']['task']['from']
    assert context.baseline() == context.baseline_before


def test_today_cli_local_boundaries(stage13_input, stage13_cli, stage13_record, monkeypatch):
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    from mofs_index.plan.history import history, HistoryRequest
    from plan_save import save_snapshot
    context, run = stage13_cli
    source, _ = stage13_input('E')
    today = datetime.now(ZoneInfo('Europe/Moscow')).replace(hour=0, minute=0, second=0, microsecond=0)
    until = today+timedelta(days=1)
    receipts = []
    for stamp in (today-timedelta(seconds=1), today, until-timedelta(seconds=1), until):
        monkeypatch.setattr(w, '_now', lambda stamp=stamp: stamp.isoformat())
        result = save_snapshot(source, project_slug='stage13-trisigma', context=context)
        assert result.exit_code == 0
        receipts.append(result.to_dict())
    result = run('history', '--project-slug', 'stage13-trisigma', '--view', 'files', '--time-field', 'received',
                 '--since', today.isoformat(), '--until', until.isoformat())
    stage13_record('today', {'result': result, 'since': today.isoformat(), 'until': until.isoformat(),
                            'expected_item_ids': [r['item_id'] for r in receipts[1:3]]})
    assert {row['item_id'] for row in result['result']['records']} == {r['item_id'] for r in receipts[1:3]}
    assert today.utcoffset().total_seconds() == 10800


def test_final_baseline_audit(request, stage13_record, tmp_path):
    root = getattr(request.config, '_acceptance_root', tmp_path)
    rows = []
    for path in (root/'reports/evidence').glob('*.json'):
        value = json.loads(path.read_text())
        if 'baseline_before' in value and 'baseline_after' in value:
            rows.append({'source':str(path),'test_id':value['test_id'],
                'before':value['baseline_before'],'after':value['baseline_after']})
    if request.config.getoption('--acceptance-stage') == '13':
        assert rows, 'No populated baseline observations before live acceptance'
    assert all(row['before'] == row['after'] for row in rows)
    stage13_record('final-baseline-audit', {'observations':rows,'status':'passed'})
