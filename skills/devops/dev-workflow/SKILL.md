---
name: dev-workflow
version: 0.3.2
description: Оркестрация разработки Hermes (файловое состояние, 10 кейсов)
---

# Dual-path (переход W0–W4)

Пока в конфиге `tools.dev_workflow.orchestration.mode` не равен `workflow-only`:

- не вызывай `pipeline init` для слагов **вне** списка `orchestration.pilot_slugs` (на W1 список пустой);
- если слаг в `pilot_slugs` и на нём **нет** живого канбан-running — **стоп**, веди задачу только этим скиллом;
- для остальных слагов — по-прежнему `hermes-feature` / `tz-workflow` и канбан;
- два поезда на одном слаге запрещены.

Подробности: `references/rollback.md`, текст баннера для чужих скиллов — `references/dual_path_banner.md`.

# dev-workflow — процедура оркестратора

Единый процесс разработки вместо связки «канбан + несколько скиллов». Норматив смысла (кейсы, фазы, гейты, роли) — в `references/canon.md`. Мастер-ТЗ инструмента: `~/WorkVault/Hermes-Backlog/TZ/DevWorkflow/DevWorkflow_TZ.md` **v0.3.2**.

**Кто ты:** Сирень (профиль default). Ты ведёшь фазы, зовёшь роли через Python, не пишешь ТЗ и код сама.

**Помощник на диске:** `Registries/pipeline/` — состояние в `dev/<slug>/_state.json`, команды через `scripts/pipeline.sh` или `python3 -m pipeline.cli`.

## Когда включать скилл

| Фраза / ситуация | Действие |
|---|---|
| разработай, доработай, почини, напиши ТЗ, исследуй, в бэклог | см. таблицу кейсов в `references/cases-guide.md` |
| слаг в `pilot_slugs` (W2+) | только `dev-workflow`, канбан для этого слага на паузе |
| после `hermes update` | `restore-all-skills.sh`, затем `pipeline status --check` (exit 0 обязателен) |

## Старт задачи

1. **Бриф в Telegram** — уточни кейс со Сашей (один вопрос, если неясно). Бриф не пишется в рецепт на диске.
2. **Закрытие брифа** — зафиксируй кейс, периметр, решения. Пока бриф открыт — `init` не делай.
3. **`pipeline init`** — обязательные поля: `--case`, `--slug`, `--title`, `--origin-chat`, `--origin-thread`. Пример и пути — `references/install.md`.
4. **Preflight create (G4)** — в `recipe[]` должны быть все фазы выбранного кейса. Ошибка → init не считается завершённым.

## Основной цикл (без cron и «тиков»)

Движение только когда: Саша написал, роль вернула результат, или ты сознательно вызываешь `next` в том же ходе.

```
pipeline next
  → читаешь action (WORK | AUTO_GATE | WAIT_SASHA | DONE | INTERRUPTED | BLOCKED)
  → действуешь по таблице ниже
  → при успехе: complete-phase --reason … --evidence …
  → при сбое роли: interrupt (не авто-ретрай)
```

| action | Что делать |
|---|---|
| **WORK** | `emit-prompt` → при exit 0 → `invoke-role` (не `agent -p` напрямую) → проверить артефакт на диске → `complete-phase` |
| **AUTO_GATE** | показать/проверить улику (AC-список, план, отчёт…) → `complete-phase` с reason+evidence |
| **WAIT_SASHA** | сообщить в **origin**-топик (не Errors), `waiting_operator`, **остановиться** (нет фонового опроса) |
| **DONE** | preflight закрытия → отчёт AC в origin |
| **INTERRUPTED** | сообщить Саше; не перезапускать фазу сама |
| **BLOCKED** | техника → ErrorBus; кейс → origin |

Перед каждой содержательной фазой (TZ/HF/BUG/REV): только цепочка **emit-prompt → invoke-role**. Обход и `--force` запрещены. Пакет контекста: `references/context.md`.

**LIGHT:** после известного объёма — `pipeline set-case --case CHANGE-LIGHT` или `BUGFIX-LIGHT` (не решает архитектор).

## Согласование ТЗ и плана (REV)

После `TZ:patch` и `HF:plan`:

1. `complete-phase` архитектора с evidence.
2. `next` → `REV:*` → emit-prompt → `invoke-role --role reviewer`.
3. Вердикт в `dev/<slug>/REV-tz.md` или `REV-plan.md`: `APPROVE` или `REQUEST-CHANGES`.
4. **APPROVE** → `complete-phase` REV → следующая фаза.
5. **REQUEST-CHANGES** → **не** закрывать REV; вернуть архитектору; повтор REV до APPROVE (или явный waive Саши).

Детали: `references/canon.md` (роли), `references/invoke.md`.

## HITL и уведомления

- Остановка поезда — только класс **O** (operator-hold) и never-auto гейты (`GATE:go`, `GATE:block-accept`).
- Показ AC (класс **S**) поезд **не** останавливает.
- Глаголы Саши — закрытый список в `references/canon.md` (`поднимай`, `ставь кроны`, `удаляй`, `answer:Q-n`, `rollback-to-kanban`).
- Снятие hold: `pipeline operator-done --verb … --evidence …` после **факта**, не после одной фразы.
- Ход кейса → origin; сбои CLI/инвариантов → ErrorBus (`references/invoke.md`).

## Запреты (кратко)

- Не склеивать фазы (`HF:impl` и `HF:test` — разные вызовы).
- Не вызывать `agent -p` в обход `invoke-role`.
- Не использовать `--continue` у cursor-cli.
- Не выбирать кейс и не пропускать фазы за архитектора (G5).
- Не ставить кроны без «ставь кроны»; не рестартовать gateway из этого процесса.

Полный список неприемлемого поведения — Б33 мастер-ТЗ.

## Миграция W0–W4 и откат

Волны, пилот, возврат на канбан: `references/rollback.md`.

## Справочники (содержание, не процедура)

| Файл | О чём |
|---|---|
| `references/canon.md` | кейсы, фазы, гейты, роли, G1–G5 |
| `references/cases-guide.md` | какой кейс когда |
| `references/cases/CHANGE.md` | эталон полного цикла |
| `references/context.md` | два источника, MUST-read, emit-prompt |
| `references/invoke.md` | бэкенды, фаталы провайдера |
| `references/cursor-cli-notes.md` | детали бэкенда cursor-cli |
| `references/rollback.md` | W0–W4, rollback-to-kanban |
| `references/install.md` | установка на голый Hermes (AC-042) |
| `references/handoff.md` | перенос живого слага (Б13.4) |
| `references/onboarding.md` | для специалиста без разработки |
| `references/config.example.yaml` | ключи `tools.dev_workflow` |
| `references/kanban-mechanics.md` | что сохранили из канбана без диспетчера |
| `references/dual_path_banner.md` | баннер W2 в hermes-feature/tz-workflow |

Комплект для нового хоста: `README.md` → `install.md` → `onboarding.md`.
