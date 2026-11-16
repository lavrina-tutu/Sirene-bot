# Этап 05 — batch: входы, обработка и восстановление

Gate: **passed**. S rc=0; selected=332; passed=332.

Реализовано:

- `S/scripts/plan_manifest.py`: строгие поля/null/ID/date/IANA/SHA; канонизация порядка/путей/label/on_error с сохранёнными defaults; Inbox без рекурсии, Unicode и диагностика исключений.
- `S/scripts/plan_batch.py`: три входа; неизменяемый запрос и контекст; freeze-all barrier до reader; последовательные continue/stop; idempotent save, frozen resume, явный retry-failed; общий инфраструктурный stop.
- `S/scripts/plan_lock.py`: межпроцессный nonblocking flock по реальной БД и batch ID; стабильный inode, автоматическое освобождение при смерти процесса.
- `S/scripts/cli.py`: batch save/resume/show; взаимоисключающие входы; глобальные пути; машинный JSON без клиента/сети.
- `S/scripts/plan_receipt.py`: полная пакетная квитанция v1, баланс, saved_with_warnings внутри saved; приоритет 2/4/5/6/0.
- `S/scripts/plan_reconcile.py`: проверка только frozen locators и committed item/event/snapshot, read-back и зеркало через общий save без нового reader/поступления/snapshot.
- `M/mofs_index/plan/writer.py`: typed atomic registration всех item/operations; barrier freeze; processing intent/attempt; typed result/event и batch completion; схемы/миграции неизменны.
- `M/mofs_index/plan/query.py`: ordered batch items, attempts, последнее событие результата и согласованное read-only SQL-наблюдение.
- `S/references/schemas/{batch-manifest,batch-receipt}.schema.json`: строгие JSON-контракты §20.4.4/§20.3.12.2.
- `S/references/cli-contract.md`: batch save/resume/show, ошибки, блокировка, frozen context, коды и граница этапа 06.
- `S/tests/{test_plan_manifest,test_plan_batch,test_batch_resume,test_plan_lock}.py`: входы/дубли/ошибки/повторы, реальные E/F+D-risks, восемь process-death границ, два процесса, freeze/commit/receipt/journaling.
- `S/tests/fixtures/batch/`: проверенные manifest fixtures, одинаковые MPP, неразбираемый вход и нерекурсивный Inbox.
- `M/tests/plan/test_batch.py`: атомарная регистрация и rollback, уникальность ID по пакету, запрет reader до общей фиксации, typed results и FK/integrity.
- `S/tests/conftest.py`: обязательные ID этапа 05, изоляция и фактический gate/report из pytest; прежние стадии сохранены.

Три входа: повторяемый --mpp, manifest и Inbox. Freeze-all завершается до reader; stop действует только на обработку. Resume работает на прежних байтах/контексте, пропускает успешные, разрешает retryable failed только явно. После commit сначала read-back, новый snapshot и reader запрещены.

Баланс: total = saved + unchanged + failed + needs_decision + not_started; saved_with_warnings входит в saved. Приоритет exit codes: 2 → 4 → 5 → 6 → 0. Published=false; baseline и публикации сохранены.

Команда S:

```text
/usr/bin/python3.9 -m pytest -c /home/tkachenkoav/hermes-workspace/skills/productivity/edit-plan-confluence/tests/pytest.ini /home/tkachenkoav/hermes-workspace/skills/productivity/edit-plan-confluence/tests --acceptance-stage 05 --test-root /home/tkachenkoav/.cache/edit-plan-confluence-acceptance/20261116-stage05-152031/stage-05 -m unit or archive_integration or mpp_fixtures --junitxml=/home/tkachenkoav/.cache/edit-plan-confluence-acceptance/20261116-stage05-152031/stage-05/reports/junit.xml
```

M/tests: rc=0, passed=85; команды/окружение/stdout/stderr/JUnit — external-checks.json и mofs-*.xml/log.

Реальные MPP:
- mpp: E=78/84, F=86/93; cold=1 MPXJ-read на вход, warm=0/read + cache hit; rc=0/0. Evidence: batch-real-mpp.json.
- manifest: E=78/84, F=86/93; cold=1 MPXJ-read на вход, warm=0/read + cache hit; rc=0/0. Evidence: batch-real-manifest.json.
- inbox: E=78/84, F=86/93; cold=1 MPXJ-read на вход, warm=0/read + cache hit; rc=0/0. Evidence: batch-real-inbox.json.
- named-risks: D-risks=74/81, E=78/84; cold=1 MPXJ-read на вход, warm=0/read + cache hit; rc=0/0. Evidence: batch-real-named-risks.json.

Восемь реальных os._exit границ: после первого freeze, до/после общей отметки, до/после snapshot commit, до single receipt, после item result и до batch receipt. Два независимых процесса подтверждают busy/4, отсутствие новых поступлений и освобождение после SIGKILL.

Защищённые файлы: 157; изменено: 0. Миграций нет. USERTOOLS before/after/patch/manifest и проверка обоих способов восстановления: usertools/MofsIndex/, external-checks.json.

Дерево исходников: `35d884c91c31fe1292b043528ea6413b815b76fec9ca5412e3ac0e6bb0575a5d`. Master 0.5.0 и контракты захэшированы в JSON. SHA финального коммита записывается после commit в журнал канонического плана.

Ограничения:

- Реализован только этап 05; proposals/decisions, retry-decisions и расширенная история относятся к этапу 06
- schedule:not_verified; live Confluence/плагин не проверялись; полная приёмка §20 не заявлена
- Нормативные E/F = 090726/230726; упомянутый в поручении 260626_risks проверен дополнительно как D-risks
- При reader failure без export telemetry число MPXJ-read остаётся null; старые CSV/calendar paths отдельно не измерялись
- Блокировка локальная POSIX flock; распределённая блокировка между разными хостами вне этого контура
- Process-death tests не моделируют отказ ОС/питания; ownCloud sync не подтверждён
- Production-БД/страницы/настройки/baseline, Gateway/кроны/наблюдатели/расписания не менялись
