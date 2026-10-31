# Hermes bugfix and routing runbook

> Detailed bug routing, diagnosis, context guards, and escalation rules moved from `SKILL.md`.

### Классификатор маршрута (баг vs прямой ответ)

| Триггерные слова | Маршрут (ОБЯЗАТЕЛЬНО) |
|---|---|
| «баг», «ошибка», «не работает», «упало», «почини», «починка», «разберись», «проанализируй ошибки», «cron run failed», «отдай на разбор/план починки», «fix», «root cause» | кейс BUGFIX (DevWorkflow) = BUG:diagnose → GATE:diagnose-review → TZ-WRITE(patch/light) → PLAN-IMPL-TAIL(-LIGHT). ПЕРВЫЙ шаг оркестратора — `pipeline init --case BUGFIX` (рецепт с `BUG:diagnose`) для slug, ДО любого agent -p / cronjob / delegate. Ретро-корень запрещён (инвариант 9). Классификация LIGHT — после GATE:diagnose-review (≤3 файла вне shared). После `TZ:finalize` (багфикс-ТЗ) `GATE:take-into-work` **auto-pass** (`auto-pass: ac-shown`), payload=AC; `GATE:diagnose-review` **auto** по артефакту `_fix_plan_*.md`/непустому body (императив 28.09, старт→финиш) |
| «спроси», «проверь», «вычисли», «найди данные», «найди в архиве», «сколько», «покажи» | прямой ответ (без кода/процесса; без DevWorkflow-slug) |
| «одношаговый ответ», RESEARCH-триггеры («проанализируй», «исследуй» без починки) | прямой ответ / RS-граф (по DPK-исключениям) |

Правило сверху: «Работа с кодом/процессом (любое изменение) по баг-триггеру — ТОЛЬКО через DevWorkflow (`pipeline init`, кейс BUGFIX). Прямой ответ — только когда НЕТ кода/процесса. Сомнение — всегда в сторону фазы `BUG:diagnose`.»

**Провайдер-недоступность LLM ≠ внутренний баг:** ошибку провайдера НЕ чинить и НЕ заводить BUGFIX-поезд — сообщать по-человечески («провайдер недоступен, система штатна»), Саша такие не чинит. Обычные ошибки (канбан/воркер/интеграция) — чинить по канону, но починку начинать только после «запусти в работу».

**Связь с tz-workflow:** после `TZ:finalize` AC показ в origin → `GATE:take-into-work` auto-pass, поезд идёт сам — этот скилл для реализации, без фразы «берём в работу».

### Блок 6В (багфикс)

При триггере «почини» — **до** TZ-ветки (кейс BUGFIX, GLOSSARY §2):

```none
корень DEV/<slug> + BUG:diagnose   # в ОДНОМ `pipeline init`-ходе (инвариант 9), до agent -p
# origin задаётся при init (см. «Origin и уведомления» выше)
GATE:diagnose-review  parents=[BUG:diagnose]   # auto по артефакту _fix_plan_*.md / непустому body
→ далее TZ-WRITE(patch|light) → GATE:take-into-work (auto-pass: ac-shown) → PLAN-IMPL-TAIL | PLAN-IMPL-TAIL-LIGHT
```

`BUG:diagnose` — read-only, план П.1…П.N → `_fix_plan_YYYYMMDD.md`. Диагноз → `BUG:diagnose`; реализация → `HF:impl`. **`HF:fix` запрещён** (GLOSSARY §7). Инвариант: даже с известным root cause — нет перехода в hermes-feature без ТЗ-файла. `GATE:diagnose-review` — **auto** (доработка B): воркер гейта complete сам, когда `BUG:diagnose` done и на диске есть `_fix_plan_*.md` **или** непустой body; классификация LIGHT — в том же ходе. `GATE:plan-approve` — always auto; `GATE:take-into-work` / `GATE:done` — **always auto**. Баг-триггер всегда начинает с фазы `BUG:diagnose`.

**Корень `DEV/<slug>` создаётся СРАЗУ, в том же `pipeline init`-ходе, что и `BUG:diagnose`** (не ретро, инвариант 9). Ретро-корень = нарушение (прецедент pfs-promote-bugfix 22.09: preflight GATE:done красный). Первый tool-шаг при баг-триггере — `pipeline init` корня `DEV/<slug>` **И** DX в одном батче, **до** любого agent -p / cronjob(repeat=1) / delegate / cronjob-аутсорсинга диагностики.

**Багфикс-батч создаёт ПОЛНЫЙ хвост сразу, не корень+DX на потом (прецедент 11.10: digest/pfs-notify стоят на DX done).** Развёл только
`корень DEV/<slug>` + `BUG:diagnose` (по букве инварианта 9) — когда DX выполнилась, граф встал: `GATE:diagnose-review` и LIGHT/полный хвост
ещё не существовали, оркестратору нечего промоутить после DX done, пришлось добирать гейт и хвост вторым ходом. Правило: в том же оркестраторском
ходе, что корень+DX, создавать и `GATE:diagnose-review` (parents=[DX]) и (после классификации) LIGHT-хвост `TZ:patch→TZ:finalize→GATE:take-into-work→HF:impl→HF:test→HF:docs-handoff→GATE:done` — **целиком**, чтобы поезд от корня шёл до GATE:done без добивания. DX при этом выполняется первой (родитель корня done → ready), гейт и хвост ждут своей очереди по parents.

