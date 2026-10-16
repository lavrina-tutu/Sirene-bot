---
version: 1.0.0
---

## Пофайловый план TaskRefresh v2.2 (batch + quiet)

Основание: `TaskRefresh_TZ.md` §23. Реализует: `./tr batch` (§23.2, §23.4, §23.5),
`--quiet` для `do` (§23.3), 7 тест-кейсов (§23.6), обновление `SKILL.md` (§23.9).
Ничего из §23.7 не трогаем.

---

### 1. `taskrefresh/pipeline.py`

**Не менять:** `run_apply`, `run_apply_confirmed`, `_verify_applied`, `run_read`,
`run_mine`, `run_show`, `_extract_numbers_from_cmd` — используются как есть/переиспользуются.

**Рефакторинг перед добавлением batch (без изменения поведения):**
- Вынести проверку `<a href>` из `run_do` в отдельный приватный хелпер
  `_check_href_guard(session, numbers_str) -> str | None` (возвращает текст WARN или
  `None`). `run_do` продолжает вызывать его как раньше — нужно, чтобы `run_batch`
  переиспользовал ту же проверку для КАЖДОЙ команды без копипасты regex.
  Сигнатура намеренно принимает `numbers_str` (не всю команду) — `run_batch` уже имеет
  парсер `_extract_numbers_from_cmd(cmd)`.

**Новые функции:**

1. `_parse_commands_from_file(path: str) -> list[str]`
   - Читает файл, по одной команде на строку.
   - Пропускает пустые строки и строки, начинающиеся с `#` (комментарии).
   - Файл не найден → `FileNotFoundError` пробрасывается наверх (CLI её ловит и печатает
     понятную ошибку — см. п.2 `__main__.py`).

2. `run_batch(commands: list[str], *, dry_run: bool = False, quiet: bool = False, no_mine: bool = False, verify: bool = True, client=None, today=None) -> str`
   - Пустой `commands` → сразу `"batch: нет команд для выполнения."` (§23.6 TC-6), без
     авто-mine и без обращения к сессии.
   - Шаг 1 (авто-mine, как в `run_do`): если `not no_mine` и сессия пуста/stale —
     `run_mine(client=client, today=today)`.
   - Перечитать сессию (`load_session()`) один раз после mine.
   - Для каждой команды `cmd` в `commands`:
     - `numbers_str, _ = _extract_numbers_from_cmd(cmd)`.
     - Если `numbers_str` не None — прогнать `_check_href_guard(session, numbers_str)`.
       Если вернулся WARN — добавить в `skipped: list[tuple[str, str]]` (команда, причина),
       перейти к следующей команде (эта задача НЕ попадает в specs, §23.6 TC-4).
     - `parse_change_command(cmd, session, today=today)` → specs для этой команды.
       Обернуть в `try/except ValueError` — при ошибке парсинга добавить в `skipped` с
       текстом ошибки, продолжить со следующей командой (не валить весь batch из-за одной
       опечатки — согласуется с духом "K ошибок" в quiet-выводе §23.2).
     - Накопить specs в общий `all_specs: list[ChangeSpec]`.
   - Если `all_specs` пуст (все команды пропущены/ошибочны) — вернуть отчёт со списком
     `skipped` и не идти дальше (ни apply, ни dry-run записи).
   - Ветка `dry_run=True`:
     - Записать `all_specs` в `PENDING_APPLY_PATH` целиком, одним JSON-массивом (тот же
       формат, что и `run_apply` пишет для одной команды — список dict через `s.__dict__`).
       Это НЕ накопление через дозапись файла, а построение объединённого списка в памяти
       и одна запись — так проще соблюсти "формат pending_apply.json обратно совместим"
       (§23.7) без риска дублирования при повторных вызовах.
     - Вернуть `format_change_preview(all_specs)` (+ пропущенные команды, если есть) —
       без реального apply. Ждёт последующего `./tr confirm`.
   - Ветка `dry_run=False`:
     - `report = apply_changes(client or _make_confluence_client(), all_specs)`.
     - `verify_lines = _verify_applied(client, report, all_specs) if verify else []`.
     - Сформировать полный (verbose) и quiet варианты отчёта (см. ниже) и вернуть один
       по флагу `quiet`.
   - **Формат вывода (не quiet):** краткий preview по каждой обработанной команде
     (переиспользовать `format_change_preview` на подмножестве specs команды, ИЛИ проще —
     на всех `all_specs` целиком одним блоком) + агрегированный отчёт `apply_changes`
     (как в `run_apply_confirmed`, тот же построчный формат `task {id} (page {page}): status`)
     + строки верификации + список `skipped`, если есть.
   - **Формат вывода (`quiet=True`)** — ровно одна строка (§23.2, §23.6 TC-3):
     - `f"batch: {len(commands)} команд, {len(all_specs)} задач, ok"` — если нет ошибок
       apply/verify и `skipped` пуст.
     - `f"batch: {len(commands)} команд, {len(all_specs)} задач, {K} ошибок"` — где `K` =
       `len(skipped)` + количество specs с `report.results[...].status not in ("ok", "partial_no_mention")`
       + количество непустых строк в `verify_lines` с `⚠️`.
     - В dry-run + quiet: `f"batch: {len(commands)} команд, {len(all_specs)} задач, dry-run"`.
   - Считать K в отдельном приватном хелпере `_count_batch_problems(report, verify_lines, skipped) -> int`,
     чтобы не размножать логику подсчёта между verbose/quiet веткой.

