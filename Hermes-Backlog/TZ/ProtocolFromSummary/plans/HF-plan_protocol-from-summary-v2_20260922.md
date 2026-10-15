# План HF:impl — §23 Промоут прохода 2 (дельта v2)

Кейс: **DEV/protocol-from-summary-v2**. Фаза: **HF:plan**. Архитектор: cursor-grok-4.6-high.
Исполнитель следующих фаз: composer-2.5. Код в этой фазе **не** писать.

Канон: `WorkVault/Hermes-Backlog/TZ/ProtocolFromSummary/ProtocolFromSummary_TZ.md` v1.16.0 §23.
Рабочая директория: `/home/tkachenkoav/USERTOOLS/ProtocolFromSummary`.

---

## 0. РЕЗЮМЕ ДИСКА (не переписывать работающее)

На диске уже лежит переходный каркас §22 + фикс v1.15.0. Дельта v2 — **не** greenfield: закрыть расхождения с каноном §23, дописать атомарные тесты, не ломая резолв цели.

**Уже есть и оставляем as-is (кроме точечных дыр ниже):**

| Место | Факт с диска |
|---|---|
| CLI | `__main__.py:_cmd_promote` + parser `promote --meeting-id --dry-run` (строки 293–298, 516–519). Существующие команды не трогать. |
| `promote_meeting` / `second_pass_all` / `PromoteResult` | `playground_promote.py:116–271` |
| Резолв цели v1.15.0 | `parse_target_page_id_from_cell` / `parse_target_space_title_from_cell` (ingest, без I/O); `_resolve_target_page_id_from_cell` (promote): id → `find_page_by_title` → пост-резолвная `_FORBIDDEN_TARGET_PAGE_IDS={PLAYGROUND_PAGE_ID, EXCLUDED_PAGE_ID_OBSHY_SPISOK}`. **Таблицу фикса не дублировать.** |
| Ingest алгоритм | `ingest_after_publish` (`playground_ingest.py:243–307`): N-5 warn, `skipped_present`, `next_task_id` + `reallocate_task_ids` + `processed_task_id = task_start + n_proto`, 4col, `insert_row_chronological` по дате боевой строки, реестр `playground_ingested_at` / `first_pass_hash` / `route_page_id_at_publish` только если пусто, snapshot `.md` fail-soft. |
| Pipeline ingest | `run_pilot` после `action ∈ {published, republished}` и `not dry_run`; kill-switch `PFS_PLAYGROUND_INGEST_OFF ∈ {1,true,yes,on}`; try/except `log.warning` (`pipeline.py:585–606`). |
| Pipeline проход 2 | `process_pending` вызывает `second_pass_all` в try/except **после** цикла publish (`pipeline.py:754–759`). |
| Реестр | `RegistryEntry` уже имеет все optional-поля §23; `schema_version` форсируется `"1.1"` в `put`. Republish пробрасывает `existing.promoted_at/first_pass_hash/promote_*_diff/route_page_id_at_publish/target_override` (`pipeline.py:516–552`). |
| Strip | `strip_playground_to_minutes_row`: td0+td1, trim первых `len(row_task_ids)`, `reallocate_task_ids(min(ids))`, `_aid` → `ValueError`. |
| TG | `notifier.format_promote_notification` / `format_promote_invalid_target`; `scripts/notify_pending.py:136–150` читает `last_action`. |
| Инвариант #12 | `entry.page_id == PLAYGROUND_PAGE_ID` → `action=error`; `tests/test_entities_registry.py:67` — `pfs.page_id != "523032632"`. |
| Фикс v1.15.0 | `tests/test_promote_title_resolve.py` — **не ломать** порядок резолва и запрет PLAYGROUND/EXCLUDED. |
| `conftest.py` | autouse `PFS_PLAYGROUND_INGEST_OFF=1` — все e2e publish-тесты с ingest выкл. Тесты, которые **должны** звать ingest, обязаны `monkeypatch.delenv`. |

**Факт, который исполнителю нельзя «поправить по памяти»:** `find_row_by_anchor` / `insert_row_chronological` / `replace_row_by_anchor` / `next_task_id` / `reallocate_task_ids` / `count_task_ids` живут в **`page_merger.py`**, не в `storage_xml.py`. `storage_xml.py` — только `render_row` и друзья. Сигнатуры merger **заморожены**.

**Четыре дыры канона (это и есть работа дельты):**

