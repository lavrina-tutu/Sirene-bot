from pathlib import Path
from collections import Counter
import gzip, hashlib, json, shutil, subprocess, sys, xml.etree.ElementTree as ET

H=Path('/home/tkachenkoav/hermes-workspace')
S=H/'skills/productivity/edit-plan-confluence'
T=Path(Path('/tmp/editplan-fix4-root').read_text())
F=T/'final'
D=S/'references/implementation/20261116/stage-13-fix4'
CANON=H/'skills/devops/dev-workflow/references/canon.md'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,v):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
manifest=[]
def deliver(src,dest):
    raw=src.read_bytes()
    linked_report = src.name=='acceptance-report.json' or src.parent==F/'reports/cases'
    if src.suffix=='.log' or (len(raw)>500_000 and not linked_report):
        dest=Path(str(dest)+'.gz');saved=gzip.compress(raw,mtime=0)
    else:saved=raw
    dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(saved)
    assert (gzip.decompress(dest.read_bytes()) if dest.suffix=='.gz' else dest.read_bytes())==raw
    manifest.append({'source':str(src),'delivered':str(dest.relative_to(D)),
        'source_sha256':hashlib.sha256(raw).hexdigest(),'delivered_sha256':sha(dest),'size_bytes':len(raw)})

report=json.loads((F/'reports/acceptance-report.json').read_text())
rc=int((F/'reports/pytest.rc').read_text())
assert rc==report['exit_code']
for folder in ('reports','live-stage13','capability-controls','live','live-stage09','live-stage10'):
    for p in (F/folder).rglob('*'):
        if p.is_file() and not p.is_symlink():deliver(p,D/'final'/p.relative_to(F))
deliver(F/'fixtures-manifest.json',D/'final/fixtures-manifest.json')
for folder in ('external','restoration'):
    for p in (T/folder).rglob('*'):
        if p.is_file() and (p.suffix in ('.xml','.log') or p.name=='pytest.rc'):
            deliver(p,D/'verification'/p.relative_to(T))
deliver(Path('/tmp/editplan-fix4-preflight.py'),D/'verification/preflight.py')
deliver(Path(__file__),D/'verification/deliver.py')
cases=[];display_only=[];blocking=[]
for case in 'ABCD':
    p=F/'reports/evidence'/('live-'+case+'.json')
    evidence=json.loads(p.read_text())
    receipt=evidence['receipt'];prep=evidence.get('preparation') or {}
    admission=prep.get('admission') or {}
    findings=admission.get('checks',[])
    for row in findings:
        item={'case':case,'classification':row.get('classification','schedule-affecting'),
            'code':row['code'],'entity':row.get('entity'),'source':row.get('source'),
            'represented':row.get('represented'),'finding_sha256':row.get('finding_sha256'),
            'evidence':'final/reports/evidence/live-'+case+'.json'}
        if row.get('classification')=='display-only':display_only.append(item)
    for row in admission.get('blockers',[]):
        blocking.append({'case':case,'classification':'identity' if row['category']=='identity' else 'schedule-affecting','finding':row,
            'evidence':'final/reports/evidence/live-'+case+'.json'})
    obs=evidence.get('plugin_observation') or {}
    cases.append({'case':case,'status':report['cases'][case]['status'],
        'page_id':evidence['page_id'],'parent_id':'519501810',
        'published':receipt['published'],'exit_code':receipt['exit_code'],
        'POST':evidence['counters']['POST'],'PUT':evidence['counters']['PUT'],
        'page_version_before':evidence['page_version_before'],'page_version_after':evidence['page_version_after'],
        'archive_task_count':receipt['task_count'],'display_task_count':receipt['display_task_count'],
        'dependency_count':receipt['dependency_count'],
        'work_hours':prep.get('result',{}).get('summary',{}).get('work',{}).get('display_hours'),
        'observed_task_count':len(obs.get('tasks',[])),'openings':len(obs.get('openings',[])),
        'source_values_verification':obs.get('source_values_verification',{}).get('status'),
        'repeat_status':evidence.get('repeat',{}).get('status'),
        'repeat_POST':evidence.get('repeat_counters',{}).get('POST'),
        'repeat_PUT':evidence.get('repeat_counters',{}).get('PUT')})
    expected={'A':(58,57,53,'1576'),'B':(62,61,60,'2096'),
        'C':(62,61,61,'2088'),'D':(72,71,76,'3136')}[case]
    assert (cases[-1]['archive_task_count'],cases[-1]['display_task_count'],
        cases[-1]['dependency_count'],str(cases[-1]['work_hours']))==expected
    if cases[-1]['status']=='passed':
        assert receipt['published'] is True and receipt['exit_code']==0
        assert cases[-1]['POST']>0 and cases[-1]['PUT']>0
        assert cases[-1]['repeat_status']=='unchanged' and cases[-1]['repeat_POST']==cases[-1]['repeat_PUT']==0
        assert cases[-1]['source_values_verification']=='verified' and cases[-1]['openings']==2

