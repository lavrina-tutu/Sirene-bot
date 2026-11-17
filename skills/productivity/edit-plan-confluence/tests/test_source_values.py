"""Source facts, displayed values and scheduling remain distinct contracts."""
from copy import deepcopy
import json

import pytest
from mpp_convert import convert_prepared_plan, EMPTY_TEMPLATE
from plan_diagnostics import flatten
from prepared_plan import PreparedPlan

pytestmark = pytest.mark.unit


@pytest.mark.parametrize('percent', ['0', '21', '47', '76', '100', '21.125'])
def test_exact_percent_without_status_setter(stage08_export, stage08_profile, percent):
    export = deepcopy(stage08_export)
    export['tasks'][1]['percent_complete'] = {'value': percent, 'quality': 'ok', 'reason': None}
    prepared = PreparedPlan.from_export(export, timezone_hint='Europe/Moscow')
    conversion = convert_prepared_plan(prepared, plugin_profile=stage08_profile)
    node = flatten(conversion['gantt']['eventsData'])[conversion['mappings']['tasks'][export['tasks'][1]['task_key']]]
    from decimal import Decimal
    assert Decimal(str(node['percentDone'])) == Decimal(percent)
    assert 'status' not in node, 'status setter quantizes percentDone'
    assert prepared.normalized_data['tasks'][1]['percent_complete']['value'] == percent


def test_columns_visible_in_both_modes():
    template = json.loads(EMPTY_TEMPLATE.read_text())
    for mode in ('view', 'edit'):
        columns = {c['id']: c for c in template['initialState'][mode]['columns']}
        assert all(columns[name].get('hidden') is False
                   for name in ('status', 'percentdone', 'startdate', 'enddate', 'duration'))


@pytest.mark.parametrize('percent,start,finish,active,review', [
    ('0', '2026-01-05T09:00', None, True, True),
    (None, None, None, True, True),
    ('47', None, '2026-01-06T18:00', True, True),
    ('21.125', None, None, False, False),
    ('100', None, '2026-01-06T18:00', True, False),
])
def test_source_facts_do_not_infer_actual_finish(percent, start, finish, active, review):
    from mpp_convert import source_fact_values
    field = lambda v: {'value': v, 'quality': 'ok' if v is not None else 'missing', 'reason': None if v is not None else 'not_set'}
    task = {'percent_complete': field(percent), 'actual_start': field(start), 'actual_finish': field(finish),
            'finish': field('2099-12-31T18:00'), 'active': field(active)}
    values = source_fact_values(task)
    assert values['custom_mpp_actual_finish'] == (finish or 'не задано')
    assert values['custom_mpp_percent_complete'] == (percent or 'не задано')
    assert ('требует проверки' in values['custom_mpp_source_state']) is review
    if active is False:
        assert 'indeterminate' in values['custom_mpp_source_state'] and 'неактивна' in values['custom_mpp_source_state']


def test_custom_summary_values_are_text_and_not_aggregates(stage08_export, stage08_profile):
    from mpp_convert import SOURCE_COLUMNS
    export = deepcopy(stage08_export)
    summary = next(t for t in export['tasks'] if t.get('summary') and t.get('id') != 0)
    summary['percent_complete'] = {'value': '47.375', 'quality': 'ok', 'reason': None}
    summary['actual_work'] = {'value': '2.125 h', 'quality': 'ok', 'reason': None,
                             'quantity': {'amount': '2.125', 'units': 'HOURS', 'source_units': 'h', 'elapsed': False}}
    out = convert_prepared_plan(PreparedPlan.from_export(export, timezone_hint='Europe/Moscow'), plugin_profile=stage08_profile)
    node = flatten(out['gantt']['eventsData'])[out['mappings']['tasks'][summary['task_key']]]
    assert node['custom_mpp_percent_complete'] == '47.375'
    assert node['custom_mpp_actual_work'] == '2.125 h'
    assert all(out['gantt']['customColumns'][column]['type'] == 'customtext' for column, _ in SOURCE_COLUMNS.values())
    for mode in ('view', 'edit'):
        columns = {c['id']: c for c in out['gantt']['initialState'][mode]['columns']}
        assert all(columns[column]['hidden'] is False for column, _ in SOURCE_COLUMNS.values())


