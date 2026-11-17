"""Real normalized audit sources retain exact remaining calendar blockers."""
from copy import deepcopy
import gzip
import json

import pytest
from prepared_plan import ROOT, PreparedPlan
from mpp_convert import convert_prepared_plan
from plugin_profile import PluginProfile
from plan_diagnostics import capability_findings

pytestmark = pytest.mark.unit
AUDIT = ROOT/'references/implementation/20261116/stage-13-fix/group-5/final/blocker-audit'


def source(case):
    return json.loads(gzip.decompress((AUDIT/(case+'-source.json.gz')).read_bytes()))


def converted(case):
    data = source(case)
    prepared = PreparedPlan.from_export({**deepcopy(data), 'provenance':data['source_identity']}, timezone_hint=data['resolved_timezone'])
    profile = PluginProfile.load()
    return data, prepared, profile, convert_prepared_plan(prepared, plugin_profile=profile)


def test_D_unassigned_resources_and_independent_interval_preserved_by_owner():
    data, prepared, profile, conversion = converted('D')
    rows = {a['assignment_key']:a for a in data['assignments']}
    assert {'uid:441','uid:699','uid:700','uid:701'} <= {k for k,a in rows.items() if a['resource_key'] is None}
    errors = {(x['entity'],x['code']) for x in conversion['diagnostics']}
    assert not {entity for entity,code in errors if code=='assignment_partial'}
    findings = capability_findings(prepared.normalized_data, profile, conversion)
    assert {f['entity'] for f in findings if f['code']=='unassigned_resource_source_display'} >= {'uid:441','uid:699','uid:700','uid:701'}
    assert not any(f['entity']=='uid:441' and f['code'].startswith('assignment_semantics_unrepresented:') for f in findings)
    assignment = rows['uid:441']; task = next(t for t in data['tasks'] if t['task_key']==assignment['task_key'])
    assert assignment['finish']['value']=='2026-03-30T09:00'
    assert task['finish']['value']=='2026-04-22T18:00'


@pytest.mark.parametrize('case', ['B','C'])
def test_historical_link_retained_without_active_revision(case):
    data, prepared, profile, conversion = converted(case)
    relation = next(d for d in data['dependencies'] if d['predecessor_task_key']=='uid:510' and d['successor_task_key']=='uid:323')
    assert relation['link_type']=='FS' and relation['lag_value']['value']['amount']=='0'
    ident = conversion['mappings']['dependencies'][relation['dependency_key']]
    assert any(d['id']==ident for d in conversion['gantt']['dependenciesData'])
    rules=json.loads((ROOT/'references/profiles/project-rules-v1.json').read_text())['historical']
    rule=next(r for r in rules if r['rule_id']==case)
    assert rule['status']=='inactive' and rule['revision']=='historical-unresolved-v1'
    assert rule['reference_snapshot_id'] is None and rule['evidence_id'] is None
    assert rule['recovery']['rule_revision'] is None
    # Exact relation representation does not prove removal is needed or harmless.
    assert len(conversion['gantt']['dependenciesData'])==len(data['dependencies'])


@pytest.mark.parametrize('case', ['A','B','C','D'])
def test_custom_actuals_are_display_only_for_real_sources(case):
    data, prepared, profile, conversion = converted(case)
    findings=capability_findings(prepared.normalized_data, profile, conversion)
    actuals=[f for f in findings if f['code'].startswith('task_actuals_display_only:')]
    assert actuals
    assert all(f['represented']['source_match'] and f['represented']['profile_supported'] for f in actuals)
    assert all(f['represented']['calendar_semantics']=='not_verified' for f in actuals)
    assert all(f['classification']=='display-only' for f in actuals)