1. **OQ-23.1.** `promote_meeting` пишет `last_action=promote_invalid_target` + `notified=False` **до** ветки `dry_run` (`playground_promote.py:155–160`). Живой повтор каждый раз сбрасывает `notified`. Канон-рекомендация: вариант 3.
2. **OQ-23.2.** Insert-ветка (`:196–199`) кладёт минутки с id прохода 1 без `next_task_id(target)`. Рекомендация: вариант 1 (insert → reallocate от `next_task_id`; replace → id прохода 1).
3. **OQ-23.3.** `_record_promote_diffs` сравнивает текущую td1 с ней же (`first_body = playground_body_inner`) → пустой body_diff. Журнал пишется **до** GET/PUT: при `invalid_target` после неудачного GET файл уже на диске. Рекомендация: закрыть в этом раунде.
4. **`process_pending` early-return.** При пустом glob `* summary.md` функция возвращает `[]` **до** `second_pass_all` (`pipeline.py:665–667`). Критерий §23.2: проход 2 даже если новых summary нет. Когда файлы есть, но все уже в реестре — вызов уже есть; дыра — пустой каталог / tick только под promote.

**Не дыра, не делать reader:** `learner.propose_pfs_dedup_from_registry` семплирует только `duplicates_skipped` (OQ-23.4 вариант 2).

**Гигиена тестов на диске:** живой `promote_meeting` в `test_promote_target_override_inserts_on_new_page_only` пишет proposal в прод-каталог `WorkVault/Registries/prompts/_proposals/` (`PROPOSALS_DIR` захардкожен). В этом раунде все живые promote/ingest-тесты **обязаны** monkeypatch `PROPOSALS_DIR` и `GOLD_PROTOCOLS_DIR` на `tmp_path`.

---

## 1. ИЗМЕНЯЕМЫЕ ФАЙЛЫ КОДА

### 1.1. `protocolfromsummary/playground_ingest.py`

**Роль:** контракт ingest-матчинга + эталон левой стороны журнала (тело, с которого считан `first_pass_hash`).

**Не трогать:** `render_target_cell`, `parse_target_page_id_from_cell`, `parse_target_space_title_from_cell`, маркеры `_PLAYGROUND_HEADER_MARKERS`, сигнатуры `ingest_after_publish` / `strip_playground_to_minutes_row` / `hash_battle_row_body`. Реэкспорт `PLAYGROUND_PAGE_ID` оставить (его импортируют `gold_publish.py` и `tests/test_link_n_dedup_transition.py`).

**Правки:**

1. **`_write_first_pass_snapshot` (сейчас `:231–240`)** — рядом с `{meeting_id}-first-pass.md` (текст td1 без HTML, как сейчас) писать sidecar **`{meeting_id}-first-pass.td1.html`**: сырой `cells[1]` боевой строки, **тот же** кусок, что хеширует `hash_battle_row_body`. Ошибка записи sidecar = `log.warning`, ingest уже успешен (как у `.md`). Новый реестровый ключ **не** вводить (`schema_version` остаётся `"1.1"`).
2. **Новая чистая функция (без I/O Confluence), имя зафиксировать:**
   ```text
   def load_first_pass_td1(meeting_id: str, *, gold_dir: Path | None = None) -> str | None
   ```
   Читает sidecar из `gold_dir or GOLD_PROTOCOLS_DIR`. Нет файла → `None`. Нужна `promote._record_promote_diffs` и unit-тестам журнала.
3. Алгоритм `ingest_after_publish` **не** менять по шагам 1–7 §23: он уже совпадает. Не писать реестр на `skipped_present` (уже так, `:270–271`). Не перетирать `route_page_id_at_publish`, если заполнено (уже так, `:302–303`).

### 1.2. `protocolfromsummary/playground_promote.py`

**Роль:** единственный оркестратор прохода 2. Сюда сходятся OQ-23.1 / 23.2 / 23.3.

**Не трогать:** `_resolve_target_page_id_from_cell` и `_FORBIDDEN_TARGET_PAGE_IDS` (канон фикса v1.15.0). Не импортировать `DedupChecker`. Не вызывать `remove_row_by_anchor`. Не вызывать `copy_meeting_to_page`. Не писать на `PLAYGROUND_PAGE_ID`. Не менять `route_page_id_at_publish`.

**Правки:**

1. **`PROPOSALS_DIR`.** Сейчас дубль литерала (`:31`). Заменить на `from .learner import PROPOSALS_DIR` (тот же Path, TZ: каталог learner). Локальный константный Path удалить.
2. **Импорты merger** — добавить `next_task_id`, `reallocate_task_ids`, `count_task_ids` к уже существующим `extract_row_xml/find_row_by_anchor/insert_row_chronological/replace_row_by_anchor/row_date_from_tr_xml`. Сигнатуры merger не менять.
3. **`_apply_invalid_target(entry, registry, *, dry_run) -> None`** (новое, приватное) — закрывает OQ-23.1 вариант 3:
   - `dry_run=True` → **никакого** `registry.put` (полный read-only, включая invalid_target).
   - `dry_run=False` и `entry.last_action == "promote_invalid_target"` → **не** трогать `notified`, **не** `put` повторно (живой retry не шумит в TG).
   - иначе: `last_action="promote_invalid_target"`, `notified=False`, `put`.
   - `promoted_at` не ставить. PUT цели нет.
