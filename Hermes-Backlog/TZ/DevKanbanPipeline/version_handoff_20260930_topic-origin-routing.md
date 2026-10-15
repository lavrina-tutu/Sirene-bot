# version-handoff — topic-origin-routing (2026-09-30)

Граф: DEV/topic-origin-routing (R5-origin)
Фаза: HF:docs-handoff
Исполнитель: composer-2.5 (docs-текст уже написан в HF:impl; здесь — верификация и метаданные)

## Скоуп изменений

Реализация политики R5-origin: канал уведомлений/пробуждения графа кейса =
origin-топик инициатора (`-1004300127777`, `--thread-id <ORIGIN> --chat-type group`),
а не хардкод мониторинга `:7`. Контракт subscribe **без** `--thread-id` запрещён;
`resolve_origin` шага 3: пустая строка `thread_id` = SILENCE; набора R5 не расширять;
SILENCE-unsubscribe снимает все telegram-подписки (DM `400307920`, пустой thread);
SILENCE не подставляет `:7`. Документирован стоп-кран identity (чеклист 4 факта)
перед `HF:impl` origin-routing и калька «диалог = origin-топик» для GATE:done.

Изменены только ДВА скилла (в скоупе HF:plan):
- `tz-workflow`: целевая версия 2.7.0 (в плане), факт на диске — 2.8.0 (позднее
  накат dev-process-tz-hardening, коммит abe1f8a)
- `hermes-feature`: целевая версия 2.10.0 (в плане), факт на диске — 2.11.0 (там же)

Версии ТЗ: DevKanbanPipeline_TZ.md 0.4.2 (AKA DKP v0.3.9→0.4.x, origin-routing
вшит в главы «Уведомления графа» / «Прекондиция identity», уже на диске).

## Что изменилось в тексте скиллов (docs-handoff подтверждает)

### tz-workflow 2.8.0 (origin-канон, наследует topic-origin-routing)
- `#### Подписка графа на уведомления (notify-subscribe)`: канал = origin-топик;
  snippet `--thread-id <ORIGIN> --chat-type group`; команда без `--thread-id` запрещена.
- Набор R5 **не расширять** (корень DEV/IDEA + GATE:take-into-work/done/go/block-accept
  + IDEA:analyze); `BUG:diagnose` не подписан; leftover «все фазы / багфикс обе» запрещён.
- Новый подраздел `##### resolve_origin` (алгоритм kind=root|child, П.1δ пустая
  строка thread_id = SILENCE, нормализация chat_type thread→group).
- Новый подраздел `##### SILENCE-unsubscribe` (list→unsubscribe все telegram при
  SILENCE / ровно одна строка group+ORIGIN+notify+wake при origin; DM и пустой thread).
- Канал wake/notify = `kanban_notify_subs.thread_id`, не metadata/body.
- `### После TZ:finalize`: AC-список в диалог = origin-топик (не `:7`, не `:11112`).
- IDEA-feed (ручной) — тот же контракт resolve_origin + R5; passive-inbox — только корень.

### hermes-feature 2.11.0 (origin-канон)
- Зеркало TW: snippet `--thread-id <ORIGIN> --chat-type group`; содержимое канала/канона.
- `##### resolve_origin` / `##### SILENCE-unsubscribe` — те же, что в TW.
- `GATE:done`: публикация отчёта AC в origin-топик (не ops `:7`, не `:11112`, не DM);
  маркер `AC-delivered: origin`.
- Стоп-кран identity (HF-7): перед `HF:impl` origin-routing чеклист 4 фактов
  (`build_session_key` → `:group:`, wake chat_type='group', SQL `chat_type='thread'`=0,
  нет вилки `telegram:thread:-1004300127777:*`); `identity-checklist:` в comment.
- Дети хвоста копируют origin с корня; `GATE:plan-approve` не подписывается.
- Wake: terminal `blocked` корня будит `group:-1004300127777:<ORIGIN>`; копий в
  `:1`/`:7` нет при другом ORIGIN. Рестарт gateway — не этот скилл.

## Манифест (для ORCH:shared-state)

Раздел `skills` в EcosystemManifest.json для `hermes_feature` и `tz_workflow`
содержит только `name/tools/triggers` — **поле version отсутствует**. Триггеры и
tools этими правками **не меняются**. → Изменение EcosystemManifest.json для этих
двух ключей НЕ требуется; ORCH достаточно выполнить `--check-drift` (без новых дыр)
и регенерацию digest/render.

## Верификация docs (эта фаза)

- Версии frontmatter: tz-workflow=2.8.0, hermes-feature=2.11.0 (>= плана 2.7.0/2.10.0;
  поздние бампы dev-process-tz-hardening задокументированы в git abe1f8a).
- Все маркеры плана присутствуют в ОБОИХ скиллах (по 13+ вхождений на файл):
  `resolve_origin`, `SILENCE-unsubscribe`, `пустая строка thread_id`, 
  `kanban_notify_subs.thread_id`, `origin-топик`, `--thread-id <ORIGIN>` обязателен,
  `--chat-type group`, «набор R5 не расширять», `identity-checklist`.
- Leftover-подписок («подписать обе» / «ОБЕИХ» / «все созданные фазы») в
  контракте subscribe — 0.
- Worktree skills: чист (изменения закоммичены, G3 git-proof соблюдён на HF:test).
- Синк-копии hermes-workspace (=~/.hermes/skills симлинки) идентичны.

Подтверждено HF:test (t_b0a8784e, решение Саши 29.09, вариант 1):
IAC-10 headless/SILENCE PASS, IAC-13 wake origin :3 PASS, IAC-12_identity PASS;
IAC-09/11 закрыты по решению Саши (недостижимы для headless-воркера).