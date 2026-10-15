# План HF:impl — §24 пост-switch контур (pfs-notify-route-bugs)

Кейс: **BUGFIX / DEV/pfs-notify-route-bugs**. Фаза: **HF:plan**. Архитектор: cursor-grok-4.6-high.
Исполнитель следующих фаз: composer-2.5. Код в этой фазе **не** писать.

Канон: `WorkVault/Hermes-Backlog/TZ/ProtocolFromSummary/ProtocolFromSummary_TZ.md` v1.17.0 §24
(+ синхронизированные абзацы §23 про DedupChecker на промоуте и `notified`).
Диагноз: `_fix_plan_20260923.md` (K1–K4). Режим: **one-pass** — план приводит к итоговой
рекомендации; цивилизованные развилки помечены блоком «Развилка» + рекомендация.
Рабочая директория: `/home/tkachenkoav/USERTOOLS/ProtocolFromSummary`.

---

## 0. РЕЗЮМЕ ДИСКА (не переписывать работающее)

| Место | Факт с диска (проверено чтением) | Баг §24 |
|---|---|---|
| `config.py` | Есть `PLAYGROUND_PAGE_ID = "523032632"`. `PFS_PLAYGROUND_INGEST_OFF` **не** вынесен в config — inline в `pipeline.py:586–591`. `PFS_POST_SWITCH` **нет**. | П.1 флаг |
| `pipeline.py:185` `run_pilot` = тело публикатора; `protocol_publish:774–797` — тонкий alias, сигнатуру не ломать | GET `route.page_id` `:283–295` → DedupChecker `:344–375` → merge в `new_storage` `:408–471` → **K1** `confluence.update_page(route.page_id, …)` `:487` → **K2** `RegistryEntry(page_id=route.page_id)` `:520–522` → property upsert `:561–568` → **K4** ingest-тень `:585–606` | П.1–П.3 |
| `pipeline.py:344–375` | `DedupChecker` на проходе 1 для не-republish; fail-soft публикует всё | K3 / П.3 |
| `pipeline.py:585–606` | ingest **после** успешного PUT цели; `PFS_PLAYGROUND_INGEST_OFF ∈ {1,true,yes,on}` | K4 |
| `notifier.py:30–32` `build_protocol_url`; `:50–82` `format_notification_markdown` (+ блок дублей); `:98–120` `format_promote_notification`; `:123–134` `format_promote_invalid_target` | Формата «приехала, ждёт разбора» / ссылки на площадку **нет** | П.2 |
| `scripts/notify_pending.py:136–145` | `last_action=="promoted"` → всегда `format_promote_notification` + `entry.page_id` | П.2 молчание успеха |
| `scripts/notify_pending.py:152–175` | `"published"/"republished"` → `build_protocol_url(entry.page_id)` + блок дублей | K2 / симптом 1 |
| `playground_promote.py:39–51` `_resolve_target_page_id_from_cell` | (а) id/href → (б) `parse_target_space_title_from_cell` (нужны **оба** space+title) → forbidden set. Шага (в) title без space **нет** | П.4 |
| `playground_promote.py:166–238` `promote_meeting` | После td3 complete: резолв → strip `:174` → dry_run `:185` → GET цели `:195` → replace/insert `:204–211` → PUT → `notified=False` `:224`. **DedupChecker не вызывается** | П.3 проход 2; `notified` |
| `playground_ingest.py:159–171` `parse_target_space_title_from_cell` | Возвращает пару только если есть и `ri:space-key`, и `ri:content-title`. `render_target_cell:82–88` — **не менять** | П.4 парсер |
| `playground_ingest.py:259–323` `ingest_after_publish` | Сигнатуру не ломать. Snapshot `:321` пишется **только если** `registry.get(meeting_id)` уже есть | порядок put vs ingest |
| `tests/conftest.py:14–17` | autouse `PFS_PLAYGROUND_INGEST_OFF=1` | тесты пост-switch обязаны `delenv` |
| `tests/test_promote_v2.py:224–229` | `test_promote_meeting_does_not_call_dedup_checker` (dry_run, флаг off) | уточнить: только flag off |
| `tests/test_promote_v2.py:305` | живой promote → `notified is False` | при флаге on станет True |
| `dedup.py` | Алгоритм §15 (`check_tasks` / `check_sections` / `check_risks`, `parse_published_rows`, fail-soft). Сигнатуры **не** менять | вызов переносится, не алгоритм |
| `page_merger.py` / `route.py` / `storage_xml.render_row` | Заморожены | не трогать |

**Факт исполнителю нельзя «поправить по памяти»:** `find_page_by_title(space_key, title)` уже есть у `ConfluenceClient` (`ConfluenceSync/confluencesync/confluence_client.py:112`). Клиент **не форкать**. Дефолтный space для шага (в) = литерал **`DPAN`** (как в `tests/test_promote_title_resolve.py:90`).