4. **`promote_meeting` — порядок живого успеха** (канон: журнал→GET→дедуп→PUT→реестр, но **persist** журнала только после успешного PUT):
   - Предусловия без изменений: нет записи → `error=not in registry`; `promoted_at` → `already_promoted`; `page_id == PLAYGROUND_PAGE_ID` → `error=invariant #12`; нет строки → `not_on_playground`; `< 4 td` → `error=not 4col playground row`; td3 incomplete → `skipped` (реестр не писать).
   - Резолв td2 через существующий `_resolve_target_page_id_from_cell`. Пусто → `_apply_invalid_target` → `action=invalid_target`.
   - `strip_playground_to_minutes_row(..., registry_row_task_ids=list(entry.row_task_ids or []))`; `ValueError` (`_aid` и т.п.) → `action=error`, PUT нет.
   - **`dry_run` после успешного резолва:** return `action=promoted` + `target_page_id` + `target_changed` + `old_page_id`. Нет PUT, нет proposal-файла, нет записи `promoted_at/page_id/target_override/promote_*_diff`.
   - **Живой путь:**
     1. GET цели. Исключение → `_apply_invalid_target` (не dry-run), **без** proposal-файла, `action=invalid_target`.
     2. Если `find_row_by_anchor(target_storage, row_anchor)` не None → `replace_row_by_anchor(..., minutes_row, row_date)` — id прохода 1, **без** `next_task_id`.
     3. Иначе (OQ-23.2 в.1): `start = next_task_id(target_storage)`; если `count_task_ids(minutes_row) > 0` → `minutes_row = reallocate_task_ids(minutes_row, start)`; затем `insert_row_chronological(target_storage, minutes_row, row_date)`.
     4. `update_page(target_page_id, ...)`. Исключение → `action=error`, реестр/proposal не писать. `update_page` только с `target_page_id` (не `old_page_id`, не `PLAYGROUND_PAGE_ID`).
     5. **После успешного PUT:** `_record_promote_diffs` → выставить `promoted_at=now UTC Z`, `page_id=target_page_id`, `last_action="promoted"`, `notified=False`; `target_override={from,to,at}` только если `target_page_id != old_page_id`; `registry.put`.
5. **`_record_promote_diffs(entry, playground_body_inner, target_page_id)`** — закрыть OQ-23.3:
   - Левая сторона: `load_first_pass_td1(entry.meeting_id)` (sidecar). Нет файла → `log.warning`, left = `""` (не подставлять текущую td1 — это и есть impl-gap).
   - Правая сторона: `playground_body_inner` (td1 площадки = `cells[1]`).
   - Обе стороны через существующий `_normalize_body_html`.
   - `body_diff = unified_diff(left → right, fromfile="first_pass", tofile="playground_td1")`.
   - `target_diff`: пусто, если `entry.route_page_id_at_publish` пуст **или** равен `target_page_id`; иначе `route_page_id_at_publish={id} -> target={id}`. **Не** фолбэчить на `entry.page_id` (сейчас `:93` — убрать `or entry.page_id`, иначе target_diff врёт, когда route ещё пуст).
   - Payload файла: `meeting_id`, `body_diff` (полный), `target_diff`, `first_pass_hash` (= `entry.first_pass_hash or ""`), `note="proposal-only для Контура A"`.
   - Файл: `PROPOSALS_DIR / f"link-n-dedup-promote-{meeting_id}-{YYYYMMDD-HHMMSS}.json"` append-only.
   - Реестр: `promote_body_diff = body_diff[:8000]`, `promote_target_diff = target_diff` целиком.
6. **`second_pass_all`** — логика кандидатов уже канонична (реестр: `row_anchor` и пустой `promoted_at`; на площадке 4col + td3 complete). Не фильтровать по kill-switch ingest. Сигнатуру не менять.

**Шум task-id в body_diff:** ingest перенумеровывает копию на площадке, эталон sidecar — id прохода 1. Исполнителю **не** маскировать `<ac:task-id>` «от себя»: канон — дифф эталон→td1 как есть. Не открывать новый OQ.

### 1.3. `protocolfromsummary/pipeline.py`

**Роль:** wiring ingest (уже канон) + fail-soft проход 2 даже без новых summary.

**Не трогать:** `protocol_publish`/`run_pilot` ingest-блок (`:585–606`), проброс `existing.*` при republish (`:516–552`), `DedupChecker` только в проходе 1 (`:335–360`), `copy_meeting_to_page`, формулу `row_anchor_for`, `_EXPECTED_COLUMNS`.

