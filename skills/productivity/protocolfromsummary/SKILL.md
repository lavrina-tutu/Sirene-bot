---
name: protocolfromsummary
description: "Use when working with the ProtocolFromSummary (PFS) tool — publishes Fireflies meeting-summary .md files into Confluence protocol tables (~/USERTOOLS/ProtocolFromSummary). Триггеры: PFS, протокол встречи, опубликовать протокол, задача не резолвится/не мешенится, ROUTES, page_layout, republish, страница протокола поменялась, out_of_scope встречи, роутинг крона PFS."
version: 1.0.0
author: agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [TUTU, ProtocolFromSummary, PFS, Confluence, Fireflies, WorkVault, protocol]
    related_skills: [tutu-confluence-jira, obsidian, hermes-feature]
---

# ProtocolFromSummary (PFS)

Publishes parsed Fireflies meeting `.md` summaries from `WorkVault/Meetings/NewMeetings/` into
per-project protocol tables on Confluence (dom.tutu.ru). Code lives at
`~/USERTOOLS/ProtocolFromSummary/protocolfromsummary/`, venv at
`~/USERTOOLS/ProtocolFromSummary/.venv`.

## Architecture (read before touching anything)

- **`config.py` → `ROUTES` dict** — pageId → {tag, kind, name_match, page_layout?}. This is the
  single source of truth for "which Confluence page does meeting X's protocol go to, with what
  tag prefix, and what table shape". `kind` ∈ {project, one_on_one, multisync, sync_aid, unknown}.
- **`route.py`** — matches `meeting_name`/participants against `ROUTES[*].name_match` (+ a few
  hardcoded exceptions like Саша+Аралов → aralov_1on1, or department-fallback routing).
- **`summary_parser.py`** — parses the `.md` summary into `MeetingSummary`/`MeetingTask`. UTC→MSK
  conversion happens here (filenames from Fireflies are UTC). `split_assignees()` splits a raw
  assignee string on "и"/commas into individual names (see Pitfall 1).
- **`contacts_resolver.py`** — ФИО string → Confluence userkey via `contacts.enc` + Confluence API
  fallback (`find_user_by_fullname`). Handles "Фамилия И.О." shorthand, ambiguous-surname
  disambiguation, DEFAULT_ASSIGNEE_LOGIN fallback for true ties.
- **`storage_xml.py` → `render_row()`** — builds the `<tr>` storage-XML fragment for one meeting
  row. `layout` param selects `2col` (default) / `5col_aid` / `3col_content_last`, must match the
  REAL column count of the target Confluence table (see Pitfall 2).
- **`page_merger.py`** — GET page → parse existing `<table>` → insert/replace row by
  `row_anchor` (stable anchor-macro survives PUT/GET, invisible in render) or `task_id` fallback →
  chronological insertion. `count_header_columns()` is a sanity-check helper (see Pitfall 2).
- **`pipeline.py` → `run_pilot()`** — orchestrates the whole flow: parse → route → resolve
  participants/assignees → render row → GET page → merge → (dry_run ? stop : PUT).

## Standard operating pattern

1. **Never apply changes without explicit imperative.** No patches, no republishes, no config edits — only after Саша says «делай», «сделай», «создай» or explicitly confirms. Questions/note → text only, no tool-calls that modify state.
2. **Always `dry_run=True` first**, inspect `result.row_xml`, THEN `dry_run=False`. Never go
   straight to a live write when debugging or after a code change.
3. For a meeting already published, republish requires `confirm_republish=True` (otherwise
   `skipped_duplicate`). Republish reuses the existing `row_anchor`/task-ids — it replaces the
   row in place, it does not duplicate it.
4. After any live write, **GET the page back and grep the relevant fragment** to confirm the real
   HTML — don't trust `result.action == "published"` alone as proof of correctness.
5. Run the offline suite before and after any code change:
   `cd ~/USERTOOLS/ProtocolFromSummary && source .venv/bin/activate && python3 -m pytest -q -m "not live_confluence"`.
   `-m live_confluence` tests hit real Confluence pages — don't run those casually.

## Pitfalls

