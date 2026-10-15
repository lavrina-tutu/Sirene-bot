---
type: tz
title: TzDevDecommission
version: 0.1.0
updated: 2026-08-13
---

# TzDevDecommission — отказ от профиля tz-dev

## Цель

Полностью заменить профиль `tz-dev` («Стажер») профилем `default` («Сирень») в роли ведущего dev-работу (ТЗ/скиллы/инструменты Hermes) по тем же правилам, без переноса файлов скиллов (они уже общие).

## Что меняем

Атомарно, по файлам:

1. `~/.hermes/SOUL.md`, строка 3 — убрать «передаю в профиль tz-dev (Стажеру)», заменить на явное указание, что Сирень сама ведёт dev-работу (ТЗ/скиллы/код/баги Hermes) в топике HermesDEV.
2. `~/WorkVault/Hermes-Backlog/TZ/AGENTS.md`, строка 3 — «Profile tz-dev (Стажер) handles TZ, skills, and Hermes tools dev.» → «Profile default (Сирень) handles TZ, skills, and Hermes tools dev.»
3. `~/.hermes/skills/devops/hermes-feature/SKILL.md`, строка 20 — «Архитектор tz-dev НЕ пишет…» / «Текущий агент tz-dev координирует…» → заменить `tz-dev` на `default`/«Сирень» в обоих упоминаниях.
4. `~/.hermes/skills/devops/hermes-feature/references/hermes-upgrade-pattern.md`, строки 11, 52, 71 — заменить пути/команды с `tz-dev` на `default`: `~/.hermes/profiles/default/config.yaml`; `profiles/default/` в списке содержимого бэкапа; `hermes -p default doctor --fix`.
5. `~/.hermes/skills/devops/hermes-feature/references/movefromloop-v042-pitfalls.md`, строка 27 — «а не из tz-dev/.env» → «а не из default/.env» (историческая пометка, факт про старую ошибку не меняется, меняется только актуальное имя профиля-эталона).
6. Скилл `tz-workflow` — без правок (упоминаний `tz-dev`/«Стажер» нет, «архитектор» используется как роль-модель, не профиль). Зафиксировано, действие не требуется.
7. `~/.hermes/memories/MEMORY.md`, строка 15 — запись «Профиль tz-dev: персонаж переименован из «Архитектор» в «Стажер»…» устарела, заменить на факт декомиссии tz-dev (дата, что заменён на default).
8. `~/.hermes/profiles/tz-dev/` — **удалить полностью** (решение закрыто, см. «Открытые вопросы», п. 2). Порядок: (1) бэкап `config.yaml` в `~/.hermes/_Archives/hermes-backup-YYYYMMDD-HHMMSS/`; (2) `rm -rf ~/.hermes/profiles/tz-dev/`.
9. `~/.hermes/skills/devops/tz-workflow/SKILL.md` (паттерн вызова Cursor CLI) и `~/.hermes/skills/devops/hermes-feature/SKILL.md` (паттерн вызова Cursor CLI) — явно зафиксировать рабочую директорию для Cursor: добавить `cd ~/WorkVault/Hermes-Backlog/TZ &&` перед `agent -p ...` в примере команды. Это не механизм разделения dev/не-dev задач (это уже делают триггерные слова скиллов), а техническое уточнение, чтобы Cursor CLI детерминированно видел `TZ/AGENTS.md` при dev-задачах.

## Что НЕ трогать

- Роли «архитектор/исполнитель/координатор» как модели Cursor CLI (`claude-sonnet-5-thinking-*`, `composer-2.5`, `gemini-3.6-flash-low`) — не привязаны к профилю, остаются как есть.
- Профили `anthropic`, `openai`.
- Инструменты USERTOOLS и их ТЗ в `MAIN_TZ_INVENTORY.md` (не обновлять в рамках этой задачи).
- Gateway — не рестартовать.
- Файлы скиллов `tz-workflow`, `hermes-feature` не перемещать (уже в общем `~/.hermes/skills/devops/`).

## Критерии успеха

- `grep -rn "tz-dev" ~/.hermes/SOUL.md ~/WorkVault/Hermes-Backlog/TZ/AGENTS.md ~/.hermes/skills/devops/hermes-feature/` — 0 совпадений.
- `~/.hermes/memories/MEMORY.md` не содержит устаревшей записи про переименование в «Стажер» без пометки о декомиссии.
- Профиль `default` при вызове Cursor CLI с рабочей директорией `TZ/` видит `TZ/AGENTS.md` и корректно ведёт dev-работу; разделение dev/не-dev задач обеспечивается триггерными словами скиллов `tz-workflow`/`hermes-feature`, а не механизмом профиля.
- `~/.hermes/profiles/tz-dev/` не существует на диске (`ls ~/.hermes/profiles/` не содержит `tz-dev`); бэкап `config.yaml` присутствует в `~/.hermes/_Archives/hermes-backup-YYYYMMDD-HHMMSS/`.
- `grep -rn "tz-dev" ~/.hermes/config.yaml` — 0 совпадений (профиль не зарегистрирован как активный).
- Без регулярных кронов, привязанных к `tz-dev` (подтверждено — все 6 задач в `cron/jobs.json` одноразовые и отработавшие).
- `MAIN_TZ_INVENTORY.md` НЕ изменён в рамках этой задачи.

## Связи с экосистемой

- Скиллы `tz-workflow`, `hermes-feature` — общие, изменения затрагивают только упоминания профиля, не логику процесса.
- `TZ/AGENTS.md` (контекст для dev-задач) продолжает существовать как файл, меняется только владелец-профиль.
- Не влияет на активные ТЗ инструментов (MoveFromFF, ProtocolFromSummary и др.) — они ведутся тем же процессом, только под другим профилем-исполнителем.

## Открытые вопросы

1. **Подгрузка dev-контекста `TZ/AGENTS.md` для Сирени — РЕШЕНО.** Отдельный механизм не нужен. Разделение dev/не-dev задач уже обеспечивается триггерными словами скиллов `tz-workflow` и `hermes-feature` (см. `~/AGENTS.md`, раздел «Маршрутизация dev-задач») — это логический уровень разделения, не связанный с профилем. Working dir `TZ/` при вызове Cursor CLI — техническая механика (как Cursor подхватывает `TZ/AGENTS.md`), а не механизм разделения задач. Решено явно зафиксировать `TZ/` как рабочую директорию в паттернах вызова Cursor внутри скиллов `tz-workflow`/`hermes-feature` (см. «Что меняем», п. 9) — для детерминизма, а не как признак «dev-режима».
2. **Судьба `~/.hermes/profiles/tz-dev/` — РЕШЕНО.** Удалить полностью. Обоснование: профиль не используется (все связанные кроны одноразовые и отработавшие), история не требуется как «живой» профиль — достаточно бэкапа. Перед удалением — бэкап `config.yaml` в `~/.hermes/_Archives/hermes-backup-YYYYMMDD-HHMMSS/` (см. «Что меняем», п. 8).
3. **Формулировка записи в `MEMORY.md` про декомиссию — УТВЕРЖДЕНО Сашей (13.08.2026).** Предлагаемый текст (1-2 строки, дата + факт + замена):

   > 2026-08-13: Профиль `tz-dev` («Стажер») выведен из эксплуатации (удалён, бэкап `config.yaml` в `_Archives/hermes-backup-20260813-*`). Dev-работу (ТЗ/скиллы/инструменты Hermes) теперь ведёт профиль `default` («Сирень»).

   Заменяет устаревшую запись про переименование «Архитектор» → «Стажер» (строка 15). Текст утверждён, применяется на этапе реализации (hermes-feature).