**Инвариант last_action:** новый подтип прохода 1 (`ingested` / `playground_published`) **не** вводить. Различитель пост-switch: флаг env + `promoted_at is None`. `page_id` в реестре на проходе 1 **остаётся маршрутным** (`route.page_id`), не `523032632`.

---

## 1. ИТОГОВАЯ РЕКОМЕНДАЦИЯ (one-pass)

Собрать kill-switch `PFS_POST_SWITCH` в `config.py` (функция, не module-level bool).
При флаге on проход 1: полный `render_row` без DedupChecker, **без** GET/PUT `route.page_id`,
ingest на `523032632` — единственный Confluence-write; реестр `last_action=published`,
`page_id=route.page_id`, `duplicates_skipped=[]`, `notified=False`. Notify прохода 1 —
ссылка на `PLAYGROUND_PAGE_ID` и текст «протокол приехал, ждёт разбора».
Дедуп §15 — внутри `promote_meeting` после td3 complete и после GET цели, до PUT;
затем существующий структурный strip+replace/insert. Успех promote при флаге on —
`notified=True`, TG молчит. Резолв td2: шаг (в) exact `find_page_by_title("DPAN", title)`.
`.env` / `jobs.json` / Gateway / `route.py` / `page_merger` / `MAIN_TZ_INVENTORY.md` /
автоочистка Кирилла 22/23.09 — вне раунда.

---

## 2. РАЗВИЛКИ (решение зафиксировано для исполнителя)

Где схема допускает цивилизованный выбор — ниже. **Делать рекомендованный вариант.**
Не эскалировать Саше: ТЗ v1.17.0 закрыто, GATE:take-into-work auto-pass.

### Р1. Где жить флагу (чтение env)

| # | Вариант | Комментарий |
|---|---|---|
| **1 (рекомендация)** | `config.env_flag_on(name) -> bool` + `post_switch_enabled()` + `playground_ingest_off()`; множество `{1,true,yes,on}` без регистра. Читать **в момент вызова**, не при импорте модуля | Тесты `monkeypatch.setenv` после импорта; один источник для pipeline / notify / promote |
| 2 | Inline `os.environ.get(...)` в каждом файле, как сейчас у ingest-off | Дубль, легко разъехаться |

Не делать: module-level `PFS_POST_SWITCH = env_flag_on(...)` при импорте — тесты не смогут переключить.

### Р2. GET целевой страницы на проходе 1 при флаге on

Сейчас `run_pilot:283` GET `route.page_id` **до** DedupChecker и PUT. При ошибке GET → `action=error`, ingest не вызывается.

| # | Вариант | Комментарий |
|---|---|---|
| **1 (рекомендация)** | При `post_switch_enabled()` **не** вызывать `get_page(route.page_id)`, **не** строить `new_storage`, **не** `update_page(route.page_id)`, **не** `upsert_page_property_row` | Закрывает K1 целиком; 404 цели не блокирует площадку; layout-check цели уезжает на проход 2 |
| 2 | GET оставить (layout/404), PUT убрать | Мёртвый route блокирует ingest — старая связка one-pass |

`task_id_start` для `render_row`: при флаге on передавать **`1`**. Ingest и так делает `next_task_id(playground)` + `reallocate_task_ids` (`playground_ingest.py:289–291`).

Ветка `append_to_existing_date_row` / sync_aid merge (`pipeline.py:408–471`) при флаге on **не выполняется** (это мутация целевого storage).

### Р3. Порядок registry.put vs ingest (пост-switch)

Сейчас ingest после PUT цели и после `registry.put(published)`. Snapshot first-pass пишется только если запись уже в реестре (`playground_ingest.py:313–321`). ТЗ: ingest-ошибка при флаге on = ошибка прохода 1, `published` не ставить.

| # | Вариант | Комментарий |
|---|---|---|
| **1 (рекомендация)** | Сначала `ingest_after_publish` (сигнатуру не менять). Если `action ∈ {"inserted", "skipped_present"}` — затем `registry.put` с `last_action=published` (или `republished` при `confirm_republish`), `duplicates_skipped=[]`, `notified=False`, `page_id=route.page_id`, `playground_ingested_at`/`first_pass_hash`/`route_page_id_at_publish`. Если `action=="error"` или исключение — `PublishResult.action="error"`, реестр **не** писать `published`, `log.warning` + существующий ErrorBus-путь (`REPORT_ERROR_SH` / тот же стиль, что `_report_pfs_route_dead`, stage=`ingest`) | Нет гонки notify до появления строки на площадке |
| 2 | put published, потом ingest, при fail — откат last_action | Гонка с кроном `pfs_notify` |

Доп. правка ingest **без смены сигнатуры:** `_write_first_pass_snapshot` вызывать при `action=inserted` даже если `entry is None` (сейчас snapshot завязан на `if entry is not None`). Иначе при порядке «ingest → put» sidecar не появится. `skipped_present` — snapshot не обязателен (строка уже была).

