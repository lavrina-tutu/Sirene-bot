# Вызов роли и граница wrapper

Нормы — Б54/Б55/Б56 master-ТЗ и [SKILL.md](../SKILL.md); модели/backend — YAML `tools.dev_workflow`. Этот справочник раскрывает строку WORK/RECONCILE единой процедуры. Процессные команды выполняет внешний оркестратор после выхода роли. Роль читает пакет, пишет разрешённые outputs и возвращается; ожидание своего wrapper не заменяет результат.

## Один запуск

До отправки сверить `(slug, phase)`, recipe/G6, журнал, свежий канон/impl evidence и receipt при наличии. Уже принятый результат не запускать повторно. Живой точный wrapper блокирует next/complete/recover/interrupt и второй invoke, даже если PID не записан в state. Повторный `start` или доставленный notify не являются основанием новой работы.

```text
pipeline emit-prompt --slug <slug> --phase <PHASE> --out /tmp/task.md
# только rc=0
pipeline invoke-role --slug <slug> --phase <PHASE> --role <architect|reviewer|executor> --prompt-file /tmp/task.md --workspace <ABS>
```

Для Hermes `terminal` запуск invoke передавать **одним** request: `background=true`, `notify=true`, `persist_on_release=true`. Это поля tool request, не shell-флаги; foreground/`terminate` не применять. Полученный session id использовать для приёма результата того же запуска, не для повторной отправки command. `notify only applies to background commands` / `persist_on_release без background` — validation error до старта: исправить request; идентичную ошибочную форму не повторять и не считать provider-fatal.

Не запускать роль напрямую через `agent -p`/`codex exec`, не применять `--continue` и `| head`/`| tail`/другой отсекатель stdout invoke (SIGPIPE оставляет агента-сироту). Служебный stdout роли не пересылать в origin; туда идут отчёт/предупреждение/причина ожидания по процессу.

В комплекте есть `scripts/pipeline.sh`: требует `PIPELINE_ROOT` из существующего YAML и вызывает тот же CLI. Абсолютный каталог скилла указан в сообщении его загрузки. Второй launcher, ENV-ключ или конфиг скилла для этого не создавать.

## Пакет B56

`pipeline_context.py` — единственный owner emit/check/invoke binding. До `invoke_prepare` проверяются schema/id/slug/phase/G6, immutable snapshot, sidecar, byte-exact render/prompt hash, успешный marker и все FileRef. `/tmp/task.md` — выход emit; ручная правка, подмена, fallback и `--force` запрещены. Контекстный отказ rc=1 не является provider-fatal и не расходует ход до prepare. Состав пакета и MUST-read — [context.md](context.md); роль не переписывает принятый входной пакет.

После prepare фаза получает exact `context_packet` (schema/id/path/prompt hash, связь со slug/phase); G2 сверяет его с успешным `context-used:`. Разрешённый output master/плана проверяется относительно принятого входного snapshot: старый input hash не должен запрещать разрешённую запись. Следующая фаза получает новый пакет. Старый snapshot/state из роли не исправлять; source drift при приёмке передать оркестратору как факт, без обхода G2. `packet_id`, stdout и rc=0 не доказывают completion/APPROVE. Для compressor публикация должна соответствовать packet+prepare и receipt; один файл extract этого не доказывает.

## После completion, timeout или обрыва

Сначала сверить точный wrapper и оставшихся писателей **этого** invoke, журнал, output, изменённые файлы и receipt. Timeout/rc=124/143/137 сам по себе не provider-fatal и не разрешение recover. После таймаута 3600s агент-сирота может ещё писать: до прекращения записи не запускать повтор и не объявлять результат стабильным. Чужой процесс/substring соседнего slug не является wrapper этой фазы.

| Факты после сверки | Решение оркестратора |
|---|---|
| Wrapper либо связанный писатель ещё жив | Ждать завершения; никакой ручной очистки PID, нового invoke или приёма промежуточного diff. |
| До prepare: `awaiting_invoke=true`, `pid=None` | Штатное окно WORK: один emit→invoke, если этот запуск ещё не отправлен. Брошенное окно диагностировать по журналу, не приравнивать автоматически к crash. |
| Sirene-фаза, `pid=None` | Штатная работа оркестратора, без invoke роли. |
| Wrapper вышел, `role` записан, свежий пригодный output есть | Post-invoke WORK/RECONCILE: проверить канон, receipt, G1/G2 и output evidence; обычный complete с reason/evidence. Re-invoke не нужен. |
| Обрыв после записи output, принятие не подтверждено | Сначала reconciliation по диску/журналу/контексту. Нет доказательств допуска — диагноз/ожидание; существующий diff сохранить, не переписывать вслепую. |
| `role` записан, обязательного результата нет | `empty-result`/`canonical_artifact_fail`, не dead-pid. Короткий stdout при свежем каноне допустим. |
| `role is None`, wrapper/писатели мертвы, `awaiting_invoke=false`, пригодного результата нет | True-crash dead-pid: один recover только при подтверждённом recoverable-классе и неисчерпанном `recover_counts[phase][class]`; повторный такой сбой — диагноз/ожидание. |
| Provider/auth/billing/503/429, budget exhausted | WAIT/INTERRUPTED, без автоматического retry/recover. Возобновление после доказанного устранения причины — по SKILL.md, без обхода лимита. |
| Повторная доставка уже принятого completion/receipt | No-op: не второй complete/start/invoke/notify. При отсутствии receipt сверить канон и завершённые переходы. |

`repair` пересобирает производный индекс, не разрешает сбрасывать dead PID или бюджеты. Прямой JSON-write, переименование класса ради нового recover, kill/restart как «обычное восстановление» и новый поезд для обхода блокера запрещены. Совпавшие симптомы одного сбоя не дают нескольких corrective-повторов. При нехватке фактов фиксировать ожидание с причиной/временем/следующим шагом.

Первый G6 mismatch до старта правильной роли исправляется ролью из канона; это не новый технический retry. Ревизор пишет текущий вердикт в `REV-tz.md`/`REV-plan.md`, блок `## Вердикт` или согласованное поле `verdict=`; старые ревизии сохраняются отдельно. REQUEST-CHANGES не complete REV.

Список recover-классов Б16.6 закрыт: `dead-pid`, `wrong-role`, `empty-result`, `rc0-no-complete`, `model-none`; часть случаев требует правильного первого invoke или complete вместо recover. При `model=None` после prepare architect/reviewer/executor complete запрещён: проверить фактический resolver/YAML, передать дефект владельцу; допустимая коррекция сохраняет one-shot/turn limits. Самовольно дописывать модель или другие поля state нельзя.

## MIGRATION и native compressor

`MIG:block-N` additionally enters only through the shared
`pipeline_mig_complete_guard`. It verifies every required earlier block's own
acceptance evidence and receipt before emit/prepare; direct ORCH/done uses the
same owner before its idempotent or state-writer branch. Repeating an accept is
a no-op only while that exact proof still verifies.

Native compressor: `hermes-native` is the prepare/status selector for `hermes-internal`. The existing native adapter sends concrete `--model` before YAML `roles.compressor.model`; a selected null/empty/native selector uses static `HERMES_COMPRESSOR_MODEL`. Whitespace/non-string or non-concrete ENV models are refused. A successful HTTP response with no valid completion is a post-prepare local refusal (rc=4): it writes no extract/result/receipt and is not provider-fatal. Missing static model/key/base URL, worker failure, or a provider/transport failure remains rc=3/provider-fatal; the static refusal occurs before SDK construction/send/publication. One send, SDK retries=0, no alternative/fallback/rotation. No configuration discovery or new keys.
