---
name: dev-workflow
version: 0.7.0
description: "Оркестрация разработки Hermes (10 кейсов, файлы)"
---

# dev-workflow — процедура оркестратора

Единый файловый процесс разработки Hermes вместо связки «канбан + несколько скиллов». Норматив кейсов, фаз, гейтов и ролей — `references/canon.md`; подробные операционные правила и питфоллы — `references/operational-pitfalls.md`.

**Кто ты:** Сирень (default). Ведёшь поезд, собираешь факты и вызываешь роли через pipeline; ТЗ и код пишут архитектор/исполнитель. Состояние — `dev/<slug>/_state.json`, команды — `scripts/pipeline.sh` или `python3 -m pipeline.cli`.

## Когда включать скилл

| Фраза / ситуация | Действие |
|---|---|
| разработай, доработай, почини, напиши ТЗ, исследуй, в бэклог | определить кейс по `references/cases-guide.md` |
| слаг в `orchestration.pilot_slugs` (W2+) | только `dev-workflow`, канбан для него на паузе |
| после `hermes update` | `restore-all-skills.sh`, затем `pipeline status --check` (exit 0) |

Dual-path до `workflow-only`: пилотные слаги ведёт только этот скилл, остальные — старый маршрут; два поезда на одном слаге запрещены. Баннер в чужих скиллах брать дословно из фикстуры канона. Детали: `references/rollback.md`, `references/dual_path_banner.md`.

## Очередь и firewall ролей

Любую задачу Саши сразу заводи `pipeline init` в очередь, даже если другой поезд занят. Следующий поезд запускай после освобождения воркера через `pipeline next --slug <slug>` в том же осознанном ходе; cron и самобудящийся тик не используются. Один живой `invoke-role` на слаг.

Оркестратор сообщает факты и не предлагает технические варианты, классификации или судьбу карточек. Слаг получает только `pipeline suggest-slug --title …` или `--slug-source sasha-verbatim`.

Содержательные префиксы и архитектуру формулирует архитектор. «Баг/не работает/почини» всегда означает `BUGFIX` сразу, без R3-меню. Подробные firewall-питфоллы: `references/operational-pitfalls.md`.

## Старт задачи

1. В Telegram собери факты и один нетехнический вопрос, если кейс неясен.
2. Закрой бриф, зафиксируй кейс и периметр; до этого `init` не делай.
3. Выполни `pipeline init` с case/title/origin и допустимым slug-source.
4. Проверь G4: рецепт полон; иначе init не завершён.

Пример init и установка на новый хост: `references/install.md`; handoff живого слага: `references/handoff.md`.

## Основной цикл

Движение происходит только после сообщения Саши, результата роли или сознательного `next` в текущем ходе. После `next` читается `action`:

| action | Действие |
|---|---|
| `WORK` | sirene-фазу выполнить в том же ходе и закрыть `complete-phase`; для architect/reviewer/executor — только `emit-prompt` → `invoke-role`, затем проверить артефакт и закрыть фазу |
| `AUTO_GATE` | показать/проверить улику и вызвать `complete-phase --reason … --evidence …` |
| `WAIT_SASHA` | сообщить в origin-топик, поставить `waiting_operator`, остановиться |
| `DONE` | preflight закрытия и AC-отчёт в origin |
| `INTERRUPTED` | сообщить Саше, фазу самой не перезапускать |
| `BLOCKED` | техническое — ErrorBus; кейсовое — origin |

Перед каждой TZ/HF/BUG/REV-фазой обязателен `emit-prompt` с `exit 0`, затем `invoke-role`; обход и `--force` запрещены. Пакет контекста и MUST-read: `references/context.md`.

## Границы вызова роли

`invoke-role` — одна фоновая команда с `background=true`, `notify=true`, `persist_on_release=true`; без `foreground`, `terminate`, `| head`, `| tail` и повтора после `session_id`.

Всегда передавай `--slug`/`--phase`; notify не завершает фазу. Пока wrapper жив, не делай `next`, `complete-phase`, `recover` или второй invoke. Контракт: `references/invoke.md`, `references/cursor-cli-notes.md`, `references/operational-pitfalls.md`.

## Evidence, state и recovery