**Правка одна — `process_pending` (`:626–761`):**

Сейчас:

```text
summary_paths = glob("* summary.md")
if not summary_paths:
    return []          # ← дыра: second_pass_all не вызывается
# parse / sort / publish loop
try:
    second_pass_all(...)
except ...
```

Нужно: **убрать early-return**. Пустой glob → `log.info` как сейчас, `results=[]`, всё равно создать/взять `confluence` (`confluence = confluence or _make_confluence_client()`) и вызвать `second_pass_all` в том же try/except. Цикл publish по-прежнему только для `pending_new`. Исключение прохода 2 → `log.warning("second_pass_all (fail-soft): ...")`, `results` прохода 1 не откатывать.

Существующие тесты `test_process_pending.py` передают `confluence=MagicMock()` — fail-soft try/except защитит от мусора мока. Не переписывать семантику publish-цикла.

### 1.4. Файлы, которые **не** меняем, хотя рядом с контрактом

| Файл | Почему не трогаем |
|---|---|
| `registry.py` | Поля §23 уже в dataclass; `schema_version="1.1"`. |
| `__main__.py` | CLI `promote` уже есть. Help «§22» можно не переименовывать (косметика вне дельты). |
| `notifier.py` / `scripts/notify_pending.py` | Форматы TG и ветки `promoted` / `promote_invalid_target` уже на диске. |
| `learner.py` | OQ-23.4 вариант 2: reader **не** в этом раунде. Только `PROPOSALS_DIR` переиспользуется импортом из promote. |
| `dedup.py` | §15 только проход 1. |
| `page_merger.py` / `storage_xml.py` | Сигнатуры заморожены. |
| `route.py` / `config.py` / `page_admin.py` / `gold_publish.py` | Вне дельты. `render_target_cell` не трогать (канон фикса v1.15.0). |

---

## 2. СОЗДАВАЕМЫЕ ФАЙЛЫ

| Файл | Оценка | Зачем |
|---|---|---|
| `tests/test_promote_v2.py` | ~350–450 строк | Атомарные критерии §23, которых нет в фиксах/transition: CLI dry-run, invariant #12, skipped td3, DedupChecker не звать, журнал, insert-reallocate, N-3 DELETE, sticky invalid_target. Хелперы **переиспользовать** из `tests/test_link_n_dedup_transition.py` (`_battle_row`, `_playground_row_complete`) — импортировать, не копировать таблицу резолва. |
| sidecar runtime `{id}-first-pass.td1.html` | не код | Артефакт ingest в `GOLD_PROTOCOLS_DIR`. Не USERTOOL, не новое поле реестра. |

Новых пакетов, скиллов, кронов, CLI-команд, USERTOOL **нет**.

---

## 3. НОВЫЕ / ПРАВЛЕНЫЕ ТЕСТЫ

Общие правила: без live API; `PROPOSALS_DIR` и `GOLD_PROTOCOLS_DIR` → `tmp_path`; ingest-вызывающие тесты делают `monkeypatch.delenv("PFS_PLAYGROUND_INGEST_OFF", raising=False)` (autouse conftest иначе глотает вызов).

Имена — **как в критериях §23**, где ТЗ их назвало.

### 3.1. `tests/test_promote_title_resolve.py` — фикс v1.15.0

**Не копировать таблицу резолва. Не удалять тесты.**

Единственная хирургическая правка под OQ-23.1 в.3:

- `test_promote_find_page_by_title_none_invalid_target` (сейчас `:103–111`) после `dry_run=True` **сейчас** ждёт `last_action==promote_invalid_target`. Заменить на: `result.action == "invalid_target"` + `registry.get("m-ui").last_action == "published"` (дефолт записи) + `update_page` не звать. Резолв (`find_page_by_title.return_value=None` → invalid) остаётся.

Остальные тесты файла проверяют только `action` / `find_page_by_title` / запрет id — они зелёные при варианте 3 без правок.

**Зависимость от ответа Саши:** если Саша выберет OQ-23.1 вариант 1 — **не** менять эту строку и не внедрять `_apply_invalid_target` read-only. Пока ответа нет — в этом раунде делаем вариант 3 (как поручено плану).

### 3.2. `tests/test_link_n_dedup_transition.py` — усилить существующие имена