**Изменение сигнатур `run_do`:** добавить keyword-only `quiet: bool = False`.
   - При `quiet=True` итоговый возврат (после apply+confirm) свернуть в одну строку:
     `f"do: #{numbers_str or '?'} ok"` при отсутствии ошибок в `report`/verify, иначе
     `f"do: #{numbers_str or '?'} ошибка — {первая_проблема}"`.
   - `mine_info` при `quiet=True` НЕ печатается отдельно (остаётся частью текущего
     tuple-возврата `(mine_info, report)`, но CLI для quiet-режима печатает только report
     — см. `__main__.py`). Проще: пусть `run_do` сама решает, что вернуть во второй
     элемент тюпла, а `mine_info` при `quiet=True` возвращает `""`, чтобы CLI ничего не
     печатал сверху.
   - WARN-ветка (`<a href>`) при `quiet=True`: вернуть `(mine_info, f"do: #{n} ошибка — <a href> в теле, do остановлен")`
     вместо полного текста WARN.

---

### 2. `taskrefresh/__main__.py`

**Не менять:** subparsers `read`, `mine`, `apply`, `confirm`, `show` — без изменений.

**Изменить `_cmd_do`:**
- Добавить `quiet=args.quiet` в вызов `run_do(...)`.
- Убрать безусловный `print(mine_info)` — печатать `mine_info` только если она непустая
  (текущее поведение уже такое — `if mine_info: print(mine_info)` — оставить, `run_do`
  сама гарантирует `mine_info == ""` при `quiet=True`).

**Добавить `--quiet` в `p_do`:**
```python
p_do.add_argument("--quiet", action="store_true", help="одна строка вывода вместо полного preview+confirm")
```

**Новая функция `_cmd_batch(args: argparse.Namespace) -> int`:**
```python
def _cmd_batch(args: argparse.Namespace) -> int:
    commands = list(args.commands)
    if args.from_file:
        from .pipeline import _parse_commands_from_file
        try:
            commands = commands + _parse_commands_from_file(args.from_file)
        except FileNotFoundError:
            print(f"Файл не найден: {args.from_file}")
            return 1
    print(run_batch(
        commands,
        dry_run=args.dry_run,
        quiet=args.quiet,
        no_mine=args.no_mine,
    ))
    return 0
```
- Импортировать `run_batch` в строку `from .pipeline import ...` наверху файла.
- `commands` из `--from-file` ДОБАВЛЯЮТСЯ к позиционным (позволяет комбинировать —
  не требуется ТЗ явно, но не противоречит; если нежелательно — заменить `+` на
  использование только файла, если он указан, и печатать warning при одновременном
  указании обоих. Выбрать более простой вариант: если `--from-file` задан —
  позиционные `commands` игнорируются с предупреждением в stderr).

