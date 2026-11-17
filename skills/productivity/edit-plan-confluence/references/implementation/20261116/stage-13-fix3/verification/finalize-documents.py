from pathlib import Path
import difflib, fcntl, hashlib, json, shutil
H=Path('/home/tkachenkoav/hermes-workspace')
D=H/'skills/productivity/edit-plan-confluence/references/implementation/20261116/stage-13-fix3'
stage=json.loads((D/'stage-report.json').read_text())
base=Path.home()/'WorkVault/Hermes-Backlog/TZ'
plan=base/'EditPlanConfluence/plans/HF-plan_EditPlanConfluence_20261116.md'
inventory=base/'MAIN_TZ_INVENTORY.md'
out=D/'group-2/documents'
(out/'before').mkdir(parents=True,exist_ok=True)
(out/'after').mkdir(exist_ok=True)
for p in (plan,inventory):shutil.copy2(p,out/'before'/p.name)
status=stage['gate'];summary=stage['summary'];rc=stage['exit_code']
text=plan.read_text()
text+='\n### Д3 — план + колонки факта, 17.11.2026\n\n'
text+=f'- Gate §20: **{status}**; полный этап 13: {summary}; rc={rc}. Master 0.5.3.\n'
text+='- Документы G0: b043f62299beb32cb164da610165d6cacd330327; реализация G1: 91534cf. SHA завершающего коммита записывается после commit.\n'
text+='- Режим: по плану; факт — в колонках. Эквивалентный пересчёт с участием факта не заявляется; archive/display/schedule сохраняют независимые подтверждения.\n'
for c in stage['cases']:
    text+=f"- {c['case']}: {c['status']}, page {c['page_id']} (parent 519501810), POST={c['POST']}, PUT={c['PUT']}, повтор={c['repeat_status']}, наблюдений задач={c['observed_task_count']}; {c['archive_task_count']}/{c['display_task_count']}/{c['dependency_count']}/{c['work_hours']}.\n"
text+=f"- Итог и все gate checks: `{D/'stage-report.json'}`; JUnit, blocker-ledger и браузерные улики сохранены рядом. 14 внешних комплектов восстановлены; R 81 passed/1 прежний необязательный skip, M 206 passed.\n"
text+='- canon.md вне коммитов, SHA a6e841a660f60f2aee932edbd558992c68fc560de4464a580ffbb1a8e0b17892. Production DB/страницы A–D/AB, Gateway, кроны/наблюдатели/расписания сохранены. §19 и ownCloud sync не заявляются. Прежние failed-прогоны не переписаны.\n'
plan.write_text(text)
with inventory.open('r+') as f:
    fcntl.flock(f,fcntl.LOCK_EX);text=f.read();lines=text.splitlines(True)
    for i,line in enumerate(lines):
        if line.startswith('updated:'):
            line=line.replace('Д3, план + колонки факта; полный повтор §20 в работе',f'Д3, план + колонки факта; §20 {status}, {summary["passed"]} passed/{summary["failed"]} failed, rc={rc}')
        if line.startswith('| EditPlanConfluence |'):
            line=line.replace('Д3 «план + колонки факта» реализован, полный повтор в работе; прежний результат 799 passed/4 failed, rc=1',f'Д3 «план + колонки факта»: полная приёмка §20 {status} ({summary["passed"]} passed/{summary["failed"]} failed, rc={rc}); прежние failed сохранены')
        lines[i]=line
    text=''.join(lines)+f'\n- 2026-11-17: EditPlanConfluence 0.5.3 — Д3 «план + колонки факта»; §20 **{status}**, rc={rc}; полная матрица AC/кейсов/сценариев и реальные A–D — в отчёте stage-13-fix3. Новый APPROVE не заявлен.\n'
    f.seek(0);f.write(text);f.truncate()
files=[];patch=[]
for p in (plan,inventory):
    shutil.copy2(p,out/'after'/p.name)
    before=out/'before'/p.name;after=out/'after'/p.name
    patch.extend(difflib.unified_diff(before.read_text().splitlines(True),after.read_text().splitlines(True),fromfile='before/'+p.name,tofile='after/'+p.name))
    files.append({'path':str(p),'before_sha256':hashlib.sha256(before.read_bytes()).hexdigest(),'after_sha256':hashlib.sha256(after.read_bytes()).hexdigest()})
(out/'changes.patch').write_text(''.join(patch))
(out/'manifest.json').write_text(json.dumps({'files':files,'gate':status},ensure_ascii=False,indent=2)+'\n')
print(status)
