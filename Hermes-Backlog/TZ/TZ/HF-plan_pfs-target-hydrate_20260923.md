# План HF:plan — pfs-target-hydrate (канон записи Цели td2)

Фаза: **HF:plan**. Роль: архитектор (cursor-grok-4.6-high). Код в этой фазе **не** писать.
Исполнитель следующих фаз: composer-2.5 — реализует **этот** документ.

Канон: `WorkVault/Hermes-Backlog/TZ/ProtocolFromSummary/ProtocolFromSummary_TZ.md` v1.18.0,
§23 алгоритм ingest шаги 4/7 + тесты 9–12 (строки 4530–4628) и §24 «Резолв цели title без
space-key» (строки 4880–4929). Рабочая директория: `/home/tkachenkoav/USERTOOLS/ProtocolFromSummary`.

Новой сущности нет — согласование Саши на сущность не требуется.

---

## 0. Что уже есть на диске (не переписывать работающее)

`playground_ingest.py` (12732 байт):

- `ingest_after_publish` (строки 275–342) — GET площадки `expand="body.storage,version"`,
  skip по якорю, `reallocate_task_ids`, затем `render_playground_row_from_battle` → PUT,
  реестр, snapshot. **Сигнатуру ingest не ломать.**
- `render_target_cell(target_page_id, display_name)` (82–88) сейчас пишет
  `ri:content-title` + `ri:content-id` **без** space-key — это и есть дыра канона v1.18.0.
- `render_playground_row_from_battle` (103–120) вызывает writer и собирает 4col `<tr>`.
  Writer в сеть не ходит: hydrate должен произойти **до** этой сборки.
- `render_playground_row` (123–136) — публичный alias.
- Парсеры цели (чистые, без I/O): `parse_target_space_title_from_cell`,
  `parse_target_page_id_from_cell`, `parse_target_title_from_cell`. **Их не менять.**
  Новый XML writer должен round-trip через space+title парсер.
- `_NSMAP` уже объявлен. Импорты: `escape` из `xml.sax.saxutils` уже есть.

`pipeline.py` оба call-site `ingest_after_publish` уже передают
`target_page_id=route.page_id` и `target_display_name=route.entity or summary.meeting_name`
(строки 275–283 `_post_switch_pass_one` и 784–794 тень после publish). Гидратация
живёт внутри ingest — **pipeline.py не нужен.**

`playground_promote.py` `_resolve_target_page_id_from_cell` (шаги а / б / в,
`find_page_by_title`) — **не трогать**. После этой фичи ingest начнёт писать формат
шага (б): space-key + фактический title. Резолв на проходе 2 уже умеет это читать.

`ConfluenceClient.get_page(page_id, expand=DEFAULT_EXPAND)` в
`/home/tkachenkoav/USERTOOLS/ConfluenceSync/confluencesync/confluence_client.py`:
дефолтный expand содержит `body.storage`. Гидратация **обязана** передать
`expand="space"` явно. 404 → `requests.HTTPError` через `raise_for_status`.
В ingest ловить широкий `Exception` (как уже сделано на GET площадки), пакет
`requests` в `playground_ingest.py` не импортировать.

Фикстура `_playground_row_complete` в `tests/test_link_n_dedup_transition.py`
кормит promote-тесты через текущий writer (content-id в td2). После смены writer
её надо починить **в тестах**, иначе шаг (а) в promote-сьюте погаснет. Это не
повод трогать `playground_promote.py`.

Тест-база на текущем коде: 71 passed (`test_post_switch`, `test_promote_v2`,
`test_promote_title_resolve`, `test_notify_pending` и остальные offline).

---

## 1. Файлы создать / изменить

Production — один файл:

- **изменить** `protocolfromsummary/playground_ingest.py` — hydrate, writer, assembler, вызов в ingest.

Тесты:

