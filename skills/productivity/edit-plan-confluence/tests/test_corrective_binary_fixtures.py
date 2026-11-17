"""Actual binary positive/negative sources; no injected cleaned export."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest
from prepared_plan import PreparedPlan
from plugin_profile import PluginProfile
from mpp_convert import convert_prepared_plan
from plan_diagnostics import diagnose
from plan_policy import evaluate

pytestmark=pytest.mark.mpp_fixtures
FIXTURES=Path(__file__).parent/'fixtures/synthetic'


@pytest.mark.parametrize('revision',[False,True],ids=['anchor','revised'])
def test_binary_positive_recipe_and_real_admission(tmp_path,revision):
    from env import select_mpxj_python
    from plan_context import PlanContext
    runtime=select_mpxj_python();context=PlanContext.resolve()
    dest=tmp_path/'recreated.mpp'
    code='''import importlib.util,sys
sys.path.insert(0,sys.argv[5])
spec=importlib.util.spec_from_file_location('binary_recipe',sys.argv[1]);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.make_identity_positive_fixture(sys.argv[2],sys.argv[3],revision=sys.argv[4]=='1')'''
    command=[runtime.python,'-c',code,str(FIXTURES/'binary_recipe.py'),str(FIXTURES/'mpp14relations.mpp'),str(dest),'1' if revision else '0',str(context.mpp_reader)]
    proc=subprocess.run(command,capture_output=True,text=True,timeout=180)
    assert proc.returncode==0,proc.stderr
    assert dest.read_bytes()==(FIXTURES/'binary-identity-positive'/('revised.mpp' if revision else 'anchor.mpp')).read_bytes()
    proc=subprocess.run([runtime.python,str(context.mpp_reader/'plan_export.py'),str(dest)],capture_output=True,text=True,timeout=180)
    assert proc.returncode==0,proc.stderr
    export=json.loads(proc.stdout[proc.stdout.index("{"):])
    assert export['telemetry']['MPXJ_read']==1
    assert len(export['tasks'])==6 and len(export['dependencies'])==4
    assert export['collections']['dependencies']['enumeration_complete'] is True
    assert all(x['status']=='complete' for x in export['collections'].values())
    assert not export['assignments'] and all(t['actual_work']['quantity']['amount']=='0' for t in export['tasks'])
    p=PreparedPlan.from_export(export,timezone_hint='Europe/Moscow');profile=PluginProfile.load()
    conversion=convert_prepared_plan(p,plugin_profile=profile)
    admission=evaluate(diagnose(p,conversion,plugin_profile=profile)['findings'])
    assert admission['exit_code']==0 and admission['allowed'] is True,admission
    assert conversion['summary']['root_task_key']=='uid:1000'