label='по плану; факт — в колонках'
failures=[{'test_id':case.get('classname','')+'::'+case.get('name',''),
    'message':failure.get('message'),'details':failure.text}
    for case in ET.parse(F/'reports/junit.xml').getroot().iter('testcase')
    for failure in list(case) if failure.tag in ('failure','error')]
ledger={'schema_version':1,'gate':report['gate'],'publication_mode':'planned_schedule_with_actuals_columns',
    'label':label,'native_actuals_schedule':'not_verified; equivalent recalculation not claimed',
    'display_only':display_only,
    'schedule_affecting_blockers':[b for b in blocking if b['classification']=='schedule-affecting'],
    'identity_blockers':[b for b in blocking if b['classification']=='identity'],'remaining_blockers':blocking,'cases':cases,
    'failed_contracts':failures,'mandatory_not_passed':report['mandatory_not_passed'],
    'blocking_boundaries':['Changed planned start/finish/duration','Facts written into schedule fields',
        'Hidden, lost or unsupported fact column','Graph/calendar/constraint/assignment semantic loss',
        'Archive/attachment/storage verification failure or target conflict'],
    'history':'history/first-full-failed/reports/acceptance-report.json'}
dump(D/'blocker-ledger.json',ledger)
initial=json.loads((F/'reports/initial-state.json').read_text())
changed=[p for p,h in initial['protected_hashes'].items() if not Path(p).is_file() or sha(Path(p))!=h]
assert not changed,changed
assert sha(CANON)=='a6e841a660f60f2aee932edbd558992c68fc560de4464a580ffbb1a8e0b17892'
dump(D/'preservation-checks.json',{'protected_count':len(initial['protected_hashes']),
    'changed_protected_files':changed,'canon_sha256':sha(CANON),
    'canon_git_status':subprocess.check_output(['git','status','--short','--',str(CANON)],cwd=H,text=True),
    'production_db_sha256':sha(Path.home()/'USERTOOLS/MofsIndex/state/index.sqlite'),
    'source_tree_sha256':report['source_tree_sha256'],'sources_stable':report['gate_checks']['sources_stable']})