- **изменить** `tests/test_playground_ingest.py` — четыре новых теста ТЗ 9–12. Существующие
  ingest-тесты с `client.get_page.return_value` (без `space`) оставить как есть: hydrate
  вернёт None, td2 пустая, insert жив — они проверяют task-id / chrono / sidecar, не канон цели.
- **изменить** `tests/test_link_n_dedup_transition.py` — только хелпер `_playground_row_complete`:
  после `render_playground_row` regex-подменить td2 на legacy-ячейку с `ri:content-id`,
  тем же приёмом, что `_playground_row_ui_target` в `test_promote_title_resolve.py`.
  Без этого покраснеют `test_parse_ingest_format_returns_id_without_api`,
  `test_promote_forbidden_playground_page_id_from_content_id` и почти весь `test_promote_v2.py`.
  Production-writer больше не умеет content-id; legacy-строки на площадке — забота фикстуры,
  не writer.

Микро-фикс интеграционного мока (рекомендуется, не блокер зелёных assert'ов):

- **изменить** `tests/test_post_switch.py` — в `_distinguishing_client` у страницы
  `ROUTE_PAGE_ID` добавить `"space": {"key": "DPAN"}` (title там уже `"Trisigma"`).
  Тогда hydrate в post_switch-пути реально пишет канон, а не пустую td2 из KeyError.

Не создавать новых модулей и новых тест-файлов.

**Не менять (и не «заодно»):**

- `pipeline.py` — оба call-site уже отдают `route.page_id`; `_post_switch_pass_one` не должен
  делать полный GET цели с `body.storage`. Обоснование не трогать: гидратация — ответственность
  ingest, сигнатуру ingest ТЗ велит оставить, лишний GET с body в pipeline прямо запрещён §24.
- `playground_promote.py` — резолв title без space-key (шаг в) уже на диске; канон **записи**
  на ingest — отдельный контур. Трогать promote «чтобы сошлось» запрещено.
- `route.py`, формула `row_anchor`, сигнатуры `page_merger.*`.
- `jobs.json`, `.env`, Gateway.
- Enum `last_action`.
- `ConfluenceClient` / пакет ConfluenceSync.
- Парсеры `parse_target_*` в ingest.

---

## 2. Точные сигнатуры

### hydrate_target_ref — новая функция

Расположение: `playground_ingest.py`, рядом с writer (сразу до или сразу после блока
`render_target_cell` / `render_empty_target_cell`). Чистая обёртка над `confluence.get_page`,
без знания route / entities / display_name.

```python
def hydrate_target_ref(confluence, target_page_id: str) -> tuple[str, str] | None:
```

Первый аргумент — тот же объект `confluence`, что у `ingest_after_publish` (утиная типизация,
как остальной модуль). Второй — `target_page_id` из ingest, на живом пути это `route.page_id`.

Возврат: `(space_key, title)` или `None`.

### render_target_cell — смена семантики

Сейчас: `render_target_cell(target_page_id: str, display_name: str) -> str`.

Ставить keyword-only, чтобы старый позиционный вызов `(page_id, display_name)` не превратил
тихо числовой id в space-key:

```python
def render_target_cell(*, space_key: str, title: str, content_id: str | None = None) -> str:
```

`content_id` в сигнатуре остаётся (ТЗ: «можно оставить для совместимости вызовов») и
**не сериализуется** в XML. Неиспользуемый параметр пометить (`_ = content_id` или эквивалент),
чтобы линтер не орал.

### render_empty_target_cell — маленький чистый хелпер

Чтобы assembler не клеил XML пустой ячейки руками в двух местах:

```python
def render_empty_target_cell() -> str:
```

Возвращает тот же хром ячейки, что writer, без ссылки:

```html
<td><div class="content-wrapper"><p></p></div></td>
```

### render_playground_row_from_battle — additive kwarg

Сигнатуру keyword-вызовов тестов не ломать, добавить `space_key`:

```python
def render_playground_row_from_battle(
    battle_row_xml: str,
    *,
    target_page_id: str,
    target_display_name: str,
    processed_task_id: int,
    space_key: str | None = None,
) -> str:
```

td2: непустой `space_key` → `render_target_cell(space_key=space_key, title=target_display_name, content_id=target_page_id)`;
иначе → `render_empty_target_cell()`. `target_page_id` в XML не класть. Когда ingest гидрировал
успешно, в `target_display_name` assembler'а передаётся **гидратированный title**, не slug.

Публичный alias `render_playground_row` прокидывает `space_key` как есть.

### ingest_after_publish — тело, не сигнатура

Сигнатура остаётся:

```python
def ingest_after_publish(
    *,
    battle_row_xml: str,
    meeting_id: str,
    target_page_id: str,
    target_display_name: str,
    registry: Registry,
    confluence,
    dry_run: bool = False,
    page_id: str = PLAYGROUND_PAGE_ID,
) -> IngestResult:
```

`target_display_name` **оставить** в сигнатуре и **игнорировать как title ссылки** (ТЗ).
`IngestResult` не расширять (row_xml не добавлять).

---

## 3. Поведение hydrate: успех / 404 / где / fail-soft

Вызов из `ingest_after_publish`, **после** skip-якоря и расчёта `processed_task_id`,
**до** `render_playground_row_from_battle`. Не вызывать на ветке `skipped_present` и на
ошибке GET площадки. Вызывать при `dry_run=True` (GET цели read-only, как `find_page_by_title`
на promote dry-run).

Алгоритм `hydrate_target_ref`:

1. `page = confluence.get_page(target_page_id, expand="space")`.
   Строка expand — именно `"space"`, без `body`, без `DEFAULT_EXPAND`.
2. Успех: `space_key = page["space"]["key"]`, `title = page["title"]` — это фактический
   заголовок целевой страницы Confluence, не slug сущности, не `entities.display_name`.
   Оба непустые после strip → `return (str(space_key), title.strip())`.
3. 404, любая `Exception`, нет `space.key`, пустой title →
   `log.warning("playground ingest: hydrate_target_ref(%s) failed: ...", target_page_id, ...)`
   и `return None`. Не пробрасывать наружу. Ingest жив (инвариант K1).

Дальше в `ingest_after_publish`:

- Hit: `space_key, real_title = hydrated`; в assembler — `space_key=space_key` и
  `target_display_name=real_title`.
- Miss: `space_key=None` → пустая td2 без `ac:link`. Аргумент ingest `target_display_name`
  (slug / entity) в ячейку не класть.

`route_page_id_at_publish` по-прежнему пишется из `target_page_id` (id маршрута), не из title.

Fail-soft: исключение hydrate **не** меняет `action` на `error`, **не** откатывает publish,
**не** мешает PUT площадки. Пустая ячейка — допустимый исход, не стоп.

---

## 4. render_target_cell: канон XML и dry_run

Канон ячейки (как UI-фикстура `_ui_target_cell` и живые строки 21.09):

```html
<td><div class="content-wrapper"><p><ac:link><ri:page ri:space-key="..." ri:content-title="..." /></ac:link></p></div></td>
```

Порядок атрибутов: сначала `ri:space-key`, потом `ri:content-title`. Self-closing `ri:page`.
Ни `ri:content-id`, ни `pageId=` в XML. Title и space-key экранировать через уже импортированный
`xml.sax.saxutils.escape`; для кавычек в title сразу `escape(s, {'"': "&quot;"})`, иначе
заголовок с кавычкой сломает атрибут.

Запрещено в writer: slug сущности, `display_name`, `route.entity` как `ri:content-title`.
Title берётся только из гидратации (`page["title"]`).

**dry_run.** Сейчас `ingest_after_publish(..., dry_run=True)` уже собирает `row_xml` и
возвращает `action="dry_run"` до PUT / реестра / snapshot. После фичи порядок тот же, но
перед сборкой строки hydrate уже отработал:

- hydrate hit при dry_run → в td2 канон space-key + фактический title, как на live PUT.
  Результат в `IngestResult` по-прежнему не сериализуется (поля row_xml нет) — это ок:
  td2 посчитана тем же путём, PUT нет.
- hydrate miss при dry_run → пустой `<p>` без `ac:link`, `action="dry_run"`, PUT нет.
- GET цели на dry_run — read-only (`expand="space"`), это не write и не нарушение dry-run.

Не делать на dry_run отдельную ветку «не гидрировать»: тогда превью td2 будет пустым при
живой цели, и тест 10 перестанет описывать тот же путь, что live.

Обратная совместимость вызовов `ingest_after_publish`: keyword-аргументы тестов
(`target_page_id=`, `target_display_name=`, `dry_run=`) не меняются. Меняется только то,
**что** попадает в td2: больше не slug и не content-id.

Существующие тесты, которые зовут `render_playground_row(..., target_page_id=..., target_display_name=...)`
без `space_key`, после фичи получат **пустую** td2. Тесты, которые только считают колонки /
strip td2 / regex-подменяют ячейку цели — зелёные. Promote-фикстуры, которым нужен content-id
как на старых строках площадки, чинятся в `_playground_row_complete`, не в writer.

---

## 5. Тесты

Имена — как в ТЗ. Мок, без live API. Четыре новых — в `tests/test_playground_ingest.py`.

**`test_render_target_cell_has_space_and_real_title`**
Вызов `render_target_cell(space_key="DPAN", title="Кирилл 1-1", content_id="508804979")`.
XML содержит `ri:space-key="DPAN"` и exact title; нет slug (`kirill_1on1` / `kirill`);
подстроки `ri:content-id` нет, хотя content_id в вызов передали. Дёшево и полезно:
`parse_target_space_title_from_cell` → `("DPAN", "Кирилл 1-1")`,
`parse_target_page_id_from_cell` → `None`.

**`test_ingest_hydrates_from_get_page`**
`get_page` — `side_effect` **по page_id**, не один `return_value`. Площадка → storage без
якоря (`body.storage,version`). Цель `TGT_ID` → `{"title": "Кирилл 1-1", "space": {"key": "DPAN"}}`
без `body`. В ingest передать `target_display_name="kirill_1on1"` (slug сущности).
PUT storage содержит `ri:space-key="DPAN"` и `Кирилл 1-1`; в td2 нет `kirill_1on1` и нет
`ri:content-id`.

**`test_ingest_hydrate_404_still_inserts_without_slug`**
GET цели поднимает `Exception` / `RuntimeError` (достаточно; `HTTPError` тоже ок, если удобно).
GET площадки успешен. `action == "inserted"`, `update_page` вызван, в новой строке нет
`ac:link`, нет slug из `target_display_name`.

**`test_ingest_does_not_get_target_body`**
По `client.get_page.call_args_list`: вызов с id цели имеет `expand`, и этот expand **не**
содержит `body` / `body.storage`. GET площадки по-прежнему с `body.storage,version`.

Фикстура `_playground_row_complete` (`tests/test_link_n_dedup_transition.py`): после
`render_playground_row` подменить td2 на

```html
<td><div class="content-wrapper"><p><ac:link><ri:page ri:content-title="Entity" ri:content-id="{target_page}" /></ac:link></p></div></td>
```

тем же regex, что `_playground_row_ui_target`. Так шаг (а) promote остаётся покрыт на
legacy-строках, а production-writer больше content-id не пишет.

Существующие ingest-тесты с одним `return_value` без ключа `space` **не чинить мок**,
если assert зелёный: hydrate → None → пустая td2, проверяемые инварианты (task-id, chrono,
sidecar, skip) от содержимого td2 не зависят.

`test_skip_overwrite_playground_on_duplicate_anchor` — hydrate на skip-ветке не зовётся;
второй GET цели не нужен.

Регресс после точки Т2:  
`pytest tests/test_promote_title_resolve.py tests/test_promote_v2.py tests/test_link_n_dedup_transition.py tests/test_post_switch.py tests/test_playground_ingest.py`

Финал: `python -m pytest -q -m "not live_confluence"` — было 71, плюс 4 новых, все зелёные.

---

## 6. Промежуточные точки проверки (исполнитель идёт молча)

**Т1. Writer.** `render_target_cell` keyword-only; XML = space-key + exact title;
`content_id` в сигнатуре есть и в XML отсутствует. Критерий: тест 9 зелёный;
в `playground_ingest.py` writer не сериализует `ri:content-id` (парсер `_CONTENT_ID_RE`
читать чужие ячейки по-прежнему может).

**Т2. Assembler + фикстуры.** `space_key` принимается; без него — пустой `<p>` без `ac:link`.
`_playground_row_complete` снова кладёт content-id. Критерий: promote-сьюты как до изменения
(шаг а жив: `test_parse_ingest_format_returns_id_without_api` и forbidden playground-id
с content-id).

**Т3. Hydrate в ingest.** `hydrate_target_ref` + вызов на шаге после skip / task-id и до
render; dry_run тоже гидрирует. Критерий: тесты 10–12 зелёные; skip-якоря без GET цели.

**Т4. Полный offline.** `python -m pytest -q -m "not live_confluence"` зелёный.

---

## 7. Риски и границы

**Границы (не трогать):** `route.py`; формула `row_anchor`; сигнатуры `page_merger.*`;
`jobs.json`; `.env` (в т.ч. `PFS_POST_SWITCH`); Gateway; enum `last_action`;
`playground_promote.py`; `pipeline.py` (в т.ч. полный GET цели с `body.storage` в
`_post_switch_pass_one`); запись `ri:content-id` / slug / `display_name` в td2;
подстановка `route_page_id_at_publish` в резолв; автоочистка Кирилла 22/23.09;
ConfluenceClient / DEFAULT_EXPAND.

**Риск моков.** `get_page.return_value` без `space` после появления hydrate даёт пустую td2.
Для старых ingest-тестов это штатно. Для теста 10 — только `side_effect` по page_id, иначе
hydrate «увидит» площадку и либо упадёт в KeyError→None, либо (если добавить space на
площадку) запишет title площадки вместо цели.

**Риск фикстуры promote.** Если забыть `_playground_row_complete`, покраснеет не ingest,
а promote. Чинить фикстуру, не `playground_promote.py`.

**Риск экранирования.** `escape` без `&quot;` ломает title с кавычкой. Сразу quoteattr-стиль.

**Риск expand.** Вызов `get_page(target)` без явного expand уйдёт в `DEFAULT_EXPAND` с body.
Тест 12 это ловит. Не использовать `expand="space,version"` и не тащить `body.storage`.

**Риск двойного GET.** Первый GET — площадка (`body.storage,version`), второй — цель
(`space`). Путать порядок или склеивать expand нельзя. На `skipped_present` второго GET нет.

---

## Порядок работы исполнителя (канон контура, не развилки)

Гидратация живёт только в `playground_ingest.py`. Writer пишет исключительно space-key +
фактический title. Пустой hydrate = пустая ячейка, ingest жив. `target_display_name` ingest
не является title ссылки. pipeline и promote не открывать. Legacy content-id остаётся только
в тестовой фикстуре старых строк площадки.

---

## Прогресс выполнения

- [ ] Т1: `render_target_cell` канон space+title, без content-id в XML
- [ ] Т2: assembler + пустая ячейка + фикстура `_playground_row_complete`
- [ ] Т3: `hydrate_target_ref` + ветка в `ingest_after_publish` (в т.ч. dry_run)
- [ ] Тесты 9–12 в `tests/test_playground_ingest.py`
- [ ] Т4: `pytest -q -m "not live_confluence"` зелёный
