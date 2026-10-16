---
type: hf-plan
title: "Пофайловый план CHANGE TaskRefresh §27 «Всё в одном» для ./tr new (HF:plan, 09.09)"
slug: TaskRefresh
case: CHANGE
phase: HF:plan
date: 2026-09-09
status: draft-plan
author: архитектор (cursor-grok-4.6-high)
source_tz: TZ/TaskRefresh/TaskRefresh_TZ.md v2.4.2 §27
executor: composer-2.5
next_phases: REV:plan → GATE:plan-approve → HF:backup → HF:impl → HF:test → HF:docs-handoff → ORCH:shared-state → GATE:done
---

# HF:plan — TaskRefresh §27 «Всё в одном» для `./tr new` (CHANGE)

Кейс **CHANGE** (GLOSSARY §2): доработка существующего `./tr new` по master-ТЗ `TZ/TaskRefresh/TaskRefresh_TZ.md` v2.4.2, секция **§27** (09.09.2026). Этот файл — артефакт фазы **HF:plan** (Блок 1А `hermes-feature`). Код в этом вызове не писать. Объект для `REV:plan` и `GATE:plan-approve`.

**Reuse-first.** Новая сущность / пакет / CLI-флаг / третий парсер дат / копия JIRA-regex **не** вводятся. Все примитивы уже есть: `parse_first_td_date`, `normalize_deadline`, `_append_link_or_jira`, `_is_jira_url`, `_build_jira_macro_element`, `_insert_element_before_time`, `rebuild_task_block(..., append_link_urls=...)`, `insert_task_into_date_row`, `JIRA_SERVER_NAME` / `JIRA_SERVER_ID` в `config.py`, `FakeConfluenceClient`, фикстура `tests/fixtures/page_432316254_bug_storage.xml`.

**Вне scope этой фазы (HF:plan):** любой diff в `~/USERTOOLS/TaskRefresh/taskrefresh/*`, любые новые/правленные `tests/*` (кроме описания в этом файле), любые `tests/`/`scripts/` скилла `taskrefresh`. Единственный файл на диске от этой фазы — этот план.

**Не трогать (чужая незакоммиченная работа на `master`):** `taskrefresh/config.py`, `taskrefresh/session_store.py`, `tests/test_session_store.py`. Не откатывать, не включать в diff §27.

---

## Цель / охват

### Цель

Одна команда `./tr new "текст [дата] [URL …]"` сама извлекает из позиционного `text`:

- первое вхождение календарной даты → дедлайн `<time datetime="YYYY-MM-DD"/>` (если нет `--deadline`);
- все `http://` / `https://` → элементы тела через **существующий** `_append_link_or_jira` (JIRA-макрос или `<a href>`).

Второй шаг `apply "#N ссылка …"` после создания не нужен. Флаги `new` не расширяются и не переименовываются. Парсинг строки — **только** в `write_ops.insert_new_task` (choke-point), не в argparse / `_cmd_new`.

### Охват файлов (HF:impl)

| Путь | Действие |
|---|---|
| `~/USERTOOLS/TaskRefresh/taskrefresh/date_parse.py` | тонкая обёртка span поверх тех же regex, что `parse_first_td_date` |
| `~/USERTOOLS/TaskRefresh/taskrefresh/write_ops.py` | helper URL + разбор строки внутри `insert_new_task` |
| `~/USERTOOLS/TaskRefresh/taskrefresh/task_block.py` | `build_new_task_block(..., append_link_urls=…)` |
| `~/USERTOOLS/TaskRefresh/tests/test_new_task.py` | **создать** — 14 кейсов §27.5 |
| `~/.hermes/skills/productivity/taskrefresh/SKILL.md` | снять «new НЕ добавляет ссылки»; описать однопроходный разбор (текст в HF:impl; `restore-all-skills.sh` — только `ORCH:shared-state`) |

### Явно не менять

`__main__.py` (`_cmd_new`, `p_new`), `change_spec.py`, `formatter.py`, `pipeline.py` (включая `_check_href_guard`), `row_insert.py`, `config.py`, `rebuild_task_block` (поведение `append_link_urls`), `normalize_deadline`, раннюю валидацию rejected-без-PUT, CLI-имена флагов `new` (не добавлять `--link`), синтаксис `apply`/`do`/`batch`.

### Критерии «готово» этой фазы (HF:plan)

- Этот файл записан по указанному пути.
- Пофайловый план покрывает §27.1–§27.7 + регресс §24/§25/§26.
- Код / тесты / SKILL / мастер-ТЗ / инвентарь / манифест **этим вызовом не изменены**.

Снятие `GATE:plan-approve` и реализация — не эта фаза.

---

## Факт на диске (проверено чтением 09.09, не по памяти)

