### Контракты прохода 1–2 (дельта v2, поверх §22 / фикса v1.15.0)

Накопительная дельта DEV-корня `protocol-from-summary-v2`. Не переписывает
бриф Q1–Q7, шаги 1–13, post-switch target и подсекцию «Промоут прохода 2:
резолв цели по title+space (BUGFIX, 22.09, v1.15.0)». Канонизирует четыре
контракта, которых в §22 не хватает как first-class: проход 2 (promote),
дедуп на промоуте, журнал дублей промоута, ingest-матчинг на площадке.

Reuse-first: новых USERTOOL / приложений / сущностей нет. Писатель —
пакет `protocolfromsummary`; канон страниц — Confluence + `_registry.json`;
proposal — уже существующий каталог `WorkVault/Registries/prompts/_proposals/`
(§22 NEW-ENTITY #1, не второй реестр). Layout площадки — переходный 4col
из §22; формальное согласование NEW-ENTITY #3 не закрывается этой дельтой.

Модули (код, не новые инструменты): `playground_ingest.py`,
`playground_promote.py`, поля `RegistryEntry` (§22-блок в `registry.py`),
wiring в `pipeline.py` (`ingest_after_publish` после успешного publish;
`second_pass_all` из `process_pending` / run-pending).

---

#### Проход 2 (promote) — first-class механизм

**Назначение.** Проход 2 — штатный механизм PFS (не админ-исключение §21
и не «скрытый хвост» ingest): переносит обработанную строку площадки
`523032632` на чистовые минутки, указанные в ячейке «Цель (минутки)».
Выдача боевого `protocol_publish` (проход 1) не подменяется: promote
идёт **после** ручного признака «обработано», отдельным вызовом.

**Механика.**

Точки входа (существующие команды не ломать):

```bash
python -m protocolfromsummary promote --meeting-id <id> [--dry-run]
```

- `promote_meeting(meeting_id, *, dry_run=False)` — одна встреча.
- `second_pass_all(*, dry_run=False)` — все записи реестра с
  `row_anchor` и пустым `promoted_at`, у которых на площадке есть 4col
  строка и признак td3 = обработано. Вызов из `process_pending`
  (run-pending) **после** цикла новых publish, в отдельном try/except:
  ошибка прохода 2 не валит batch и не откатывает проход 1.
- Ручной reset `promoted_at` не нужен: крон сам подхватывает пустое
  поле (приёмка фикса v1.15.0).

Предусловия (fail без PUT цели, кроме оговорки dry-run / invalid_target
ниже): запись есть в `_registry.json`; `promoted_at` пуст; `page_id ≠
PLAYGROUND_PAGE_ID` (инвариант #12 — primary никогда не площадка);
строка есть на площадке (`find_row_by_anchor`); строка 4col; td3
обработан (`parse_playground_processed_flag`). Иначе действия:
`already_promoted` / `error` / `not_on_playground` / `skipped` /
`error=not 4col`.

Резолв цели (td2) — **не дублировать** таблицу фикса v1.15.0: порядок
id → title+space → `invalid_target`; парсер без I/O в
`playground_ingest.py`; `find_page_by_title` и в dry-run (read-only API);
без aliases / `display_name` / подстановки `route_page_id_at_publish`.
После финального `target_page_id` — **одна** пост-резолвная проверка
`{PLAYGROUND_PAGE_ID=523032632, EXCLUDED_PAGE_ID_OBSHY_SPISOK=432316254}`
→ `invalid_target` (канон фикса; дырка §1.10 закрыта там же).

`--dry-run` (успешный резолв): Confluence PUT нет; proposal-файл нет;
`promoted_at` / `page_id` / `target_override` / `promote_*_diff` не
пишутся; результат `action=promoted` + `target_page_id` (превью).
`invalid_target` на диске пишется в реестр **до** ветки dry-run
(`last_action=promote_invalid_target`, `notified=False`) — см. OQ-23.1.
Живой проход при `invalid_target`: PUT цели нет; `promoted_at` остаётся
пустым (повтор на следующем тике).

Живой успешный проход (не dry-run): журнал (§ след. подсекция) → GET
цели → дедуп-вставка (§ след. подсекция) → PUT цели → реестр:

| Поле | Значение |
|---|---|
| `promoted_at` | now UTC Z |
| `page_id` | `target_page_id` (primary = чистовая) |
| `last_action` | `"promoted"` |
| `notified` | `False` (notify_pending шлёт `format_promote_notification`) |
| `target_override` | только если `target_page_id ≠ page_id` до промоута: `{from, to, at}` |
| `route_page_id_at_publish` | **не** менять (иммутабельно с прохода 1) |

`last_action=promote_invalid_target` → `format_promote_invalid_target`
(⚠️, без PUT). Смена цели в TG: строка «↪️ цель сменена, на старой
странице осталась строка 1-го прохода».

**N-3.** Source на площадке **не** удаляется (строка 4col остаётся).
`remove_row_by_anchor` на площадке из promote **запрещён**. Если цель
≠ страница прохода 1, боевая строка прохода 1 на старой странице тоже
остаётся. Допускаются **два** `<ac:task>` одной сути до ручного удаления
Сашей в UI или `page move --yes --confirm-move` (§21 Q-21.1). Это контракт
фикса v1.15.0, не баг парсера. Promote ≠ Метод B и ≠ `copy_meeting_to_page`
(МЕХАНИЗМ А копирует весь `<tr>` и плодит чекбоксы — для bind/promote
не использовать, канон §22).

Kill-switch прохода 1 на площадку: `PFS_PLAYGROUND_INGEST_OFF` ∈
`{1,true,yes,on}` (без регистра) отключает ingest после publish; на
проход 2 не действует. Отдельного kill-switch promote нет — `dry_run`
и отсутствие признака «обработано» достаточны.

**Тесты / критерии (атомарно, без live API).**

1. CLI `promote --meeting-id X --dry-run` при валидной цели: `action=promoted`,
   `update_page` не звать, `promoted_at` в реестре пуст.
2. `second_pass_all` из `process_pending`: вызывается даже если новых
   summary нет; исключение внутри — warning, batch не падает.
3. Порядок резолва и запрет PLAYGROUND/EXCLUDED — тесты фикса v1.15.0
   (`test_promote_title_resolve.py`) остаются зелёными; эту таблицу не
   копировать.
4. `page_id == PLAYGROUND_PAGE_ID` → `error` (инвариант #12), PUT нет.
5. td3 incomplete → `skipped`, реестр и цель не трогать.
6. Успешный promote: `notified=False`, `last_action=promoted`; при смене
   цели — `target_override` заполнен, старая страница без PUT
   (`test_promote_target_override_inserts_on_new_page_only`).
7. Diff реализации прохода 2 не содержит `jobs.json`, `.env`, Gateway,
   `route.py`, формулы `row_anchor`.

**Связи.** §22 live: площадка вне ROUTES, ingest строго после publish.
Фикс v1.15.0: резолв + пост-резолвная защита — единственный канон цели.
§21: удаление source только `page move --confirm-move`, не automate.
§1.10: `432316254` никогда не цель автоматики. §15 на проходе 2 **не**
вызывается (следующая подсекция).

---

#### Дедуп на промоуте (не §15)

**Назначение.** На чистовой странице у одной встречи — **одна** `<tr>`
с тем же `row_anchor` и **не больше** набора `<ac:task>` прохода 1
(реестровые `row_task_ids`). Проход 2 не создаёт второй чекбокс «той же
сути» на той же странице. Это **структурный** дедуп якоря/id, не
семантический `DedupChecker`.

**Механика.**

1. С площадки берётся 4col `<tr>`. `strip_playground_to_minutes_row`:
   оставить td0+td1 (дата+якорь и тело); td2/td3 отбросить (цель и
   служебный чекбокс «обработано» на минутки не едут). Если
   `registry_row_task_ids` непуст — в td1 оставить **первые**
   `len(row_task_ids)` штук `<ac:task>`, затем `reallocate_task_ids`
   от `min(row_task_ids)` (вернуть id боевого прохода 1). Лишние
   `<ac:task>`, которые Саша добавил на площадке, **не** промоутятся.
   Служебный task-id td3 в минутки не попадает. `_aid` в строке —
   ошибка, promote стоп.
2. На целевой странице: `find_row_by_anchor(target, row_anchor)`:
   - есть → `replace_row_by_anchor` (та же строка, те же id прохода 1 —
     второй `<ac:task>` не порождается);
   - нет → `insert_row_chronological` по дате строки (свежие сверху,
     канон §1.1). На диске insert идёт с id после strip (id прохода 1),
     без `next_task_id(target)` — см. OQ-23.2.
3. `DedupChecker` / окно 3 недели / fuzzy 80% / LLM fallback / fail-soft
   §15–§18 / intra-summary сито **на промоуте не применяются**. Тело
   td1 после правок Саши едет как есть (решения/блокеры/риски не
   фильтруются). `duplicates_skipped` прохода 1 не пересчитывается.

**Чем это не §15 (зафиксировать различия):**

| | §15 `DedupChecker` | Дедуп на промоуте |
|---|---|---|
| Когда | `protocol_publish` до `render_row` | `promote_meeting` после признака «обработано» |
| Объект | новые задачи/секции vs история страницы за 3 нед. | одна встреча: якорь + `row_task_ids` прохода 1 |
| Алгоритм | fuzzy 80% + LLM, правило open/complete | strip + replace/insert по якорю |
| Fail-soft | ошибка → публиковать всё | ошибка strip → `action=error`, PUT нет |
| Republish | выключен | не применимо (это не republish §1.7) |
| TG «пропущены дубли» | да | нет; журнал промоута — отдельный контракт |
| Intra-summary | не трогает | не трогает |
| Второй `<ac:task>` на **другой** странице (N-3) | вне scope | допускается до ручного удаления |

**Тесты / критерии.**

1. Якорь уже на цели → после promote `count(row_anchor)==1` на цели
   (`test_replace_by_anchor_single_row_on_clean_page`).
2. Якоря нет, цель другая → insert только на цель; source-страница
   прохода 1 без PUT; площадка без DELETE.
3. `strip`: 4col → 2col; task-id служебного чекбокса отсутствует;
   число `<ac:task>` ≤ `len(row_task_ids)`; extras trimmed.
4. Мок: `DedupChecker.check_tasks` на пути `promote_meeting` не звать.
5. Пустые `row_task_ids` → strip без reallocate, минутки без протоколных
   `<ac:task>` (допустим для встреч без задач).

**Связи.** §15 остаётся каноном **только** боевого publish. §22 P0 «два
`<ac:task>`»: на одной целевой странице закрывает эта подсекция; между
страницами — N-3 / фикс v1.15.0. МЕХАНИЗМ А не использовать.

---

#### Журнал дублей промоута

**Назначение.** Артефакт «что изменилось между проходом 1 и строкой
площадки к моменту promote» + «сменилась ли цель». Это журнал для
обучения Контура А, **не** отдельный USERTOOL и не замена
`duplicates_skipped` §15 (тот — семантика сита publish). Proposal-only:
в канон промптов журнал сам не пишет (Q5).

**Механика.**

Пишется только на **живом** успешном пути `promote_meeting` (не dry-run,
не `invalid_target`, не `skipped`). Два слоя одного события:

1. **Файл proposal** (полный текст):
   `WorkVault/Registries/prompts/_proposals/link-n-dedup-promote-<meeting_id>-<YYYYMMDD-HHMMSS>.json`
   Каталог тот же, что learner Контуров 0/А/bind (`learner.py`
   `PROPOSALS_DIR`). Имя префиксом отделяет promote от `ff_summary-*` /
   `pfs_dedup-*` / `task_bind-*`. Поля payload:

   | Ключ | Смысл |
   |---|---|
   | `meeting_id` | id встречи |
   | `body_diff` | unified_diff: эталон прохода 1 → актуальная td1 площадки |
   | `target_diff` | пусто, либо `route_page_id_at_publish=<id> -> target=<id>` |
   | `first_pass_hash` | sha256 тела прохода 1 (нормализованные пробелы) |
   | `note` | `proposal-only для Контура A` |

2. **Поля реестра** (укороченный индекс, `schema_version` `_registry.json`
   остаётся `"1.1"`, поля optional):

   | Поле | Ограничение |
   |---|---|
   | `promote_body_diff` | `body_diff[:8000]` (хвост отбрасывается; полный текст — в файле) |
   | `promote_target_diff` | строка `target_diff` целиком (короткая) |

Эталон левой стороны `body_diff`: snapshot прохода 1
`Meetings/GoldProtocols/<meeting_id>-first-pass.md` (пишет ingest) и/или
тело, с которого посчитан `first_pass_hash`. Правая сторона — td1
площадки **после** правок Саши. Канон назначения — именно этот дифф,
а не дифф td1 с самой собой. Расхождение кода `_record_promote_diffs`
на диске (левая сторона = текущая td1) — impl-gap, не замораживать
как канон (OQ-23.3).

Lifecycle: append-only файлы proposal; реестровые поля перезаписываются
этим promote (повторный promote той же встречи не штатный —
`already_promoted`). Republish прохода 1 **сохраняет** уже записанные
`promote_*_diff` / `first_pass_hash` / `promoted_at` (pipeline
пробрасывает `existing.*`). Удаление proposal — руками / ретенция
каталога `_proposals/`; отдельного GC-инструмента нет.

Кто читает: learner Контура А (`propose_pfs_dedup_from_registry` и
будущие ревизии `pfs_*_dedup`). Канон: besides `duplicates_skipped`,
Контур А **имеет право** читать `promote_body_diff` /
`promote_target_diff` и файлы `link-n-dedup-promote-*.json` как кейсы
«Саша поправил на площадке / сменил цель». На диске learner пока
семплирует только `duplicates_skipped` — расширение reader не новый
инструмент, аддитивный шаг того же модуля (OQ-23.4, не блокер записи
журнала). Контур 0 (`propose_ff_summary`, raw+gold) и bind эти поля
не обязаны читать. TaskRefresh / OFC / OpenTasks журнал не читают.

Нет отдельного USERTOOL «журнал дублей», нет дашборда, нет TG-блока
§15 «Пропущены дубли» для промоута.

**Тесты / критерии.**

1. Живой promote пишет ровно один файл
   `link-n-dedup-promote-<id>-<ts>.json` и заполняет оба поля реестра.
2. `--dry-run` / `skipped` / `already_promoted` — файлов и полей нет.
3. `promote_body_diff` в реестре ≤ 8000 символов при длинном диффе;
   файл proposal без truncate.
4. `target_diff` пуст, если цель = `route_page_id_at_publish`; иначе
   содержит оба id.
5. Learner без `-y` по-прежнему не пишет канон `Registries/prompts/`
   (кроме `_proposals/`) и не пишет `entities.json`.
6. Нет нового пакета/скилла/крона под журнал.

**Связи.** §22 Контур А: эталон минуток vs предложение PFS; журнал
промоута — дополнительный сигнал «правка на площадке». §15
`duplicates_skipped` — другой слой (сито publish). Q5 proposal-only.
NEW-ENTITY #1 (каталог промптов) переиспользуется, не плодится.

---

#### Ingest-матчинг строки на площадке

**Назначение.** Проход 1 не плодит вторую 4col-строку той же встречи на
`523032632`. Площадка — служебная очередь необработанных, **не** боевые
минутки: протоколный `<ac:task>` на ней не является домом задачи в
ROUTES/OpenTasks.

**Механика.**

Вызов: `ingest_after_publish` строго после успешного
`protocol_publish` (`action` ∈ `{published, republished}`), отдельный
try/except в `pipeline.py`. Нет успешного publish — ingest не звать.
Ошибка ingest → `log.warning`, publish не откатывать, статус публикации
не менять (канон §22 порядок publish → ingest). `dry_run` publish →
ingest не звать. Флаг `PFS_PLAYGROUND_INGEST_OFF` — выкл.

Алгоритм (атомарные шаги):

1. GET `PLAYGROUND_PAGE_ID`; N-5: `len(storage) > 4 MB` → warning, не
   блокер.
2. `find_row_by_anchor(storage, row_anchor_for(meeting_id))` не None →
   `action=skipped_present`, PUT нет, реестр/snapshot не трогать
   (идемпотентность; republish не дублирует строку).
3. Иначе: `task_start = next_task_id(storage)`; `n_proto =
   count_task_ids(battle_row_xml)`; перенумеровать копию боевого `<tr>`
   от `task_start`; `processed_task_id = task_start + n_proto`.
4. Собрать 4col: `render_playground_row_from_battle` =
   td0+td1 из боевой строки + `render_target_cell(route.page_id,
   display_name)` + `render_processed_cell(processed_task_id)`.
   Layout (канон §22 переходный 4col, не переопределять enum
   `page_layout`):
   `Дата постановки | Задачи и Договорённости | Цель (минутки) | Обработано`.
   Заголовок — маркеры `_PLAYGROUND_HEADER_MARKERS`; не 2col / не
   `3col_content_last` / не `5col_aid`.
5. `insert_row_chronological(storage, row_xml, date)` — дата из боевой
   строки (`<time datetime>`), не «всегда вверх». PUT площадки.
6. Реестр (если entry есть): `playground_ingested_at = now`;
   `first_pass_hash = sha256(нормализованная td1 боевой строки)`;
   `route_page_id_at_publish` записать **только если пусто** (иммутабельно
   после первого ingest/publish). Snapshot
   `Meetings/GoldProtocols/<meeting_id>-first-pass.md` — текст td1 без
   HTML (ошибка записи файла = warning, ingest уже успешен).
7. Цель в td2 при ingest = страница маршрута (`route.page_id`), ссылка
   title+content-id без space-key (`render_target_cell`). UI Саши может
   переписать в space+title без id — это закрыто **фиксом v1.15.0** на
   проходе 2, ingest из‑за этого не менять (канон фикса: `render_target_cell`
   можно не трогать).

**Инвариант «не боевой дом».** `523032632` нет в ROUTES /
`entities[*].pfs.page_id` (#12). Live `protocol_publish` сюда не пишет.
Единственный **родной** `<ac:task>` площадки — служебный чекбокс td3
«обработано» (`incomplete` при ingest). td1 содержит **копию** тела
прохода 1 (в т.ч. протоколные `<ac:task>` как рабочий текст для правок
Саши), но эта копия не primary: TaskRefresh/теггер смотрят ROUTES-страницы.
Promote снимает служебный чекбокс (`strip`) и кладёт минутки на цель.
Запрещено: назначать площадку `pfs.page_id`; promote **на** площадку
(пост-резолвная защита); рисовать `_aid`. OQ-22.6 (сканирует ли OpenTasks
площадку) **не закрыт** этой дельтой: если макрос сканирует — fail в
сторону текста без протоколного чекбокса (шаг 12 §22), это по-прежнему
требует проверки, не молчаливого «уже решено».

**Тесты / критерии.**

1. Повторный ingest того же `meeting_id` при якоре на площадке →
   `skipped_present`, `update_page` не звать
   (`test_skip_overwrite_playground_on_duplicate_anchor`).
2. Искусственная ошибка ingest не меняет боевую страницу и не откатывает
   `_registry.json` publish (`test_fail_soft_ingest_does_not_break_publish`).
3. 4col: четыре `<td>` / четыре `<th>`; есть служебный `<ac:task>`
   «обработано»; нет `_aid`.
4. `processed_task_id == next_task_id(before) + n_proto`.
5. Хроно-вставка: встреча более старая, чем уже лежащие строки —
   не первая после `<th>`.
6. `route_page_id_at_publish` и `first_pass_hash` не перетираются вторым
   успешным ingest той же встречи (`skipped_present`) и не перетираются
   republish pipeline.
7. `PFS_PLAYGROUND_INGEST_OFF=1` (как `tests/conftest.py`) → ingest не
   вызывается; боевой publish жив.
8. `523032632` отсутствует среди `entities[*].pfs.page_id`.

**Связи.** §22: writer ingest = шаг PFS после publish; layout 4col уже
упомянут; эта подсекция — операционный контракт идемпотентности и id.
Фикс v1.15.0: парсеры `parse_target_page_id_from_cell` /
`parse_target_space_title_from_cell` живут в ingest-модуле, резолв —
в promote. §1.1 / `page_merger.insert_row_chronological` / `next_task_id`
/ `reallocate_task_ids` — reuse as-is, сигнатуры не менять (§21 «Что НЕ
трогать» на merger). §15 на ingest не вызывается (копируется уже
отдедупленный боевой `row_xml`).

---

### Контракты экосистемы (аддендум дельты v2)

Дополнение к корневому разделу и аддендуму §21. При `TZ:finalize` —
влить строки в существующие таблицы, не плодить третий раздел
«Контракты экосистемы».

#### Источник истины
- Владелец боевых строк и полей прохода 1–2: ProtocolFromSummary
  (`_registry.json`; `row_anchor` в storage-html)
- Владелец площадки `523032632`: ProtocolFromSummary (ingest/promote),
  страница вне ROUTES
- Владелец proposal-файлов: ProtocolFromSummary (запись) / learner
  Контура А (чтение); канон промптов пишет только CLI `-y` (§22 Q5)
- Владелец маршрутов: EntityRegistry (`entities.json`, блок `pfs`)

#### Входные контракты
| Поле | Тип | Обязательность | Источник (кто отдаёт) | Формат/enum |
|---|---|---|---|---|
| meeting_id | str | required | MoveFromFF / CLI promote | stem summary |
| row_anchor | str | required | ProtocolFromSummary | pfsrow-{sha256(meeting_id)[:12]} |
| row_task_ids | str | optional | ProtocolFromSummary проход 1 | json-список int, задачи боевой строки |
| td2_target_cell | str | required | площадка 523032632 | ri:content-id/pageId= или ri:space-key+ri:content-title |
| td3_processed | bool | required | площадка 523032632 | ac:task-status complete → promote eligible |
| PFS_PLAYGROUND_INGEST_OFF | str | optional | env | enum[1,true,yes,on] без регистра; дефолт unset=ingest on |

#### Выходные контракты
| Поле | Тип | Потребитель (кто получает) | Формат/enum |
|---|---|---|---|
| RegistryEntry.route_page_id_at_publish | str | promote (target_diff), диагностика | pageId; иммутабельно после первого publish/ingest |
| RegistryEntry.playground_ingested_at | datetime(iso8601) | диагностика | UTC Z; пусто если skipped_present |
| RegistryEntry.promoted_at | datetime(iso8601) | second_pass_all, notify_pending | UTC Z; пусто = ещё не промоут |
| RegistryEntry.first_pass_hash | str | журнал промоута / learner Контура А | sha256 hex тела td1 прохода 1 |
| RegistryEntry.target_override | str | notify_pending, диагностика | json:{from,to,at} либо null |
| RegistryEntry.promote_body_diff | str | learner Контура А | unified_diff, truncate 8000 |
| RegistryEntry.promote_target_diff | str | learner Контура А | пусто или route_page_id_at_publish=… -> target=… |
| RegistryEntry.last_action | enum[published, republished, copied, exported, promoted, promote_invalid_target] | notify_pending | promoted / promote_invalid_target — проход 2 |
| RegistryEntry.notified | bool | notify_pending | после promote/invalid_target = false |
| RegistryEntry.duplicates_skipped | str | learner Контура А, notify_pending | json-список DuplicateInfo §15; проход 2 не пересчитывает |
| proposal_promote_path | str | learner Контура А | Registries/prompts/_proposals/link-n-dedup-promote-<meeting_id>-<ts>.json |
| first_pass_snapshot | str | журнал промоута | Meetings/GoldProtocols/<meeting_id>-first-pass.md |

#### Зависимости
- Получает от: [MoveFromFF, EntityRegistry, ConfluenceSync]
- Отдаёт: [Confluence (площадка + цель), Telegram/notify_pending, learner Контура А (proposal + поля реестра), ErrorBus (fail-soft warning)]

#### Breaking changes policy
- `schema_version` `_registry.json` остаётся `"1.1"`: поля дельты v2
  optional, старые записи читаются с дефолтами dataclass.
- Имя/формула `row_anchor` не меняется.
- При breaking change truncate/полей журнала: уведомить потребителя
  «learner Контура А»; migrate не требуется, пока поля optional.

#### Границы («что НЕ трогать»)
- Не удалять строку площадки и строку прохода 1 из promote (N-3)
- Не вызывать `DedupChecker` на проходе 2
- Не писать `523032632` в `pfs.page_id` / не promote на площадку / не
  писать в `432316254`
- Не менять сигнатуры `page_merger.*` и формулу `row_anchor`
- Не заводить USERTOOL журнала дублей и не auto-apply proposal в канон
  промптов
- Не поднимать YAML `version` / `last-section-added` в этом драфте
  (`TZ:finalize`)
- Gateway, `jobs.json`, `.env` (кроме уже существующего
  `PFS_PLAYGROUND_INGEST_OFF`), `EcosystemManifest.json`

---

### Критерии успеха дельты v2 (сводка, проверяемые)

Каждый пункт — отдельный атом приёмки; реализация кода в этом
`TZ:patch` не выполняется.

1. `promote --meeting-id --dry-run` при валидной цели: превью
   `promoted` + `target_page_id`, без PUT, без `promoted_at`.
2. `second_pass_all` из run-pending fail-soft; пустой `promoted_at` +
   td3 complete → кандидат; reset реестра руками не нужен.
3. Резолв цели и запрет PLAYGROUND/EXCLUDED — без регресса фикса
   v1.15.0.
4. На целевой странице после promote якорь встречается один раз;
   `DedupChecker` не вызывался.
5. N-3: площадка и (при смене цели) страница прохода 1 сохраняют
   строки.
6. Живой promote: proposal-файл + `promote_body_diff` ≤ 8000 +
   `notified=False`.
7. Повторный ingest того же якоря: `skipped_present`.
8. `route_page_id_at_publish` / `first_pass_hash` иммутабельны после
   первого успешного ingest.
9. Площадка 4col; служебный чекбокс только в td3; `_aid` нет;
   `523032632` не в ROUTES.
10. Нет нового USERTOOL, нет правки `MAIN_TZ_INVENTORY.md` в фазе
    `TZ:patch`, нет рестарта Gateway.

---

### Открытые вопросы (OQ-23.x, не блокируют запись канона)

**OQ-23.1. `--dry-run` и запись реестра при `invalid_target`.**
На диске `promote_invalid_target` + `notified=False` пишутся **до**
ветки `dry_run` (тесты фикса это фиксируют). Успешный dry-run реестр
не пишет. Каждый повтор живого `invalid_target` снова ставит
`notified=False` → риск повторного TG на каждом тике run-pending.

1. Оставить как есть (invalid_target всегда side-effect в реестр, даже
   dry-run; retry сбрасывает notified).
2. Dry-run полностью read-only, включая invalid_target; живой retry
   сбрасывает notified только при **смене** `last_action`.
3. Dry-run read-only; живой invalid_target пишет реестр один раз, пока
   Саша не сменит цель (notified не сбрасывать, если уже
   `promote_invalid_target`).

Рекомендация: **вариант 3** (меньше TG-шума, dry-run честный). До ответа
в каноне зафиксирован факт диска (вариант 1 как default поведения кода).

**OQ-23.2. `reallocate_task_ids` при insert на новую страницу.**
Replace по якорю обязан сохранить id прохода 1 (иначе OpenTasks
потеряет чекбокс). Insert на другую страницу на диске тоже несёт id
прохода 1, без `next_task_id(target)` — риск коллизии с чужими
`<ac:task-id>` на цели (id уникальны per-page).

1. Канон: insert → `reallocate_task_ids` от `next_task_id(target)`;
   replace → id прохода 1. Рекомендация.
2. Всегда id прохода 1 (как диск); коллизии чинить руками.
3. Всегда `next_task_id(target)`, даже на replace — **отклонить**
   (ломает identity чекбокса на той же странице).

Рекомендация: **вариант 1**. Не блокер записи дедупа: replace-path
уже каноничен.

**OQ-23.3. Левая сторона `body_diff`.**
Канон назначения журнала — first-pass snapshot vs td1 площадки.
`_record_promote_diffs` на диске сравнивает текущую td1 с ней же
(дифф тела фактически пустой). Нужен ли отдельный BUGFIX после
`TZ:finalize`?

1. Да, закрыть в том же CHANGE/BUGFIX-хвосте, что канон. Рекомендация.
2. Оставить диск; журнал = только `target_diff` + hash.
3. Считать каноном «дифф td1 с собой» — **отклонить** (бессмысленно).

Рекомендация: **вариант 1**.

**OQ-23.4. Когда learner Контура А начинает читать журнал промоута.**
Запись журнала канонична сейчас. Reader в `propose_pfs_dedup_from_registry`
на диске читает только `duplicates_skipped`.

1. Reader — обязательный шаг того же раунда (аддитивно в `learner.py`).
2. Запись канонична; reader — после «переключаем» / отдельной команды.
   Рекомендация: не блокировать ingest/promote ожиданием reader.
3. Не читать никогда, журнал только для глаз Саши в `_proposals/`.

Рекомендация: **вариант 2** (журнал есть, learner подключается явным
шагом, Q5 не ломаем).

Не блокер, не переоткрывать здесь: OQ-22.2 / NEW-ENTITY #3 (формальный
layout), OQ-22.6 (скан OpenTasks площадки) — остаются в §22.