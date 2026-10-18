# Вызов роли (`invoke-role`)

Скилл **не** вызывает `agent -p` напрямую. Единая точка — CLI `pipeline invoke-role` (обёртка `invoke_role.py`).

Мастер-ТЗ: DevWorkflow **Б13.2**, **Б32**.

## Бэкенды

| `--backend` | Как работает | Когда |
|---|---|---|
| `cursor-cli` | `agent -p … -f --model … --workspace … --output-format json` | default этого контура |
| `codex` | внешний CLI Codex (`bin` из конфига) | другой Hermes / другой провайдер |
| `hermes-internal` | внутренняя модель Hermes (`call_llm`) | без внешнего бинаря |

Default backend и модели ролей — `tools.dev_workflow.invoke` и `tools.dev_workflow.roles` в `EcosystemConfig.yaml`. Секреты (`CURSOR_API_KEY` и т.д.) — только в `~/.hermes/.env`, не в YAML.

Пример:

```bash
pipeline invoke-role --role executor \
  --prompt-file /tmp/task.md \
  --workspace /home/…/USERTOOLS/MyTool \
  [--backend cursor-cli] [--model composer-2.5] [--resume <session_id>]
```

**Всегда передавай `--slug <slug> --phase <PHASE>` в `invoke-role`.** Без них g6/canonical-трэкинг фазы не выполняется, и вызов может падать мгновенным `rc=1` с пустым stdout — фаза остаётся `doing` без живого pid, результат роли теряется. Для фазы из рецепта это те же `--slug/--phase`, что и в `complete-phase`.

**Транзиентный сбой Cursor ≠ «провайдер мёртв».** Если `agent -p` отвечает `Failed to reach the Cursor API`, но `curl -I https://api2.cursor.sh` даёт HTTP 200 и токен в `~/.config/cursor/auth.json` на месте — это временный сбой сессии, не обрыв бэкенда. Смоук: `timeout 60 agent -p "Ответь ровно одним словом: ок" -f --model <модель-роли> --workspace <ws> --output-format json`; если вернул `"result":"ок"` rc=0 — Cursor жив, повторяем тот же `invoke-role` (не `interrupt`, не авто-цикл). Диагноз «бэкенд недоступен» ставь только после того, как и curl 200, и смоук-агент упали.

## Запреты

- **`--continue`** у cursor-cli — запрещён (берёт «последнюю сессию каталога»).
- **`--resume`** — только явный `session_id` из фазы, не «продолжи как было».
- Два живых PID с одним `--workspace` — не запускать параллельно.
- **Авто-ретрай** после фатала — запрещён; повтор только по решению Саши или осознанный `next` после разбора.

## Фаталы провайдера (структурно-осознанный классификатор, Б42 / AC-065…068)

Обёртка обязана вернуть **rc ≠ 0**, вызвать `interrupt`, отправить в **ErrorBus** (`--tool dev_workflow`), **без** авто-ретрая. Классификатор (`invoke_role.py`) структурный, **не** regex по всему stdout+stderr:

1. Вывод `--output-format json` парсится как JSON: `is_error=true` / `type==\"error\"` → fatal; легитимный JSON (rc=0) с бытовой лексикой `timeout`/`credits`/`billing`/`payment` → **НЕ** fatal (это текст роли/подсказки).
2. Не-JSON → fallback на **строгие** сигнатуры провайдера (без голых бытовых слов): `Iteration budget exhausted`, `(90/90)`, `No API key`, `HTTP 5xx/429`, `request timed out`.
3. **rc ≠ 0 ≠ мгновенный fatal.** Киллы терминала `124/137` («вызов не завершён», retry) и rc=1 (usage/argv, контракт-ошибка) — **не** провайдер-fatal и **не** ErrorBus critical. Провайдер-fatal — только rc ∈ {2,3} (LLM-провайдер).

| Сигнал | Вердикт |
|---|---|
| JSON `is_error=true` / `type=\"error\"` | fatal (detail: `json is_error=true: …`) |
| `Iteration budget exhausted`, `(90/90)`, `No API key`, `HTTP 5xx/429`, `request timed out` | fatal (detail: паттерн) |
| rc ∈ {2,3} (LLM-провайдер) | fatal |
| rc ∈ {124,137} (килл терминала) | **не** fatal — retry («вызов не завершён») |
| rc=1 (usage/argv) | **не** fatal — контракт-ошибка, не провайдер |
| rc=0 + легитимный JSON / бытовая лексика timeout·credits·billing | **не** fatal |

Событие ErrorBus самодиагностируемо: `--source-kind` (дефис), `--severity critical`, `--exit-code`, `--stage`, `--cmdline` (redacted), `--llm-model`, `--detail=<why>`. Флаг — именно `--source-kind` (дефис), парсер `report_error.sh` другую форму молча теряет (AC-067).

После фатала: статус слага `interrupted` при мёртвом PID; оркестратор сообщает Саше, не перезапускает фазу молча.

## Успех без complete

rc = 0 **не** означает, что фазу можно закрыть. Нужен ожидаемый **артефакт на диске** (путь в `--evidence`). Пустой ответ или «готово» без path/sha256/session — не `complete-phase`.

## REV — канонические имена (G6 / AC-047)

Ревизор пишет **только** `dev/<slug>/REV-tz.md` или `REV-plan.md`. Соседние `REV-tz-2.md` и т.п. → `invoke_role` exit ≠ 0 с hint на канон; оркестратор не «перекладывает» файлы за роль. Архив итераций — `REV-tz-1-REQUEST.md` (гейт не читает). Вердикт парсится из блока `## Вердикт` / `verdict=` (`rev_verdict()`), не по всему телу файла.

## Workspace по типу фазы

| Фазы | Workspace (типично) |
|---|---|
| TZ:*, REV:tz | `…/Hermes-Backlog/TZ` |
| HF:impl/test USERTOOL | `…/USERTOOLS/<Tool>` |
| патч скилла | `…/hermes-workspace/skills` |
| ORCH:shared-state | `…/WorkVault/Registries` |

Для пакета DevWorkflow (`pipeline/` + скилл): два последовательных invoke на `HF:impl` — сначала WorkVault, потом hermes-workspace (одна фаза, два дерева; не склейка impl+test).

## Уведомления vs ErrorBus

- Сообщения о ходе кейса, HITL, AC — **origin**-топик (`pipeline_notify.py`).
- Падение CLI, hash mismatch, CRISIS, billing, 90/90 — **ErrorBus** thread `11112`, не дублировать в origin как технику.

Детали cursor-cli: `cursor-cli-notes.md`.