| Тест | Что добавить (критерий §23) |
|---|---|
| `test_replace_by_anchor_single_row_on_clean_page` | Помимо чистого merger: прогнать **`promote_meeting`** (якорь уже на цели) → в PUT-storage цели `count(row_anchor)==1`, `update_page` один раз по target. Сейчас тест не вызывает promote. |
| `test_promote_target_override_inserts_on_new_page_only` | Уже: insert только на новую, OLD без PUT. Добавить: `PLAYGROUND_PAGE_ID not in updated`; `remove_row_by_anchor` не импортирован/не звать (patch или assert id площадки не в `update_page`); `entry.notified is False`; `last_action=="promoted"`; `target_override` заполнен `{from,to,at}`; monkeypatch `PROPOSALS_DIR`. |
| `test_invalid_target_skips_without_put` | Живой (не dry-run) — оставить: первый invalid пишет реестр. Это не dry-run. |
| `test_fail_soft_ingest_does_not_break_publish` | **Ложный зелёный:** autouse `PFS_PLAYGROUND_INGEST_OFF=1` → ingest не зовут, patch не срабатывает. Исправить: `delenv` флага; после `action=published` проверить `registry.get(...).page_id == route.page_id`, `last_action=="published"`, `update_page` боевой страницы был, ingest-исключение не откатывает реестр. |
| `test_skip_overwrite_playground_on_duplicate_anchor` | Добавить: заранее заполнить `first_pass_hash` и `route_page_id_at_publish` → после `skipped_present` значения те же; `playground_ingested_at` не переписан. |

### 3.3. Новый `tests/test_promote_v2.py`

Хелпер `_patch_dirs(monkeypatch, tmp_path)`: `learner.PROPOSALS_DIR` и `playground_ingest.GOLD_PROTOCOLS_DIR` → `tmp_path / "_proposals"` и `tmp_path / "gold"`.

| Имя теста | Что проверяет | Критерий §23 |
|---|---|---|
| `test_cli_promote_dry_run_valid_target_no_put` | `protocolfromsummary.__main__.main(["promote","--meeting-id",X,"--dry-run"])` с моком registry+confluence (patch `_make_confluence_client` + `REGISTRY_JSON`). stdout JSON `action=promoted` + `target_page_id`; `update_page` не звать; `promoted_at` пуст; proposal-файлов 0. | Promote §23.1 / сводка 1 |
| `test_promote_page_id_playground_invariant_12` | `entry.page_id=PLAYGROUND_PAGE_ID` → `action=error`, `error` содержит invariant; `update_page` не звать. | Promote §23.4 / сводка — |
| `test_promote_td3_incomplete_skipped` | td3 incomplete → `action=skipped`; реестр без изменений (`last_action` прежний, `promoted_at` пуст); цель без PUT. | Promote §23.5 |
| `test_promote_insert_source_page_and_playground_untouched` | Якоря на цели нет, цель ≠ страница прохода 1 → PUT только target; source прохода 1 и площадка без `update_page` и без DELETE. | Дедуп §23.2 + N-3 сводка 5 |
| `test_strip_4col_drops_service_task_and_trims_extras` | 4col → 2col; id служебного чекбокса td3 отсутствует в минутках; extras сверх `len(row_task_ids)` срезаны; `count_task_ids(minutes) <= len(row_task_ids)`. | Дедуп §23.3 |
| `test_strip_empty_row_task_ids_no_reallocate` | `row_task_ids=[]` → минутки без протоколных `<ac:task>` (td1 без task-list или 0 task); `reallocate_task_ids` не обязан вызываться (можно patch и `assert_not_called`). | Дедуп §23.5 |
| `test_promote_meeting_does_not_call_dedup_checker` | `patch("protocolfromsummary.dedup.DedupChecker.check_tasks")` и/или `patch.object(DedupChecker, "check_tasks")` — на пути `promote_meeting` не звать. | Дедуп §23.4 / сводка 4 |
| `test_promote_insert_reallocates_from_next_task_id` | На цели уже есть `<ac:task-id>99`; insert (якоря нет) → id в новой строке начинаются с `next_task_id==100`, не с id прохода 1. Replace-path в этом тесте не используется. | OQ-23.2 в.1 |
| `test_promote_replace_keeps_pass1_task_ids` | Якорь на цели, `row_task_ids=[10]` → после replace в строке task-id 10, не `next_task_id`. | OQ-23.2 replace канон |
| `test_live_promote_writes_one_proposal_and_registry_fields` | Успешный живой promote: ровно один файл `link-n-dedup-promote-<id>-<ts>.json`; `promote_body_diff` и `promote_target_diff` заполнены; `notified=False`; `last_action=promoted`. Sidecar left ≠ right → `body_diff` непустой. | Журнал §23.1 / сводка 6 |
| `test_dry_run_skipped_already_promoted_no_journal` | Три кейса (или три теста с суффиксами): dry-run валидная цель; skipped (td3); `already_promoted` — файлов 0, `promote_*_diff` в реестре не появляются. | Журнал §23.2 |
| `test_promote_body_diff_truncated_in_registry_full_in_file` | Искусственно длинный left/right → `len(entry.promote_body_diff) ≤ 8000`; JSON-файл содержит полный `body_diff` без среза. | Журнал §23.3 |
| `test_target_diff_empty_when_same_as_route` | `route_page_id_at_publish == target` → `promote_target_diff == ""` и payload `target_diff` пуст. | Журнал §23.4 |
| `test_target_diff_contains_both_ids_when_changed` | route ≠ target → строка содержит оба id в формате `route_page_id_at_publish=… -> target=…`. | Журнал §23.4 |
| `test_dry_run_invalid_target_is_read_only` | dry-run + нерезолвящаяся td2 → `action=invalid_target`, реестр не записан, proposal нет. | OQ-23.1 в.3 |
| `test_live_invalid_target_does_not_reset_notified_if_already_flagged` | `last_action=promote_invalid_target`, `notified=True` → повторный живой invalid **не** ставит `notified=False`. | OQ-23.1 в.3 sticky |
| `test_promote_aid_in_row_is_error_no_put` | `_aid` в 4col → `action=error`, PUT нет. | Дедуп механика `_aid` |