| Артефакт | Факт |
|---|---|
| `insert_new_task` | `write_ops.py:169-259`. Сигнатура: `(client, page_id, date_str, text, *, assignee_raw=None, deadline=None, today=None, resolver=None, audit=None, retry_left=1)`. Разбора строки нет. `text` сырой. При unresolved: `text = f"{display} {text}".strip()` — **к исходному `text`**. Retry 409 вызывает себя с тем же `text`/`assignee_raw`/`deadline` (после `deadline = normalize_deadline(...)`, если флаг был). |
| Ранняя валидация §26 | `write_ops.py:187-191`: если `deadline is not None` — `normalize_deadline`; `ValueError` → `ApplyResult(..., "rejected")` **до GET/PUT**. |
| `build_new_task_block` | `task_block.py:35-71`. Параметра `append_link_urls` **нет**. Mention / текст / `<time>`. Ссылок не вставляет. |
| `rebuild_task_block` | уже принимает `append_link_urls: list[str] \| None = None` (`task_block.py:87`) и для каждого URL зовёт `_append_link_or_jira` (`194-196`). Контракт §25 — не менять. |
| `_is_jira_url` / `_build_jira_macro_element` / `_append_link_or_jira` | `task_block.py:204-267`. Regex `^https://hq\.tutu\.ru/browse/([A-Za-z]+-\d+)$`. Макрос через lxml + `JIRA_SERVER_NAME`/`JIRA_SERVER_ID` из `config.py:46-47`. Не копировать. |
| `parse_first_td_date` | `date_parse.py:38-95`. Кандидаты `(m.start(), dt)` из `_ISO_RE`, `_DMY_RE`, `_RU_DATE_RE`, `_DMY_SHORT_YEAR_RE`, `_DM_RE`; sort по start; первая слева. **`m.end()` не сохраняется.** Возвращает только `date \| None`. |
| `normalize_deadline` | `date_parse.py:98-111`. CLI-токены `+Nд` / `today` / «без дедлайна»/«убрать»/«нет»; иначе `parse_first_td_date`. Не ослаблять. |
| `_cmd_new` / `p_new` | `__main__.py:97-113` и `203-213`. Позиционный `text`; флаги `--date`, `--page-id`, `--assignee`, `--deadline`. `--project` / `--link` нет. Передаёт сырой `args.text`. |
| `_check_href_guard` | `pipeline.py:315-335`. Только `apply text` / `do` / `batch`. На `new` не распространяется (§27.3). Не трогать. |
| `insert_task_into_date_row` | `row_insert.py:95+`. Поиск по ячейке `<p><time datetime="YYYY-MM-DD"`, не `body.find(date)`. Не трогать. |
| Фикстура | `tests/fixtures/page_432316254_bug_storage.xml`. Строки таблицы: `2026-08-19`, `2026-08-15`, `2026-08-17`. Строки `2026-08-18` **нет**; дедлайн `2026-08-18` висит на задаче `622138` в строке 15.08. Max `task-id` = `622138` → следующий `622139`. |
| `test_new_task.py` | **отсутствует**. |
| `FakeConfluenceClient` | `tests/conftest.py:38-81`. `put_calls`, `fail_put_times` (409). |
| SKILL `taskrefresh` | v2.6.1. Запрет ссылок в `new`: строки **476–478** и чеклист **637**. CLI `new` — строка **71**. |
| Незакоммиченное (не §27) | `config.py`, `session_store.py`, `test_session_store.py`. |

---

## Пофайловые изменения

Общий контракт исполнителя: идти сверху вниз. Если функция уже совпадает с сигнатурой/поведением — не переписывать. Не плодить третий парсер дат. Не решать тип макроса/href в write_ops.

### 1. `~/USERTOOLS/TaskRefresh/taskrefresh/date_parse.py`

**Назначение §27.** Не третий парсер форматов. Тонкая обёртка над **теми же** regex (`_ISO_RE`, `_DMY_RE`, `_RU_DATE_RE`, `_DMY_SHORT_YEAR_RE`, `_DM_RE`), что `parse_first_td_date`, плюс применение `normalize_deadline` в choke-point (не здесь на уровне форматов).

**Что добавить** (после `parse_first_td_date`, до `normalize_deadline` или сразу после него — без разницы, имена публичные):

```python
def find_first_td_date_span(
    td_text: str,
    default_year: int | None = None,
) -> tuple[date, int, int] | None:
    """Первая дата слева направо теми же форматами, что parse_first_td_date.
    Возвращает (date, start, end) — span ТОГО ЖЕ regex-матча, которым дата найдена.
    None, если ни один формат не распознан.
    """
```

**Как вставлять (reuse, не копия логики в третий раз):**

