---
name: dev-workflow
version: 0.8.2
description: "Разработай, доработай, почини Hermes/USERTOOLS."
metadata:
  hermes:
    tags: [development, workflow, Hermes, USERTOOLS]
    related_skills: [hermes-feature, tz-workflow]
---

# dev-workflow — единственный маршрут разработки

Изменения, баги, ТЗ, исследования и скиллы Hermes/USERTOOLS. Обычные предметные поручения — через свои инструменты. Норма — Б55/Б56 [master-ТЗ](/home/tkachenkoav/WorkVault/Hermes-Backlog/TZ/DevWorkflow/DevWorkflow_TZ.md). **выжимка ≠ SoT; при расхождении — открыть master**.

Роли/кейсы/фазы/G1–G6 — [канон](references/canon.md); кейс — по [триггерам](references/cases-guide.md). Оркестратор ведёт факты/процесс, не предлагает слаги и технические варианты. Архитектор — ТЗ/план/диагноз без боевого кода, ревизор — независимый вердикт, исполнитель — реализация/проверки плана; существенное отклонение возвращает архитектору. Модели/backend — YAML `tools.dev_workflow`. `HF:impl` и `HF:test` — отдельные вызовы.

## Исполняемая таблица

| Событие / состояние | Обязательное действие |
|---|---|
| Приём / FIFO | Сохранить запрос/origin/время; `idea=true` — triage без автостарта. FIFO: первая подтверждённая готовность → порядок журнала → slug. Текущая задача держит поток до `GATE:done`+отчёта либо отмены Сашей. Приоритет — только его указание с evidence. |
| `WORK` | Сверить фазу/журнал/имеющийся результат. Роль — по invoke ниже; оркестратор — действие рецепта и complete с уликой либо interrupt в том же ходе. |
| Wrapper жив | Не next/complete-phase/recover/interrupt/второй invoke. Роль пишет outputs и возвращается оркестратору; мониторинг своего wrapper не работа фазы. |
| `RECONCILE` / post-invoke | После выхода wrapper сверить slug/phase, журнал, receipt при наличии и свежий output → штатный complete с reason/evidence. `role` без результата — `empty-result`/`canonical_artifact_fail`. Не повторять side effect. |
| Повтор completion / `start` | Принятый результат — no-op. Новый запуск требует необработанной работы и основания ниже. Notify/timeout/`pid=None` сами по себе его не дают. |
| `RECOVER` | Подтверждённый recoverable-класс без результата, wrapper мёртв: один recover с reason/evidence → warn в origin → next. Развилки — [invoke](references/invoke.md). |
| `AUTO_GATE` | Проверить улику и complete без LLM. Never-auto `GATE:go`/`GATE:block-accept` ждут operator evidence. |
| `WAIT` / `INTERRUPTED` / `BLOCKED` | Причина, начало, чей шаг и условие продолжения. Контекст/блокер/лимит/provider-fatal/пауза держат очередь; неизменный отказ не перезапускать. |
| Завершение | Проверить весь объём/evidence; `GATE:done` требует preflight=0 и доставленный AC-report. Затем root `done`; `aborted` — отмена. FAIL/no-entry/частичный объём сохраняют вердикт. |

Продолжать 24/7 по проверенному completion без сообщения Саши. Лимит — ждать подтверждения восстановления, затем та же фаза без смены backend/модели/reset. Doorbell — wake по смене fingerprint, без LLM на прежнем состоянии и next/recover/spawn/kill из tick.

## Три разных регламента

1. **Техническое восстановление:** один corrective-повтор класса/фазы с новой уликой; повторный сбой — диагноз/стоп. Provider-fatal не recoverable.
2. **Повтор замечания:** первый REQUEST-CHANGES — архитектору, второй подряд тот же дефект — диагноз с ревизором до третьей доработки. REV complete только по APPROVE в `REV-tz.md`/`REV-plan.md`.
3. **Пересмотр требований:** новое указание Саши меняет контракт/AC/scope; записать источник, влияние и минимальный rework, согласовать архитектором с ревизором.

Перед повтором: регламент, прежний факт, новая улика. «Доделай» и диагноз счётчики не сбрасывают. Первый идентичный повтор IAC FAIL после доработки — диагноз архитектору до следующего прогона. Локальную незавершённость исправляет исполнитель; [примеры](references/operational-pitfalls.md).

## Границы роли и контекста

Перед ролью читать [invoke](references/invoke.md): `emit-prompt` rc=0 → один `invoke-role`. Контекстом владеет `pipeline_context.py`; packet/MUST-read — [context](references/context.md).

Только immutable packet/sidecar/render, без ручного prompt/fallback/`--force`. До complete — G2 accepted binding/`context-used:`, применимый `pipeline check` и output evidence. HF:impl сверяет write-set/полноту матрицы; HF:test исполняет каждый IAC.verify. Missing обязательного узла/проверки блокирует complete при любом числе passed — [сверка](references/operational-pitfalls.md).

## Состояние, ограничения и ссылки

`_state.json` — SoT хода, только штатный writer; `repair` не сброс PID. Статус по запросу: выполненные за 48 часов, текущие любого возраста; устаревание помечать, архив — по запросу.

Соблюдать phase write-set, backup и G3. Не менять case/recipe/G6, чужие state/journal и паузы B3/B4/w3/w4; не создавать сервис/БД/очередь/канал/cron, budget engine или global mutex; Gateway не рестартовать. **[NEW-ENTITY, требует согласования Саши]** сохранять дословно, проектирование/создание — после согласования. Operator-словарь и S/O/C — в каноне.

[Онбординг](references/onboarding.md), [установка](references/install.md), [handoff](references/handoff.md), [rollback](references/rollback.md), [история](references/kanban-mechanics.md) — по задаче. `hermes-feature`/`tz-workflow` сохраняют предметные проверки. Оформление — [Creating Skills](https://hermes-agent.nousresearch.com/docs/developer-guide/creating-skills/).
