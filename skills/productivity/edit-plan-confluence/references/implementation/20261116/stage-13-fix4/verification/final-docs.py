from pathlib import Path
import json,hashlib,shutil,difflib
H=Path('/home/tkachenkoav/hermes-workspace')
D=H/'skills/productivity/edit-plan-confluence/references/implementation/20261116/stage-13-fix4'
stage=json.loads((D/'stage-report.json').read_text())
Z=Path('/home/tkachenkoav/WorkVault/Hermes-Backlog/TZ')
plan=Z/'EditPlanConfluence/plans/HF-plan_EditPlanConfluence_20261116.md'
inventory=Z/'MAIN_TZ_INVENTORY.md'
out=D/'completion-documents'
for name in ('before','after'):(out/name).mkdir(parents=True,exist_ok=True)
for file in (plan,inventory):shutil.copy2(file,out/'before'/file.name)
summary=stage['summary'];gate=stage['gate'];rc=stage['exit_code']
text=plan.read_text()+f'\n### Д4 — актуальность по mtime, история как дифф, 17.11.2026\n\n'
text+=f'- Корректирующий цикл реализован и полностью проверен; цель полного §20 passed **{("достигнута" if gate=="passed" else "не достигнута")}**. Gate: **{gate}**; {summary["passed"]} passed / {summary["failed"]} failed / {summary["skipped"]} skipped, rc={rc}. Master 0.5.4.\n'
text+='- Коммиты: G0 `ec6c452388ff67e3549ad9097a3f47eadab65a08`; G1 `48c566402f4fd0ee65c695ed83fac58398bef304`; G2 `0a509dc5f14806c4087b55bff4ba365f6f0a6888`. Завершающий G3 фиксируется после commit. Параллельный чужой `84b1386` не является работой Д4.\n'
text+='- Решение владельца исполнено: B/C UID510→UID323 сохранена, историческое правило не применяется; resource_uid: missing не превращается в выдуманный ресурс. Исходные назначения/интервалы/работа сохранены; mtime фиксируется при согласованном чтении; compare возвращает добавленные/удалённые задачи и все их связи.\n'
for c in stage['cases']:
 text+=f'- {c["case"]}: {c["status"]}, page {c["page_id"]} (parent 519501810), POST={c["POST"]}, PUT={c["PUT"]}, повтор={c["repeat_status"]}, наблюдаемых задач={c["observed_task_count"]}; {c["archive_task_count"]}/{c["display_task_count"]}/{c["dependency_count"]}/{c["work_hours"]}.\n'
if stage['remaining_blockers']:
 text+='- Остались самостоятельные блокеры: '+', '.join(sorted({b['finding']['code']+' '+str(b['finding'].get('entity')) for b in stage['remaining_blockers']}))+'. У D веха UID373: duration=0, start=30.03.2026 09:00, finish=22.04.2026 18:00; установленный плагин сводит её к одной дате. Эти значения не изменены, gate не смягчён.\n'
text+='- Первый полный прогон Д4: 813 passed/6 failed, rc=1 — сохранён в history/first-full-failed. Затем устранены три расхождения тестовых контрактов и автоматический пересчёт даты B/C; режим снимка подтверждён GET-only пробами и отдельными живыми публикациями. Статический снимок не заявляет эквивалентность пересчёта MS Project.\n'
text+=f'- Отчёт: `{D/"stage-report.json"}`; Markdown, JUnit и все источники evidence сохранены рядом. R: 81 passed/1 прежний необязательный skip; M: 206 passed; 14 внешних комплектов восстановлены.\n'
text+='- canon.md вне коммитов, SHA-256 a6e841a660f60f2aee932edbd558992c68fc560de4464a580ffbb1a8e0b17892. Production targets исключены; Gateway/cron/наблюдатели не менялись. §19 и ownCloud sync этим прогоном не заявлены. Новый APPROVE не заявлен.\n'
plan.write_text(text)
text=inventory.read_text();lines=text.splitlines(True)
for i,line in enumerate(lines):
 if line.startswith('| EditPlanConfluence |'):
  parts=line.split('|');parts[3]=' 0.5.4 ';parts[5]=f' §19 approved ранее; Д4 реализован; полная приёмка §20 {gate} ({summary["passed"]} passed/{summary["failed"]} failed, rc={rc}); новый APPROVE не заявлен ';lines[i]='|'.join(parts)
text=''.join(lines)+f'\n- 2026-11-17: EditPlanConfluence 0.5.4 — Д4: mtime, дифф задач/связей, исторические B/C не применяются; resource_uid: missing сохраняется без выдуманного ресурса. Полный §20 **{gate}**, {summary["passed"]} passed/{summary["failed"]} failed, rc={rc}. Отдельное оставшееся ограничение D — UID373, нулевая веха с разными датами.\n'
inventory.write_text(text)
manifest=[];patch=[]
for file in (plan,inventory):
 shutil.copy2(file,out/'after'/file.name)
 a=out/'before'/file.name;b=out/'after'/file.name
 patch.extend(difflib.unified_diff(a.read_text().splitlines(True),b.read_text().splitlines(True),fromfile='before/'+file.name,tofile='after/'+file.name))
 manifest.append({'path':str(file),'before_sha256':hashlib.sha256(a.read_bytes()).hexdigest(),'after_sha256':hashlib.sha256(b.read_bytes()).hexdigest()})
(out/'changes.patch').write_text(''.join(patch))
(out/'manifest.json').write_text(json.dumps({'gate':gate,'files':manifest},ensure_ascii=False,indent=2)+'\n')
print(gate,summary)
