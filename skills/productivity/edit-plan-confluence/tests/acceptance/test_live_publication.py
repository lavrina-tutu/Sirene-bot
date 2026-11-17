"""Real A-D via the public CLI; admission is never patched to force a pass."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

import pytest
from mofs_index.db import connect_durable
from mofs_index.plan import query as q, writer as w

pytestmark = [pytest.mark.acceptance, pytest.mark.confluence_live]
PRODUCTION = {'496600693', '499550441', '499566117', '506248940', '519492935'}
PARENT = '519501810'


@pytest.fixture
def live_page(tmp_path, request, monkeypatch, stage13_record):
    from env import load_confluence_env
    from conf_client import ConfluenceClient
    import conf_client, gantt_attachment
    from urllib.parse import urlsplit
    token = load_confluence_env(Path.home()/'USERTOOLS/ConfluenceSync/.env')['CONFLUENCE_TOKEN']
    monkeypatch.setenv('CONFLUENCE_TOKEN', token)
    calls = []
    def trace(original):
        def invoke(req, *args, **kwargs):
            path = urlsplit(req.full_url).path
            assert not any('/'+page+'/' in path or path.endswith('/'+page) for page in PRODUCTION)
            calls.append({'method': req.get_method(), 'path': path})
            return original(req, *args, **kwargs)
        return invoke
    monkeypatch.setattr(conf_client, 'urlopen', trace(conf_client.urlopen))
    monkeypatch.setattr(gantt_attachment, 'urlopen', trace(gantt_attachment.urlopen))
    client = ConfluenceClient(token=token)
    parent = client.get_page(PARENT)
    child = client.create_page('EditPlanConfluence stage 13 '+request.node.name+' '+
        datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f'), parent['space']['key'],
        '<p>Stage 13 acceptance neighbour</p>', PARENT)
    page_id = str(child['id'])
    assert page_id not in PRODUCTION|{PARENT}
    if hasattr(request.config, '_stage13_live_pages'):
        request.config._stage13_live_pages.add(page_id)
    stage13_record('live-target-'+page_id, {'page_id': page_id, 'parent_id': PARENT,
        'title': child['title'], 'before': child, 'source': 'dedicated newly created test page'})
    yield client, page_id, child
    stage13_record('live-target-'+page_id+'-calls', {'page_id': page_id, 'calls': calls,
        'POST': sum(c['method']=='POST' for c in calls), 'PUT': sum(c['method']=='PUT' for c in calls)})


def observe_plugin(client, page_id, expected, request, folder, *, attachment_version, browser_context=None, require_planned_label=True):
    """Read-only normal view: dates, raw facts, rendered cells and reopening."""
    root = getattr(request.config, '_acceptance_root', folder)
    if (root/'browser-deps').is_dir(): sys.path.insert(0, str(root/'browser-deps'))
    if (root/'browsers').is_dir(): os.environ['PLAYWRIGHT_BROWSERS_PATH'] = str(root/'browsers')
    from playwright.sync_api import sync_playwright
    from urllib.parse import urlsplit
    from mpp_convert import SOURCE_COLUMNS
    from plugin_profile import PluginProfile
    from plan_publication_verify import verify_source_value_observation
    folder.mkdir(parents=True, exist_ok=True)
    observation = {'page_id':page_id, 'attachment_version':attachment_version,
        'input_sha256':hashlib.sha256(expected).hexdigest(), 'openings':[]}
    from contextlib import ExitStack
    with ExitStack() as stack:
        if browser_context is None:
            playwright=stack.enter_context(sync_playwright())
            browser=playwright.chromium.launch(headless=True,args=['--no-sandbox'])
            ctx=browser.new_context(timezone_id='Europe/Moscow',extra_http_headers={'Cache-Control':'no-cache'})
        else:
            browser=None;ctx=browser_context
        def route(r):
            if (urlsplit(r.request.url).netloc != urlsplit(client.base_url).netloc
                    or r.request.method not in ('GET','HEAD')):
                r.abort(); return
            r.continue_(headers={**r.request.headers, 'Authorization':'Bearer '+client.token})
        if browser_context is None:ctx.route('**/*', route)
        try:
            for opening in range(2):
                page = ctx.new_page(); received=[]
                def capture(response):
                    if response.status == 200 and '/download/attachments/'+page_id+'/' in response.url:
                        received.append(response.body())
                    for key, suffix in [('asset_sha256','7b1ccf34.b54da94330ce3dd5.js'),
                                        ('wrapper_asset_sha256','103.dc91403c7e11c30e.js')]:
                        if response.status==200 and response.url.endswith(suffix):
                            observation[key]=hashlib.sha256(response.body()).hexdigest()
                page.on('response', capture)
                try:
                    page.goto(client.base_url+'/pages/viewpage.action?pageId='+page_id, wait_until='domcontentloaded', timeout=60000)
                    from mpp_convert import PUBLICATION_LABEL
                    if require_planned_label:
                        assert PUBLICATION_LABEL in page.locator('#main-content').inner_text()
                    frame = page.wait_for_selector('iframe[src*="gantt-chart.html"]', timeout=45000).content_frame()
                    frame.wait_for_function('() => window.gantt?.project?.eventStore?.allRecords?.length > 1', timeout=45000)
                    data = frame.evaluate("""async () => {
                        await gantt.project.commitAsync();
                        const local = d => d && [d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-')+'T'+[d.getHours(),d.getMinutes(),d.getSeconds()].map(x=>String(x).padStart(2,'0')).join(':');
                        return {build:__NEXT_DATA__.buildId,engine_version:bryntum.getVersion('gantt'),readOnly:gantt.readOnly,
                            tasks:gantt.project.eventStore.allRecords.map(t=>({id:t.id,name:t.name,start:local(t.startDate),finish:local(t.endDate),milestone:t.isMilestone,percentDone:t.percentDone,status:t.status,model:t.toJSON(),persistable:t.persistableData})),
                            columns:gantt.columns.records.map(c=>({id:c.id,field:c.field,hidden:c.hidden})),
                            dependencies:gantt.project.dependencyStore.records.map(d=>({from:d.fromEvent.id,to:d.toEvent.id,type:d.type,lag:d.lag})),
                            dependency_count:gantt.project.dependencyStore.count};
                    }""")
                    from collections import Counter
                    expected_dependencies = json.loads(expected)['dependenciesData']
                    assert data['dependency_count'] == len(expected_dependencies)
                    assert Counter((d['from'],d['to'],d['type'],d['lag']) for d in data['dependencies']) == Counter(
                        (d['from'],d['to'],d['type'],d['lag']) for d in expected_dependencies)
                    assert received and received[-1] == expected
                    observation.update(build=data['build'],engine_version=data['engine_version'],
                        confluence_version=page.locator('meta[name="ajs-version-number"]').get_attribute('content'),
                        browser_received_sha256=hashlib.sha256(received[-1]).hexdigest())
                    (folder/('browser-received-'+str(opening)+'.json')).write_bytes(received[-1])
                    columns={c['id']:c for c in data['columns']};data['visible_values']={}
                    assert all(columns[c]['hidden'] is False for c in ('status','percentdone','startdate','enddate','duration'))
                    # Expanding/scrolling is ordinary viewing, without changing schedule fields.
                    frame.evaluate('async()=>{await gantt.expandAll();return null;}')
                    for column,_ in SOURCE_COLUMNS.values():
                        assert columns[column]['hidden'] is False
                        frame.evaluate('async(id)=>{await gantt.scrollColumnIntoView(gantt.columns.getById(id));return null;}',column)
                        values=[]
                        for task in data['tasks']:
                            frame.evaluate('async(id)=>{await gantt.scrollRowIntoView(id);return null;}',task['id'])
                            cell=frame.locator('.b-grid-row[data-id="'+str(task['id'])+'"] .b-grid-cell[data-column="'+column+'"]')
                            assert cell.count()==1
                            text=cell.inner_text().strip();values.append(text)
                            assert text==task['model'][column]
                        data['visible_values'][column]=values
                        if opening==0:page.screenshot(path=str(folder/('visible-'+column+'.png')),full_page=True)
                    from mpp_convert import UNASSIGNED_COLUMN, SNAPSHOT_COLUMN
                    expected_tasks = {}
                    def collect(rows):
                        for task in rows:
                            expected_tasks[str(task['id'])] = task
                            collect(task.get('children', []))
                    collect(json.loads(expected)['eventsData'])
                    if any(t.get(SNAPSHOT_COLUMN) for t in expected_tasks.values()):
                        assert columns[SNAPSHOT_COLUMN]['hidden'] is False
                        frame.evaluate('async(id)=>{await gantt.scrollColumnIntoView(gantt.columns.getById(id));return null;}', SNAPSHOT_COLUMN)
                        data['visible_snapshot_mode'] = {}
                        for task in data['tasks']:
                            assert task['model']['manuallyScheduled'] is True
                            text = expected_tasks[str(task['id'])][SNAPSHOT_COLUMN]
                            frame.evaluate('async(id)=>{await gantt.scrollRowIntoView(id);return null;}', task['id'])
                            cell = frame.locator('.b-grid-row[data-id="'+str(task['id'])+'"] .b-grid-cell[data-column="'+SNAPSHOT_COLUMN+'"]')
                            assert cell.count()==1 and cell.inner_text().strip()==text
                            assert task['model'][SNAPSHOT_COLUMN]==text
                            data['visible_snapshot_mode'][str(task['id'])] = text
                    if any(t.get(UNASSIGNED_COLUMN) for t in expected_tasks.values()):
                        assert columns[UNASSIGNED_COLUMN]['hidden'] is False
                        frame.evaluate('async(id)=>{await gantt.scrollColumnIntoView(gantt.columns.getById(id));return null;}', UNASSIGNED_COLUMN)
                        data['visible_unassigned'] = {}
                        for task in data['tasks']:
                            text = expected_tasks[str(task['id'])].get(UNASSIGNED_COLUMN, '')
                            if not text:
                                continue
                            frame.evaluate('async(id)=>{await gantt.scrollRowIntoView(id);return null;}', task['id'])
                            cell = frame.locator('.b-grid-row[data-id="'+str(task['id'])+'"] .b-grid-cell[data-column="'+UNASSIGNED_COLUMN+'"]')
                            assert cell.count() == 1 and cell.inner_text().strip() == text
                            assert task['model'][UNASSIGNED_COLUMN] == text
                            data['visible_unassigned'][str(task['id'])] = text
                        if opening == 0:
                            page.screenshot(path=str(folder/'visible-unassigned.png'), full_page=True)
                    observation['openings'].append(data)
                    page.screenshot(path=str(folder/('render-'+str(opening)+'.png')),full_page=True)
                finally:page.close()
        finally:
            if browser is not None:
                ctx.unroute_all(behavior='wait');browser.close()
    observation['tasks']=observation['openings'][0]['tasks']
    observation['dependency_count']=observation['openings'][0]['dependency_count']
    observation['source_values_verification']=verify_source_value_observation(json.loads(expected),observation,
        plugin_profile=PluginProfile.load(),page_id=page_id,attachment_version=attachment_version)
    assert observation['source_values_verification']['status']=='verified'
    (folder/'observation.json').write_text(json.dumps(observation,ensure_ascii=False,indent=2)+'\n')
    return observation


@pytest.mark.parametrize('case', ['A','B','C','D'])
def test_real_publish_repeat_and_observed_dates(case, live_page, stage13_input, stage13_cli, stage13_record, request):
    from macro import find_macro
    from itogo import compute_itogo_from_prepared
    from prepared_plan import PreparedPlan, fingerprint
    client, page_id, before = live_page
    context, run = stage13_cli
    source, fixture = stage13_input(case)
    # Real Trisigma scope also exercises historical B/C rule diagnostics.
    result = run('publish', '--mpp', str(source), '--page-id', page_id, '--project-slug', 'trisigma',
                 '--timezone-hint', 'Europe/Moscow', live=True)
    counters = deepcopy(run.last_probe)
    after = client.get_page(page_id)
    conn = connect_durable(context.db)
    try:
        operation = result['operation_id']
        snapshot = q.get_snapshot(conn, result['snapshot_id']) if result['snapshot_id'] else None
        prep = q.get_preparation_result(conn, operation) if operation else None
        versions = q.list_versions(conn, snapshot['plan_id']) if snapshot else None
        status = {'case': case, 'fixture': fixture, 'receipt': result, 'counters': counters,
            'page_id': page_id, 'page_version_before': before['version']['number'],
            'page_version_after': after['version']['number'], 'storage_from_GET': after['body']['storage']['value'],
            'preparation': prep, 'versions': versions, 'baseline_before': context.baseline_before,
            'baseline_after': context.baseline(), 'functional_status': 'passed' if result['published'] is True else 'failed',
            'plugin_observation': None, 'limitation': None if result['published'] is True else 'Real public pipeline did not admit this MPP; no direct-upload fallback'}
        stage13_record('live-'+case, status)
        assert result['verification']['archive'] == 'verified', result
        assert counters['MPXJ_read'] == 1
        assert result['exit_code'] == 0 and result['published'] is True, result
        from mpp_convert import PUBLICATION_LABEL
        assert PUBLICATION_LABEL in after['body']['storage']['value']
        assert counters['POST'] > 0 and counters['PUT'] > 0
        assert after['version']['number']-before['version']['number'] == 1
        attachment_version_before = 0  # Dedicated empty page has no managed attachment.
        assert result['attachment_version']-attachment_version_before == 1
        assert len([v for v in versions['versions'] if v['kind']=='publication']) == 1
        artifact = q.get_artifact(conn, prep['representation_artifact_id'])
        expected = Path(w.verify_artifact(conn, artifact['artifact_id'])).read_bytes()
        macro = find_macro(after['body']['storage']['value'])
        attachment = next(a for a in client.list_attachments(page_id) if a['title']==macro.attachment_name)
        received = client.download_attachment_version(page_id, attachment['id'], macro.attachment_name, result['attachment_version'])
        assert expected == received
        status.update(attachment_id=attachment['id'], attachment_version_before=0,
            attachment_version_after=result['attachment_version'], expected_sha256=hashlib.sha256(expected).hexdigest(),
            received_sha256=hashlib.sha256(received).hexdigest())
        root = request.config._acceptance_root
        observation = observe_plugin(client, page_id, expected, request, root/'live-stage13'/case, attachment_version=result['attachment_version'])
        status['plugin_observation'] = observation
        normalized = json.loads(snapshot['source_json'])
        source_dates = {str(t['id']):t for t in normalized['tasks'] if t.get('id') != 0}
        # The converter preserves source IDs. Compare each task/milestone to the
        # source, never just the summary root or a local scheduler result.
        for task in observation['tasks']:
            source_task = source_dates.get(str(task['id']))
            if source_task:
                duration_amount = None
                try:
                    duration_amount = source_task.get('duration', {}).get('quantity', {}).get('amount')
                except AttributeError:
                    pass
                collapsed = (source_task.get('milestone') is True and duration_amount == '0'
                             and source_task.get('start', {}).get('value') != source_task.get('finish', {}).get('value'))
                for original, observed in [('start','start'),('finish','finish')]:
                    expected_date = source_task[original].get('value')
                    if expected_date:
                        if collapsed:
                            # Решение владельца: веха с duration=0 и расходящимися
                            # start/finish публикуется как есть, плагин рисует точку.
                            # Наблюдается одна дата; обе исходные даты остаются в архиве.
                            delta = abs((datetime.fromisoformat(task[observed])-datetime.fromisoformat(source_task['start'].get('value'))).total_seconds())
                            if original == 'start':
                                assert delta <= 60
                            else:
                                assert delta <= 60 or abs((datetime.fromisoformat(task[observed])-datetime.fromisoformat(source_task['finish'].get('value'))).total_seconds()) <= 60
                        else:
                            delta = abs((datetime.fromisoformat(task[observed])-datetime.fromisoformat(expected_date)).total_seconds())
                            assert delta <= 60
        repeat = run('publish', '--mpp', str(source), '--page-id', page_id, '--project-slug', 'trisigma',
                     '--timezone-hint', 'Europe/Moscow', live=True)
        status['repeat'] = repeat; status['repeat_counters'] = run.last_probe
        assert repeat['status'] == 'unchanged' and repeat['published'] is True
        assert run.last_probe['MPXJ_read'] == 0 and run.last_probe['cache_hit'] >= 1
        assert run.last_probe['POST'] == run.last_probe['PUT'] == 0
        assert client.get_page(page_id)['version']['number'] == after['version']['number']
        assert client.get_attachment(attachment['id'])['version']['number'] == result['attachment_version']
        stage13_record('live-'+case, status)
    finally:
        conn.close()


@pytest.mark.parametrize('action', ['diff','publish'])
def test_new_binary_identity_to_publication(action, live_page, stage13_cli, stage13_record, tmp_path):
    _binary_identity_chain(action,live_page,stage13_cli,stage13_record,tmp_path,positive=True)


@pytest.mark.parametrize('action', ['diff','publish'])
def test_binary_identity_does_not_override_semantic_losses(action,live_page,stage13_cli,stage13_record,tmp_path):
    _binary_identity_chain(action,live_page,stage13_cli,stage13_record,tmp_path,positive=False)


def _binary_identity_chain(action,live_page,stage13_cli,stage13_record,tmp_path,*,positive):
    from plan_rules import relation_signature,task_context
    from prepared_plan import fingerprint
    client,page_id,_=live_page
    context,run=stage13_cli
    fixtures=Path(__file__).resolve().parents[1]/'fixtures/synthetic'
    binary=fixtures/'binary-identity-positive'
    anchor_source=tmp_path/'anchor.mpp'
    anchor_source.write_bytes((binary/'anchor.mpp' if positive else fixtures/'mpp14relations.mpp').read_bytes())
    new_source=tmp_path/'new-binary.mpp'
    new_source.write_bytes((binary/'revised.mpp' if positive else fixtures/'relations-all-types.mpp').read_bytes())
    source_hash=hashlib.sha256(new_source.read_bytes()).hexdigest()
    slug='stage13-binary-positive' if positive else 'stage13-binary-negative'
    label=('new-source-' if positive else 'semantic-negative-')+action
    anchor=run('diff','--mpp',str(anchor_source),'--page-id',page_id,'--project-slug',slug,
               '--timezone-hint','Europe/Moscow',live=True)
    assert anchor['snapshot_id'] and anchor['verification']['archive']=='verified'
    if positive:assert anchor['exit_code']==0,anchor
    conn=connect_durable(context.db)
    try:
        normalized=json.loads(q.get_snapshot(conn,anchor['snapshot_id'])['source_json'])
        # The revised fixture changes UID 1's FS lag; the addressed rule excludes
        # the unchanged UID 2 relation, only for the exact revised source bytes.
        dep=(next(d for d in normalized['dependencies'] if d['uid']['value']==2) if positive
             else next(d for d in normalized['dependencies'] if d['link_type']=='FF'))
        signature=relation_signature(dep,normalized['project'])
        tasks={t['task_key']:t for t in normalized['tasks']}
        keys=(dep['predecessor_task_key'],dep['successor_task_key'])
        evidence=tmp_path/'test-only-user-evidence.txt';evidence.write_bytes((binary/'test-only-user-evidence.txt').read_bytes())
        digest=hashlib.sha256(evidence.read_bytes()).hexdigest()
        eid=w.record_artifact(conn,digest,'other',str(evidence))
        content={'predecessor_key':keys[0],'successor_key':keys[1],'expected_relation':signature,
            'task_contexts':{k:task_context(tasks[k]) for k in keys},'action':'exclude_dependency',
            'reason':'Explicit test-only exclusion of this relation for these exact revised binary bytes; no production consent',
            'approved_at':'2026-11-17T00:00:00Z','policy_revision':'publication-admission-v1',
            'termination':'Exact source, pair, context, relation or policy changes',
            'cause':{'code':'explicit_dependency_exclusion','entity':dep['dependency_key'],
                     'source_sha256':fingerprint(signature),'exact_source_required':source_hash}}
        w.record_project_rule(conn,w.ProjectRuleSpec(label,'binary-fixture-v1',slug,anchor['snapshot_id'],eid,digest,content))
        plan=q.get_snapshot(conn,anchor['snapshot_id'])['plan_id']
        assert all(v.get('source_mpp_sha256')!=source_hash for v in q.list_versions(conn,plan)['versions'])
        first=run(action,'--mpp',str(new_source),'--page-id',page_id,'--project-slug',slug,
                  '--timezone-hint','Europe/Moscow',live=True)
        first_counters=deepcopy(run.last_probe)
        shown=run('operation','show','--operation-id',first['operation_id'],live=True)
        result={'kind':'positive' if positive else 'semantic-negative','action':action,'anchor':anchor,'first':first,
            'operation_show':shown,'first_counters':first_counters,'source_sha256':source_hash}
        stage13_record(label,result)
        assert first['snapshot_id'] and first['verification']['archive']=='verified' and first['published'] is False
        assert first_counters['MPXJ_read']==1 and first_counters['POST']==first_counters['PUT']==0
        assert first['exit_code']==(3 if positive else 5),first
        assert first['status']==('needs_decision' if positive else 'failed'),first
        requirement=shown['identity_requirements'][0]
        assert requirement['from_snapshot_id']==anchor['snapshot_id'] and requirement['to_snapshot_id']==first['snapshot_id']
        identity=run('identity','confirm','--project-slug',slug,'--from','snapshot:'+anchor['snapshot_id'],
            '--to','snapshot:'+first['snapshot_id'],'--mode','continuity','--evidence',str(evidence),
            '--reason','Explicit test fixture identity: same documented binary recipe and stable task UIDs',live=True)
        assert identity['exit_code']==0,identity
        new_source.unlink()
        resumed=run('resume','--operation-id',first['operation_id'],'--mapping-revision',identity['mapping_revision_id'],live=True)
        resumed_counters=deepcopy(run.last_probe)
        result.update(identity=identity,resume=resumed,resume_counters=resumed_counters,
            functional_status='passed' if resumed['published'] is positive else 'failed')
        stage13_record(label,result)
        assert resumed['snapshot_id']==first['snapshot_id'] and resumed_counters['MPXJ_read']==0
        assert len([v for v in q.list_versions(conn,plan)['versions'] if v.get('source_mpp_sha256')==source_hash])==1
        if positive:
            assert resumed['exit_code']==0 and resumed['published'] is True,resumed
            assert resumed_counters['POST']==resumed_counters['PUT']==1
            versions=client.get_page(page_id)['version']['number']
            repeat=run('resume','--operation-id',first['operation_id'],live=True)
            result.update(repeat=repeat,repeat_counters=deepcopy(run.last_probe));stage13_record(label,result)
            assert repeat['status']=='unchanged' and repeat['exit_code']==0 and repeat['published'] is True
            assert run.last_probe['MPXJ_read']==run.last_probe['POST']==run.last_probe['PUT']==0
            assert client.get_page(page_id)['version']['number']==versions
        else:
            assert resumed['exit_code']==5 and resumed['status']=='failed' and resumed['published'] is False,resumed
            assert resumed['external_effect']=='none' and resumed_counters['POST']==resumed_counters['PUT']==0
    finally:conn.close()


def test_installed_names_after_live(request, stage13_record):
    # The existing loader contract is reused again at the mandated final point.
    from test_skill_contract import (test_active_library_loads_both_names, test_wrapper_has_one_canon_and_no_algorithm,
                                     examples, test_documented_cli_examples_parse)
    test_active_library_loads_both_names(request)
    test_wrapper_has_one_canon_and_no_algorithm()
    parsed = examples()
    for source, line in parsed:
        test_documented_cli_examples_parse(source, line)
    stage13_record('installed-names-final', {'status':'passed','source':'installed Hermes skill_view; both names and qualified names',
        'compatible_commands_parsed':len(parsed)})