1. **Multiple assignees in one task line ("Иванов И. и Петров П.: ...") silently fail to
   resolve.** `pipeline.py` used to pass the WHOLE `assignee_raw` string to
   `resolve_participants()` as a single candidate — no such contact exists, so the entire task
   stayed as unlinked text even though each name resolves fine individually. Fix: split first via
   `summary_parser.split_assignees()` (handles "и" and comma separators), resolve each name
   separately, then render as multiple `ac:link` mentions joined by `, ` in one task line
   (`storage_xml._task_body()` accepts either a single `ResolvedParticipant` or a `list[...]`).
   Room-redirect logic (meeting-room "assignee" → DEFAULT_ASSIGNEE_LOGIN) now also handles the
   mixed case (some assignees are rooms, some are people). See
   `references/multi-assignee-fix-2026-07-15.md` for the full before/after and test names.
   Инцидент с массовой публикацией из-за aliases и рецепт восстановления: `references/historical-guard-incident-20260722.md`.
2. **`page_layout` in `ROUTES` can silently drift from the REAL Confluence table structure** — the
   user sometimes manually edits a protocol page's table (adds/removes a column) without telling
   the tool. A stale `page_layout` will render the wrong number of `<td>` cells and corrupt the
   table. `pipeline.py` now calls `page_merger.count_header_columns()` on every run and logs a
   loud WARNING (not a hard-stop — publication still proceeds) if the live `<th>` count doesn't
   match what the configured layout expects (`2col`→2, `5col_aid`→5, `3col_content_last`→3). If
   you see this warning: GET the page, look at the real `<th>` row, and update (or remove) the
   `page_layout`/`content_column_index` override in `config.py` to match — don't just silence the
   warning. Concrete precedent: `ai_analitik` (pageId 477061038) was hardcoded to
   `3col_content_last` after a one-off BUG-1 fix; the user later reverted the page to the default
   2-column shape and the override became stale until this session caught and removed it.
