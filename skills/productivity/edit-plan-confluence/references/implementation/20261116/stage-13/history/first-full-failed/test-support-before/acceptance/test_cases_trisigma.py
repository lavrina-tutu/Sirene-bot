"""Real bytes -> public CLI -> archive read-back; no injected parsed exports."""
from decimal import Decimal
import hashlib
import json
from pathlib import Path

import pytest
from mofs_index.db import connect_durable
from mofs_index.plan import query as q, writer as w
from prepared_plan import PreparedPlan, fingerprint
from itogo import compute_itogo_from_prepared

pytestmark = [pytest.mark.acceptance, pytest.mark.mpp_fixtures]
EXPECTED = {'A': (58, 57, 53, '1576'), 'B': (62, 61, 60, '2096'),
            'C': (62, 61, 61, '2088'), 'D': (72, 71, 76, '3136'),
            'E': (78, 77, 84, None), 'F': (86, 85, 93, None)}


def readback(context, receipt):
    conn = connect_durable(context.db)
    try:
        w.verify_snapshot(conn, receipt['snapshot_id'])
        snapshot = q.get_snapshot(conn, receipt['snapshot_id'])
        item = q.get_import_item(conn, receipt['item_id'])
        source = Path(w.verify_artifact(conn, snapshot['source_artifact_id']))
        assert hashlib.sha256(source.read_bytes()).hexdigest() == receipt['source']['sha256']
        normalized = json.loads(snapshot['source_json'])
        export = q.find_artifact_by_hash(conn, snapshot['normalized_data_sha256'])
        assert Path(w.verify_artifact(conn, export['artifact_id'])).read_bytes() == snapshot['source_json'].encode()
        metrics = [json.loads(e['detail']) for e in q.get_operation_events(conn, receipt['operation_id'])
                   if e['event_kind'] == 'save_metrics'][-1]
        prepared = PreparedPlan({'schema_version': 1, 'normalized_data': normalized,
                                 'semantic_sha256': fingerprint(normalized), 'provenance': {}})
        # Snapshot stores semantic data; the public summary consumes those same
        # values, without invoking a second reader or substituting golden JSON.
        summary = compute_itogo_from_prepared(prepared)
        return {'snapshot': snapshot, 'item': item, 'metrics': metrics, 'summary': summary,
                'collections': normalized['collections'], 'versions': {
                    **normalized['source_identity'], 'export': normalized['export_version'],
                    'normalization': normalized['normalization']}}
    finally:
        conn.close()


@pytest.mark.parametrize('case', ['A', 'B', 'C', 'D', 'E', 'F', 'D-risks'])
def test_real_cold_warm_archive(case, stage13_input, stage13_cli, stage13_record):
    source, fixture = stage13_input(case)
    context, run = stage13_cli
    cold = run('save', '--mpp', str(source), '--project-slug', 'stage13-trisigma',
               '--timezone-hint', 'Europe/Moscow')
    assert cold['exit_code'] == 0, cold
    proof = readback(context, cold)
    stage13_record('case-'+case+'-cold', {'case': case, 'fixture': fixture, 'receipt': cold,
        'readback': proof, 'client': 'constructor/import forbidden in subprocess',
        'baseline_before': context.baseline_before, 'baseline_after': context.baseline(),
        'counters': proof['metrics']['counters'], 'functional_status': 'archive_verified'})
    assert proof['metrics']['counters']['MPXJ_read'] == 1
    assert proof['metrics']['counters']['cache_miss'] == 1
    assert cold['published'] is False and cold['external_effect'] == 'none'
    if case in EXPECTED:
        tasks, display, deps, hours = EXPECTED[case]
        assert (cold['task_count'], cold['display_task_count'], cold['dependency_count']) == (tasks, display, deps)
        if hours:
            assert abs(Decimal(proof['summary']['work']['hours'])-Decimal(hours)) <= Decimal('0.001')
    if case == 'A':
        assert fixture['identity_status'] == 'confirmed'
        assert Path(fixture['origin']).name == 'doc_c7df61c64ba6_Переход_на_Trisigma_Только_пилот_150526.mpp'
        assert proof['summary']['d1'] == '23.04.26' and proof['summary']['d2'] == '24.08.26'
        assert cold['exceptions'] == []
    if case == 'D':
        assert Decimal(proof['summary']['duration_working_days']) == Decimal('106.875')
        assert proof['summary']['n_days'] == 107
    if case in ('B', 'C'):
        # Historical numbers remain evidence, not a target to force by removing links.
        stage13_record('case-'+case+'-history', {'case': case,
            'historical': {'model': 98 if case == 'B' else 89,
                           'root_days': '84.875' if case == 'B' else '76.875'},
            'current_summary': proof['summary'],
            'rule_status': 'not_evaluated_without_confirmed_historical_rule_context'})
    renamed = source.with_name('same-bytes-renamed.mpp')
    source.rename(renamed)
    warm = run('save', '--mpp', str(renamed), '--project-slug', 'stage13-trisigma',
               '--timezone-hint', 'Europe/Moscow')
    warm_proof = readback(context, warm)
    stage13_record('case-'+case+'-warm', {'case': case, 'receipt': warm,
        'counters': warm_proof['metrics']['counters'], 'baseline_before': context.baseline_before,
        'baseline_after': context.baseline()})
    assert warm['status'] == 'unchanged' and warm['snapshot_id'] == cold['snapshot_id']
    assert warm['item_id'] != cold['item_id']
    assert warm_proof['metrics']['counters']['MPXJ_read'] == 0
    assert warm_proof['metrics']['counters']['cache_hit'] == 1
    assert context.baseline() == context.baseline_before