1. Вынести сбор кандидатов из текущего тела `parse_first_td_date` (строки 48–95) в внутреннюю функцию, например `_first_td_date_candidates(text, default_year) -> list[tuple[int, int, date]]` — тройка `(start, end, dt)`, где `start`/`end` = `m.start()`/`m.end()` того матча, который дал `dt`.
2. `parse_first_td_date` оставить **внешним контрактом без изменений**: `found = find_first_td_date_span(...); return found[0] if found else None`. Существующие `tests/test_date_parse.py` остаются зелёными без правок.
3. Сортировка как сейчас: `sort(key=lambda t: t[0])` (stable) — при равном start побеждает тот кандидат, который раньше добавлен (ISO → DMY → RU → YY → DM). Это сохраняет текущее поведение «14.09.2026» vs усечённый `DD.MM`.
4. **Не** распознавать в этой обёртке CLI-токены `+Nд` / `today` / «без дедлайна» — их нет в regex `parse_first_td_date`; в строке постановки они остаются текстом (§27.3).
5. **Не** вырезать текст здесь. Вырезание — в `write_ops`: `visible = text[:start] + text[end:]`. **Запрещено** `str.replace(token, "", 1)`.
6. **Не** менять `normalize_deadline`. Choke-point передаёт в него **подстроку матча** `remaining[start:end]` (не `date.isoformat()`), затем ISO из `normalize_deadline`.

**Промежуточная точка П1.** `pytest tests/test_date_parse.py` зелёный. Новый юнит в `test_new_task.py` (не в `test_date_parse.py`): для `"Сделать X 14.09 хвост"` при `default_year=2026` span указывает ровно на `"14.09"`, `text[:start]+text[end:]` == `"Сделать X  хвост"` (пробелы ещё не схлопнуты). Повторная `"14.09"` правее не срезается.

---

### 2. `~/USERTOOLS/TaskRefresh/taskrefresh/write_ops.py`

**Назначение §27.** Choke-point разбора строки постановки. Единственное место, где из сырого `text` получаются `(visible_text, urls, date_from_text)`.

**Сигнатура `insert_new_task` — не менять** (внешний контракт = сырой `text`). `append_link_urls` в публичные kwargs **не** добавлять.

**Что добавить** (модульные private-хелперы рядом с choke-point, сразу над `insert_new_task`, после `_next_task_id`):

```python
def _extract_http_urls(text: str) -> tuple[list[str], str]:
    """Шаг A. Все http:// и https:// в порядке текста.
    www. без схемы — не URL. Хвост пунктуации .,;:!?)] в URL не входит
    (пробел в списке ТЗ — и так граница токена).
    Возвращает (urls, text_без_url_по_span). Тип макроса/href НЕ решать.
    """

def _collapse_ws(text: str) -> str:
    """Шаг C. strip + схлопнуть повторные пробелы."""

def _parse_new_task_text(
    text: str,
    *,
    consume_date: bool,
    today: date,
) -> tuple[str, list[str], str | None]:
    """Шаги A → (B если consume_date) → C.
    Возвращает (visible_text, urls, date_from_text_iso | None).
    date_from_text — ISO от normalize_deadline(matched_span, today), либо None.
    """
```

**Правила helper URL (Шаг A):**

- Regex вида `https?://[^\s<>\"']+` (оба регистра схемы). Без схемы `www.` не матчить.
- После матча: `url = raw.rstrip(".,;:!?)]")`. Пустой после rstrip — пропустить.
- Span **удаления** = `(m.start(), m.start() + len(url))` — хвостовая пунктуация остаётся в видимом тексте, в URL не входит.
- Несколько URL: собрать все spans, вырезать **справа налево** (чтобы индексы не поехали). **Не** `str.replace`.
- Дубликаты: сколько раз встретились — столько в списке, порядок текста.
- Тип JIRA vs `<a href>` **здесь не решать** — это `_append_link_or_jira`.

**Правила `_parse_new_task_text`:**

1. Шаг A всегда (URL снимаются до поиска даты — «дата внутри URL не рассматривается»).
2. Шаг B **только если** `consume_date is True` (то есть CLI `--deadline` **не** передан). Иначе дата в строке не ищется и не вырезается.
3. Шаг B: `find_first_td_date_span(remaining, default_year=today.year)`. Если не None: `matched = remaining[start:end]`; `date_from_text = normalize_deadline(matched, today)`; `remaining = remaining[:start] + remaining[end:]`. Несколько дат — только первая слева; остальные остаются текстом.
4. Шаг C: `_collapse_ws`. Пустой остаток допустим, если есть URL и/или дедлайн.

**Изменения тела `insert_new_task` (строки 182–259), порядок:**

1. В самом начале сохранить **исходные** `orig_text = text` и `orig_deadline = deadline` (ссылка на аргумент **до** любой мутации). `today = today or date.today()`.
2. Разобрать `orig_text` **до** префикса unresolved-assignee:
   - `consume_date = (orig_deadline is None)`
   - `visible_text, urls, date_from_text = _parse_new_task_text(orig_text, consume_date=consume_date, today=today)`
