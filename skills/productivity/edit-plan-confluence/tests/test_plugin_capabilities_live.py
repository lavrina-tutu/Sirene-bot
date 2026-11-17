"""Independent corrective controls on the installed Confluence wrapper.

Only allowlisted test children are written. Browser observation never injects
models or modifies scheduling state. Unknown-field roundtrip grants no support.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

import pytest

pytestmark = pytest.mark.confluence_live
CASES = json.loads((Path(__file__).parent/'fixtures/golden/capability-controls.json').read_text())['cases']
PARENT = '519501810'


@pytest.fixture(scope='module')
def capability_page(request):
    from env import load_confluence_env
    from conf_client import ConfluenceClient
    from macro import build_macro_html, new_macro_ids
    root = request.config._acceptance_root
    for name in ('browser-deps','browsers'):
        assert (root/name).is_dir(), name
    sys.path.insert(0,str(root/'browser-deps'))
    os.environ['PLAYWRIGHT_BROWSERS_PATH'] = str(root/'browsers')
    from playwright.sync_api import sync_playwright
    from urllib.parse import urlsplit
    token = load_confluence_env(Path.home()/'USERTOOLS/ConfluenceSync/.env')['CONFLUENCE_TOKEN']
    client = ConfluenceClient(token=token)
    parent = client.get_page(PARENT)
    mid,pid,phash = new_macro_ids()
    page = client.create_page('EditPlanConfluence corrective capability controls '+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f'),
        parent['space']['key'],build_macro_html(mid,pid,phash),PARENT)
    request.config._acceptance_counters['live_POST'] += 1
    page_id = str(page['id'])
    assert page_id not in {PARENT,'496600693','499550441','499566117','506248940','519492935'}
    if hasattr(request.config,'_stage13_live_pages'): request.config._stage13_live_pages.add(page_id)
    folder = root/'capability-controls';folder.mkdir(exist_ok=True)
    (folder/'target.json').write_text(json.dumps({'page_id':page_id,'parent':PARENT,'title':page['title']}))
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True,args=['--no-sandbox'])
        ctx = browser.new_context(timezone_id='Europe/Moscow',extra_http_headers={'Cache-Control':'no-cache'})
        def authorize(route):
            if urlsplit(route.request.url).netloc != urlsplit(client.base_url).netloc or route.request.method not in ('GET','HEAD'):
                route.abort();return
            route.continue_(headers={**route.request.headers,'Authorization':'Bearer '+token})
        ctx.route('**/*',authorize)
        yield client,page_id,'gantt-chart-'+pid+'.json',ctx,folder
        ctx.unroute_all(behavior='wait');browser.close()


@pytest.mark.parametrize('case',CASES,ids=lambda c:c['id'])
def test_installed_capability_control(case,capability_page,request):
    from gantt_attachment import _create_attachment
    from prepared_plan import canonical_bytes
    from plugin_profile import PluginProfile
    client,page_id,filename,ctx,root = capability_page
    folder=root/case['id'];folder.mkdir(exist_ok=True)
    payload=canonical_bytes(case['input']);(folder/'input.json').write_bytes(payload)
    # create helper resolves existing attachment updates through the same endpoint.
    from gantt_attachment import _post_attachment_data,attachment_info
    prior=[a for a in client.list_attachments(page_id) if a['title']==filename]
    att=(_post_attachment_data(client,page_id,prior[0]['id'],filename,payload) if prior
         else _create_attachment(client,page_id,filename,payload))
    request.config._acceptance_counters['live_POST']+=1
    received=client.download_attachment(page_id,filename,att.version)
    assert received==payload
    (folder/'received.json').write_bytes(received)
    storage=client.get_page(page_id);(folder/'storage.xml').write_text(storage['body']['storage']['value'])
    page=ctx.new_page();fetched=[];assets=set();wrappers=set();errors=[]
    def capture(response):
        if response.status==200 and '/download/attachments/'+page_id+'/' in response.url:
            fetched.append({'url':response.url,'bytes':response.body()})
        if response.status==200 and '/static/chunks/' in response.url and response.url.endswith('7b1ccf34.b54da94330ce3dd5.js'):
            assets.add(hashlib.sha256(response.body()).hexdigest())
        if response.status==200 and response.url.endswith('103.dc91403c7e11c30e.js'):
            wrappers.add(hashlib.sha256(response.body()).hexdigest())
    page.on('response',capture);page.on('pageerror',lambda err:errors.append(str(err)))
    observation={'case':case['id'],'capabilities':case['capabilities'],'status':'not_verified','page_id':page_id,
        'attachment_id':att.attach_id,'attachment_version':att.version,'page_version':storage['version']['number'],
        'source_normalization':case.get('source_normalization'),'expected':case['expected'],'input_sha256':hashlib.sha256(payload).hexdigest(),'runtime_errors':errors}
    try:
        page.goto(client.base_url+'/pages/viewpage.action?pageId='+page_id,wait_until='domcontentloaded',timeout=60000)
        frame=page.wait_for_selector('iframe[src*="gantt-chart.html"]',timeout=45000).content_frame()
        try:
            frame.wait_for_function('()=>window.gantt?.project?.eventStore?.allRecords?.length>=3',timeout=45000)
        except Exception:
            (folder/'initial-load-errors.json').write_text(json.dumps({'runtime_errors':errors[:],'recovery':'one_read_only_reload'}))
            page.reload(wait_until='domcontentloaded',timeout=60000)
            frame=page.wait_for_selector('iframe[src*="gantt-chart.html"]',timeout=45000).content_frame()
            frame.wait_for_function('()=>window.gantt?.project?.eventStore?.allRecords?.length>=3',timeout=45000)
        data=frame.evaluate('''async()=>{
            await Promise.race([gantt.project.commitAsync(),new Promise((_,r)=>setTimeout(()=>r(new Error('commit_timeout')),10000))]);
            const local=d=>d&&[d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-')+'T'+[d.getHours(),d.getMinutes(),d.getSeconds()].map(v=>String(v).padStart(2,'0')).join(':');
            const fields=['actualStartDate','actualEndDate','actualDuration','actualEffort','stopDate','resumeDate','stop','resume','startDate','endDate','availability'];
            const native=m=>Object.fromEntries(fields.map(f=>[f,Boolean(m.getFieldDefinition?.(f))]));
            return {build:__NEXT_DATA__.buildId,engine_version:bryntum.getVersion('gantt'),
                tasks:gantt.project.eventStore.allRecords.map(t=>({...t.toJSON(),children:undefined,startDate:local(t.startDate),endDate:local(t.endDate),calendar:t.calendar?.id??t.calendar,segments:t.segments?.map(s=>({...s.toJSON(),startDate:local(s.startDate),endDate:local(s.endDate)})),native_fields:native(t)})),
                resources:gantt.project.resourceStore.records.map(r=>({...r.toJSON(),calendar:r.calendar?.id??r.calendar,native_fields:native(r)})),
                assignments:gantt.project.assignmentStore.records.map(a=>({...a.toJSON(),native_fields:native(a)})),
                calendars:gantt.project.calendarManagerStore.allRecords.map(c=>({id:c.id,parentId:c.parentId,intervals:c.intervals?.map(i=>i.toJSON())}))};
        }''')
        observation.update(data)
        profile=PluginProfile.load()
        assert 'frontend-build:'+data['build']==profile.document['plugin']['version']
        assert profile.document['plugin']['asset_sha256'] in assets
        observation['asset_sha256']=profile.document['plugin']['asset_sha256']
        if profile.document['plugin'].get('wrapper_asset_sha256'):
            assert profile.document['plugin']['wrapper_asset_sha256'] in wrappers
            observation['wrapper_asset_sha256']=profile.document['plugin']['wrapper_asset_sha256']
        observation['confluence_version']=page.locator('meta[name="ajs-version-number"]').get_attribute('content')
        assert fetched and fetched[-1]['bytes']==payload
        from urllib.parse import urlsplit,parse_qs
        assert parse_qs(urlsplit(fetched[-1]['url']).query).get('version')==[str(att.version)]
        (folder/'browser-received.json').write_bytes(fetched[-1]['bytes'])
        observation['browser_received_sha256']=hashlib.sha256(fetched[-1]['bytes']).hexdigest()
        checks={}
        for path,expected in case['expected'].items():
            ident,*parts=path.split('.')
            collection='tasks'
            if ident in ('assignments','resources'):
                collection=ident;ident,*parts=parts
            actual=next(t for t in data[collection] if str(t['id'])==ident)
            for part in parts:actual=len(actual) if part=='length' else actual.get(part) if isinstance(actual,dict) else None
            checks[path]={'expected':expected,'actual':actual,'passed':actual==expected}
        observation['checks']=checks
        observation['status']='passed' if case.get('assertion_kind') != 'unsupported' and checks and all(c['passed'] for c in checks.values()) else 'not_verified'
        observation['assertion_kind']=case.get('assertion_kind','supported')
        if checks:assert all(c['passed'] for c in checks.values()),checks
    finally:
        (folder/'observation.json').write_text(json.dumps(observation,ensure_ascii=False,indent=2)+'\n')
        try:page.locator('body').screenshot(path=str(folder/'render.png'))
        finally:page.close()
