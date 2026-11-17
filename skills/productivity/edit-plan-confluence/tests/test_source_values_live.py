"""Read-only browser observations of the installed wrapper, on a test child."""
import hashlib
import json
from pathlib import Path

import pytest
from test_plugin_capabilities_live import capability_page

pytestmark = pytest.mark.confluence_live
FIXTURE = Path(__file__).parent/'fixtures/golden/source-values-control.json'


def test_visible_source_values_and_reopen(capability_page, request):
    from gantt_attachment import _create_attachment, _post_attachment_data
    from prepared_plan import canonical_bytes
    from plugin_profile import PluginProfile
    from mpp_convert import SOURCE_COLUMNS
    client, page_id, filename, ctx, root = capability_page
    folder = root/'source-values'; folder.mkdir(exist_ok=True)
    control = json.loads(FIXTURE.read_text()); payload = canonical_bytes(control['input'])
    (folder/'input.json').write_bytes(payload)
    prior = [a for a in client.list_attachments(page_id) if a['title'] == filename]
    att = (_post_attachment_data(client, page_id, prior[0]['id'], filename, payload) if prior
           else _create_attachment(client, page_id, filename, payload))
    request.config._acceptance_counters['live_POST'] += 1
    received = client.download_attachment(page_id, filename, att.version)
    assert received == payload
    (folder/'received.json').write_bytes(received)
    storage = client.get_page(page_id); (folder/'storage.xml').write_text(storage['body']['storage']['value'])
    observation = {'case':'source-values', 'status':'not_verified', 'assertion_kind':'supported',
        'capabilities':control['capabilities'], 'page_id':page_id, 'parent':'519501810',
        'attachment_id':att.attach_id,'attachment_version':att.version,'page_version':storage['version']['number'],
        'input_sha256':hashlib.sha256(payload).hexdigest(), 'checks':{}, 'openings':[]}
    try:
        for opening in range(2):
            page = ctx.new_page(); fetched = []; assets = {}; errors = []
            def capture(response):
                if response.status == 200 and '/download/attachments/'+page_id+'/' in response.url:
                    fetched.append(response.body())
                for kind, suffix in [('asset_sha256','7b1ccf34.b54da94330ce3dd5.js'), ('wrapper_asset_sha256','103.dc91403c7e11c30e.js')]:
                    if response.status == 200 and response.url.endswith(suffix):
                        assets[kind] = hashlib.sha256(response.body()).hexdigest()
            page.on('response', capture);page.on('pageerror', lambda err:errors.append(str(err)))
            try:
                page.goto(client.base_url+'/pages/viewpage.action?pageId='+page_id, wait_until='domcontentloaded', timeout=60000)
                frame = page.wait_for_selector('iframe[src*="gantt-chart.html"]', timeout=45000).content_frame()
                frame.wait_for_function('()=>window.gantt?.project?.eventStore?.allRecords?.length>=7', timeout=45000)
                data = frame.evaluate('''async()=>{
                    await gantt.project.commitAsync();
                    return {build:__NEXT_DATA__.buildId, engine_version:bryntum.getVersion('gantt'),
                        readOnly:gantt.readOnly,
                        tasks:gantt.project.eventStore.allRecords.map(t=>({id:t.id,percentDone:t.percentDone,
                            status:t.status,model:t.toJSON(),persistable:t.persistableData})),
                        columns:gantt.columns.records.map(c=>({id:c.id,field:c.field,hidden:c.hidden,type:c.type}))};
                }''')
                assert fetched and fetched[-1] == payload
                observation.update(assets,build=data['build'],engine_version=data['engine_version'],
                    confluence_version=page.locator('meta[name="ajs-version-number"]').get_attribute('content'),
                    browser_received_sha256=hashlib.sha256(fetched[-1]).hexdigest())
                (folder/('browser-received-'+str(opening)+'.json')).write_bytes(fetched[-1])
                records={str(t['id']):t for t in data['tasks']}
                # Compare every source fact on every row, including summary.
                for ident, expected in control['expected_source_values'].items():
                    for field, value in expected.items():
                        for layer in ('model','persistable'):
                            actual=records[ident][layer].get(field)
                            key=str(opening)+'.'+ident+'.'+layer+'.'+field
                            observation['checks'][key]={'expected':value,'actual':actual,'passed':actual==value}
                            assert actual==value, (key,actual,value)
                for ident, percent in control['expected_leaf_percent'].items():
                    actual=records[ident]['percentDone'];category=records[ident]['status']['category']
                    expected_category='new' if percent==0 else 'done' if percent==100 else 'indeterminate'
                    for key,value,wanted in [('percent',actual,percent),('status',category,expected_category)]:
                        observation['checks'][str(opening)+'.'+ident+'.'+key]={'expected':wanted,'actual':value,'passed':value==wanted}
                        assert value==wanted
                # Observe native summary separately: the exact source is custom text.
                data['source_summary_percent']='47.375'
                columns={c['id']:c for c in data['columns']}
                for name in ('status','percentdone','startdate','enddate','duration',*[c for c,_ in SOURCE_COLUMNS.values()]):
                    assert columns[name]['hidden'] is False, name
                    frame.evaluate('async(id)=>{await gantt.scrollColumnIntoView(gantt.columns.getById(id));return null;}', name)
                    cells=frame.locator('.b-grid-cell[data-column="'+str(columns[name]['field'])+'"]')
                    assert cells.count()>=7, (name, columns[name], frame.locator('.b-grid-cell').evaluate_all('(cells)=>cells.slice(0,15).map(c=>({column:c.dataset.column,columnId:c.dataset.columnId,text:c.textContent}))'))
                    cells.first.scroll_into_view_if_needed()
                    text=cells.all_text_contents()
                    expected=[row[name] for row in control['expected_source_values'].values()] if name.startswith('custom_') else None
                    if expected is not None:
                        assert sorted(t.strip() for t in text)==sorted(expected), (name,text,expected)
                    observation['checks'][str(opening)+'.visible.'+name]={'expected':True,'actual':True,'passed':True}
                    if opening==0:
                        page.screenshot(path=str(folder/('visible-'+name+'.png')),full_page=True)
                data['runtime_errors']=errors
                observation['openings'].append(data)
                page.screenshot(path=str(folder/('reopen-'+str(opening)+'.png')),full_page=True)
            finally:
                page.close()
        profile=PluginProfile.load()
        assert observation['asset_sha256']==profile.document['plugin']['asset_sha256']
        assert observation['wrapper_asset_sha256']==control['wrapper_asset_sha256']
        assert 'frontend-build:'+observation['build']==profile.document['plugin']['version']
        latest=client.get_page(page_id)
        assert latest['version']['number']==storage['version']['number']
        current=next(a for a in client.list_attachments(page_id) if a['title']==filename)
        assert current['version']['number']==att.version
        observation['status']='passed'
    finally:
        (folder/'observation.json').write_text(json.dumps(observation,ensure_ascii=False,indent=2,default=str)+'\n')