3. Резолв дедлайна по приоритету §27.3:
   1. Если `orig_deadline is not None` — **существующая** ранняя валидация `normalize_deadline(orig_deadline, today)`; `ValueError` → `rejected` без GET/PUT, даже если в строке есть своя дата (TC-10). Шаг B не выполнялся.
   2. Иначе `deadline = date_from_text` (уже ISO или None).
   3. Иначе дедлайна нет. **Не** подставлять `today` как дедлайн.
4. GET / `task_id` / резолв `--assignee` как сейчас. При неудачном резолве: `visible_text = f"{display} {visible_text}".strip()` — префикс к **уже разобранному** `visible_text`, **не** к `orig_text`. Переменную `text` (аргумент) больше не мутировать.
5. Вызов:

```python
task_xml = build_new_task_block(
    task_id,
    visible_text,
    userkey=userkey,
    deadline=deadline,          # ISO или None
    today=today,
    append_link_urls=urls or None,
)
```

6. `insert_task_into_date_row(storage_html, date_str, task_xml)` — `date_str` как пришёл (CLI `--date` / сегодня из `_cmd_new`). Дата из строки постановки **не** меняет `date_str`.
7. Retry 409: рекурсивный вызов с **`orig_text`, `orig_deadline`, `assignee_raw`** (как внешний контракт «как сейчас» по аргументам). Список URL **пересчитывать заново** из `orig_text` внутри следующего входа, не из `visible_text`. Не передавать уже вырезанную строку. Не передавать `deadline=date_from_text` вместо `orig_deadline=None` — иначе на retry Шаг B будет пропущен и дата останется в видимом тексте.
8. Audit `new_value`: писать `visible_text` (то, что ушло в блок), не сырой orig с URL.

**Импорт:** добавить `find_first_td_date_span` из `.date_parse` рядом с уже существующим `normalize_deadline`. `rebuild_task_block` в этом файле не трогать (он нужен `_build_new_block` для apply).

**Промежуточная точка П2.** Юниты `_extract_http_urls` / `_parse_new_task_text` в `test_new_task.py` без PUT: URL+пунктуация, порядок, `www.` не URL, `--deadline` путь = `consume_date=False` оставляет `14.09` в visible, `+7д` в строке не становится датой.

---

### 3. `~/USERTOOLS/TaskRefresh/taskrefresh/task_block.py`

**Назначение §27.** Прокидка списка URL в сборку **новой** задачи тем же механизмом, что §25.

**Сигнатура — расширить, не ломая позиционные:**

```python
def build_new_task_block(
    task_id: int,
    text: str,
    *,
    userkey: str | None = None,
    deadline: str | None = None,
    today: date | None = None,
    append_link_urls: list[str] | None = None,
) -> str:
```

**Куда вставлять:** после существующей вставки `<time>` (строки 67–69), **до** `return etree.tostring(...)` (строка 71).

**Тело (один из двух допустимых путей ТЗ; дублировать вставку запрещено).** Рекомендация плана — прямой reuse `_append_link_or_jira` (не второй проход через `rebuild_task_block`, чтобы не нормализовать дедлайн дважды и не плодить parse/serialize):

```python
if append_link_urls:
    for url in append_link_urls:
        _append_link_or_jira(body_el, url, "(ссылка)")
```

Label не-JIRA = дефолт `rebuild_task_block` (`"(ссылка)"`). Подпись из строки постановки не парсится.

Порядок вызовов относительно `<time>` не важен: `_insert_element_before_time` уже кладёт элемент перед `<time>` на любой глубине или в конец.

**Запреты (жёстко):**

- Не копировать `_is_jira_url` / `_build_jira_macro_element`.
- Не собирать макрос f-string.
- `JIRA_SERVER_NAME` / `JIRA_SERVER_ID` — только импорт из `config.py` (уже есть в этом файле, строки 13, 221–222). Не хардкодить, не импортировать в `write_ops`.
- `rebuild_task_block` — **поведение не менять**. Существующие тесты `append_link_urls` / `_is_jira_url` зелёные без правок контракта.

**Промежуточная точка П3.** Существующие `tests/test_task_block.py` + `tests/test_jira_link.py` зелёные. Новые юниты в `test_new_task.py`: `build_new_task_block` с JIRA URL → ровно один `ac:name="jira"` key=ADD-1, нет `href="https://hq.tutu.ru/browse/`; loop → `<a href>` `(ссылка)`; смешанный список — макрос затем `<a href>` в порядке текста.

---

### 4. `~/USERTOOLS/TaskRefresh/taskrefresh/__main__.py` — НЕ МЕНЯТЬ

`_cmd_new` (97–113) по-прежнему:

```python
insert_new_task(
    client, args.page_id, date_str, args.text,
    assignee_raw=args.assignee, deadline=args.deadline,
)
```

`p_new` (203–213): не добавлять `--link`, не добавлять `--project`, не переименовывать флаги, не парсить `args.text`. `date_str = args.date or date.today().isoformat()` остаётся датой **строки таблицы**, не дедлайном.

**Промежуточная точка П4.** `git diff taskrefresh/__main__.py` пустой (в части §27).

