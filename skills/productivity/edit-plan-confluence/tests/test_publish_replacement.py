"""Changed publication replaces the complete plan, preserving target identity."""
from copy import deepcopy
import hashlib
import json

import pytest
import pipeline
from macro import find_macro
from mofs_index.plan import query as q, writer as w
from plan_diagnostics import flatten
from test_publish_prepare import prepare, _fake_raw_upload

pytestmark = pytest.mark.unit


def test_full_replacement_retains_macro_and_repeat_versions(publish_case, monkeypatch):
    c=publish_case;_fake_raw_upload(c,monkeypatch)
    c['client'].page['body']['storage']['value'] += '<p>Unmanaged replacement neighbour</p>'
    first=pipeline.publish_prepared(c['client'],prepare(c))
    assert first.exit_code==0 and first.receipt['published'] is True,first.receipt
    initial_macro=find_macro(c['client'].page['body']['storage']['value'])
    changed=deepcopy(c['export'])
    changed['tasks']=[t for t in changed['tasks'] if t['task_key']!='uid:3']
    changed['tasks'][0]['child_task_keys']['value']=['uid:2']
    changed['tasks'][1]['name']='Replacement task'
    changed['tasks'][1]['percent_complete']={'value':'47.375','quality':'ok','reason':None}
    changed['dependencies']=[];changed['collections']['dependencies']['count']=0
    changed['collections']['tasks']['count']=len(changed['tasks'])
    c['source'].write_bytes(c['source'].read_bytes()+b' changed source removes task and relation')
    changed['provenance'].update(sha256=hashlib.sha256(c['source'].read_bytes()).hexdigest(),size_bytes=c['source'].stat().st_size)
    c['export']=changed
    second=pipeline.publish_prepared(c['client'],prepare(c))
    assert second.exit_code==0 and second.receipt['published'] is True,second.receipt
    assert second.counters['POST']==1
    # The macro and summary storage already match; replacing attachment bytes
    # must not create an unnecessary page version.
    assert second.counters['PUT']==0
    storage=c['client'].page['body']['storage']['value'];macro=find_macro(storage)
    assert (macro.macro_id,macro.param_id,macro.param_hash)==(initial_macro.macro_id,initial_macro.param_id,initial_macro.param_hash)
    assert 'Unmanaged replacement neighbour' in storage
    latest=q.get_preparation_result(c['conn'],second.receipt['operation_id'])
    raw=w.verify_artifact(c['conn'],latest['representation_artifact_id'])
    expected=json.loads(__import__('pathlib').Path(raw).read_text());nodes=flatten(expected['eventsData'])
    assert set(nodes)=={1,2} and not expected['dependenciesData']
    assert nodes[2]['name']=='Replacement task' and nodes[2]['custom_mpp_percent_complete']=='47.375'
    assert second.receipt['attachment_version']==first.receipt['attachment_version']+1
    page_version=c['client'].page['version']['number']
    again=pipeline.publish_prepared(c['client'],prepare(c))
    assert again.exit_code==0 and again.receipt['status']=='unchanged'
    assert again.counters['POST']==again.counters['PUT']==0
    assert c['client'].page['version']['number']==page_version
    assert again.receipt['attachment_version']==second.receipt['attachment_version']
    assert c['conn'].execute('SELECT count(*) FROM plan_snapshot').fetchone()[0]==2