**Новый subparser `batch`:**
```python
p_batch = sub.add_parser(
    "batch",
    help="один mine + одна apply + один confirm на N команд (экономия токенов, v2.2)",
)
p_batch.add_argument("commands", nargs="*", metavar="command", help='напр. "#3 закрыть" "#5 дедлайн 10.08"')
p_batch.add_argument("--dry-run", action="store_true", help="показать preview всех изменений без применения")
p_batch.add_argument("--quiet", action="store_true", help="только агрегированный итог (одна строка)")
p_batch.add_argument("--from-file", default=None, metavar="PATH", help="читать команды из файла, по одной на строку")
p_batch.add_argument("--no-mine", action="store_true", help="не делать авто-mine")
p_batch.set_defaults(func=_cmd_batch)
```
- Разместить после `p_do` (порядок в help — логичное продолжение).

---

### 3. `taskrefresh/formatter.py`

**Не менять:** `format_brief`, `order_tasks_for_display`.

**`format_change_preview`** — оставить как есть, переиспользуется без изменений
(принимает произвольный список specs, для batch просто передаём объединённый список).
Никаких новых функций здесь не требуется — batch-специфичное форматирование (quiet-строка,
список `skipped`) держим внутри `pipeline.run_batch`, а не в `formatter.py`, т.к. оно
завязано на `ApplyReport`/`skipped`, которых `formatter` сегодня не знает. Если по ходу
реализации понадобится третья форматирующая функция — добавить `format_batch_summary(...)`
сюда, но по умолчанию план держит логику в `pipeline.py` рядом с `run_batch`.

---

### 4. `taskrefresh/change_spec.py`, `taskrefresh/write_ops.py`, `taskrefresh/session_store.py`

**Не менять.** `parse_change_command`, `apply_changes`, `Session`/`load_session`/`save_session`
используются batch без модификаций (§23.7). `run_batch` вызывает `parse_change_command`
в цикле по командам и склеивает результаты сама — правка самого парсера не нужна.

---

### 5. Тесты — новый файл `tests/test_batch.py`

Создать по образцу `tests/test_multi_apply.py` (те же фикстуры `_task`, `_Session`,
`FakeConfluenceClient`/mocks, что уже используются в `test_pipeline_e2e.py` — свериться
и переиспользовать существующие фикстуры из `tests/conftest.py`, если там есть общий
`FakeConfluenceClient`).

7 тест-кейсов из §23.6 (нумерация TC-1..TC-7):

1. **TC-1** `test_batch_three_commands_all_applied` — 3 команды на разные `#N`,
   мокнутый client, `run_batch([...], verify=True)` → все specs применены, один вызов
   `apply_changes` (проверить через `MagicMock`/spy, что `client.get_page`/`update_page`
   вызван по числу уникальных страниц, а не по числу команд), отчёт содержит все task_id.
2. **TC-2** `test_batch_dry_run_writes_pending_no_apply` — `dry_run=True` →
   `PENDING_APPLY_PATH` содержит JSON-массив со всеми specs всех команд; `client.update_page`
   (или эквивалент записи) НЕ вызван ни разу.
3. **TC-3** `test_batch_quiet_single_line` — `quiet=True` → результат — ровно одна строка
   (`"\n" not in result` либо `len(result.splitlines()) == 1`), содержит `"batch:"`.
4. **TC-4** `test_batch_href_task_skipped_others_applied` — одна из N команд адресует
   задачу с `text_storage` содержащим `<a href`; результат содержит WARN про эту задачу,
   `apply_changes` вызван только для specs остальных команд (проверить, что task_id
   href-задачи отсутствует в применённых).
5. **TC-5** `test_batch_from_file` — через `tmp_path` создать файл с командами (включая
   пустые строки и строку с `#comment`), вызвать `_parse_commands_from_file(path)` напрямую
   → список команд без пустых/комментариев; отдельно — `run_batch` с этим списком работает
   как TC-1.
6. **TC-6** `test_batch_empty_commands_list` — `run_batch([])` → строка с "нет команд"/
   warning, `apply_changes` не вызван, сессия/pending_apply не тронуты.
7. **TC-7** `test_do_quiet_single_line` — в `test_multi_apply.py` ИЛИ новом файле:
   `run_do(cmd, quiet=True, ...)` → второй элемент тюпла — одна строка `"do: #N ok"`.
   (Разместить в `test_batch.py` для группировки v2.2-тестов, либо дописать в
   `test_multi_apply.py` рядом с существующими TC do — выбрать `test_batch.py`, чтобы не
   трогать существующий проверенный файл.)

