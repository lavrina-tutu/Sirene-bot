"""Actual plugin observations on an acceptance-only child of the allowlisted test page.

No production plan pages; no model injection. The plugin reads the attachment
from Confluence, calculates it, and the browser observes that loaded project.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone

import pytest

pytestmark=pytest.mark.confluence_live
TEST_PARENT='519501810'
FIXTURES=Path(__file__).parent/'fixtures/golden/plugin-controls.json'


def test_installed_plugin_controls_live(request,tmp_path):
    from env import load_confluence_env
    from conf_client import ConfluenceClient
    from macro import new_macro_ids,build_macro_html,find_macro
    from gantt_attachment import _create_attachment,_post_attachment_data
    from prepared_plan import canonical_bytes
    root=getattr(request.config,'_acceptance_root',tmp_path)
    evidence=root/'live';evidence.mkdir(exist_ok=True)
    status={'status':'not_run','test_parent':TEST_PARENT,'POST':0,'PUT':0,'cases':[],
            'observed_at':datetime.now(timezone.utc).isoformat()}
    try:
        token=load_confluence_env(Path.home()/'USERTOOLS/ConfluenceSync/.env')['CONFLUENCE_TOKEN']
        # Browser is a test dependency, never a product runtime dependency.
        deps=root/'browser-deps'
        if deps.is_dir():sys.path.insert(0,str(deps))
        if (root/'browsers').is_dir():os.environ['PLAYWRIGHT_BROWSERS_PATH']=str(root/'browsers')
        from playwright.sync_api import sync_playwright
        client=ConfluenceClient(token=token)
        parent=client.get_page(TEST_PARENT)
        assert parent['id']==TEST_PARENT
        prior_path=root/'reports/stage08-live.json'
        prior=json.loads(prior_path.read_text()) if prior_path.is_file() else {}
        if prior.get('page_id'):
            child=client.get_page(prior['page_id'],expand='body.storage,version,space,ancestors')
            assert child['title'].startswith('EditPlanConfluence stage 08 controls ')
            assert TEST_PARENT in [a['id'] for a in child['ancestors']]
            macro=find_macro(child['body']['storage']['value'])
            mid,pid,phash=macro.macro_id,macro.param_id,macro.param_hash
        else:
            mid,pid,phash=new_macro_ids()
            title='EditPlanConfluence stage 08 controls '+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
            child=client.create_page(title,parent['space']['key'],build_macro_html(mid,pid,phash),TEST_PARENT)
            status['POST']+=1
        page_id=child['id'];status['page_id']=page_id
        assert page_id!=TEST_PARENT
        filename='gantt-chart-'+pid+'.json'
        from gantt_attachment import attachment_info
        found=[a for a in client.list_attachments(page_id) if a.get('title')==filename]
        assert len(found)<=1
        previous=attachment_info(found[0]) if found else None
        with sync_playwright() as playwright:
            browser_path=root/'browsers'
            if browser_path.is_dir():os.environ['PLAYWRIGHT_BROWSERS_PATH']=str(browser_path)
            browser=playwright.chromium.launch(headless=True,args=['--no-sandbox'])
            context=browser.new_context(bypass_csp=True,timezone_id='Europe/Moscow',extra_http_headers={'Cache-Control':'no-cache'})
            from urllib.parse import urlparse
            authorized_origin=urlparse(client.base_url).netloc
            def authorize_confluence(route):
                if urlparse(route.request.url).netloc != authorized_origin:
                    route.abort()
                    return
                headers={**route.request.headers,'Authorization':'Bearer '+token}
                route.continue_(headers=headers)
            context.route('**/*',authorize_confluence)
            page=context.new_page()
            browser_errors=[]
            browser_downloads=[]
            observed_asset_hashes=set()
            def capture_download(response):
                if response.status==200 and '/static/chunks/' in response.url and response.url.endswith('7b1ccf34.b54da94330ce3dd5.js'):
                    observed_asset_hashes.add(hashlib.sha256(response.body()).hexdigest())
                if response.status==200 and '/download/attachments/'+str(page_id)+'/' in response.url and filename in response.url:
                    browser_downloads.append({'url':response.url,'bytes':response.body()})
            page.on('response',capture_download)
            def verify_browser_bytes(folder,payload,version):
                from urllib.parse import urlparse,parse_qs
                assert browser_downloads, 'plugin did not fetch the uploaded attachment'
                fetched=browser_downloads[-1]
                assert fetched['bytes']==payload, 'browser loaded different attachment bytes'
                assert parse_qs(urlparse(fetched['url']).query).get('version')==[str(version)]
                (folder/'browser-received.json').write_bytes(fetched['bytes'])
                return hashlib.sha256(fetched['bytes']).hexdigest()
            page.on('pageerror',lambda error:browser_errors.append(str(error)))
            for case in json.loads(FIXTURES.read_text())['cases']:
                browser_errors.clear()
                browser_downloads.clear()
                folder=evidence/case['id'];folder.mkdir(exist_ok=True)
                payload=canonical_bytes(case['input']);(folder/'input.json').write_bytes(payload)
                if previous:
                    att=_post_attachment_data(client,page_id,previous.attach_id,filename,payload)
                else:
                    att=_create_attachment(client,page_id,filename,payload)
                previous=att;status['POST']+=1
                metadata=client.get_attachment(att.attach_id)
                assert metadata['version']['number']==att.version and metadata['title']==filename
                assert metadata['container']['id']==page_id
                received=client.download_attachment(page_id,filename,att.version)
                (folder/'received.json').write_bytes(received)
                assert received==payload
                stored=client.get_page(page_id)
                storage=stored['body']['storage']['value'];(folder/'storage.xml').write_text(storage)
                macro=find_macro(storage)
                assert (macro.macro_id,macro.param_id,macro.param_hash)==(mid,pid,phash)
                page.goto(client.base_url+'/pages/viewpage.action?pageId='+str(page_id),wait_until='domcontentloaded',timeout=60000)
                element=page.wait_for_selector('iframe[src*="gantt-chart.html"]',timeout=45000)
                frame=element.content_frame()
                assert frame is not None
                frame.wait_for_url('**/gantt-chart.html',wait_until='domcontentloaded',timeout=45000)
                if case['id']=='elapsed-lag':
                    frame.wait_for_selector('.b-gantt',timeout=30000)
                    for _ in range(10):
                        if any('Conversion unit' in error for error in browser_errors):break
                        page.wait_for_timeout(1000)
                    observation=frame.evaluate('() => ({build:window.__NEXT_DATA__?.buildId,engine_version:window.bryntum?.getVersion("gantt")})')
                    observation.update(case=case['id'],page_id=page_id,status='not_verified',
                        reason='attempted_eday_encoding_has_no_verified_schedule',tasks=[],runtime_errors=browser_errors[:],
                        page_version=stored['version']['number'],attachment_id=att.attach_id,attachment_version=att.version,
                        input_sha256=hashlib.sha256(payload).hexdigest(),received_sha256=hashlib.sha256(received).hexdigest(),
                        confluence_version=page.locator('meta[name="ajs-version-number"]').get_attribute('content'))
                    observation['browser_received_sha256']=verify_browser_bytes(folder,payload,att.version)
                    (folder/'observation.json').write_text(json.dumps(observation,indent=2)+'\n')
                    (folder/'rendered-text.txt').write_text(frame.locator('body').inner_text())
                    frame.locator('body').screenshot(path=str(folder/'render.png'))
                    status['cases'].append(observation)
                    continue
                try:
                    frame.wait_for_function('() => window.gantt?.project?.eventStore?.allRecords?.length >= 3',timeout=30000)
                except Exception:
                    (folder/'initial-load-errors.json').write_text(json.dumps({'runtime_errors':browser_errors[:],'reason':'project_not_ready;read_only_reload'}))
                    page.reload(wait_until='domcontentloaded',timeout=60000)
                    element=page.wait_for_selector('iframe[src*="gantt-chart.html"]',timeout=45000)
                    frame=element.content_frame()
                    assert frame is not None
                    frame.wait_for_url('**/gantt-chart.html',wait_until='domcontentloaded',timeout=45000)
                    frame.wait_for_function('() => window.gantt?.project?.eventStore?.allRecords?.length >= 3',timeout=45000)
                observation=frame.evaluate('''async () => {
                    await Promise.race([gantt.project.commitAsync(), new Promise((_,reject)=>setTimeout(()=>reject(new Error('commit_timeout')),10000))]);
                    const local = d => d && [d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-')+'T'+[d.getHours(),d.getMinutes(),d.getSeconds()].map(x=>String(x).padStart(2,'0')).join(':');
                    return {build:__NEXT_DATA__.buildId,engine_version:bryntum.getVersion('gantt'),
                        relation_codes:gantt.project.dependencyStore.modelClass.Type,
                        hours_per_day:gantt.project.hoursPerDay,dependency_calendar:gantt.project.dependenciesCalendar,
                        tasks:gantt.project.eventStore.allRecords.map(t=>({id:t.id,start:local(t.startDate),finish:local(t.endDate),duration:t.duration,duration_unit:t.durationUnit})),
                        dependencies:gantt.project.dependencyStore.records.map(d=>({id:d.id,type:d.type,lag:d.lag,lagUnit:d.lagUnit})),
                        resources:gantt.project.resourceStore.records.map(r=>({id:r.id,name:r.name})),
                        assignments:gantt.project.assignmentStore.records.map(a=>({id:a.id,event:a.eventId,resource:a.resourceId,units:a.units})),
                        calendars:gantt.project.calendarManagerStore.records.map(c=>({id:c.id,name:c.name,parentId:c.parentId}))};
                }''')
                observation.update(case=case['id'],page_id=page_id,page_version=stored['version']['number'],
                                   attachment_id=att.attach_id,attachment_version=att.version,
                                   input_sha256=hashlib.sha256(payload).hexdigest(),received_sha256=hashlib.sha256(received).hexdigest(),
                                   confluence_version=page.locator('meta[name="ajs-version-number"]').get_attribute('content'))
                observation['browser_received_sha256']=verify_browser_bytes(folder,payload,att.version)
                (folder/'observation.json').write_text(json.dumps(observation,ensure_ascii=False,indent=2)+'\n')
                frame.locator('body').screenshot(path=str(folder/'render.png'))
                status['cases'].append(observation)
            context.unroute_all(behavior='wait')
            browser.close()
        status['status']='observed'
        from plugin_profile import PluginProfile
        installed=PluginProfile.load()
        assert installed.document['plugin']['asset_sha256'] in observed_asset_hashes
        assert all('frontend-build:'+case['build']==installed.document['plugin']['version'] for case in status['cases'])
        status['asset_sha256']=installed.document['plugin']['asset_sha256']
        # Expectations are independent, versioned golden assertions, not echoed input dates.
        expectations=Path(__file__).parent/'fixtures/golden/plugin-controls-expected.json'
        if expectations.is_file():
            expected=json.loads(expectations.read_text())
            for case in status['cases']:
                if expected[case['case']].get('status') == 'not_verified':
                    assert case.get('status') == 'not_verified'
                    continue
                actual=next(t for t in case['tasks'] if t['id']==3)
                assert {k:actual[k] for k in ('start','finish')}==expected[case['case']]
            resource_case=next(c for c in status['cases'] if c['case']=='resources-assignments')
            assert len(resource_case['resources'])==2
            assert {a['units'] for a in resource_case['assignments']}=={0,50}
            status['status']='passed'
        else:
            pytest.fail('Golden observed-date expectations missing; observations saved for inspection')
    except Exception as exc:
        status['error_type']=type(exc).__name__
        raise
    finally:
        request.config._acceptance_counters['live_POST']+=status['POST']
        request.config._acceptance_counters['live_PUT']+=status['PUT']
        (root/'reports/stage08-live.json').write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n')