`ingest_after_publish` при существующей записи обновляет `playground_ingested_at` — если записи ещё нет, pipeline сам проставляет поля при `put`.

### Р4. Текст TG «приехала, ждёт разбора»

| # | Вариант | Комментарий |
|---|---|---|
| **1 (рекомендация)** | Новая `format_ingest_notification(...)` в `notifier.py`. Markdown, как `format_notification_markdown`. 2 строки: дата; `📌 [title](playground_url) — протокол приехал, ждёт разбора`. **Без** `duplicates_skipped`. `format_notification_markdown` не трогать (регресс флага off) | Отдельный контракт, не ломает §5 |
| 2 | Флаг-параметр в существующей функции | Риск сломать точный 2-строчный тест |

URL: `build_protocol_url(PLAYGROUND_PAGE_ID)` → `pageId=523032632`. Не из `entry.page_id`.

### Р5. `last_action` при confirm_republish + пост-switch

| # | Вариант | Комментарий |
|---|---|---|
| **1 (рекомендация)** | Первичный ingest → `published`; `confirm_republish` → `republished` (enum без новых значений). Notify: **оба** + `promoted_at is None` + флаг on → формат ingest на площадку | «Новый подтип не вводить» ≠ запрет существующего `republished` |
| 2 | Всегда `published` даже на republish | Ломает смысл `republished` без выигрыша |

Republish при флаге on **не** делает replace на цели. Если якорь уже на площадке → `skipped_present` = успех прохода 1 (ТЗ). **Не** добавлять replace-by-anchor на площадке в этом раунде.

### Р6. Как скормить DedupChecker XML прохода 2

`check_tasks` ждёт `list[tuple[MeetingTask, ResolvedParticipant\|list, date]]`, не XML.

| # | Вариант | Комментарий |
|---|---|---|
| **1 (рекомендация)** | Приватный адаптер в `playground_promote.py` (не менять `dedup.py`): `parse_published_rows` по `minutes_row` (обернуть в `<table>…</table>` если нужно) → синтетические `(MeetingTask(text=…, assignee_raw=userkey or "", deadline_raw=None), ResolvedParticipant(raw=…, userkey=…, resolved=bool(userkey)), meeting_date)` → `check_tasks` / `check_sections` / `check_risks` против истории **цели**. Затем вычистить из `minutes_row` XML дубли (`<ac:task>` / `<li>` секций), чьи тексты попали в `DuplicateInfo` | Алгоритм §15 живой; merger/storage_xml не трогаем |
| 2 | Пере-парсить исходный summary | Потеряет правки Саши на площадке |

**Самосовпадение (отпечаток K1 на цели):** перед `parse_published_rows(target_storage)` из **локальной копии** HTML убрать `<tr>` текущего `row_anchor` (через `find_row_by_anchor` + вырезание строки; **не** `remove_row_by_anchor` на живой странице, **не** PUT удаления). Иначе Kirill 22/23.09 просеется сам в себя и на цель уедет пустое тело.

`llm_fn` на промоуте: тот же `_dedup_llm_fn` из `pipeline` (ленивый import внутри promote, чтобы не плодить циклы `promote → pipeline → promote`). Fail-soft: исключение DedupChecker → WARN, промоутить `minutes_row` как есть, PUT жив.

Порядок внутри `promote_meeting` при флаге **on** (после td3 complete):

1. Резолв td2 (с новым шагом в).
2. `strip_playground_to_minutes_row` (как сейчас `:174`).
3. GET цели (нужна история). Исключение GET → `_apply_invalid_target`, как сейчас.
4. DedupChecker против истории цели за `meeting_date - 3 weeks` (исключая свой якорь).
5. `dry_run`: вернуть `action=promoted` **без** PUT и **без** записи реестра; DedupChecker на dry_run при флаге on **вызывается** (read-only GET).
6. Структурный слой: `replace_row_by_anchor` / `insert_row_chronological` — **как сейчас** `:204–211` (сигнатуры merger не менять).
7. PUT → журнал → реестр: `last_action=promoted`, `notified=True` (флаг on) / `False` (флаг off).

При флаге **off**: ветка DedupChecker в promote **не** выполняется (`test_promote_meeting_does_not_call_dedup_checker` остаётся зелёным). `notified=False` как сейчас.

### Р7. Константа дефолтного space

| # | Вариант | Комментарий |
|---|---|---|
| **1 (рекомендация)** | `config.DEFAULT_CONFLUENCE_SPACE = "DPAN"` | Совпадает с тестами v1.15.0; новый env не плодить |
| 2 | Env `PFS_DEFAULT_SPACE` | Лишний переключатель вне ТЗ |

---

## 3. ИЗМЕНЯЕМЫЕ ФАЙЛЫ КОДА

Общие правила исполнителя: сигнатуры `protocol_publish` / `run_pilot` / `process_pending` / `ingest_after_publish` / `promote_meeting` / `second_pass_all` / `copy_meeting_to_page` / `page_merger.*` **не ломать**. `.env` не писать. `ConfluenceClient` не форкать.