### 3.4. `tests/test_process_pending.py`

| Имя | Что | Критерий |
|---|---|---|
| `test_second_pass_all_called_when_no_new_summaries` | Каталог с summary, все уже в реестре **или** пустой каталог (оба варианта — parametrize): `patch("protocolfromsummary.playground_promote.second_pass_all")` → вызван 1 раз, `protocol_publish` не вызван. | Promote §23.2 / сводка 2 |
| `test_second_pass_all_exception_is_fail_soft` | `second_pass_all` `side_effect=RuntimeError` + один новый summary, publish успешен → `process_pending` не падает, в results есть published, exception не пробрасывается. | Promote §23.2 |

При правке early-return `test_process_pending_zero_new_files_empty_dir` остаётся валидным (`results==[]`, publish не звать); добавить к нему assert вызова `second_pass_all` **или** покрыть новым тестом выше и старый не ломать.

### 3.5. `tests/test_playground_ingest.py`

| Имя | Что | Критерий |
|---|---|---|
| `test_playground_row_has_four_columns_with_ac_task` | Уже есть: 4 `<td>`/`<th>`, есть «обработано», нет `_aid`. Не ломать. | Ingest §23.3 / сводка 9 |
| `test_ingest_processed_task_id_is_next_plus_n_proto` | Мок GET площадки с известным max task-id; захват `update_page` storage; `service_task_id_from_row` == `next_task_id(before)+n_proto`. `delenv` ingest-off не нужен — тест зовёт `ingest_after_publish` напрямую. GOLD_DIR → tmp. | Ingest §23.4 |
| `test_ingest_chrono_old_meeting_not_first_after_th` | На площадке строка с датой новее; ingest более старой встречи → новая `<tr>` **не** сразу после `<th>`. | Ingest §23.5 |
| `test_ingest_writes_sidecar_td1_and_hash` | Успешный insert → есть `.md` и `.td1.html`; `first_pass_hash == hash_battle_row_body(battle)`. | OQ-23.3 подготовка |

Прямой вызов `ingest_after_publish` **не** зависит от conftest kill-switch (флаг проверяет только pipeline).

### 3.6. `tests/test_pipeline_dedup.py` + ingest kill-switch / иммутабельность republish

Не ломать существующие §15-тесты. Добавить (в `test_link_n_dedup_transition.py` или `test_promote_v2.py` — предпочтительно transition, рядом с fail-soft):

| Имя | Что | Критерий |
|---|---|---|
| `test_ingest_off_skips_ingest_publish_lives` | Не `delenv`: autouse уже OFF. Явно `PFS_PLAYGROUND_INGEST_OFF=1`, patch `ingest_after_publish`, `protocol_publish` → ingest `assert_not_called`, `action=published`. | Ingest §23.7 |
| `test_republish_preserves_promote_fields` | existing с `promoted_at` / `first_pass_hash` / `promote_body_diff` / `route_page_id_at_publish`; `confirm_republish=True`; после publish поля те же. Ingest с якорем на площадке → `skipped_present` не перетирает hash. Нужен `delenv` + мок GET площадки с якорем, иначе ingest (если включить) мог бы писать. Проще: оставить OFF и проверить только проброс `existing.*` в `RegistryEntry` после republish. | Ingest §23.6 / сводка 8 |

`test_pfs_page_id_is_digits` уже запрещает `523032632` — **не дублировать**, критерий ingest §23.8 закрыт существующим тестом.

### 3.7. Learner (журнал §23.5–6, OQ-23.4 в.2)

Новый тест в `tests/test_promote_v2.py` или коротко в существующем prompt-файле:

