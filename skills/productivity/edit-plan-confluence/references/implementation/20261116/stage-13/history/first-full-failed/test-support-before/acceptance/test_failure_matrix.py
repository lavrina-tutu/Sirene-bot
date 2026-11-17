"""Fail-closed checks for acceptance itself; product failures reuse prior tests.

ac-matrix.json explicitly enumerates the existing process-death, concurrent
HTTP, cache, migration, deduplication and decision tests. They run once as part
of the full collection rather than being invoked again through wrappers.
"""
import json
from pathlib import Path

import pytest

pytestmark = [pytest.mark.acceptance, pytest.mark.unit]


@pytest.mark.parametrize('phase,outcome,expected', [
    ('call', 'passed', 'passed'), ('call', 'failed', 'failed'),
    ('setup', 'failed', 'failed'), ('teardown', 'failed', 'failed'),
    ('setup', 'skipped', 'not_run'), ('call', 'skipped', 'not_run')])
def test_report_never_promotes_incomplete_execution(phase, outcome, expected):
    import conftest
    rows = [{'test_id': 'test_example.py::test_one', 'phase': phase, 'status': outcome}]
    assert conftest._stage13_test_status(['test_example.py::test_one'], rows) == expected
    assert conftest._stage13_test_status(['test_example.py::absent'], rows) == 'not_run'


def test_report_aggregate_rejects_missing_evidence(tmp_path):
    import conftest
    rows = [{'test_id': 'test_example.py::test_one', 'phase': 'call', 'status': 'passed'}]
    assert conftest._stage13_requirement_status(
        {'tests': ['test_example.py::test_one'], 'evidence': ['absent.json']}, rows, tmp_path)['status'] == 'not_run'


def test_matrix_requires_all_ac_and_subcases():
    matrix = json.loads((Path(__file__).parent/'ac-matrix.json').read_text())
    assert set(matrix['requirements']) == {'AC-%02d' % i for i in range(1, 28)}
    for ac in ('AC-04', 'AC-09'):
        assert len(matrix['requirements'][ac]['subcases']) >= 7
    for ac in ('AC-19', 'AC-20', 'AC-22'):
        assert len(matrix['requirements'][ac]['subcases']) >= 11
    assert len([key for key in matrix['requirements']['AC-19']['subcases'] if key.startswith('decision-')]) == 9
    assert len(matrix['requirements']['AC-24']['subcases']) == 10
    for requirement in matrix['requirements'].values():
        assert requirement['tests'] and requirement['fixtures'] and requirement['required_evidence']
        for subcase in requirement['subcases'].values():
            assert subcase['tests'] and subcase['fixtures'] and subcase['required_evidence']


def test_final_order_has_all_phases(request):
    if request.config.getoption('--acceptance-stage') != '13':
        return  # Ordinary targeted pytest runs need no full acceptance collection.
    import conftest
    order = request.config._stage13_execution_order
    assert [r['phase'] for r in order] == sorted(r['phase'] for r in order)
    assert [r['group'] for r in order] == sorted(r['group'] for r in order)
    assert set(r['phase'] for r in order) == set(range(2,12))


@pytest.mark.parametrize('choice', ['missing', 'automatic', 'ambiguous-explicit', 'later-revision', 'replace-selected'])
def test_identity_choice_complete_preparation_chain(choice, publish_case, stage13_record):
    """Complete synthetic preparation chain, in addition to real binary tests."""
    from mofs_index.plan import query as q
    from plan_identity import identity_action
    from test_plan_rules import cyclic, register_rule, change_source, confirm, resume, FIXTURE
    from test_publish_prepare import prepare
    c = publish_case
    export = cyclic(c['export'])
    reference = prepare(c, export=export).receipt['snapshot_id']
    register_rule(c, reference, export)
    changed = change_source(c, export)
    started = prepare(c, export=changed)
    operation = started.receipt['operation_id']
    assert started.exit_code == 3 and started.receipt['verification']['archive'] == 'verified'
    if choice == 'missing':
        blocked = resume(c, operation)
        stage13_record('identity-choice-'+choice, {'receipt': blocked.receipt, 'counters': blocked.counters})
        assert blocked.exit_code == 3 and blocked.counters['POST'] == blocked.counters['PUT'] == 0
        assert q.get_identity_requirements(c['conn'], operation)[0]['mapping_revision_id'] is None
        return
    proof = confirm(c, reference, started.receipt['snapshot_id'])
    assert proof['exit_code'] == 0
    def second_revision():
        result = identity_action('confirm', project_slug='test', from_selector='snapshot:'+reference,
            to_selector='snapshot:'+started.receipt['snapshot_id'], mode='continuity', evidence=FIXTURE/'test-only-user-evidence.txt',
            reason='Second explicit synthetic identity assertion', db_path=c['db'], workvault=c['wv'], cache_dir=c['cache'])
        assert result['exit_code'] == 0
        return result['mapping_revision_id']
    if choice == 'ambiguous-explicit':
        second_revision()
        assert resume(c, operation).exit_code == 3
    first = resume(c, operation, **({} if choice=='automatic' else {'mapping_revision':proof['mapping_revision_id']}))
    assert first.exit_code == 0
    selected = q.get_identity_requirements(c['conn'], operation)[0]['mapping_revision_id']
    assert selected == proof['mapping_revision_id']
    if choice in ('later-revision','replace-selected'):
        other = second_revision()
        again = resume(c, operation, **({'mapping_revision':other} if choice=='replace-selected' else {}))
        assert again.exit_code == (4 if choice=='replace-selected' else 0)
        assert q.get_identity_requirements(c['conn'], operation)[0]['mapping_revision_id'] == selected
    else:
        again = resume(c, operation)
        assert again.exit_code == 0
    assert first.receipt['snapshot_id'] == again.receipt['snapshot_id'] == started.receipt['snapshot_id']
    assert again.counters['MPXJ_read'] == 0
    stage13_record('identity-choice-'+choice, {'source_kind':'explicit synthetic export; not a real MPXJ measurement',
        'initial':started.receipt,'identity':proof,'resumed':first.receipt,'repeated':again.receipt,
        'selected_mapping_revision':selected,'counters':again.counters})