### 3.1. `protocolfromsummary/config.py`

**Роль:** П.1 §24 — единственное место определения флага и дефолтного space.

**Не трогать:** `ROUTES` / `_load_routes_from_registry` / `PLAYGROUND_PAGE_ID` / LLM-блок.

**Правки:**

1. После `PLAYGROUND_PAGE_ID = "523032632"` (сейчас строка 26):

```python
_TRUTHY_ENV = frozenset({"1", "true", "yes", "on"})

def env_flag_on(name: str) -> bool:
    """True если env `name` ∈ {1,true,yes,on} без регистра; иначе False (в т.ч. unset)."""
    return os.environ.get(name, "").strip().lower() in _TRUTHY_ENV

def post_switch_enabled() -> bool:
    """Kill-switch прямой публикации на route.page_id (§24). Дефолт off."""
    return env_flag_on("PFS_POST_SWITCH")

def playground_ingest_off() -> bool:
    return env_flag_on("PFS_PLAYGROUND_INGEST_OFF")

DEFAULT_CONFLUENCE_SPACE = "DPAN"
```

2. В `.env` / `jobs.json` **не** писать `PFS_POST_SWITCH` (включение — отдельная команда «переключаем»).

**Сигнатуры:** три новые функции, без ломки существующих.

**Точка проверки:** `post_switch_enabled()` False при unset/`0`/`false`/`off`/мусоре; True при `1`/`TRUE`/`Yes`/`on`.

---

### 3.2. `protocolfromsummary/pipeline.py`

**Роль:** закрыть K1/K3/K4 на проходе 1. Функция-тело: `run_pilot` `:185`. Alias `protocol_publish` `:774` не дублировать логику.

**Не трогать:** сигнатуру `run_pilot`/`protocol_publish`/`process_pending`; `copy_meeting_to_page`; `row_anchor_for`; цикл `process_pending` + `second_pass_all` (уже канон §23).

**Импорт:** `post_switch_enabled`, `playground_ingest_off` из `.config` (и `PLAYGROUND_PAGE_ID` не обязателен здесь).

**Правки в `run_pilot`:**

1. **Сразу после** резолва задач (`:282`, перед GET `:283`) прочитать флаги:

```text
post_switch = post_switch_enabled()
ingest_off = playground_ingest_off()
```

2. **Сочетание on+on** (ТЗ 1.3): `log.warning` с обоими именами флагов; `return PublishResult(..., action="error", error="PFS_POST_SWITCH with PFS_PLAYGROUND_INGEST_OFF: nowhere to write")`. Ни GET, ни `update_page`, ни ingest, ни `registry.put` с `published`.

3. **Ветка `post_switch` (флаг on, ingest не off):**

   - **Не** входить в GET `:283–295`.
   - DedupChecker `:335–375` **не** вызывать: `unique_tasks = resolved_tasks`, то же для decisions/blockers/risks, `all_duplicates = []`.
   - `render_row` / `render_content_block` как сейчас, `task_id_start=1` (и republish: если `old_row_task_ids` — `min(old_row_task_ids)`, чтобы id прохода 1 в `row_task_ids` реестра совпали с каноном strip).
   - Блок merge `:408–471` и `update_page(route.page_id)` `:486–494` и `upsert_page_property_row` `:561–573` — **пропустить**.
   - `dry_run`: `PublishResult(action=published|republished, page_id=route.page_id, row_xml=row_xml, version_*=None)` без ingest и без реестра — как нынешний dry_run по смыслу «нет side-effect».
   - Живой путь: вызвать `ingest_after_publish` (K4 становится основным) с теми же аргументами, что `:596–604` (`target_page_id=route.page_id` — это td2, не id площадки).
     - `inserted` / `skipped_present` → собрать `RegistryEntry` как `:520–553`, но `duplicates_skipped=[]`, `notified=False`, `page_id=route.page_id`, `last_action=action` (`published`/`republished`), проставить `playground_ingested_at` / `first_pass_hash` (если ingest их не записал из-за отсутствия entry), `route_page_id_at_publish` иммутабелен с первого ingest.
     - `error` / исключение → `action="error"`, `published` не ставить, warning + ErrorBus.
   - `PublishResult.page_id` по-прежнему `route.page_id` (не площадка).

4. **Ветка флага off:** бит-в-бит текущий контур. Единственная косметика: `playground_ingest_off()` вместо inline `:586–591`. DedupChecker на проходе 1 жив. Ingest-тень после PUT цели — как сейчас, fail-soft (ошибка ingest **не** откатывает published).

**Сигнатуры:** без изменений.

**Точки проверки:** `update_page` с `route.page_id` не вызывался при флаге on; `update_page` с `PLAYGROUND_PAGE_ID` (внутри ingest) вызывался; реестр `page_id == route.page_id`; `duplicates_skipped == []`.