---

### 5. Файлы контекста — НЕ МЕНЯТЬ

| Файл | Почему в плане |
|---|---|
| `change_spec.py` | парсер `apply`/`ссылка`; контракт §25 |
| `formatter.py` | preview `apply` |
| `pipeline.py` | `_check_href_guard` для `do`/`batch`/`apply text`; на `new` не распространяется |
| `row_insert.py` | алгоритм дата-строки §24 |
| `config.py` | JIRA-константы уже есть; плюс незакоммиченный чужой diff |
| `session_store.py` / `tests/test_session_store.py` | чужой незакоммиченный diff; TTL не §27 |

---

## Новые тесты (`tests/test_new_task.py`)

**Создать файл** `~/USERTOOLS/TaskRefresh/tests/test_new_task.py`. Не править `test_write_ops.py` / `test_task_block.py` / `test_jira_link.py` / `test_date_parse.py` «под реализацию» — они остаются регрессом. Новых `tests/`/`scripts/` у скилла `taskrefresh` нет.

**Общие фикстуры файла:**

- `_TODAY = date(2026, 9, 9)` — фиксировать во всех вызовах `insert_new_task(..., today=_TODAY)` и `build_new_task_block(..., today=_TODAY)`.
- Storage: читать `tests/fixtures/page_432316254_bug_storage.xml` (как `test_write_ops.test_insert_new_task_end_to_end`).
- Клиент: `FakeConfluenceClient` из `tests.conftest`. Живого PUT нет.
- `date_str` по умолчанию для CLI-семантики «без `--date`» = `_TODAY.isoformat()` (`2026-09-09`). Строки с такой датой в фикстуре нет — вставка создаст новую `<tr>` (как кейс 18.08 в §24).
- Хелпер `_client(storage=None)` + `_insert(...)` чтобы не копировать boilerplate.
- Импорты: `insert_new_task`, `build_new_task_block`, `find_first_td_date_span`, `_extract_http_urls` / `_parse_new_task_text` (private write_ops), `find_date_row_bounds`.

Юниты разбора можно звать напрямую (хелперы). Кейсы §27.5, которым нужен PUT-контракт / строка таблицы / assignee — через `insert_new_task`.

### Маппинг 14 кейсов §27.5

| TC | Имя теста (рекоменд.) | Что проверять | Слой |
|---|---|---|---|
| 1 | `test_tc1_date_in_text_becomes_deadline_row_is_today` | text=`"Сделать X 14.09"`, без `deadline`, `date_str=_TODAY.isoformat()`. В блоке `datetime="2026-09-14"`, нет `datetime="14.09"`. Строка таблицы = сегодня: `find_date_row_bounds(..., "2026-09-09")` not None; **не** искать/создавать строку по `14.09`/`2026-09-14` как дате постановки. `find_date_row_bounds(..., "2026-08-18")` по-прежнему None (чужой дедлайн в фикстуре). Видимый текст содержит `"Сделать X"`, не содержит токен `14.09`. | `insert_new_task` |
| 2 | `test_tc2_iso_in_text` | text=`"Сделать X 2026-09-14"` → `datetime="2026-09-14"`, ISO из текста вырезан из visible. | `insert_new_task` |
| 3 | `test_tc3_deadline_flag_wins_date_stays_visible` | text=`"Сделать X 14.09"`, `deadline="20.09"`. Дедлайн `datetime="2026-09-20"`; токен `14.09` **остаётся** в видимом тексте. Шаг B не выполнялся. | `insert_new_task` |
| 4 | `test_tc4_no_date_no_deadline_no_time` | text без даты и URL, `deadline=None`. В новом `<ac:task>` нет `<time`. Не писать `datetime="{today}"`. Строка таблицы всё равно сегодня (`date_str=_TODAY`). | `insert_new_task` |
| 5 | `test_tc5_jira_url_macro_not_href` | text=`"Разбор https://hq.tutu.ru/browse/ADD-1"`. Ровно один `ac:name="jira"`, key=`ADD-1`; visible без голого URL; нет `href="https://hq.tutu.ru/browse/`. Можно дополнительно юнит `build_new_task_block` с `append_link_urls=[...]`. | `insert_new_task` +/или `build_new_task_block` |
| 6 | `test_tc6_non_jira_url_href` | loop/иной URL → `<a href="...">(ссылка)</a>` через `_append_link_or_jira`; нет `ac:name="jira"`. | то же |
| 7 | `test_tc7_mixed_urls_preserve_order` | JIRA затем loop в одной строке → макрос, затем `<a href>` (индексы в XML: key раньше href). Как `rebuild_task_block(..., append_link_urls=...)`. | `insert_new_task` или `build_new_task_block` |
| 8 | `test_tc8_onepass_date_and_two_urls` | text=`"Trisigma. Обсудить 14.09 https://hq.tutu.ru/browse/ADD-1 https://loop.tutu.ru/x"` без `--deadline`. Дедлайн с `14.09` → `2026-09-14`; два элемента ссылок; префикс `Trisigma. Обсудить` сохранён; URL из текста вырезаны; нет голого URL в visible. | `insert_new_task` — приёмка §27.7.1 |
| 9 | `test_tc9_assignee_plus_date_and_url` | `assignee_raw` + resolver → `(userkey, display)`; text с датой и URL. Есть `ri:userkey`; плюс дедлайн и ссылка из строки. Исполнитель из текста **не** парсится. | `insert_new_task` |
| 10 | `test_tc10_invalid_deadline_rejected_no_put` | `deadline="99.99"`, text содержит валидную дату (напр. `14.09`). `status=="rejected"`; `len(client.put_calls)==0`; дата из text не спасает. GET тоже не обязателен (валидация до GET, как сейчас). | `insert_new_task` §26 |
| 11 | `test_tc11_text_date_does_not_select_table_row` | text с датой, совпадающей с чужим дедлайном на странице (`2026-08-18` / `18.08`), `date_str=_TODAY.isoformat()`. Новая задача **не** в строке 15.08 и не создаёт строку `2026-08-18` как постановку. `find_date_row_bounds(..., "2026-08-18") is None`. Новая `<tr>` — по `--date`/сегодня. Паттерн ячейки `<p><time datetime="YYYY-MM-DD"` не ломается. | `insert_new_task` §24 |
| 12 | `test_tc12_section25_append_link_urls_contract` | Короткий контрактный smoke: `rebuild_task_block(BLOCK, append_link_urls=[JIRA, LOOP])` — макрос + `<a href>`, без правки `test_jira_link.py`. Плюс точка П5: полный прогон `tests/test_jira_link.py tests/test_task_block.py`. | `rebuild_task_block` без изменения контракта |
| 13 | `test_tc13_deadline_flag_plus_url_no_date_in_text` | text=`"Разбор https://loop.tutu.ru/x"`, `deadline="20.09"`. Ссылка из строки; дедлайн только из флага `2026-09-20`; в visible нет URL. | `insert_new_task` |
| 14 | `test_tc14_unresolved_assignee_prefix_on_parsed_visible` | `assignee_raw="<нерезолвленное ФИО>"`, resolver → `(None, display)`; text=`"X 14.09 https://loop.tutu.ru/y"`. Дедлайн и ссылка извлечены из **исходного** text. Видимый текст = `f"{display} {visible_text}"` без даты и URL (напр. `"{display} X"`). `status=="partial_no_mention"`. PUT был. | `insert_new_task` |

