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