---

### 3.3. `protocolfromsummary/notifier.py`

**Роль:** П.2 формат прохода 1 post-switch.

**Не трогать:** `format_notification`, `format_notification_markdown`, `format_promote_notification`, `format_promote_invalid_target`, `notify_telegram`, `build_protocol_url`.

**Правка:** добавить функцию (имя зафиксировать):

```python
def format_ingest_notification(
    meeting_date: date,
    meeting_time: str | None,
    meeting_title: str,
    protocol_url: str,
) -> str:
```

Поведение — см. Р4.1. Импорт `PLAYGROUND_PAGE_ID` в notifier **не** обязателен: URL собирает вызывающий через `build_protocol_url(PLAYGROUND_PAGE_ID)`.

**Сигнатура:** новая функция; старые без изменений.

**Точка проверки:** URL содержит `pageId=523032632`; подстрока «протокол приехал, ждёт разбора»; нет «Пропущены дубли».

---

### 3.4. `scripts/notify_pending.py`

**Роль:** маршрутизация текста. Крон/`jobs.json` не менять.

**Импорт:** `format_ingest_notification`; `post_switch_enabled`, `PLAYGROUND_PAGE_ID` из config.

**Правки в `build_text_for_entry` `:115`:**

1. Ветка `last_action == "promoted"` (`:136–145`):
   - если `post_switch_enabled()` → **`return None`** (не слать `format_promote_notification`). Дубль защиты: `promote_meeting` уже ставит `notified=True`, такие записи не попадут в pending; `None` страхует ручной `notified=False`.
   - иначе — как сейчас.

2. Ветка `promote_invalid_target` (`:147–150`) — **без изменений**.

3. Ветка published/republished (`:152–175`):
   - если `post_switch_enabled()` и `getattr(entry, "promoted_at", None) in (None, "")`:
     `protocol_url = build_protocol_url(PLAYGROUND_PAGE_ID)`;
     `return format_ingest_notification(...)` — **без** `duplicates_skipped`.
   - иначе — текущий `format_notification_markdown` + `entry.page_id` + блок дублей.

**Сигнатуры:** `build_text_for_entry(entry)` без изменений.

**Точка проверки:** published + флаг on + `promoted_at is None` → в тексте `523032632`, нет `508804979` (если page_id записи целевой); promoted + флаг on → `None`/нет stdout успеха.

---

### 3.5. `protocolfromsummary/playground_ingest.py`

**Роль:** парсер шага (в); snapshot при ingest-first. `render_target_cell` **не менять**.

**Не трогать:** `render_target_cell`, `ingest_after_publish` **сигнатуру**, `strip_playground_to_minutes_row`, `parse_target_page_id_from_cell`, поведение `parse_target_space_title_from_cell` (по-прежнему только пара space+title).

**Правки:**

1. Новая чистая функция (без I/O):

```python
def parse_target_title_from_cell(cell_html: str) -> str | None:
    """ri:content-title даже без space-key/content-id. html.unescape. Пустой → None."""
```

Реализовать через уже существующий `_CONTENT_TITLE_RE` + `unescape`, как в `parse_target_space_title_from_cell:167`. Не резолвить aliases/`display_name`. Plain-текст без `ri:content-title` → `None` (регресс `test_no_resolve_by_plain_display_name_alias`).

2. `ingest_after_publish`: при успешном `inserted` вызывать `_write_first_pass_snapshot` **даже если** `entry is None`. Блок обновления реестра оставить под `if entry is not None`.

**Сигнатуры публичных функций ingest — без ломки; только добавление `parse_target_title_from_cell`.**

---

### 3.6. `protocolfromsummary/playground_promote.py`

**Роль:** П.3 дедуп на проходе 2; П.4 шаг (в); `notified=True` при успехе post-switch.

**Не трогать:** `_FORBIDDEN_TARGET_PAGE_IDS`; `_apply_invalid_target`; `_record_promote_diffs`; сигнатуры `promote_meeting` / `second_pass_all`; вызовы `remove_row_by_anchor` (их нет и не добавлять на живую цель); `copy_meeting_to_page`; `render_target_cell`; подстановку `route_page_id_at_publish` в резолв.

**Импорты:** `DedupChecker`, `parse_published_rows` из `.dedup`; `DEFAULT_CONFLUENCE_SPACE`, `post_switch_enabled` из `.config`; `parse_target_title_from_cell` из `.playground_ingest`; `MeetingTask` / `ResolvedParticipant` для адаптера.

**Правки:**