**Дополнительно (не из нумерации §27.5, но закрывает жёсткое правило retry — один короткий тест):**

| Extra | Имя | Зачем |
|---|---|---|
| E1 | `test_extract_urls_strips_trailing_punct_keeps_order` | `"см. https://loop.tutu.ru/x."` → URL без точки; точка может остаться в remainder. `"https://a https://a"` → два одинаковых URL. `www.tutu.ru/x` не URL. |
| E2 | `test_cli_tokens_in_text_are_not_deadline` | text=`"Сделать +7д today без дедлайна"` без `--deadline` → нет `<time>` (токены только через флаг). |
| E3 | `test_409_retry_reparses_urls_from_orig_text` | `fail_put_times={"432316254": 1}`; text с URL. После ok: ссылки есть в storage (retry не получил вырезанную строку). `orig_deadline is None` + дата в тексте → на retry дата всё ещё потребляется, не остаётся visible. |

TC-12 не заменяет прогон пакета §25.

**Живой PUT:** только smoke на HF:test / приёмка §27.7.8 (GET после реального `./tr new`). В `test_new_task.py` живого Confluence нет.

**Промежуточная точка П5.** `pytest tests/test_new_task.py tests/test_write_ops.py tests/test_task_block.py tests/test_jira_link.py tests/test_date_parse.py tests/test_row_insert.py` — все зелёные.

---

## Изменение SKILL (`HF:impl`; restore — `ORCH:shared-state`)

Файл: `~/.hermes/skills/productivity/taskrefresh/SKILL.md` (v2.6.1). Не создавать `tests/`/`scripts/` у скилла.

**Снять / заменить:**

1. Строки **476–478** — блок «`./tr new` НЕ добавляет ссылки» + прецедент 07.09 про отдельный PUT loop-ссылки. Заменить описанием однопроходного разбора.
2. Чеклист строка **637**: «Создание задачи через `./tr new` — ссылка добавлена отдельно через `./tr apply "#N ссылка <URL>"` + `confirm` (`new` не вставляет ссылки)» → создание с URL в `--text` **не** требует отдельного `apply "#N ссылка"`.

**Добавить в раздел «Вставка новой задачи — через `./tr new`» (после примеров ~468–474):**

