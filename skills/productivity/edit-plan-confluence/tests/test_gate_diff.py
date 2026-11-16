from __future__ import annotations

from gate_diff import build_diff, is_confirmed


def test_is_confirmed():
    assert is_confirmed("лей")
    assert is_confirmed("пиши")
    assert is_confirmed("да")
    assert not is_confirmed("нет")
    assert not is_confirmed("")


def test_build_diff_contains_warning():
    text = build_diff(
        page_id="519501810",
        title="Test",
        operation="замена",
        had_existing_plan=True,
    )
    assert "заменён целиком" in text
    assert "лей" in text


def test_four_value_layers_never_promote_model_to_observed(stage08_export,stage08_profile):
    from prepared_plan import PreparedPlan
    from mpp_convert import convert_prepared_plan
    from gate_diff import representation_diagnostics,format_representation_diagnostics
    p=PreparedPlan.from_export(stage08_export,timezone_hint='Europe/Moscow')
    r=convert_prepared_plan(p,plugin_profile=stage08_profile)
    model={'status':'supported_subset','evidence':'local-only','tasks':{'a':{'start':'2026-02-01'}}}
    diag=representation_diagnostics(p,r,model=model)
    task=next(t for t in diag['tasks'] if t['entity']=='a')
    assert task['source']['start']=='2026-01-05T09:00:00'
    assert task['model']['start']=='2026-02-01' and task['observed'] is None
    assert diag['observed_status']=='not_observed' and diag['schedule']=='not_verified'
    text=format_representation_diagnostics(diag)
    assert '0.3 ч-ч' in text and 'not_observed' in text



def test_four_layers_include_links_calendars_assignments_without_schedule_promotion(stage08_export,stage08_profile):
    from prepared_plan import PreparedPlan
    from mpp_convert import convert_prepared_plan
    from gate_diff import representation_diagnostics
    p=PreparedPlan.from_export(stage08_export)
    result=convert_prepared_plan(p,plugin_profile=stage08_profile)
    diag=representation_diagnostics(p,result,observation={'status':'verified'})
    assert len(diag['dependencies'])==5
    assert len(diag['calendars'])==1
    assert diag['assignments'][0]['source']['work']['quantity']['amount']=='0.1'
    assert diag['dependencies'][1]['represented']['lag']==-1
    assert diag['schedule']=='not_verified'