Дополнительно (не из явного списка §23.6, но требуется для покрытия рефакторинга):
- `test_href_guard_helper_matches_run_do_behavior` — сверка, что вынесенный
  `_check_href_guard` даёт тот же результат, что раньше давал инлайн-код в `run_do`
  (регресс-защита рефакторинга из п.1).

**Не трогать:** `test_multi_apply.py`, `test_pipeline_e2e.py`, `test_change_spec.py`,
`test_write_ops.py`, `test_session_store.py`, `test_formatter.py` — если рефакторинг
`run_do` не изменил наблюдаемое поведение, эти файлы обязаны остаться зелёными без правок.

---

### 6. `~/.hermes/skills/.../taskrefresh/SKILL.md` (§23.9)

Найти актуальный путь скилла (`find ~/.hermes/skills ~/hermes-workspace/skills -iname "SKILL.md" -path "*taskrefresh*"`)
и применить правки §23.9 D1–D3 из ТЗ:
- **D1**: дописать в конец `description` (frontmatter) фразу про batch/`--quiet`
  (текст уже зафиксирован в ТЗ — копировать буквально).
- **D2**: в разделе `## Команда (...)` после строки про `./tr do` добавить 5 строк
  с примерами `./tr batch ...` (текст из ТЗ).
- **D3**: добавить новый раздел `## Batch-режим (v2.2) — когда использовать` перед
  `## Что уже решено кодом...` (текст из ТЗ, там markdown обрезан в выдержке — прочитать
  полный текст §23.9 D3 в `TaskRefresh_TZ.md` до конца перед копированием).
- Обновить версию скилла (frontmatter `version:`) на `2.2.0`.
- После правок — прогнать `restore-all-skills.sh` для синка между профилями (правило
  workspace: "После изменений скиллов → restore-all-skills.sh").

---

### 7. Точки промежуточной проверки

1. **После п.1 (pipeline.py, рефакторинг href-guard):** прогнать весь `pytest tests/`
   (112 тестов) — должны остаться зелёными без единой правки в самих тестах. Это
   проверка, что вынос `_check_href_guard` не изменил поведение `run_do`.
2. **После п.1 (добавление `run_batch`, `run_do(quiet=...)`) + п.4 не трогали:**
   написать и прогнать `tests/test_batch.py` изолированно (`pytest tests/test_batch.py -v`),
   добиться зелёных TC-1..TC-7 + доп. регресс-теста href_guard.
3. **После п.2 (`__main__.py`):** ручной smoke через CLI с фейковым/мок-client не
   возможен напрямую (реальный `_make_confluence_client()`) — ограничиться:
   `python -m taskrefresh batch --help` и `python -m taskrefresh do --help` — проверить,
   что `--quiet`, `--dry-run`, `--from-file`, `--no-mine` отображаются корректно, argparse
   не падает на пустых `commands`.
4. **Полный прогон:** `pytest tests/` — весь набор (112 старых + новые из test_batch.py)
   зелёный. Зафиксировать итоговое число тестов в отчёте о реализации.
5. **Smoke на живом Confluence (§23.8, ручной шаг, не автоматизируется в этом плане):**
   `./tr mine` → `./tr batch "#N1 ..." "#N2 ..." "#N3 ..." --dry-run` → визуально свериться
   с превью → `./tr confirm` → проверить страницы Confluence вручную. Затем отдельно
   `./tr batch "..." --quiet` на 2–3 безопасных задачах и `./tr do "..." --quiet` —
   свериться, что вывод действительно однострочный.
6. **После п.6 (SKILL.md):** визуально сверить итоговый файл с §23.9 D1–D3 ТЗ построчно,
   затем `restore-all-skills.sh`.

---

### Порядок реализации (сводка)

1. `pipeline.py`: `_check_href_guard` (рефакторинг) → прогон 112 тестов.
2. `pipeline.py`: `_parse_commands_from_file`, `run_batch`, `run_do(quiet=...)`.
3. `tests/test_batch.py`: TC-1..TC-7 + регресс href_guard.
4. `__main__.py`: `--quiet` в `do`, subparser `batch`, `_cmd_batch`.
5. Полный прогон `pytest tests/`.
6. `SKILL.md` v2.2.0 (D1–D3) + `restore-all-skills.sh`.
7. Ручной smoke на живом Confluence (§23.8).
