# Дизайн отказа от канбана → dev-orchestrator (вердикт архитектора, 13.10.2026)

Что это: согласованный архитектором дизайн замены Hermes Kanban как runtime оркестрации DEV/IDEA. Это **план**, ожидающий решения Саши «берём в работу» — не оперативный рабочий процесс, пока Саша не утвердил. Не реализовывать фрагменты до явного «го». Граф `DEV/kanban-stalled-train-age` — НЕ реализовывать (это фикс сторожа, который снимаем); его diagnose можно использовать как улику-обоснование.

## Вердикт
Полный отказ от канбана как оркестрации. Не чинить ядро, не канбан-клон, не гибрид с живым `kanban.db`. Канон (кейсы, фазы, AC, гейты) НЕ пересматривается — меняется только машина исполнения. Причина: диспетчер (claim/heartbeat/reaper/block_loop/stalled-train) исполняет линейный инженерный рецепт через чужую очередь и наказывает легитимную паузу (HITL) так же, как сбой воркера.

## Три слоя замены
1. **Скилл `dev-orchestrator`** — процедура: выбор кейса со Сашей, `pipeline init/next`, один `agent -p` на фазу (роль D2), HITL-вопросы в TG, вызов notify. Не пишет ТЗ/код, не крутит фон, не claim'ит.
2. **`tz-workflow` / `hermes-feature`** — содержание фаз (`TZ:*`/`HF:*`/`BUG:*`/`RS:*`), без `kanban_create/complete/block`, без D1, без off-board/dispatch.
3. **Python `pipeline/`** — рецепт кейса, gating AC, git-proof, operator-hold, свежесть ТЗ, probe боевого python, статус-карта. SoT = файл, не БД. Расширять существующий `pipeline_gate_done_preflight.py` / `pipeline_context_bundle.py`, перевернув их источник с `kanban.db` на `_state.json`.

## Т1 — Единая очередь + «ничего не теряется»
- SoT членства = каталог `dev/<slug>/_state.json`; SoT сквозного списка = `dev/queue.json` (вычисляемый индекс, НЕ sqlite — свой `.db` это канбан-клон).
- Синк: **single-writer** + `flock` на `.queue.lock` + atomic rename tmp+fsync + журнал мутаций `queue.log.jsonl`. Второй писатель ждёт lock.
- Дедуп по `slug` = имя каталога `[a-z0-9][a-z0-9-]*`; `init` на занятый → exit 1.
- Гарантия «не потеряно» = 4 проверки: дедуп slug; `glob */*.json` vs `queue.items` (папка есть-индекса нет → **repair**; индекс есть-папки нет → **CRISIS** в HITL, не удалять); `state_sha256` сверка; журнал мутаций diff vs glob. `abort` не rm — только `abort --purge` по императиву Саши.
- `pipeline reindex` = чистая функция glob → queue.json. Строка отчёта = **один слаг**, не каждая фаза.

## Т2 — Тот же формат статуса
`pipeline status` печатает layout текущего `kanban_status_report.py` (заголовок, строка счётчиков, эмодзи-префиксы, секции HITL и «Закрыто сегодня») — Саша не переучивается. HITL = поле `status=waiting_operator`, а НЕ regex по reason (это и был корень рассинхрона eco-config-w2).
Маппинг колонок: blocked→`waiting_operator`|`blocked`; HITL→`waiting_operator`; фоновый блок→`blocked`; scheduled→`interrupted` (PID мёртв, честный, без reaper); ready→`idle`; todo→`idle`; running→`in_phase` (PID жив; hb= из `last_progress_at`, возраст от `started_at` НЕ душит); triage→IDEA-бэклог; done за сегодня→«Закрыто сегодня». `scheduled` теперь только `interrupted`.

## Т3 — Код vs скилл (мировые практики)
Принцип индустрии 2024-26: control flow и состояние — детерминированный код; LLM — короткий цикл внутри шага. Источники: 12-Factor Agents (github.com/humanlayer/12-factor-agents), SWE-agent ACI (arxiv 2405.15793), spec-driven/TDD (github/github/spec-kit), Cursor/Codex/CodexCLI/Aider (git как факт реализации = наш G3).
- **Обязательно кодом** (exit 0/1, атомарно): фазы/рецепт кейса, gating AC/operator-hold/open Q, git-proof, синк очереди, формат stdout, probe, `accepted`-по-реплике, emit-prompt freshness, единственность живого слага.
- **Обязательно скиллом** (промпт/диалог): текст ТЗ, диагноз, REV, вопросы Саше (R3), выбор кейса, код, интерпретация красных тестов.

## Т4 — Устойчивость к `hermes update`
Ноль кода в `hermes-agent`, ноль `kanban_*`/`HERMES_KANBAN_TASK`/dispatcher. Код в `~/WorkVault/Registries/pipeline/` + скиллы в `~/hermes-workspace/skills/` (симлинки). Пути через `EcosystemConfig.yaml` (`DEV_STATE_ROOT`, `TZ_ROOT`) — этот канал уже портабелен. 3 адаптера: `invoke_role`, `notify`, `paths` — смена Hermes = правка адаптера, не инвариантов. `cronjob`/`delegate_task` опционально только для длинного `agent -p` с fallback на блокирующий вызов. Санity-check после апдейта: `pipeline status --check` (exit 1 = апдейт задел контур) — шаг в `hermes-feature/references/hermes-upgrade-pattern.md`, не в ядре.

## Волны внедрения (после утверждения)
W0 канон-текст (GLOSSARY «граф»=рецепт `_state.json`; скиллы: вырезать kanban-шаг, добавить dev-orchestrator) → W1 Python (`pipeline_state.py` + перенос preflight/emit-prompt на файлы; pytest на фикстуре) → W2 пилот (eco-config-w3) → W3 остальные кейсы (BUGFIX-LIGHT, RESEARCH, DECOMM) → W4 выключение (перестать create, `dispatch_in_gateway` выкл. по согласованию, БД в `_Archives`).

## Неприемельность (не сделать канбан-клон)
Любое из: цикл опроса каждую минуту + запуск воркера; heartbeat/reaper/claim_lock/max_in_progress; статусы ready/running/blocked/triage как очередь; auto-promote детей; возраст от `started_at` как сигнал «задуши»; второй sqlite/tasks таблица; скилл, «сам себя будит» без фразы Саши или без `pipeline next` из чата.