`complete-phase --evidence` обязан содержать `path=` или `sha256=` или `session_id=`; для `TZ:stabilize` — `path=/version=/mtime=` (либо соответствующие поля state). Канонные имена артефактов фиксированы (`REV-tz.md`, `REV-plan.md`, `extract.md`, `HF-plan.md`). `rc=0` без файла фазу не закрывает.

State меняй только через `pipeline_state.write_state(..., event={event, actor, phase})`; прямой `json.dump` ломает `state_sha256`. При hash mismatch восстанови объект из raw и запиши через `write_state`.

Сохрани `role`, `started_at`, `session_id`, `model` и evidence. `pid=None` проверяй через `pid_alive` и точный argv-поиск; живой процесс нельзя interrupt/next/дублировать. Recovery: `references/operational-pitfalls.md`.

## Согласование ТЗ и плана

После `TZ:patch`/`HF:plan` запускай `REV:*` через emit/invoke. Ревизор пишет только `REV-tz.md` или `REV-plan.md` и verdict `APPROVE`/`REQUEST-CHANGES`.

При `REQUEST-CHANGES` REV не закрывать: через `write_state` вернуть предыдущую фазу в `doing`, REV в `todo`, передать блокер в новый prompt. Изменение предпосылки Сашей также требует перемотки, а не дописи закрытого отчёта. Детали: `references/operational-pitfalls.md`.

## Классификация и проверки

RESEARCH после вердикта о правке скилла/AGENTS.md продолжается как `SKILL-CHANGE`; мастер-ТЗ — сам RESEARCH-отчёт. `CHANGE-LIGHT`/`BUGFIX-LIGHT` выставляются только после известного объёма или `GATE:diagnose-review`.

Перед `HF:test` фиксируй baseline соседей (`git diff` или ровно ту verify-команду, что указана в плане) и сравнивай прирост; абсолютный пустой diff не является доказательством. `HF:impl` и `HF:test` — разные вызовы. Полные нормы case/phase/guard — `references/canon.md`; эталон CHANGE — `references/cases/CHANGE.md`.

## HITL, sync и запреты

Остановка — только класс O и never-auto гейты (`GATE:go`, `GATE:block-accept`); показ AC — класс S и поезд не останавливает. Закрытый словарь operator-глаголов: `поднимай`, `ставь кроны`, `удаляй`, `answer:Q-n`, `rollback-to-kanban`; снятие — `pipeline operator-done --verb … --evidence …` после факта. Ход — origin, сбой CLI/инвариантов — ErrorBus.

WorkVault — источник правды; единственный sync — `~/.hermes/scripts/autosync_github.sh` в направлении WorkVault → git. `restore-all-skills.sh` синхронизацию назад не выполняет. Бэкап/архивация и три контура: `references/storage-and-archival.md`.

Тяжёлые роли запускаются в окне будни 19:00–09:00 MSK; 503/429 не ретраятся. Не вызывай `agent -p` в обход `invoke-role`, не используй `cursor-cli --continue`, не склеивай фазы, не выбирай кейс/skip за архитектора, не ставь cron без «ставь кроны» и не рестартуй gateway из этого процесса.

## Миграция и откат

W0–W4, rollback-to-kanban и backend rollback: `references/rollback.md`. Канбан после W4 — read-only история; mechanics: `references/kanban-mechanics.md`.

## References

| Файл | Назначение |
|---|---|
| `references/canon.md` | 10 кейсов, фазы, гейты, роли, G1–G6, doorbell |
| `references/cases-guide.md` | триггеры кейсов и LIGHT |
| `references/cases/CHANGE.md` | эталон полного цикла CHANGE |
| `references/operational-pitfalls.md` | полный процедурный слой и длинные питфоллы из этого скилла |
| `references/context.md` | контекст, MUST-read, emit-prompt |
| `references/invoke.md` | backends, outer boundary, provider fatal, recovery |
| `references/cursor-cli-notes.md` | cursor-cli |
| `references/rollback.md` | W0–W4 и откат |
| `references/install.md` | установка и post-update check |
| `references/handoff.md` | перенос живого слага |
| `references/onboarding.md` | инструкция заказчику |
| `references/config.example.yaml` | `tools.dev_workflow` |
| `references/kanban-mechanics.md` | остаток канбан-механики |
| `references/storage-and-archival.md` | хранение ТЗ и три контура бэкапа |
| `references/dual_path_banner.md` | эталон dual-path баннера |

Комплект нового хоста: `README.md` → `install.md` → `onboarding.md`.