1. **`_resolve_target_page_id_from_cell` `:39–51`** — расширить иерархию, не ломая (а)(б) и forbidden:

   | Шаг | Код |
   |---|---|
   | (а) | `parse_target_page_id_from_cell` — как сейчас |
   | (б) | `parse_target_space_title_from_cell` → `confluence.find_page_by_title(space_key, title)` exact — как сейчас |
   | **(в) NEW** | если (а)(б) пусты: `title = parse_target_title_from_cell(cell)`; если title: `find_page_by_title(DEFAULT_CONFLUENCE_SPACE, title)` exact, тот же клиент |
   | (г) | иначе / 0 результатов / forbidden → `None` → `invalid_target` |

   Запрещено: aliases, `display_name`, `route_page_id_at_publish`, перебор space, fuzzy. `find_page_by_title` звать и в dry-run (уже так для шага б).

2. **`promote_meeting`** — вставить семантический дедуп только при `post_switch_enabled()`, **после** td3 complete и strip, **после** успешного GET цели, **до** replace/insert/PUT. Порядок — Р6. Адаптер и вычищение XML — приватные функции в этом файле (`_tasks_from_minutes_row`, `_dedup_minutes_row_against_target`). Ошибка → `log.warning`, тело без фильтра.

   Для dry_run + флаг on: GET цели (read-only) + DedupChecker, **без** PUT / без `registry.put` успеха.

   Для флага off: не вызывать DedupChecker; dry_run как сейчас (return до GET цели) — чтобы `test_promote_meeting_does_not_call_dedup_checker` остался валиден.

3. **Реестр успеха** `:221–231`: `entry.notified = True` если `post_switch_enabled()` else `False`. `last_action="promoted"` без изменений. `duplicates_skipped` при пост-switch **записать** сериализованный список с прохода 2 (ТЗ §23: «результат пишется в duplicates_skipped»; TG-блок всё равно не уйдёт из-за молчания). При флаге off поле на промоуте не пересчитывать.

**Сигнатура `promote_meeting` без изменений.**

**Точки проверки:** title без space → один вызов `find_page_by_title("DPAN", title)`; miss `kirill_1on1` → `invalid_target`; exact title минуток → не `invalid_target`; `DedupChecker.check_tasks` called при флаге on; `count(row_anchor)==1` при уже лежащей строке.

---

### 3.7. `protocolfromsummary/dedup.py`

**Не менять.** Алгоритм §15 и сигнатуры `DedupChecker.*` / `parse_published_rows` остаются. Вызов переезжает в promote, не реализация.

---

### 3.8. Файлы, которые **не** меняем

| Файл | Почему |
|---|---|
| `route.py` | Запрет ТЗ |
| `page_merger.py` | Сигнатуры заморожены |
| `storage_xml.py` | `render_row` as-is |
| `registry.py` | Поля уже есть; enum last_action не расширять |
| `__main__.py` | CLI promote/run-pending без новых флагов в argv (env достаточен) |
| `jobs.json`, `.env`, Gateway, `EcosystemManifest.json` | Запрет; PFS_POST_SWITCH только по «переключаем» |
| `MAIN_TZ_INVENTORY.md` | Фаза TZ:finalize |
| `copy_meeting_to_page` / МЕХАНИЗМ А | Вне scope |
| `ConfluenceClient` | Не форкать |
| Автоудаление строк с `508804979` | Только по отдельному ОК Саши, не этот раунд |

---

## 4. ТЕСТЫ

Каталог: `tests/`. Маркер `"not live_confluence"`. `PROPOSALS_DIR` / `GOLD_PROTOCOLS_DIR` → `tmp_path` в живых promote/ingest тестах (как `_patch_dirs` в `test_promote_v2.py`).

`conftest.py` autouse **не** ставить `PFS_POST_SWITCH`. Тесты пост-switch сами `monkeypatch.setenv("PFS_POST_SWITCH", "1")` и `monkeypatch.delenv("PFS_PLAYGROUND_INGEST_OFF", raising=False)` когда нужен реальный ingest.

### 4.1. Новый файл `tests/test_post_switch.py`

Имена из §24 + критерии 2–3 флага:

| Тест | Что проверяет | Как |
|---|---|---|
| `test_post_switch_skips_direct_publish` | §24.1 | `PFS_POST_SWITCH=1`, delenv ingest-off. Mock confluence: `get_page`/`update_page` различают page_id. `protocol_publish`/`run_pilot` → `update_page` **не** звался с `route.page_id`; `update_page` звался с `"523032632"`; реестр `last_action=="published"`, `page_id == route.page_id` (для Кирилла — `508804979`), `duplicates_skipped==[]`, `notified is False`. Хелперы store/summary — как `test_pipeline_dedup.py` |
| `test_post_switch_flag_off_keeps_direct_publish` | регресс unset/`0`/`false` | Три параметризации: unset, `"0"`, `"false"`. `update_page(route.page_id)` вызван (autouse ingest-off можно оставить — проверяем прямую ветку, не ingest) |
| `test_post_switch_and_ingest_off_writes_nowhere` | §24.1 п.3 | Оба флага on. `update_page` assert_not_called; `registry.get` is None или last_action не published; `action=="error"` |
| `test_dedup_not_run_on_pass1_post_switch` | §24.3 | patch `DedupChecker.check_tasks` / конструктор. Флаг on, delenv ingest-off. После `run_pilot` checker **не** создавался / `check_tasks` not called. `render_row` получил полный набор decisions/tasks (не отфильтрованный, в отличие от `test_dedup_filters_fuzzy_duplicate_decision`) |

