# LIGHT-эмиты и AUTO_GATE: два неочевидных правила

Точечные поезда CHANGE-LIGHT/SKILL-CHANGE по dev-workflow упираются в две ловушки, которые не видны сразу.

## 0. invoke-role НЕЛЬЗЯ без emit-prompt — читает sidecar .packet.json

`invoke-role` принимает не сам `--prompt-file`, а `sidecar` `<out>.packet.json`, который генерирует ТОЛЬКО `emit-prompt`. Рукописный промпт без emit даёт мгновенный `rc=1 [Errno 2] No such file or directory: '/tmp/task_*.packet.json'` — роль вообще не стартует. Поэтому при пересмотре/перезапуске фазы (директива владельца, RETRY после деад-пида, доработка плана на ТОТ ЖЕ слаг) всегда полный проход: переоткрыть фазу штатным writer'ом (или recover) + свежий `emit-prompt --out /tmp/task_*.md` (создаст `.packet.json`) + ОДИН background `invoke-role --prompt-file <тот же out>`. «Собрать промпт роли вручную и позвать invoke» — не самостоятельный путь, а пропуск обязательного emit.

## 1. Точное имя IAC-секции для LIGHT HF:impl

`emit-prompt` для LIGHT-фазы реализации требует явную секцию master в handoff-contract `brief.md` и отдаёт разные ошибки в зависимости от того, как её задали:

- `master_section: []` → `LIGHT: explicit master IAC section required`
- имя обобщённого уровня, напр. `- IAC`, при `--master-tz` → `ReadRef: missing or ambiguous section: IAC`

Правильный вариант: передать ТОЧНЫЙ полный заголовок раздела из master-ТЗ без уровня решёток, напр. `- "22.5. План реализации и IAC (LIGHT)"`. Перед эмитом проверить grep'ом, что такой заголовок встречается ровно один раз. После правки `brief.md` пере-запускать `emit-prompt` с `--master-tz /путь/до/EditPlanConfluence_TZ.md` — без него эмит снова упадёт на том же требовании.

## 2. Evidence AUTO_GATE обязано содержать path/sha256

`complete-phase` авто-гейта (`GATE:take-into-work` и другие, возвращённые `next` как `AUTO_GATE`) принимает evidence ТОЛЬКО с одним из `path=` / `sha256=` / `session_id=`. Канонного `AC-shown origin_thread=… file=…` в одиночку недостаточно — CLI вернёт `evidence must include path= or sha256= or session_id=`, гейт не закроется.

Решение: класть в evidence сразу обе формы — `AC-shown origin_thread=<N> file=<abs unknown-path>` и `path=<abs path> sha256=<hash>` (например на собранный AC-list.md). Тогда гейт закрывается с первой попытки. AC-list.md собрать непустым ДО закрытия (из ТЗ/диагноза), иначе класс-S показ пустого списка теряет смысл.