| Имя | Что |
|---|---|
| `test_learner_contour_a_without_yes_does_not_write_canon` | `propose_pfs_dedup_from_registry` пишет только под `PROPOSALS_DIR` (monkeypatch tmp); канон `Registries/prompts/*.json` вне `_proposals/` и `entities.json` не меняются; payload по-прежнему содержит `duplicates_skipped_sample`, **нет** обязательного ключа `promote_body_diff` (reader не в этом раунде). |

Не добавлять чтение `promote_*_diff` в `learner.py`.

### 3.8. `tests/test_pipeline_dedup.py`

Только регресс: DedupChecker остаётся на `run_pilot`, не на promote. Отдельный тест в `test_promote_v2.py` (см. 3.3) достаточен; этот файл не расширять без нужды.

---

## 4. ПОРЯДОК РАБОТ

Зависимости: sidecar ingest → левая сторона журнала; OQ-23.1 меняет один assert фикса; wiring `process_pending` независим от XML.

```text
Шаг A  playground_ingest.py
       sidecar .td1.html + load_first_pass_td1
       тесты 3.5 (processed_task_id, chrono, sidecar)

Шаг B  playground_promote.py
       PROPOSALS_DIR из learner
       _record_promote_diffs (left=sidecar, persist только после PUT)
       insert: next_task_id + reallocate (OQ-23.2)
       _apply_invalid_target (OQ-23.1 в.3)
       порядок promote_meeting как в §1.2

Шаг C  tests/test_promote_title_resolve.py
       одна правка assert dry-run invalid_target
       прогнать весь файл — должен быть зелёный

Шаг D  pipeline.py process_pending
       убрать early-return, second_pass_all всегда
       тесты 3.4

Шаг E  Усилить transition-тесты (3.2) + новый test_promote_v2.py (3.3)
       + fail-soft ingest delenv + republish preserve + ingest_off (3.6)
       + learner без canon (3.7)

Шаг F  Греб: promote не вызывает remove_row_by_anchor / DedupChecker /
       copy_meeting_to_page; diff не содержит jobs.json, .env, Gateway, route.py
```

Не параллелить A и B: B читает sidecar из A.

Оценка объёма: ~80–120 строк продакшн-правок (два модуля + early-return) и ~400–550 строк тестов. Новых продакшн-модулей нет.

---

## 5. ПРОМЕЖУТОЧНЫЕ ТОЧКИ ПРОВЕРКИ

После каждого шага — `pytest` без live API, из корня пакета.

| Точка | Команда | Критерий прохождения |
|---|---|---|
| A | `pytest tests/test_playground_ingest.py tests/test_promote_title_resolve.py -q` | 4col/strip без регресса; фикс v1.15.0 ещё зелёный (promote код пока старый — title_resolve не зависит от sidecar). |
| B+C | `pytest tests/test_promote_title_resolve.py tests/test_link_n_dedup_transition.py -q` | Резолв id/title/запрет id зелёный; dry-run invalid больше **не** пишет реестр; override-тест зелёный. |
| D | `pytest tests/test_process_pending.py -q` | Старые batch-тесты + second_pass вызывается без новых summary + fail-soft. |
| E | `pytest tests/test_promote_v2.py tests/test_link_n_dedup_transition.py tests/test_playground_ingest.py tests/test_pipeline_dedup.py tests/test_entities_registry.py::test_pfs_page_id_is_digits -q` | Все имена §23 зелёные. |
| F финал | `pytest tests/test_promote_title_resolve.py tests/test_promote_v2.py tests/test_link_n_dedup_transition.py tests/test_playground_ingest.py tests/test_process_pending.py tests/test_pipeline_dedup.py -q` | Сводка критериев 1–10 (ниже). `git diff --stat` без `jobs.json` `.env` `route.py` `page_merger.py` `storage_xml.py`. |

**Сводка §23 → где проверяется**

1. CLI dry-run preview без PUT/promoted_at → `test_cli_promote_dry_run_valid_target_no_put`
2. second_pass_all fail-soft, пустой promoted_at + td3 complete → `test_second_pass_all_*` + существующий `second_pass_all` фильтр
3. Резолв / PLAYGROUND / EXCLUDED без регресса → `test_promote_title_resolve.py` целиком
4. Один якорь на цели, DedupChecker не звать → `test_replace_by_anchor_single_row_on_clean_page` + `test_promote_meeting_does_not_call_dedup_checker`
5. N-3 площадка и страница прохода 1 целы → `test_promote_insert_source_page_and_playground_untouched` + override-тест
6. Живой promote: proposal + truncate 8000 + notified=False → журнал-тесты 3.3
7. Повторный ingest skipped_present → `test_skip_overwrite_playground_on_duplicate_anchor`
8. Иммутабельность route/hash → skipped_present + `test_republish_preserves_promote_fields`
9. 4col / чекбокс td3 / нет `_aid` / 523032632 не в ROUTES → ingest 4col-тест + `test_pfs_page_id_is_digits`
10. Нет USERTOOL / нет MAIN_TZ_INVENTORY / нет Gateway — контроль diff (шаг F), код не создаёт пакетов