### 4.2. `tests/test_notify_pending.py` + `tests/test_notifier.py`

| Тест | Куда | Критерий |
|---|---|---|
| `test_notify_ingest_points_to_playground` | `test_notify_pending.py` | entry `last_action=published`, `page_id="508804979"`, `promoted_at=None`, `monkeypatch.setenv PFS_POST_SWITCH=1` → текст содержит `523032632`, **не** содержит `508804979`, содержит «протокол приехал, ждёт разбора», нет «Пропущены дубли» |
| `test_notify_published_flag_off_still_uses_entry_page_id` | регресс | флаг off → URL с `entry.page_id` |
| `test_notify_promote_success_silent_when_post_switch` | `test_notify_pending.py` | `last_action=promoted`, флаг on → `build_text_for_entry` is None; `main()` не печатает «обновлено на чистовой» |
| `test_notify_promote_invalid_target_unchanged` | регресс | `last_action=promote_invalid_target` → `format_promote_invalid_target`, есть «невалидная цель», независимо от флага |
| `test_format_ingest_notification_layout` | `test_notifier.py` | точные 2 строки Markdown + фраза |

Существующие `test_build_text_for_published_entry` / republished — зелёные при флаге off (дефолт).

### 4.3. `tests/test_promote_title_resolve.py` (дописать, таблицу v1.15.0 не переписывать)

Хелпер UI-ячейки без space (рядом с `_ui_target_cell`):

```python
def _title_only_target_cell(title: str) -> str:
    inner = f'<ac:link><ri:page ri:content-title="{title}" /></ac:link>'
    ...
```

| Тест | Критерий |
|---|---|
| `test_promote_title_without_space_key` | td2 только `ri:content-title="Парсинг-К: Задачи"` без space → `find_page_by_title("DPAN", "Парсинг-К: Задачи")`; mock miss → `action=="invalid_target"`, `update_page` not called. Отдельный под-кейс hit → dry_run `promoted` |
| `test_promote_kirill_2209_target_resolves` | mock `find_page_by_title("DPAN", "Кирилл 1-1")` → `{"id": "508804979"}`; td2 title-only `"Кирилл 1-1"` → резолв годен (`action=="promoted"` на dry_run), **не** `invalid_target` из-за отсутствия space-key |
| `test_promote_kirill_entity_slug_is_invalid_target` | `ri:content-title="kirill_1on1"` + mock `find_page_by_title` → `None` → `invalid_target` (сущность ≠ title минуток). Не подставлять `508804979` из маршрута |

Регресс v1.15.0 без правок ожиданий: ingest-id, UI space+title, miss, excluded, playground, empty td2, plain alias. Если на диске появится кейс «только title → сразу invalid без lookup» — **обновить ожидание** на exact default-space lookup (ТЗ §24 прямо разрешает).

### 4.4. `tests/test_promote_v2.py` (регресс + дедуп прохода 2)

| Тест | Действие |
|---|---|
| `test_promote_meeting_does_not_call_dedup_checker` | Оставить. Явно: флаг off (не setenv). Комментарий: «только контур §15» |
| `test_promote_dedup_runs_on_pass2_post_switch` | **NEW.** `PFS_POST_SWITCH=1`. Живой (не только dry_run) путь с мок-историей цели за 3 недели. patch `DedupChecker.check_tasks` **assert_called**. После PUT `storage.count(row_anchor)==1` |
| `test_promote_anchor_already_on_target_replaces_not_inserts` | **NEW** (пострадавшие данные, мок). Якорь уже в `target_storage`; promote → `count(anchor)==1`, не вторая `<tr>`. Live-очистку 508804979 **не** делать |
| `test_live_promote_writes_one_proposal_and_registry_fields` | При флаге off оставить `notified is False`. Добавить близнец или parametrize: флаг on → `notified is True` |
| `test_promote_dedup_fail_soft_still_puts` | **NEW.** `check_tasks` side_effect=RuntimeError → PUT всё же был, `action=="promoted"`, warning-путь |

### 4.5. Регресс существующих наборов (не ломать, прогнать целиком)

| Файл | Зачем |
|---|---|
| `tests/test_pipeline_dedup.py` | Флаг off: fuzzy на проходе 1 жив, `duplicates_skipped` сериализуется |
| `tests/test_playground_ingest.py` | 4col, strip, ingest skipped_present |
| `tests/test_process_pending.py` | `second_pass_all` при пустом каталоге; fail-soft; сигнатура process_pending |
| `tests/test_notify_pending.py` | limit/historical/stale/dry-run |
| `tests/test_pipeline_notify.py` | `is_one_on_one` в render_row |
| `tests/test_link_n_dedup_transition.py` | переходный контур, delenv ingest-off где нужно |
| `tests/test_promote_v2.py` | insert-reallocate, journal, sticky invalid_target, invariant #12 |

