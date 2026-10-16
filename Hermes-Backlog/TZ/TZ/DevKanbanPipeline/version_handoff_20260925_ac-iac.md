# version-handoff — dev-pipeline-ac-criteria (2026-09-25)

Граф: DEV/dev-pipeline-ac-criteria
Фаза: HF:docs-handoff
Исполнитель: composer-2.5 (docs text уже написан в HF:impl; здесь — верификация и метаданные)

## Скоуп изменений

Bагфикс по канбану: устранение попадания Cursor-slug в `model_override` воркера
(прецедент t_2c8ee3b2, HTTP 400 `must include upstream provider prefix`, protocol_violation)
+ внедрение СЛОЯ AC/IAC (DKP v0.3.2) в канон разработки.

Изменены ТОЛЬКО два скилла (в скоупе HF):
- `tz-workflow`: 2.4.3 → 2.5.0
- `hermes-feature`: 2.7.3 → 2.8.0

Вне скоупа (ложный git-drift, задокументировано): skills/devops/kanban-dev-pipeline-orchestration/SKILL.md,
skills/devops/kanban-worker/SKILL.md, skills/productivity/mfl-mfe-urgent-contacts/references/exchange-digest-filtering.md.

## Версии

| Скилл | До | После |
|---|---|---|
| tz-workflow | 2.4.3 | 2.5.0 |
| hermes-feature | 2.7.3 | 2.8.0 |

## Что изменилось в тексте скиллов (docs-handoff подтверждает)

### tz-workflow 2.5.0
- Требование 4 (авто take-into-work после diagnose-review) **отменено**: `GATE:take-into-work` — HITL never auto в любом режиме.
- `GATE:diagnose-review` — не HITL Саши; subject = архитектор + REV:tz; complete вручную архитектором.
- AC-список после TZ:finalize: сначала в диалоговый чат, затем kanban_comment+block на гейте (payload = список AC).
- Запрет `model` на create TZ:*/REV:tz (model_override IS NULL); колонка «Модель» = внутренний `agent -p`, не `kanban_create --model`.
- Слой AC/IAC: маркеры I1 current/target, подраздел `### Критерии приёмки (AC)` с якорями AC-001… только пакета.
- Набор R5 notify-subscribe (корень + гейты), не полная подписка.

### hermes-feature 2.8.0
- Запрет `model` на create HF:*/BUG:diagnose/REV:plan (анти-пример t_2c8ee3b2).
- GATE:plan-approve — always auto (`auto-pass: architect-plan`), HF:plan обязателен.
- GATE:done — HITL never auto (и в one-pass); preflight exit 0 необходим, не достаточен.
- Таблица IAC в HF:plan (path/verify/depends/covers), iac_passed в metadata.
- Блок 6Б namespace: cronjob/delegate — D1 модель; Cursor-slug в воздух запрещён.
- Полный документ в agent -p без обрезки (канон cursor-cli).
- Набор R5 notify-subscribe.
- Блок 8 (RESEARCH) = граф RS:* (collect/analyze=grok, REV:report=sonnet).

## Манифест (для ORCH:shared-state)

Наблюдение: раздел `skills` в EcosystemManifest.json для `hermes_feature` и `tz_workflow`
**поле version не содержит** — только name/tools/triggers. Эти три поля данным багфиксом
**не меняются**. → Изменение EcosystemManifest.json для этих двух ключей НЕ требуется;
ORCH достаточно выполнить `--check-drift` (без новых дыр) и регенерацию digest/render.

## Верификация docs (эта фаза)

- Версии в frontmatter: tz-workflow=2.5.0, hermes-feature=2.8.0 — совпадают с plan.
- Устаревших ссылок на «требование 4» / «auto-pass one-pass mode» / старые версии — нет.
- Канон AC/IAC, запрет --model, набор R5, HITL-гейты — присутствуют в обоих скиллах.
- Синк-копии (hermes-workspace ↔ ~/.hermes) идентичны (подтверждено HF:test).

Подтверждено HF:test: pytest 22 passed (20/20), IAC-01..14 PASS.