---

## 6. ЧТО НЕ ТРОГАЕМ

- `jobs.json`, `.env`, Gateway, `EcosystemManifest.json`, кроны Hermes, `MAIN_TZ_INVENTORY.md`
- `protocolfromsummary/route.py` и формула `row_anchor` / `row_anchor_for`
- Сигнатуры `page_merger.insert_row_chronological` / `next_task_id` / `reallocate_task_ids` / `replace_row_by_anchor` / `find_row_by_anchor` / `remove_row_by_anchor`
- `storage_xml.render_row` и весь `storage_xml.py`
- `render_target_cell` (ingest кладёт title+content-id; UI снимает id — закрыто фиксом v1.15.0 на проходе 2)
- Канон фикса v1.15.0: порядок резолва, пост-резолвная проверка двух запрещённых id, без aliases/`display_name`/`route_page_id_at_publish` как fallback цели
- `DedupChecker` / окно 3 недели / fuzzy / LLM / `duplicates_skipped` пересчёт на проходе 2
- `copy_meeting_to_page` и Метод B (`page move --confirm-move`) как путь promote
- `remove_row_by_anchor` из promote (разрешён только `page_admin.move_meeting_row` при `--confirm-move`)
- Отдельный kill-switch promote; `PFS_PLAYGROUND_INGEST_OFF` не действует на проход 2
- `learner.py` reader журнала (OQ-23.4); Contour 0 / bind; TaskRefresh / OFC / OpenTasks
- `page_layout` enum / NEW-ENTITY #3 / OQ-22.6 (скан OpenTasks площадки) — не эта дельта
- Назначение `523032632` в `pfs.page_id`; рисование `_aid`; promote **на** площадку

---

## 7. OQ-23.x — КАК ПЛАН ИХ ЗАКРЫВАЕТ

### OQ-23.1 invalid_target × dry-run

- **Поручение плану:** вариант 3.
- **Код:** `_apply_invalid_target` в `promote_meeting` (оба места: пустой резолв и failed GET цели).
- **Тесты:** `test_dry_run_invalid_target_is_read_only`; `test_live_invalid_target_does_not_reset_notified_if_already_flagged`; живой первый invalid по-прежнему пишет (`test_invalid_target_skips_without_put`); хирургический assert в `test_promote_find_page_by_title_none_invalid_target`.
- **Зависимость от ответа Саши:** в каноне ТЗ default кода = вариант 1 (факт диска). Если до HF:impl придёт ответ «вариант 1» — **отменить** шаг B `_apply_invalid_target` и правку title_resolve; оставить диск. Пока ответа нет — реализуем вариант 3, как в задании на план.
- Пометить в отчёте impl: «OQ-23.1 закрыт вариантом 3, ждать подтверждения Саши».

### OQ-23.2 reallocate на insert

- **Вариант 1 в том же раунде.** Replace без изменений (id прохода 1). Insert: `reallocate_task_ids(minutes_row, next_task_id(target_storage))` только если в минутках есть `<ac:task>`.
- **Тесты:** `test_promote_insert_reallocates_from_next_task_id`, `test_promote_replace_keeps_pass1_task_ids`.
- Не блокер дедупа якоря: replace-path уже каноничен на диске.

### OQ-23.3 левая сторона body_diff

- **Вариант 1 в том же раунде.** Sidecar `.td1.html` при ingest = тело хеша прохода 1. `_record_promote_diffs` читает его, а не текущую td1. Persist файла proposal — только после успешного PUT.
- **Тесты:** `test_ingest_writes_sidecar_td1_and_hash`, `test_live_promote_writes_one_proposal_and_registry_fields` (непустой diff при разном left/right).
- Не замораживать текущий пустой дифф как канон.

### OQ-23.4 learner reader

- **Вариант 2.** Запись журнала канонична (шаг B). `propose_pfs_dedup_from_registry` **не** расширять. Тест «без -y не пишет канон / entities.json». Reader — отдельная команда после «переключаем», не блокер ingest/promote.

---

## 8. ЗАПРЕТЫ ИСПОЛНИТЕЛЮ

- Не писать код в фазе, которая ещё plan (этот файл — артефакт plan).
- Не «улучшать» резолв цели и не подставлять `route_page_id_at_publish` как цель.
- Не переносить функции merger в `storage_xml.py`.
- Не включать ingest в autouse-тестах без явного `delenv`.
- Не писать в прод `GoldProtocols/` и `_proposals/` из тестов.
- Не создавать USERTOOL, скилл, крон, дашборд, TG-блок §15 для промоута.
- Не править ТЗ.
- Коммит — только по отдельной команде Саши.