- Строка постановки (позиционный `text`) может содержать календарную дату и URL; инструмент сам разбирает.
- Дата в строке → дедлайн (`normalize_deadline`, те же форматы, что ячейка таблицы: ISO / `DD.MM.YYYY` / `DD.MM.YY` / `DD.MM` / русские месяцы). Токены `+Nд` / `today` / «без дедлайна» в строке **не** распознаются — только `--deadline`.
- URL `http://`/`https://` → JIRA-макрос или `<a href>` тем же механизмом, что `apply … ссылка` (§25). `www.` без схемы — не URL.
- Приоритет дедлайна: `--deadline` > дата из строки > нет дедлайна. Если передан `--deadline`, дата в строке остаётся видимым текстом.
- `--date` / сегодня = дата-строка таблицы (`<p><time datetime=`), **не** дедлайн из строки.
- `--assignee` как раньше; ФИО из строки не парсятся. `--project` у `new` нет; префикс `<Проект>. ` — часть текста.
- Пример однопрохода: `./tr new "Trisigma. Обсудить AB 14.09 https://hq.tutu.ru/browse/ADD-1 https://loop.tutu.ru/x"`.
- `apply "#N ссылка …"` остаётся для **уже существующих** задач.

CLI-строка **71** — флаги не менять; можно уточнить комментарий, что `text` сам разбирает дату/URL (без нового флага).

Версию SKILL бампать на `HF:docs-handoff` (не выдумывать номер в impl). Манифест / `restore-all-skills.sh` — только оркестратор.

---

## Порядок реализации (HF:impl)

Исполнитель идёт молча по точкам П1–П6. Код — `composer-2.5`. Скилл-тексты в том же impl, как указано в постановке.

1. `date_parse.py`: кандидаты с `end` + `find_first_td_date_span`; `parse_first_td_date` — фасад. П1.
2. `write_ops.py`: `_extract_http_urls`, `_collapse_ws`, `_parse_new_task_text` (ещё без смены PUT-ветки). Юниты E1/E2 + span. П2.
3. `task_block.py`: параметр `append_link_urls` + цикл `_append_link_or_jira`. П3.
4. `insert_new_task`: встроить разбор / приоритет / unresolved-префикс / retry от `orig_*`. Не менять `__main__.py`.
5. `tests/test_new_task.py`: TC-1…TC-14 + E3. П5.
6. SKILL.md: снять 476–478 и 637, описать однопроход. П6 (grep).
7. Полный `pytest tests/` в venv ProtocolFromSummary (как SKILL: «не только тронутый файл»). Не гонять живой PUT в этой точке — smoke на HF:test.

Отклонение: если удобнее собрать ссылки через `rebuild_task_block(block, append_link_urls=…)` вместо цикла в `build_new_task_block` — допустимо по §27.4, но **не** оба сразу (дубля вставки нет). Предпочтение плана — прямой `_append_link_or_jira`.

Мелкое отклонение (≤2 файла, не ломает choke-point / reuse JIRA) — исполнитель сам. Крупное (новый парсер, новый флаг, копия макроса, разбор в `__main__`) — стоп, не делать.

---

## Промежуточные точки проверки

Исполнитель проходит молча. Критерий точки = колонка «критерий».

| ID | Когда | Критерий |
|---|---|---|
| П1 | после `date_parse` | `pytest tests/test_date_parse.py` зелёный; span-юнит: вырезание по `start:end`, не `replace`; форматы 1-в-1 с `parse_first_td_date`; `+Nд`/`today` в обёртке не матчатся |
| П2 | после URL-хелпера | юниты A/C без PUT: порядок URL, пунктуация, `www.` не URL, `consume_date=False` не вырезает дату |
| П3 | после `build_new_task_block` | `test_task_block.py` + `test_jira_link.py` зелёные; новый блок с URL даёт макрос/`<a href>` без второй копии regex в diff (`rg "_JIRA_URL_RE\|_is_jira_url" write_ops.py` пусто) |
| П4 | после `insert_new_task` | `__main__.py` без diff; grep `p_new.add_argument` — нет `--link`; разбор только в `write_ops` |
| П5 | после `test_new_task.py` | 14 кейсов §27.5 зелёные; extra E3 retry; регресс `test_write_ops` / `test_row_insert` / `test_date_parse` / `test_jira_link` / `test_task_block` зелёные |
| П6 | после SKILL | нет фразы «`./tr new` НЕ добавляет ссылки»; чеклист 637 обновлён; однопроход и приоритет `--deadline` / `--date` ≠ дедлайн описаны |
| П7 | HF:test / приёмка | полный `pytest tests/`; живой smoke GET после `./tr new` с датой+JIRA+loop: макрос, `<a href>`, `<time datetime="YYYY-MM-DD"/>`, нет сырого `14.09` в атрибуте (§27.7.8) |

---

## Риски / регресс

### Регресс-зона §27.6 (не трогать)