Новых пакетов, CLI-команд, кронов, USERTOOL **нет**.

---

## 5. ПОСТРАДАВШИЕ ДАННЫЕ (не код)

Кирилл 22.09 и 23.09: якоря уже на `508804979` (прямой отпечаток K1, `promoted_at=null`) и на площадке. **Автоудаление с цели в реализацию не входит.** После фикса: повторный promote с корректным td2 (exact title «Кирилл 1-1» / id / space+title, **не** `kirill_1on1`) сделает `replace_row_by_anchor`, не вторую строку. Очистка цели — отдельный ОК Саши.

---

## 6. ПОРЯДОК РЕАЛИЗАЦИИ ДЛЯ ИСПОЛНИТЕЛЯ

1. `config.py` — флаг + `DEFAULT_CONFLUENCE_SPACE` + маленький unit в `test_post_switch.py` или `test_config_llm.py`.
2. `playground_ingest.py` — `parse_target_title_from_cell` + snapshot без entry.
3. `pipeline.py` — ветка пост-switch (K1/K3/K4) + dual-flag error.
4. `notifier.py` + `notify_pending.py` — формат и маршруты.
5. `playground_promote.py` — шаг (в) резолва, затем DedupChecker + `notified`.
6. Тесты §24 + правки регресса `test_promote_v2` / title-resolve.
7. `python -m pytest -q -m "not live_confluence"` — зелёный.

Промежуточные точки — молча, без отчётов Саше.

---

## 7. ТОЧКИ ПРОВЕРКИ (критерии приёмки кода)

Исполнитель отмечает чекбоксы по факту прогона (не Саша).

- [x] `PFS_POST_SWITCH=1` → нет `update_page(route.page_id)` (в т.ч. republish); ingest на `523032632` есть; реестр `published` + маршрутный `page_id` + `duplicates_skipped=[]`
- [x] Флаг unset/`0`/`false` → прямая публикация жива
- [x] Оба флага on → нет PUT ни цели, ни площадки; `published` нет
- [x] Notify прохода 1 post-switch → URL `523032632`, текст «протокол приехал, ждёт разбора», без блока дублей
- [x] Promote успех + флаг on → `notified=True`, `format_promote_notification` не уходит
- [x] `promote_invalid_target` → формат без изменений
- [x] Pass 1 + флаг on → `DedupChecker` не вызван
- [x] Pass 2 + флаг on → `DedupChecker.check_tasks` вызван (мок истории цели, 3 недели); fail-soft не стопит PUT
- [x] Якорь уже на цели → после promote `count(row_anchor)==1`
- [x] Title без space → `find_page_by_title("DPAN", title)`; miss → `invalid_target`; `kirill_1on1` → `invalid_target`; «Кирилл 1-1» + mock hit → резолв годен
- [x] `python -m pytest -q -m "not live_confluence"` зелёный (389 passed, 4 deselected)
- [x] Diff не содержит `route.py`, `page_merger.py`, `.env`, `jobs.json`, `MAIN_TZ_INVENTORY.md`, Gateway, нового значения enum `last_action`

Live-приёмка (`run-pending` на новой встрече Кирилла) — **после** команды «переключаем» (запись `.env`), не в этом HF:impl.

---

## 8. КАРТА §24 → ФАЙЛ

| Пункт §24 | Файл / функция | Якорь на диске |
|---|---|---|
| 1. Флаг `PFS_POST_SWITCH` | `config.env_flag_on` / `post_switch_enabled` | новый, рядом с `PLAYGROUND_PAGE_ID:26` |
| 2. Проход 1 только ingest | `pipeline.run_pilot` | K1 `:487`; K2 `:522`; K4 `:585–606`; GET `:283`; merge `:408–471` |
| 2. Dual-flag warning | `run_pilot` до GET | перед `:283` |
| 3. Notify площадка / молчание promote | `notifier.format_ingest_notification`; `notify_pending.build_text_for_entry` | `:152` published; `:136` promoted |
| 4. Дедуп только проход 2 | `run_pilot:344–375` skip; `promote_meeting` после strip+GET цели | promote `:166–211` |
| 5. Title без space | `parse_target_title_from_cell`; `_resolve_target_page_id_from_cell:39–51` | ingest `:159–171` не ломать |
| 6. Данные Кирилла | не код | §5 плана |

---

## Прогресс выполнения

- [x] HF:plan — этот файл
- [x] config.py — флаг
- [x] pipeline.py — пост-switch проход 1
- [x] notifier.py + notify_pending.py
- [x] playground_ingest.py — title parser + snapshot
- [x] playground_promote.py — резолв (в) + DedupChecker + notified
- [x] tests §24 + регресс
- [x] pytest `-m "not live_confluence"` зелёный (389 passed, 4 deselected)