3. **Contacts resolution is substring-based** (`store.find_contacts(query)` matches `query` as a
   substring of `fio`/login) — a bare "Ткаченко" without initials is ambiguous between namesakes;
   `contacts_resolver` disambiguates via `DEFAULT_ASSIGNEE_LOGIN` fallback only when it's among
   the ambiguous candidates, otherwise leaves it as unresolved text. "Фамилия И.О." shorthand
   (Fireflies' typical format) is handled by a dedicated regex path BEFORE the substring search,
   because "Ткаченко А.В." is not literally a substring of "Ткаченко Александр Владимирович".
4. **`row_anchor`** is an invisible `ac:structured-macro name="anchor"` embedded in the date cell
   — Confluence's storage sanitizer strips plain HTML comments/data-attributes on PUT, but the
   anchor macro survives. This is the only reliable way to find "this meeting's row" again on
   republish; task-id-based lookup is the fallback for rows published before this mechanism
   existed.

5. **`out_of_scope` for all meetings is expected during pilot phase** — the PFS batch cron
   (`a6e62d06249f`) only covers two entities (Trisigma + Кирилл 1-1 per §3 of the TZ). Everything
   else correctly falls through to `out_of_scope`. A report of "239 files, all out_of_scope" is
   normal, not a bug — it means no new meetings matched the pilot scope.

11. **`KeyError: 'vstrechi_nerazobrannoe'` (и аналогичные) — отсутствие системных fallback-entity в ROUTES** —
    Четыре entity — `vstrechi_nerazobrannoe`, `sink_aid`, `vstrechi_pro`, `aralov_1on1` — это
    **системные fallback-таргеты** `route.py`. Если любой из них отсутствует в `entities.json`
    или присутствует **без блока `pfs`**, `_load_routes_from_registry()` не включает его в ROUTES,
    и `_route_from_entity(slug)` падает с `KeyError` при первой встрече, попавшей в fallback.
    Симптом: краш в `route.py::resolve_route`, шаг 3 (строки 163–169), а не ошибка маршрутизации.
    **Диагностика (быстрая проверка):**
    ```python
    from protocolfromsummary.config import ROUTES
    for key in ["vstrechi_nerazobrannoe", "sink_aid", "vstrechi_pro", "aralov_1on1"]:
        print(key, "→", "OK" if key in ROUTES else "MISSING!")
    ```
    **Фикс:** добавить в `entities.json` отсутствующую сущность с блоком `pfs`.
    Эталонный page_id берётся из `tests/test_entities_registry.py` (строка 74/101):
    - `vstrechi_nerazobrannoe` → page_id `508804852`, kind `unknown`, aliases `[]`
    - `sink_aid` → page_id `331125844`, kind `sync_aid`
    После правки проверить: `pytest tests/test_entities_registry.py -q`.
    См. `references/entities-json-routing-bug-20260728.md` для полного разбора инцидента.

12. **Встреча не резолвится (попадает в fallback) из-за отсутствия `pfs` у entity** —
    Если в `entities.json` у сущности (например, `okr`) есть `aliases`, но нет блока `pfs`,
    `_load_routes_from_registry()` её пропускает (`if not pfs: continue`) — entity не входит
    в ROUTES, name_match не срабатывает, встреча проваливается в fallback (и может упасть с
    KeyError по Питфолу 11).
    **Диагностика:**
    ```python
    from protocolfromsummary.config import ROUTES
    print("okr" in ROUTES)  # False = pfs не задан в entities.json
    ```
    **Фикс:** добавить в `entities.json` блок `pfs` с реальным `page_id` Confluence и тегом:
    ```json
    "pfs": { "page_id": "<CONFLUENCE_PAGE_ID>", "tag": "OKR." }
    ```
    Шаблон: найти нужную страницу в Confluence → взять page_id из URL → добавить в entities.json
    → проверить `test_baseline_invariant_matches_pfs_routes`.

13. **PFS публикует пустую строку если MFF записал Bullet points формат вместо Custom Skill** —
    Fireflies иногда не возвращает Custom AI Skill output для конкретной встречи. Тогда MFF пишет
    `## Bullet points` + `## Notes` вместо `Участники:/Задачи:/Решения:`. `summary_parser.py` не
    находит секций → публикуется пустая строка в Confluence без участников/задач/решений.
    **Диагностика:** если summary содержит `## Bullet points` и нет `Участники:` — Custom Skill не сработал.
    **Фикс — перескачать встречу через MFF:**
    ```bash
    # Найти meeting_id
    python3 -c "
    import json; data = json.load(open('~/WorkVault/Meetings/NewMeetings/_registry_meet.json'))
    for k,v in data.get('meetings',{}).items():
        if '<название>' in v.get('title',''): print('meeting_id:', k)
    "
    # Удалить запись из registry (чтобы MFF перескачал)
    python3 -c "
    import json; path='~/WorkVault/Meetings/NewMeetings/_registry_meet.json'
    data=json.load(open(path)); del data['meetings']['<meeting_id>']
    with open(path,'w') as f: json.dump(data,f,ensure_ascii=False,indent=2)
    "
    rm "~/WorkVault/Meetings/NewMeetings/<filename> - summary.md"
    cd ~/USERTOOLS/MoveFromFF && source ~/USERTOOLS/ProtocolFromSummary/.venv/bin/activate
    python3 -m movefromff --mode manual --meeting-id <meeting_id> --no-tg --verbose
    ```
    После перескачивания — убедиться что появились секции `Участники:`, затем republish через PFS.
    Доработка MFF (retry + TG-уведомление при Bullet points формате) — запланирована в MFF v2.1.

6. **Расширение aliases в entities.json вызывает непреднамеренную массовую публикацию** —
   если добавить новые aliases, ранее невидимые исторические встречи становятся видимыми для
   ROUTES. Если они отсутствуют в реестре (`registry.get = None`), `process_pending` публикует
   их как новые. **Инцидент 22.07.2026**: 42 встречи Sep 2025 – Jun 2026 опубликованы без команды.
   Canary-тест: `test_baseline_invariant_matches_pfs_routes` в `test_entities_registry.py` — если
   он падает после правки aliases, ОСТАНОВИТЬ cron до синхронизации `config.py` ROUTES.
   **Лечение инцидента**:
   1. Бэкап реестра: `cp _registry.json _registry.json.bak-YYYYMMDD-fix`
   2. Пометить пострадавшие записи `"historical_no_reload": true` — атомарно (tmp + os.replace):
      записи где `published_at` начинается с сегодня, а `meeting_id` НЕ начинается с сегодня.
   3. `CUTOVER_DATE` guard (§11.7, Питфол 7) предотвращает повторение.

7. **`CUTOVER_DATE` guard (§11.7) — обязательная защита от исторических публикаций** —
   константа в `pipeline.py`, добавляется сразу после блока импортов из `.config`:
   ```python
   # §11.7 — встречи старше этой даты не публикуются автоматически через run-pending.
   # Обходить через: run-pending --allow-historical или protocol_publish напрямую.
   CUTOVER_DATE = date(2026, 7, 10)
   ```
   В `process_pending` фильтр `pending_new` включает `and s.meeting_date >= CUTOVER_DATE`.
   Плюс логирование: `пропущено N исторических встреч (до YYYY-MM-DD) — historical guard`.
   Проверка: `python -m protocolfromsummary run-pending --dry-run 2>&1 | grep -E 'исторических|пропущено|published'`

8. **Тесты `test_process_pending.py` падают после изменения `CUTOVER_DATE`** — все
   захардкоженные даты фикстур должны быть >= CUTOVER_DATE, иначе guard отфильтрует тестовые
   встречи и тесты упадут. При изменении константы — поднять все даты в тестовых фикстурах
   (`_write_summary` + `RegistryEntry.meeting_date`) до значения >= CUTOVER_DATE.
   Симптом: `AssertionError: assert None is not None` в `test_process_pending_registry_updated_after_publish`.

9. **`risks` поле не рендерилось в протоколах (починено v1.6.1)** — `summary_parser.py` парсит
   `MeetingSummary.risks: list[str]` корректно, но `render_row()` / `_render_row_5col_aid()` /
   `_render_row_ncol_content_at()` не принимали параметр `risks` и не рендерили блок
   `<h2>Риски:</h2>`. Исправлено: добавлен keyword-only параметр `risks: list[str] = []` во все
   три функции, блок рендерится после блокеров, перед задачами. Pipeline передаёт
   `risks=summary.risks`. Если риски снова пропадут — проверить `storage_xml.py::render_row`
   signature и `pipeline.py` call-site.

10. **Дублирование даты задачи в протоколе** — симптом: строка вида
    «Ткаченко /3 августа 2026 3 авг. 2026 г.» означает что Fireflies записал дату прямо в текст
    задачи без разделителя ` / `, и `_parse_task_line` не смог выделить `deadline_raw`. Тогда
    `task.text` содержит строку с датой, а `_task_body()` всё равно добавляет `<time datetime=.../>`.
    Итого — дата в виде текста + дата в виде Confluence-тега.
    **Диагностика:** найти summary-файл встречи, проверить строку задачи — есть ли ` / ` перед датой.
    **Фикс парсера (v1.6.1):** `summary_parser.py` теперь ловит оба варианта через
    `_DEADLINE_SEP_RE = re.compile(r" /\s*")` (модульная константа) — ищет последнее вхождение
    `" /"` с любым количеством пробелов после. `rfind(" / ")` заменён на `finditer + last match`.
    **Фикс для уже опубликованных строк:** переопубликовать встречу через `run --confirm-republish`.

## Dedup module (`dedup.py`)

`dedup.py` implements LLM-backed deduplication of tasks/decisions/blockers/risks against
published history. Key design points:

- **Three LLM paths** — each uses a different JSON field for the duplicate index:
  - `_llm_check_tasks` → `duplicate_of_published_index` in `PROMPT_TASK_DEDUP` results
  - `_llm_check_section` → `duplicate_of_published_index` in `PROMPT_SECTION_DEDUP` results
  - `_check_risks_impl` → `same_as_published_index` (+ `severity_changed` gate) in `PROMPT_RISK_DEDUP` results
- LLM вызывается через `llm_fn` (инъектируется из `pipeline.py::_dedup_llm_fn`, который создаёт
  `openai.OpenAI(base_url="https://llm-gateway.tutu.ru/api/openrouter/v1")` — ТУТУ-шлюз в
  OpenRouter-совместимом формате). Модель/провайдер/усилие вынесены в `config.py` (§16,
  единая точка правки — смена модели не требует изменений в `dedup.py`/`pipeline.py`):
  - `DEDUP_LLM_MODEL` — по умолчанию `deepseek/deepseek-v4-pro` (заменил `claude-haiku-4-5`)
  - `DEDUP_LLM_PROVIDER` — по умолчанию `"default"`: маршрутизацию к апстриму делегируем шлюзу,
    без явного `provider.order`-override
  - `DEDUP_LLM_REASONING_EFFORT` — по умолчанию `"high"`
- **`reasoning` field** is present in all three prompts' JSON schema — the LLM (DeepSeek v4 Pro)
  always returns it as a short one-phrase justification. It's `None`/missing when the model omits
  it (treat as `"нет"`).
- **Fuzzy-first, LLM-second** — tasks/sections first do `SequenceMatcher.ratio() >= 0.80`; only
  misses go to the LLM batch. Risks skip fuzzy entirely (severity-change logic requires semantic
  understanding).

### Adding `log.info` for LLM-detected duplicates

When adding debug/audit logging for LLM-detected duplicates, the standard pattern is:

```python
reasoning = result_item.get("reasoning")   # or extracted from results loop
log.info(
    "dedup: дубль [%s] %r → %r (reasoning: %s)",
    section_ru,          # "задача" / "решение" / "блокер" / "риск"
    new_text[:80],       # truncate to 80 chars
    pub_text[:80],       # truncate to 80 chars
    reasoning or "нет",
)
```

In `_llm_check_tasks` and `_llm_check_section`, `reasoning` requires a **second pass** over
`results` (the first pass only extracts the index). In `_check_risks_impl`, `reasoning` is
available directly from `result_item` (already found in the first loop). When adding the log,
place it BEFORE the `dups.append(...)` call, AFTER resolving `pub_text` from `all_published`.

### Tests for dedup

```bash
cd ~/USERTOOLS/ProtocolFromSummary && source .venv/bin/activate
python -m pytest tests/test_dedup.py tests/test_pipeline_dedup.py -q
```
Expect `36 passed` (as of 2026-07-27). All tests use mock `llm_fn` — no real LLM calls.

## Cron routing rules (17.07.2026)

**Batch cron `a6e62d06249f`** (`deliver=local`):
- `published=0, error=0` → silent, no notification sent.
- `published>0` → also silent; individual notifications are handled by the separate `notify_pending` cron (`21255143c523`) which delivers to WorkVault topic.
- `error>0` → agent sends alert via `hermes send --to "telegram:-1004300127777:5"` with meeting_id(s) and error detail. This is the ONLY case the batch cron actively sends anything.

Do NOT restore `deliver=telegram:400307920` on the batch cron — Саша explicitly requested no routine run reports.

14. **MOFS генерирует `## Секция` без двоеточия — PFS не парсит (28.07.2026)** —
    `summary_parser._find_sections()` ищет заголовки по паттерну `^{name}\b.*:\s*$` — обязательно
    двоеточие в конце. MoveFromFF старый формат: `Участники:` (plain, с двоеточием) — парсится.
    MOFS новый формат: `## Участники` (markdown H2, без двоеточия) — НЕ парсится → PFS публикует
    пустую строку.
    **Диагностика:** `grep "^## Участники\|^Участники:" <summary>.md` — если `## Участники` (без `:`)
    — парсер не найдёт секции.
    **Быстрый фикс для конкретной встречи:**
    ```bash
    sed -i \
      -e 's/^## Участники$/Участники:/' \
      -e 's/^## Решения$/Решения:/' \
      -e 's/^## Блокеры$/Блокеры:/' \
      -e 's/^## Задачи$/Задачи:/' \
      -e 's/^## Риски$/Риски:/' \
      "<путь>/summary.md"
    python -m protocolfromsummary run "<путь>/summary.md" --confirm-republish
    ```
    **Системный фикс (реализован 29.07.2026)** — в `summary_parser._find_sections()` строка 130
    расширен regex: двоеточие стало опциональным, добавлена защита от ложных срабатываний:
    ```python
    # было:
    if re.match(rf"^{re.escape(name)}\b.*:\s*$", header_candidate, re.IGNORECASE):
    # стало:
    if re.match(rf"^{re.escape(name)}\b[^:\n]*:?\s*$", header_candidate, re.IGNORECASE):
    ```
    `[^:\\n]*` вместо `.*` — не зацепить строки с двоеточием посередине (`Участники: обсудили X`).
    Регэксп уже снимал `##` на строке 123, поэтому оба формата парсятся корректно.
    Тест: `test_find_sections_header_without_colon` в `tests/test_summary_parser.py`.

16. **MFF retry Custom AI Skill (v2.1, реализовано 29.07.2026)** —
    При `summary_format == "bullet_points"` MFF планирует 3 повторных попытки (+5/+10/+15 мин).
    После 3 неудачных попыток → `status = "completed"` + TG-уведомление в мониторинг-топик:
    ```
    ⚠️ MoveFromFF: не получен custom summary
    📌 <название встречи> | 🕐 <дата Europe/Moscow>
    ❗ Custom AI Skill не вернул результат после 3 попыток
    🔧 Для переимпорта: python -m movefromff --mode manual --meeting-id <id>
    ```
    Bullet points файл **не удаляется** между ретраями — перезаписывается при успехе.
    Поля в MeetingRecord: `summary_format: str`, `custom_skill_retries: int`.
    Конфиг: `MFF_CUSTOM_SKILL_RETRY_DELAYS = [5, 10, 15]` (минуты).

15. **Встреча с Лёней/1-1-контактом роутится по названию, а не по участникам** —
    `route.py` шаг 2 (name_match) срабатывает ДО шага 3 (participants fallback). Если встреча
    называется «OKR. ...» но участник — Цыба Леонид, встреча пойдёт в `okr`, а не `lenya_1on1`.
    **Это известное ограничение**: только `aralov_1on1` определяется по составу участников
    (хардкодное правило в шаге 1). Остальные 1-1 идут по name_match на alias в названии.
    **Практика**: убедиться что встречи с Лёней называются «Лёня 1-1» в Fireflies, а не по теме.
    Если встреча попала не туда — переопубликовать с `--confirm-republish` после переименования
    или ручной правки summary-файла (добавить `lenya_1on1` в frontmatter `projects:`).
    **lenya_1on1** → page_id `508804891` (та же страница что и `ilya_1on1` — Лёня заменил Илью).
    Подробный рецепт переноса: `references/force-route-meeting-29072026.md`.

## Перенос встречи на другую страницу (force-route)

Полные рецепты обоих методов — `references/force-route-meeting-29072026.md`.

**Выбор метода по ситуации:**
- **Метод A (прямой API, РЕКОМЕНДОВАН)** — строка **уже опубликована** на Confluence. GET source → вырезать `<tr>` с нужным anchor (счётчик вложенности `<tr>`) → PUT source (version+1) → вставить после `</tr>` строки-заголовка на target → PUT target (version+1) → обновить реестр. Не требует PFS pipeline.
- **Метод B (monkey-patch + run_pilot)** — строки ещё нет на Confluence или нужно переопубликовать от оригинального summary-файла. Удалить из реестра → monkey-patch resolve_route → dry_run → live.

**Питфолл: поле `space` отсутствует в GET-ответе** — `?expand=body.storage,version` не возвращает `space`. Для payload PUT нужны только `title` + `version.number`. Если нужен space_key — явно добавить `expand=...,space`.

**Критически важный порядок шагов (Метод A):**

1. **Убедись, что строка существует на source-странице** (GET + проверь anchor) перед удалением.
2. **Вырежи `<tr>...</tr>` с нужным anchor** — `rfind('<tr>', 0, anchor_pos)` + счётчик глубины для matching `</tr>`.
3. **PUT source** (version+1) с body без строки.
4. **Вставь строку на target** сразу после `</tr>` строки-заголовка (`find('</tr>', find('<th>'))`).
5. **PUT target** (version+1).
6. **Бэкап реестра** + обновить `page_id` и `entity` атомарно (tmp + os.replace).
7. **Верификация:** GET обеих страниц, проверить anchor присутствует/отсутствует.

**Критически важный порядок шагов (Метод B):**

1. **Убедись, что строка существует на source-странице**, прежде чем удалять её — `copy_meeting_to_page` ищет anchor на source_page из реестра. Если удалить строку до вызова copy — получишь `action=not_found`.
2. **Удали строку с исходной страницы** через прямой API PUT.
3. **Бэкап реестра:** `cp _registry.json _registry.json.bak-YYYYMMDD-reason`
4. **Удали запись из реестра** (иначе `run_pilot` вернёт `skipped_duplicate`):
   ```python
   import json; from pathlib import Path
   reg = Path('~/WorkVault/ProtocolFromSummary/_registry.json').expanduser()
   data = json.loads(reg.read_text())
   data['entries'].pop('<meeting_id>', None)
   reg.write_text(json.dumps(data, ensure_ascii=False, indent=2))
   ```
5. **Monkey-patch и dry_run=True:**
   ```python
   import protocolfromsummary.pipeline as pm
   from protocolfromsummary.route import _route_from_entity
   from pathlib import Path

   pm.resolve_route = lambda name, **kw: _route_from_entity('target_entity_slug')
   result = pm.run_pilot(Path('/path/to/summary.md'), dry_run=True)
   # ожидаем: action=published, entity=target_entity_slug, page_id=<correct>
   print(result.action, result.entity, result.page_id)
   ```
6. Убедившись — запусти с `dry_run=False`. Реестр обновится автоматически.

**Pitfall: `kind: person_1on1` vs `kind: one_on_one` в entities.json** —
`pipeline.py` проверяет `route.kind == "one_on_one"` для включения режима one_on_one в `render_row`.
`kind: person_1on1` (новый тип для людей без папки) этот флаг НЕ триггерит. Если нужен режим
1-1 в рендере — используй `kind: one_on_one` в entities.json.

**Pitfall: `resolve_participants` и `render_row` — актуальные сигнатуры (29.07.2026)** —
```python
# resolve_participants требует confluence=
resolve_participants(raws, *, store, confluence, rooms)
# render_row НЕ принимает meeting_id — только через row_anchor отдельно
render_row(*, meeting_date, meeting_name, participants, decisions, blockers,
           risks=[], tasks, tag_prefix, task_id_start=1, is_one_on_one=False,
           row_anchor=None, layout='2col', content_column_index=None)
# tasks = list[tuple[MeetingTask, list[ResolvedParticipant], date]] — НЕ raw strings
# Собирать через pipeline._resolve_tasks или запускать через run_pilot
```
При прямом вызове `render_row` вне pipeline — проще вызвать `run_pilot` с monkey-patched route,
чем собирать resolved_tasks вручную (это 50+ строк кода из pipeline.py).

## Verification checklist

- [ ] Ran `dry_run=True` and inspected `row_xml` before any live write
- [ ] Multi-assignee task lines split via `split_assignees()`, not passed whole to
      `resolve_participants()`
- [ ] No `page_layout mismatch` WARNING in logs — if there is one, `ROUTES` config updated to
      match the live page, not silenced
- [ ] After a live write, GET the page back and grepped the actual fragment (mentions, dates,
      task-ids) — didn't trust `action == "published"`/`"republished"` alone
- [ ] Full offline suite green (`pytest -q -m "not live_confluence"`) before AND after any code
      change to `pipeline.py`/`storage_xml.py`/`contacts_resolver.py`/`summary_parser.py`
- [ ] After changes to `dedup.py` — run `pytest tests/test_dedup.py tests/test_pipeline_dedup.py -q`
      (separate from the main suite for speed; expect 36 passed)
- [ ] После любой правки aliases в `entities.json` — проверить `test_baseline_invariant_matches_pfs_routes`
      до запуска cron; если тест падает — синхронизировать ROUTES в `config.py` перед следующим прогоном
- [ ] Четыре системных fallback-entity (`vstrechi_nerazobrannoe`, `sink_aid`, `vstrechi_pro`,
      `aralov_1on1`) присутствуют в ROUTES — проверить `python -c "from protocolfromsummary.config
      import ROUTES; [print(k, 'OK' if k in ROUTES else 'MISSING!') for k in
      ['vstrechi_nerazobrannoe','sink_aid','vstrechi_pro','aralov_1on1']]"` при подозрении на
      KeyError в fallback-ветке
- [ ] Dry-run проверка CUTOVER_DATE guard: `run-pending --dry-run | grep -E 'исторических|пропущено|published'`
      должен показывать `пропущено N исторических встреч` и `published: 0` (если нет новых реальных встреч)
- [ ] Пустой протокол в Confluence? → проверить `grep "## Bullet\|Участники:" <summary>.md` — если только Bullet points, Custom Skill не сработал → перескачать через MFF (Питфолл 13); с v2.1 MFF сам сделает retry и уведомит в мониторинг
- [ ] `lenya_1on1` → page_id `508804891` (та же страница что и `ilya_1on1`). Встречи с Лёней Цыбой где в названии НЕ «Лёня 1-1» — уйдут по name_match не туда (Питфолл 15); переносить вручную через Метод A