def test_displayed_actuals_use_planned_schedule(stage08_export):
    from plugin_profile import PluginProfile
    from plan_diagnostics import capability_findings
    export = deepcopy(stage08_export)
    export['tasks'][2]['actual_start'] = {'value':'2026-01-05T09:00:00','quality':'ok','reason':None}
    prepared = PreparedPlan.from_export(export, timezone_hint='Europe/Moscow')
    profile = PluginProfile.load()
    conversion = convert_prepared_plan(prepared, plugin_profile=profile)
    found = next(f for f in capability_findings(prepared.normalized_data, profile, conversion)
                 if f['entity']==export['tasks'][2]['task_key'] and f['code']=='task_actuals_display_only:actual_start')
    assert found['category']=='display_only'
    assert found['represented']['profile_supported'] and found['represented']['source_match']
    assert found['represented']['calendar_semantics']=='not_verified'


@pytest.mark.parametrize('damage', ['date', 'duration', 'native', 'hidden', 'missing', 'type', 'text'])
def test_actuals_display_cannot_hide_schedule_or_display_loss(stage08_export, damage):
    from plugin_profile import PluginProfile
    from plan_diagnostics import capability_findings
    from plan_policy import evaluate
    export = deepcopy(stage08_export)
    task = export['tasks'][2]
    task['actual_start'] = {'value':'2026-01-05T09:00:00','quality':'ok','reason':None}
    prepared = PreparedPlan.from_export(export, timezone_hint='Europe/Moscow')
    profile = PluginProfile.load()
    conversion = convert_prepared_plan(prepared, plugin_profile=profile)
    node = flatten(conversion['gantt']['eventsData'])[conversion['mappings']['tasks'][task['task_key']]]
    column = 'custom_mpp_actual_start'
    if damage == 'date': node['startDate'] = '2099-01-01T09:00:00'
    elif damage == 'duration': node['duration'] += 1
    elif damage == 'native': node['actualStart'] = task['actual_start']['value']
    elif damage == 'hidden':
        next(c for c in conversion['gantt']['initialState']['view']['columns'] if c['id']==column)['hidden']=True
    elif damage == 'missing': del node[column]
    elif damage == 'type': conversion['gantt']['customColumns'][column]['type']='number'
    else: node[column] = 'wrong fact'
    found = [f for f in capability_findings(prepared.normalized_data,profile,conversion) if f['entity']==task['task_key']]
    assert evaluate(found)['exit_code']==5
    assert any(f['classification']=='schedule-affecting' for f in found)


def test_publish_with_all_actuals_then_repeat(publish_case, monkeypatch):
    import pipeline
    from test_publish_prepare import _fake_raw_upload
    from mpp_convert import PUBLICATION_LABEL
    from plugin_profile import PluginProfile
    c = publish_case
    _fake_raw_upload(c, monkeypatch)
    data = deepcopy(c['export'])
    task = data['tasks'][2]
    for field, value in [('actual_start','2026-01-05T09:00:00'),
                         ('actual_finish','2026-01-06T18:00:00'),
                         ('actual_duration','2 h'), ('actual_work','3 h'),
                         ('stop','2026-01-05T10:00:00'), ('resume','2026-01-05T11:00:00')]:
        task[field] = {'value':value,'quality':'ok','reason':None}
    options = dict(page_id='test-page',mpp_path=c['source'],project_slug='test',
        timezone_hint='Europe/Moscow',context=c['context'],export=data,plugin_profile=PluginProfile.load())
    result = pipeline.publish_plan(c['client'], **options)
    assert result.exit_code == 0 and result.receipt['published'] is True, result.receipt
    assert PUBLICATION_LABEL in c['client'].get_page('test-page')['body']['storage']['value']
    assert result.receipt['verification']['schedule']['status']=='not_verified'
    repeat = pipeline.publish_plan(c['client'], **options)
    assert repeat.exit_code == 0 and repeat.receipt['status']=='unchanged'
    assert repeat.counters['POST']==repeat.counters['PUT']==0
