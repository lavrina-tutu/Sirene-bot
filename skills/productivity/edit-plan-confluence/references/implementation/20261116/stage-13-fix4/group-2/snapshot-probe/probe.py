from pathlib import Path
import json,sys,hashlib
from urllib.parse import urlsplit
from datetime import datetime
S=Path('/home/tkachenkoav/hermes-workspace/skills/productivity/edit-plan-confluence')
T=Path('/home/tkachenkoav/.cache/edit-plan-confluence-acceptance/accept-fix4-20261117')
sys.path.insert(0,str(S/'scripts'));sys.path.insert(0,str(T/'final/browser-deps'))
import os
os.environ['PLAYWRIGHT_BROWSERS_PATH']=str(T/'final/browsers')
from env import load_confluence_env
from conf_client import ConfluenceClient
from playwright.sync_api import sync_playwright
client=ConfluenceClient(token=load_confluence_env(Path.home()/'USERTOOLS/ConfluenceSync/.env')['CONFLUENCE_TOKEN'])
folder=T/'snapshot-probe';folder.mkdir(exist_ok=True)
for case in ('A','B','C','D'):
 e=json.loads((T/'final/reports/evidence'/('live-'+case+'.json')).read_text());page_id=e['page_id']
 data=json.loads((T/'final/live-stage13'/case/'browser-received-0.json').read_bytes());expected={}
 def snapshot(rows):
  for node in rows:
   node['manuallyScheduled']=True
   node['skipNonWorkingTimeWhenSchedulingManually']=False
   expected[str(node['id'])]=node
   snapshot(node.get('children',[]))
 snapshot(data['eventsData']);raw=json.dumps(data).encode()
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,args=['--no-sandbox']);ctx=browser.new_context(timezone_id='Europe/Moscow')
  def route(r):
   if urlsplit(r.request.url).netloc!=urlsplit(client.base_url).netloc or r.request.method not in ('GET','HEAD'):r.abort();return
   if '/download/attachments/'+page_id+'/' in r.request.url:
    r.fulfill(status=200,body=raw,content_type='application/json');return
   r.continue_(headers={**r.request.headers,'Authorization':'Bearer '+client.token})
  ctx.route('**/*',route);page=ctx.new_page();received=[];assets={}
  def capture(response):
   if response.status==200 and '/download/attachments/'+page_id+'/' in response.url:received.append(response.body())
   for key,suffix in [('asset_sha256','7b1ccf34.b54da94330ce3dd5.js'),('wrapper_asset_sha256','103.dc91403c7e11c30e.js')]:
    if response.status==200 and response.url.endswith(suffix):assets[key]=hashlib.sha256(response.body()).hexdigest()
  page.on('response',capture);page.goto(client.base_url+'/pages/viewpage.action?pageId='+page_id,wait_until='domcontentloaded',timeout=60000)
  frame=page.wait_for_selector('iframe[src*="gantt-chart.html"]',timeout=45000).content_frame();frame.wait_for_function('()=>window.gantt?.project?.eventStore?.allRecords?.length>1',timeout=45000)
  observed=frame.evaluate('''async()=>{await gantt.project.commitAsync();const local=d=>d&&[d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-')+'T'+[d.getHours(),d.getMinutes(),d.getSeconds()].map(x=>String(x).padStart(2,'0')).join(':');return {build:__NEXT_DATA__.buildId,tasks:gantt.project.eventStore.allRecords.map(t=>({id:t.id,start:local(t.startDate),finish:local(t.endDate),manual:t.manuallyScheduled})),dependencies:gantt.project.dependencyStore.records.map(d=>({from:d.fromEvent.id,to:d.toEvent.id,type:d.type,lag:d.lag}))}}''')
  confluence_version=page.locator('meta[name="ajs-version-number"]').get_attribute('content')
  ctx.unroute_all(behavior='wait');browser.close()
 failures=[]
 for task in observed['tasks']:
  node=expected[str(task['id'])]
  for a,b in (('start','startDate'),('finish','endDate')):
   if abs((datetime.fromisoformat(task[a])-datetime.fromisoformat(node[b])).total_seconds())>60:failures.append({'id':task['id'],'field':a,'expected':node[b],'observed':task[a]})
 from collections import Counter
 assert Counter((d['from'],d['to'],d['type'],d['lag']) for d in observed['dependencies'])==Counter((d['from'],d['to'],d['type'],d['lag']) for d in data['dependenciesData'])
 result={'case':case,'page_id':page_id,'scope':'GET-only browser candidate attachment interception; NOT a publication','POST':0,'PUT':0,'candidate_sha256':hashlib.sha256(raw).hexdigest(),'observed':observed,'date_mismatches':failures}
 assert received and received[-1]==raw
 result.update(status='passed' if not failures else 'failed',assertion_kind='supported',
  capabilities=['publication:source_snapshot_dates'],build=observed['build'],confluence_version=confluence_version,
  input_sha256=hashlib.sha256(raw).hexdigest(),browser_received_sha256=hashlib.sha256(received[-1]).hexdigest(),**assets,
  checks={'dates':{'passed':not failures,'expected':0,'actual':len(failures)},
          'manual_display':{'passed':all(t['manual'] for t in observed['tasks']),'expected':len(expected),'actual':sum(t['manual'] for t in observed['tasks'])},
          'links':{'passed':True,'expected':data['dependenciesData'],'actual':data['dependenciesData']}})
 # Exact links are independently asserted above against the observed model.
 result['checks']['links'].update(expected=sorted((d['from'],d['to'],d['type'],d['lag']) for d in data['dependenciesData']),
  actual=sorted((d['from'],d['to'],d['type'],d['lag']) for d in observed['dependencies']))
 (folder/(case+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(case,len(observed['tasks']), 'date mismatches',len(failures),flush=True)