**Классификация LIGHT (кейс BUGFIX-LIGHT, GLOSSARY §2/§5.2)** — **после** `GATE:diagnose-review`, а не на холодном старте. Критерий: ≤3 файла кода+тесты, вне shared-модулей, без новых сущностей/cron/.env/манифеста. Тогда:
- корень `DEV/<slug>` + `BUG:diagnose` → `GATE:diagnose-review` → `TZ:patch` → `TZ:finalize` → `GATE:take-into-work` → `HF:impl` → `HF:test` → `HF:docs-handoff` → `GATE:done` (preflight `--case BUGFIX-LIGHT`);
- skip: `HF:plan`, `GATE:plan-approve`, `HF:backup`, `REV:tz`/`REV:plan`, `HF:compress`, `ORCH:shared-state`;
- план = `_fix_plan_*.md` **или** непустой body `BUG:diagnose` (утверждён уже на diagnose-review);
- не генерировать пустые `auto-pass`-флаги (фальшивый audit).

**Auto-гейт (DKP 0.4.0, императив 28.09):** после `TZ:finalize` `GATE:take-into-work` **auto-pass** (`auto-pass: ac-shown`), payload=AC; `GATE:diagnose-review` — **auto** по `_fix_plan_*.md` (доработка B). Leftover «never auto» на `take-into-work`/`done` — устранён.

**G5 (AC-H03/H09/H10):** воркер HF/BUG **не** `pipeline init` кейсовый граф и **не** skip фаз. `pipeline init` / `pipeline set-case` / LIGHT-хвост — **только оркестратор (Сирень) на триггере в чате**, ДО фаз архитектора. Классификация BUGFIX→BUGFIX-LIGHT — **после** `GATE:diagnose-review` оркестратором (перепись хвоста / `--case`); архитектор в `_fix_plan` может написать оценку числа файлов, `pipeline init` LIGHT-хвоста ему **запрещён**.

**Перед любым `agent -p` по инструменту на `BUG:diagnose` (и далее по багфикс-ветке):** обязательный `emit-prompt` — exit 0, иначе **СТОП**, `agent -p` не вызывать. Легальный вызов только от файла `--out` (промпт: `$(cat /tmp/task.md)`):

- `pipeline emit-prompt --slug <slug> --phase <PHASE> --out /tmp/task.md`
- exit 0 → `invoke-role` с `/tmp/task.md` (или `agent -p` внутри роли); в `journal.md` должен появиться `context-used:` (G2/AC-H06)
- exit ≠ 0 → СТОП
- перед `complete-phase` HF/BUG/REV: `pipeline check --slug <slug> --phase <PHASE>` — exit 0 обязателен (G2)

**Питфолл `check` (G2):** `pipeline check` сверяет `journal.md` на маркер `context-used:` после emit-prompt. Без него `complete-phase` TZ/HF/BUG/REV → fail. См. `dev-workflow` `references/context.md`.

**Обхода context-bundle нет (решение Саши 26.09, без исключений):** ни `flag-waived`, ни `--force` / `--force-bypass-sasha-ok` как обход тройки digest+GLOSSARY+мастер-ТЗ; скрипт `emit-prompt`/`check` блокируют всегда.

**Новая сущность / первый прогон ТЗ (chicken-and-egg):** на первом `TZ:patch` нового инструмента/скилла guard падает «инструмент не найден в манифесте: <Name>» — потому что `emit-prompt` требует И запись `tools.<key>` в EcosystemManifest.json, И мастер-ТЗ на диске, а у новой сущности ещё нет ни того ни другого. Это НЕ баг и НЕ повод `--force`: предусловие — **зарегистрировать stub** `tools.<key>` (status draft, `tz_ref` → целевой `TZ/<Name>/<Name>_TZ.md`) в манифесте ДО прогона; stub пишет оркестратор (зона ORCH по сути, хотя формально ORCH:shared-state позже — это аддитивный stub, не полная запись). Мастер-ТЗ даёт резолв по `tz_ref` или фоллбэку `TZ/<Name>/<Name>_TZ.md`, поэтому путь должен существовать. `resolve_tool_entry` матчит и по snake_case-ключу, и по полю `name`, поэтому ключ `dev_workflow` матчится и через `--tool DevWorkflow`.

## Блок 6В: Диагностика перед починкой

Когда «что-то не работает» — **не чинить сразу**. Порядок:

1. **Заведи slug с фазой `BUG:diagnose`** (`pipeline init --case BUGFIX`, read-only). Роль: `emit-prompt` → invoke-role (архитектор). Оркестратор **не** пишет `_fix_plan` сам.
2. `GATE:diagnose-review` — **auto**: после `_fix_plan_*.md` / body DX; LIGHT — оркестратором в том же ходе. REV качества ТЗ — `REV:tz` в TZ-WRITE.
3. Исполнитель реализует по плану на фазах HF (GLOSSARY §5.2)

План сохранить в `_fix_plan_YYYYMMDD.md` рядом с инструментом.

---

## Блок 7: Диагностика и отладка

**При изменении ТЗ** (параллельно передаче задачи в Cursor): запустить drift-check манифеста:

```bash
python3 ~/WorkVault/Registries/render_manifest.py --check-drift
```

Расхождения — в отчёт Саше; обновление манифеста — после согласованной реализации (Блок 4).

**Метод:** скилл `systematic-debugging` (4 фазы: root cause → pattern → hypothesis → fix). Диагноз — `BUG:diagnose`; фикс — `HF:impl` (не `HF:fix`).

**Reuse-first при фиксе (см. references/reuse-first-rule.md):** root cause чинится через существующие инструменты; новый инструмент — только предложение на согласование.

**Специфика:**
- Модель: исполнитель (composer-2.5)
- Мелкий баг → исполнитель чинит сам (1 попытка)
- Крупный → Саша решает → архитектор делает hotfix-план
- Системный блокер → вопрос Саше напрямую
- Эскалация к архитектору: root cause в архитектуре, не воспроизвелось за 2 попытки
- Эскалация к Саше: данные могут быть повреждены, production down