- `normalize_deadline` и ранняя валидация в `insert_new_task` (§26) — не ослаблять, не обходить датой из строки при сломанном флаге.
- §24: `insert_task_into_date_row`, паттерн ячейки, «новые выше старых». Дата из `text` ≠ `--date`.
- §25: `_is_jira_url`, `_build_jira_macro_element`, `_append_link_or_jira`, `rebuild_task_block(..., append_link_urls=...)`, константы JIRA в `config.py`, guard `pipeline._check_href_guard` для `apply text`/`do`/`batch`.
- Синтаксис `apply`/`do`/`batch` / мульти-поле `;` / W1–W5.
- Парсинг исполнителя и проекта из строки (out of scope).
- CLI-имена `new`; не добавлять `--link`.
- Чужой контент страницы; правка существующих `<ac:task-body>` вне W1–W5.

### Риски реализации

| Риск | Как закрыть |
|---|---|
| Третий парсер дат | только `find_first_td_date_span` = те же regex + `m.end()`; `parse_first_td_date` фасад |
| `str.replace` срежет вторую такую же дату/URL | только span |
| `--deadline` передан, но Шаг B всё равно вырезает дату | `consume_date = (orig_deadline is None)` строго |
| Retry 409 получает `visible_text` без URL | рекурсия с `orig_text` / `orig_deadline` |
| Retry с `deadline=ISO_from_text` при исходном `None` | пропустит Шаг B; запрещено, передавать `orig_deadline` |
| Unresolved-префикс до разбора | дата/URL попадут в `display …`; префикс только на `visible_text` |
| Двойной префикс на retry | сейчас `text` мутируется и передаётся снова вместе с `assignee_raw` — при §27 перестать мутировать аргумент `text` |
| Копия JIRA-сборки в write_ops | helper URL возвращает `list[str]`; тип решает `_append_link_or_jira` |
| Guard href на new | не вызывать `_check_href_guard` из `insert_new_task` |
| Пустой visible при одних URL | допустимо §27.3; тело = ссылки ± `<time>` |
| `deadline="без дедлайна"` + дата в строке | флаг передан → Шаг B skip → дата остаётся текстом, `<time>` нет (нормализуется в `None`) |
| Живой PUT в юнитах | запрещён кроме smoke HF:test |

Существующие тесты `test_insert_new_task_end_to_end` / `_deadline_dmy_normalized` / `_invalid_deadline_rejected` должны остаться зелёными: они не кладут дату/URL в `text`.

---

## Новая сущность

**Нет — reuse-first.** Новая сущность EntityRegistry / новый USERTOOLS-пакет / новый CLI-флаг / новый модуль-парсер / вторая копия JIRA-regex/serverId **не вводятся**. Согласование Саши на новую сущность не требуется.

Примитивы reuse:

- даты: `parse_first_td_date` + `normalize_deadline` + новые span из тех же матчей;
- ссылки: `_append_link_or_jira` / `_is_jira_url` / `_build_jira_macro_element`;
- строка таблицы: `insert_task_into_date_row`;
- JIRA server: `config.JIRA_SERVER_NAME` / `JIRA_SERVER_ID`;
- тесты: `FakeConfluenceClient`, фикстура `page_432316254_bug_storage.xml`.

---

## Прогресс выполнения

Устойчивость к сбою: исполнитель отмечает чекбоксы по мере прохождения. Не ставить «готово» на весь план — это Саша / `GATE:done`.

### HF:plan (эта фаза)

- [x] План записан: `TZ/TaskRefresh/plans/HF-plan_taskrefresh-new-onepass_2026-09-09.md`
- [x] Факты проверены `read_file` (ТЗ §27, write_ops/date_parse/task_block/__main__, тесты, SKILL, фикстура)
- [x] Новая сущность: нет
- [ ] `REV:plan` / `GATE:plan-approve` — не эта фаза

### HF:impl

- [ ] П1 `date_parse.py`: `find_first_td_date_span`, фасад `parse_first_td_date`
- [ ] П2 `write_ops.py`: `_extract_http_urls` / `_parse_new_task_text`
- [ ] П3 `task_block.py`: `build_new_task_block(..., append_link_urls=)`
- [ ] П4 `insert_new_task`: разбор, приоритет, unresolved-префикс, retry от orig; `__main__.py` без diff
- [ ] П5 `tests/test_new_task.py`: TC-1…TC-14 (+ E1–E3)
- [ ] П6 SKILL.md: снять 476–478 и 637; описать однопроход
- [ ] Не тронуты: `config.py`, `session_store.py`, `test_session_store.py`, `pipeline.py`, `row_insert.py`, `change_spec.py`, `formatter.py`, `normalize_deadline`

### HF:test / хвост

- [ ] П5 полный регресс `pytest tests/`
- [ ] П7 живой smoke §27.7.8 (не юнит)
- [ ] `HF:docs-handoff`: версия SKILL при необходимости; ТЗ не переписывать
- [ ] `ORCH:shared-state`: `restore-all-skills.sh`; манифест только если есть `manifest_hints`