stage={'schema_version':1,'stage':'13','correction':'fix4','master_version':'0.5.4',
    'gate':report['gate'],'exit_code':rc,'summary':report['summary'],'gate_checks':report['gate_checks'],
    'publication_mode':'planned_schedule_with_actuals_columns','label':label,'cases':cases,
    'display_only_count':len(display_only),
    'schedule_affecting_blocker_count':sum(b['classification']=='schedule-affecting' for b in blocking),
    'identity_blocker_count':sum(b['classification']=='identity' for b in blocking),
    'original_blockers':{'B':'resolved_by_owner_decision','C':'resolved_by_owner_decision','D_unassigned_resources':'resolved_by_owner_decision'},
    'remaining_blockers':blocking,'migrations_added':[],
    'master':report['documents']['master'],'canon_sha256':sha(CANON),
    'implementation_commits':['ec6c452388ff67e3549ad9097a3f47eadab65a08','48c566402f4fd0ee65c695ed83fac58398bef304','0a509dc5f14806c4087b55bff4ba365f6f0a6888'],
    'command':report['command'],'source_tree_sha256':report['source_tree_sha256'],
    'acceptance_report':'final/reports/acceptance-report.json',
    'junit':'junit.xml','blocker_ledger':'blocker-ledger.json', 'owner_decision':'owner-decision.md', 'actuality':'source_file_mtime_ns', 'history':'source_local_key_diff_with_incident_links'}
dump(D/'stage-report.json',stage)
shutil.copy2(F/'reports/junit.xml', D/'junit.xml')
lines=['# Д4 — этап 13','',f"Gate: **{report['gate']}**; pytest rc={rc}; {report['summary']}.",'',
    'ТЗ 0.5.4. Актуальность — исходный mtime; история — дифф snapshot с задачами и их связями. '
    'B/C: историческое правило не применяется (решение владельца), UID510→UID323 сохранена. '
    'D: назначения без ресурса допускаются как есть (resource_uid: missing). Отдельное противоречие вехи UID373 (duration=0, start 30.03, finish 22.04) не исправляется; его фактический результат указан ниже.','',
    '| Кейс | Статус | Тестовая страница | POST / PUT | Повтор | Наблюдаемых задач |',
    '|---|---|---|---|---|---|']
for c in cases:lines.append(f"| {c['case']} | {c['status']} | {c['page_id']} | {c['POST']} / {c['PUT']} | {c['repeat_status']} | {c['observed_task_count']} |")
lines += ['', 'Все страницы — дети тестового родителя 519501810. Даты и исходные значения проверяются после двух открытий. '
    'Числа A–D и gate полной приёмки сохранены. Подробные статусы — в JSON; отсутствующие наблюдения не заменяются предположениями.',
    '', 'Оставшиеся блокеры: '+('; '.join(sorted({str(b['finding'].get('code'))+' '+str(b['finding'].get('entity')) for b in blocking})) or 'нет')+'.',
    '', '[Полный отчёт](final/reports/acceptance-report.md), [JUnit](junit.xml), [машинный итог](stage-report.json).',
    '', 'canon.md вне коммитов; SHA-256 a6e841a660f60f2aee932edbd558992c68fc560de4464a580ffbb1a8e0b17892. '
    'Прежние failed-прогоны сохранены. §19 и ownCloud sync этим прогоном не подтверждаются.']
(D/'stage-report.md').write_text('\n'.join(lines)+'\n')
dump(D/'delivery-manifest.json',{'files':manifest})

# Compare actual credentials in memory; never write their values or hashes.
sys.path.insert(0,str(S/'scripts'))
from env import load_confluence_env
settings=load_confluence_env(Path.home()/'USERTOOLS/ConfluenceSync/.env')
secrets=[str(v).encode() for k,v in settings.items() if any(t in k.upper() for t in ('TOKEN','PASSWORD','SECRET')) and v and len(str(v))>=8]
leaks=[];scanned=0
for p in D.rglob('*'):
    if not p.is_file() or p.suffix=='.png':continue
    raw=p.read_bytes()
    if p.suffix=='.gz':raw=gzip.decompress(raw)
    scanned+=1
    if any(v in raw for v in secrets):leaks.append(str(p.relative_to(D)))
assert not leaks,leaks
dump(D/'secret-scan.json',{'scanned_files':scanned,'actual_credentials_checked':True,'leaks':leaks})
print(json.dumps({'gate':stage['gate'],'summary':stage['summary'],'cases':cases,'delivered':len(manifest)},ensure_ascii=False))
