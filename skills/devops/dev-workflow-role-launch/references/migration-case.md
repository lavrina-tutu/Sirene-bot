# MIGRATION-кейс dev-workflow (свежий инстанс/переезд) — правила на старте ТЗ

Тема: запуск dev-workflow-поезда на свежем MIGRATION-слаге (новый инстанс Hermes, переезд на другой машину/ОС). Уроки кейса `klon-germes-agenta-na-windows-mashinu`.

## Обязательный скелет master-ТЗ на старте

Свежий MIGRATION-кейс не имеет master-ТЗ, и `emit-prompt` БЕЗ `--master-tz` падает `master binding required; DevWorkflow fallback is forbidden` (exit 2, файл не создан). Порядок на старте TZ:patch:

1. Создать скелет `TZ/<Имя>/<Имя>_TZ.md` заранее: frontmatter (`tool`, `type`, `version: 0.1.0`, `status: draft`, `case`), поле `precedent` со ссылкой на прошлый аналог того же класса (напр. MigrationToVM/TZ.md), `reuse_first` с запретами и границами. Это заготовка-привязка, не содержание.
2. `emit-prompt --phase TZ:patch --master-tz <этот мастер> --out …` — проходит, `st.tz_path/tz_version` проставляются из скелета.
3. Архитектор в TZ:patch пишет полное ТЗ и поднимает `version:` (0.1.0 → 0.2.0). Легальный бамп, но `st.tz_version` остался на старом → `check`/`G1 fail: tz version drift` перед complete.

## Лечение дрейфа версии в MIGRATION — повторный emit, НЕ ручный writer

В MIGRATION не нужен refresh_producer/manual `pipeline_state.write_state` (это путь компрессорных CHANGE/DEV с extract). Повторный `emit-prompt --phase TZ:patch --master-tz <файл>` перечитывает `version:` из master на диске и сам обновляет `st.tz_version`/`st.tz_mtime`/`st.tz_path`. После повторного emit `check` чист (нет вывода = ok), и только тогда `complete-phase`. Статус/пид фазы при этом не сбрасываются (фаза уже `doing`/`done` — повторный emit НЕ перезаписывает вердикт).

В CHANGE/DEV (компрессорные) дрейф лечится refresh_producer/manual writer по `^version:\s*([^\n]+)` — см. body SKILL.md; это два разных контура, не подменять.

## `outputs`/`write_scope` handoff-contract — список, не одиночный dict

`TZ:patch:
  - {kind: canonical, path: '<абс>', required: true}` (yaml-список), а НЕ `TZ:patch: {kind:…, path:…}` — одиночный dict даёт `invalid OutputRef`, emit не запускается. То же для всех фаз с outputs. Схема outputs прогоняется по списку, dict трактуется как итерируемый по ключам → ValueError.

## Ревью ревизора в MIGRATION нет в рецепте — вызывается НЕ pipeline-фазой

Рецепт MIGRATION не содержит REV:tz/REV:plan (в отличие от CHANGE/DEV): `next` идёт TZ:finalize → GATE:take-into-work → MIG:plan без штатной ревизии. Если владелец требует ревизию ревизора (обычное требование для переезда), НЕ пытайся `emit-prompt --phase REV:tz` (упадёт `phase is not in recipe: REV:tz`) и НЕ `invoke-role --role reviewer` по этому пакету (`…packet.json` не создан, т.к. emit не прошёл) — это не баг запуска, а отсутствие фазы в рецепте. Рабочий путь — независимая проверка ВНЕ pipeline: собрать промпт ревизору (постановка владельца verbatim + master-ТЗ путь/SHA-256 + бриф + пункты проверки + формат вердикта), запустить reviewer-модель напрямую из YAML (`tools.dev_workflow.roles.reviewer`, на этой машине gpt-6-astra) через `codex exec`, вердикт ревизор пишет в `dev/<slug>/evidence/REV-tz.md` + указатель `dev/<slug>/REV-tz.md`. Требование вердикта закрывается фактом файла в evidence (архитектор сам помечает REV как незакрытый F-02), а не receipt-фазы pipeline. Зафиксировать требование «план прошёл ревизию ревизора» в brief/постановке ЕЩЁ до запуска поезда.

## MIG:plan требует AC-list.md — создать ДО emit

`emit-prompt --phase MIG:plan` падает `required input missing: …/AC-list.md`, если файла нет. Создать `dev/<slug>/AC-list.md` со списком AC из master-ТЗ (таблица Б34, для MIGRATION AC-001…NN) ДО emit MIG:plan; затем emit + invoke architect. План обязан связать каждый AC с IAC/блоком/командой проверки.

## codex exec флаги для ревизора и ролей вне pipeline

- Эта сборка codex exec НЕ знает `--output-format`/`-f` (rc=2 `unexpected argument`; `-f` конфликтует с short-flag output-format).
- Для детерминированного вывода использовать `--json` (признак валидности — `"text"` + `turn.completed`), либо отдавать промпт аргументом/stdin без output-flag.
- Записывающей role на изолированной headless-ВМ: `codex exec -m <model> -c shell_environment_policy.inherit=all --sandbox danger-full-access --dangerously-bypass-approvals-and-sandbox "<промпт из файла>"`. Итог проверять по записанному файлу (REV-tz.md), не по stdout.

## Проектные решения владельца по способу развёртывания — фиксировать в brief сразу

Когда владелец задаёт способ установки (native Windows vs WSL/виртуализация) и это меняет core-решение, архитектор может заложить один вариант (например WSL) как базовый. Если владелец позже это отменяет, зафиксировать правку в brief как ДИРЕКТИВУ владельца verbatim + обязательные следствия (заменить базовый вариант, добавить пункт адаптации скиллов/инструментов под целевой ОС в ТЗ), затем пере-emit TZ:patch и заново invoke architect на переработку master — НЕ продолжать поезд как будто ТЗ не изменилось. ТЗ в draft до ревизии — это правка master, не открытие новой фазы.
