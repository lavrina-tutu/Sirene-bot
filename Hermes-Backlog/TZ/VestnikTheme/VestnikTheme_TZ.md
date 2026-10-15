---
tool: VestnikTheme
type: skill-scripts
title: "Инструмент добавления темы в «Вестник Аналитики и Данных»"
version: 0.2.2
date: 2026-09-07
status: draft
author: архитектор (cursor-grok-4.6-high, Cursor CLI)
description: "Скрипты скилла tutu-confluence-jira (scripts/vestnik_theme_*.py): одна строка в таблицу «Итоговый материал» верхней вкладки Вестника (Confluence pageId=324382467). Не USERTOOL, не отдельный скилл."
---

# VestnikTheme — добавление темы в «Вестник Аналитики и Данных»

Скрипты скилла `tutu-confluence-jira` (`scripts/vestnik_theme_*.py`). Канон страницы: Confluence `pageId=324382467`, space `DPAN`, title «Вестник Аналитики и Данных». NEW-ENTITY снято (Q1): каталога `~/USERTOOLS/VestnikTheme/` и скилла `productivity/vestnik-theme` нет.

## Цель

По фразе Саши («добавь тему в вестник» / «добавь в вестник» / «тема для вестника» / «размести на страничке вестника») + ссылке(ам) на материал — вставить одну строку в таблицу «Итоговый материал» самого свежего периода (первый `horizontal-nav-item`) страницы `324382467`.

Критерий успеха: после `--apply` повторный GET `pageId=324382467` содержит в первой таблице первого `horizontal-nav-item` ровно одну новую (или ранее существовавшую при идемпотентном повторе) строку из 6 `<td>`, где «Тема» и «Материалы» — `ac:link`+`ri:page` на резолвнутый pageId материала, «Автор» — `ri:user` createdBy, «Блок» — отдел руководителя АИД либо пусто с предупреждением; колонки месяца и технологий пустые, если месяц не назван в команде; число `horizontal-nav-item` и прочих вкладок не изменилось.

## Ввод

Команда Саши в Telegram + одна или несколько ссылок на материал.

Формат ссылок (любая комбинация, парсер `ConfluenceSync.url_utils.parse_confluence_url`):

- числовой `pageId` (`517103930`);
- `https://dom.tutu.ru/pages/viewpage.action?pageId=…`;
- `https://dom.tutu.ru/display/SPACE/Title` (резолв в pageId через API).

Пример: «Новый экран поездок» + `517103930` / `517103955` / `517104066` → одна строка на материал (Q4).

Опционально во фразе: явное имя месяца для колонки «Предполагаемая версия - в месяц». Без явного месяца колонка пустая (Q2). Флаг CLI `--apply` = писать; без него только `--dry-run` превью (Q8, Q10).

## Выходные артефакты

1. **Таблица Вестника** (`324382467`, свежий период): одна строка «Итоговый материал» (при `--apply`). Идемпотентный повтор тех же pageId — строка не дублируется (Q10).
2. **Превью `--dry-run`** (режим по умолчанию): 6 полей строки, title вкладки, pageId/space материалов, login автора, источник «Блока» (AC / GAL / пусто), версия страницы. PUT нет.
3. **HITL-вопрос Саше** (stdout/Telegram скилла, не ErrorBus): дедуп по теме при другом pageId (Q7); контакт не найден ни в AC, ни в GAL (Q9а). PUT нет.
4. **Предупреждение**: автор найден, отдел руководителя АИД не определён → строка пишется (или превью), «Блок» пустой, текст «контакт/блок не найден».
5. **ErrorBus** (Mode A): технические сбои GET/PUT/409-исчерпание/verify. `--tool VestnikTheme --source-kind skill`.

## Логика

Инварианты рекона (storage v139, не полагаться на `h1–h6`):

- Периоды = `horizontal-nav-group` → `horizontal-nav-item`. Свежая вкладка = **первый** `horizontal-nav-item` (эталон name: «Август-Сентябрь 2026»).
- Таблица периода: 6 колонок, заголовок «Итоговый материал» — `<p>`, не heading. В таблице уже есть пустые `<tr>` — вставлять в **первую пустую** строку (все 6 ячеек пустые/`<br/>`), не append.
- `ri:page` писать после GET материала: фактические `space.key` + `title`. Не копировать `space-key` из соседних живых ячеек (прецедент DATASC vs MLE `511561073`).
- `section_patch.py` / `verify_skeleton.py` по heading на этой странице не работают; паттерн PUT без `space` и `load_confluence_token` — да.
- Дерево Confluence `310322545` / страница структуры `383117988` в цепочке v0.1.0 **не участвуют** (Q9а: без других fallback).

Цепочка блоков:

1. **ParseIntent.** Фраза + URL/pageId → список pageId, опциональный месяц, флаг `--apply` vs dry-run.
2. **FetchMaterial.** GET каждого pageId (`expand=body.storage,version,space,history`): `title`, `space.key`, `history.createdBy` (`username`, `userKey` / `displayName`). Не `version.by`.
3. **ResolveAuthor.** userkey createdBy прогнать через тот же путь, что `userkey_resolve.py` (`GET /rest/api/user?key=`). В ячейку — только подтверждённый `ri:userkey`. Прямой PUT непроверенного ключа запрещён (Q6).
4. **ResolveAIDUnit (Q2, Q9, Q9а).**
    1. `ContactStore.get_contact(username)` / `find_contacts`.
    2. Если контакта нет → **inline** EWS `ResolveNames` по login/email (латиница; кириллический GAL-поиск не использовать). CLI/очередь `ExchangeOrgLookup`/`orglookup` **не** вызывать (Q9а).
    3. GAL нашёл человека → в этой сессии взять manager/department/team для шага (4); **в `contacts.enc` не писать** (импорт — бэклог Q9б).
    4. GAL не нашёл → **СТОП**, вопрос Саше, PUT нет.
    5. Контакт есть (AC или GAL in-memory): идти по `reports_to` до руководителя АИД (login из фиксированного набора глав с `383117988`: `peretyatkova`, `zhirov`, `kotelnikova`, `rasov`, `nabieva`, `alekseeva.ym`, `sereda`, `tkachenkoav`; либо сам автор в этом наборе; стоп на `aralov` как директоре — тогда отдел = `department`/`team` предыдущего узла). «Блок» = `department` руководителя АИД, если пусто — `team`. Если строка совпадает с коротким ярлыком скрипта (`DS`, `BI` и т.п. — таблица в коде по главам структуры) — писать ярлык, иначе текст отдела как в контакте.
    6. Человек известен, руководитель АИД / отдел не выводятся → предупреждение, «Блок» пустой, строку не блокировать.
5. **ComposeRow.** Собрать 6 ячеек (см. «Поля таблицы»). Несколько pageId — одна строка (Q4): «Тема» = title **первой** страницы как `ac:link`+`ri:page`; «Материалы» = все резолвнутые ссылки.
6. **SelectFreshTab.** Первый `horizontal-nav-item` в единственном `horizontal-nav-group`. Если макроса нет или у первой таблицы ≠ 6 `<th>` — СТОП, ErrorBus, PUT нет.
7. **Dedup (Q7, Q10).** В этой таблице: если **все** входные pageId уже есть в `ri:page` / `pageId` ячеек — идемпотентный no-op (успех, без новой строки). Если совпал текст темы, но pageId другие — СТОП, вопрос Саше. Без угадывания.
8. **RowPatch.** Заменить inner первой пустой `<tr>` эталонной разметкой 6 `<td>`. Пустых строк нет — СТОП (не append, не трогать другие вкладки). Патч только этой таблицы; остальной storage байт-в-байт.
9. **PUT.** Только `--apply`. Payload как `section_patch.build_put_payload`: `title` + `type:page` + `version.number+1` + полный body, **без `space`**. Клиент: `ConfluenceClient.update_page` или PUT из `section_patch.py`. LLM не генерирует `body.storage`. HTTP 409: GET → снова шаги 6–8 → PUT, максимум 2 ретрая; исчерпание → ErrorBus, выход ≠ 0.
10. **Verify.** GET после PUT: version = ожидание (или честно подхвачен concurrent +1 после ретрая); число `horizontal-nav-item` не изменилось; первый item `name` тот же; в целевой таблице 6 `<th>` и в новой строке 6 `<td>`; pageId/title материала есть в «Тема»/«Материалы»; нет утечки брифа («Не копировать», «см. бриф»). Провал = не успех; ErrorBus.
11. **ErrorBus.** Mode A, `~/.hermes/scripts/report_error.sh --tool VestnikTheme --source-kind skill` на технические ошибки. HITL-вопросы — ответ скилла Саше, не шина.

## Поля таблицы (Итоговый материал)

Живые заголовки (порядок фиксирован): `Предполагаемая версия - в месяц` | `Блок` | `Тема` | `Материалы` | `Используемые технологии` | `Автор`.

| # | Колонка на странице | v0.1.0 |
|---|---|---|
| 1 | Предполагаемая версия - в месяц | Пусто. Заполнять **только** если месяц явно назван в команде (не из `name` вкладки) (Q2). |
| 2 | Блок | Текст отдела руководителя АИД автора (Q2). Ярлык вроде `DS`/`BI`, если сработал словарь скрипта; иначе `department`/`team` контакта главы. Не вывелось — пусто + предупреждение. Колонки «подразделение» нет: подразделение = эта ячейка. |
| 3 | Тема | Полный `title` основной (первой) страницы материала как гиперссылка `ac:link` + `ri:page` (`ri:space-key` + `ri:content-title` из GET, не из соседних строк) (Q3, Q4). |
| 4 | Материалы | Те же `ac:link`+`ri:page`: одна ссылка — дубль темы; несколько pageId — все ссылки в этой ячейке (Q4). |
| 5 | Используемые технологии | Не заполнять (пустая ячейка) (Q2). |
| 6 | Автор | `@mention`: `<ac:link><ri:user ri:userkey="…"/></ac:link>` создателя `history.createdBy`, ключ после `userkey_resolve` (Q5, Q6). Не plaintext ФИО, не last modifier. |

Эталон пустой `<tr>` (куда писать):

```html
<tr><td style="vertical-align: top;"><br /></td><td style="vertical-align: top;"><span> </span></td><td><p class="with-breadcrumbs" style="text-align: left;"><br /></p></td><td style="vertical-align: top;"><br /></td><td style="vertical-align: top;"><br /></td><td style="vertical-align: top;"><div class="content-wrapper"><br /></div></td></tr>
```

## Что НЕ трогать

- Страницу `324382467` целиком, кроме целевой таблицы первого `horizontal-nav-item` (другие вкладки, PDF `view-file`, expand, jira-макросы, info-макрос, пустые строки кроме первой заполняемой).
- `section_patch.py` / `verify_skeleton.py` как библиотеку heading-span (не ломать контракт PFS/других страниц); для Вестника — отдельные `vestnik_theme_*.py`.
- ConfluenceSync `converter.html_to_md` / `md_to_html`; LLM → `body.storage`.
- Прямой PUT `ri:userkey` в обход `userkey_resolve` / `GET /rest/api/user?key=`.
- Схему `contacts.enc` (`schema_version`, ключ `login`, `CUSTOM_FIELDS`). Точечный импорт контакта из Exchange в store — **вне скоупа**, бэклог **Q9б** (не реализовывать в VestnikTheme).
- `entities.json` не трогать и не читать для контактов (в нём контактных полей нет; контакты — только `contacts.enc`, единственный источник `login` / `reports_to` / manager).
- CLI, очередь `needs_gal.jsonl`, крон и запись в ContactStore инструмента **ExchangeOrgLookup** / `orglookup` — в цепочку не встраивать (Q9а). EWS только inline в `vestnik_theme_*.py` для резолва блока.
- Пайплайны ProtocolFromSummary, TaskRefresh, ObsidianFromConfluence, MofsIndex, AggregateFromMeetings.
- `~/.hermes/cron/jobs.json`, новые кроны, рестарт Gateway.
- Страницу «Расчёт баллов за Вестник Аналитики» (`pageId=496620177`) — другой инструмент.
- HTML-комментарии и `data-*` как якоря строк (Confluence DC вырезает при PUT).
- Каталог `~/USERTOOLS/VestnikTheme/` и скилл `productivity/vestnik-theme`.
- `MAIN_TZ_INVENTORY.md` в этой операции (карточка TZ:finalize).

## Связи с существующими инструментами

| Инструмент | Роль | Что берём | Чего нет |
|---|---|---|---|
| tutu-confluence-jira | дом скриптов (Q1) | `load_confluence_token`, PUT без `space`, `userkey_resolve.py`, паттерн GET→точечный patch→PUT | heading-`section_patch` на Вестнике |
| ConfluenceSync | клиент API | `get_page`, `get_children`, `update_page`, `url_utils`; токен `~/USERTOOLS/ConfluenceSync/.env` | converter md/html; `pull --to-file` в этом потоке |
| AnywhereContacts | read оргцепочки | `ContactStore.get_contact` / `find_contacts`, `department`/`team`/`reports_to`, `render_contact(level="summary")` для превью | запись нового контакта из GAL (Q9б) |
| ErrorBus | write ошибок | `report_error.sh --tool VestnikTheme` Mode A | крон-registry; Mode B wrap |
| ExchangeOrgLookup | нет в цепочке | протокол EWS ResolveNames известен из его ТЗ | вызов CLI/очереди/записи в AC |

Справочник `entities.json` в v0.1.0 не используется (в нём контактных полей нет; карта сущностей не нужна для цепочки подразделения); используется только `contacts.enc` (AnywhereContacts).

Связей нет с: MoveFromFF, ProtocolFromSummary, TaskRefresh, OFC, MofsIndex, MeetingScheduler, DialogBacklog (кроме будущего бэклога Q9б).

## Связи с инфраструктурой Hermes

- Вызов: on-demand из Telegram через скилл `tutu-confluence-jira` (Cursor CLI / агент default). Крон не ставить.
- Запись Confluence: только скрипт (`vestnik_theme_*.py` + клиент ConfluenceSync / PUT `section_patch`). Не LLM→storage.
- Токены: `CONFLUENCE_TOKEN` из `~/USERTOOLS/ConfluenceSync/.env` (не `source` всего файла); `CONTACTS_ENCRYPTION_KEY` через `usertools_env`; EWS — те же креды, что MeetingScheduler/OrgLookup (`~/.config/hermes/.env`), без нового секрета.
- Gateway не рестартовать.
- ErrorBus: `--source-kind skill`, без записи в `instrumentation_registry.json` (нет cron `job_id`).

## Контракты экосистемы

### Источник истины

- Таблица Вестника: Confluence `api_confluence`, страница `324382467` (человек + VestnikTheme-скрипты — писатели одной строки свежего периода).
- Контакты: AnywhereContacts (`ContactStore`, `contacts.enc`, ключ `login`). VestnikTheme v0.1.0 — только читатель.
- Материалы: Confluence-страницы по входным pageId (title, space, `history.createdBy`).

### Входные контракты

| Поле | Тип | Обязательность | Источник (кто отдаёт) | Формат/enum |
|---|---|---|---|---|
| command_text | str | required | Hermes / скилл tutu-confluence-jira (Telegram Саши) | фраза + URL или pageId |
| material_page_ids | str | required | ParseIntent / ConfluenceSync.url_utils | один или несколько pageId через запятую |
| month_override | str | optional | фраза Саши | имя месяца; пусто = не писать в колонку 1 |
| apply | bool | required | CLI `--apply` | false = dry-run (дефолт); true = PUT |
| login | str | required | Confluence history.createdBy.username | login = email до "@" |
| created_by_userkey | str | required | Confluence history.createdBy.userKey | opaque userkey; в storage только после GET /rest/api/user?key= |
| contact.department | str | optional | AnywhereContacts.ContactStore | текст отдела |
| contact.team | str | optional | AnywhereContacts.ContactStore | текст команды |
| contact.reports_to | str | optional | AnywhereContacts.ContactStore | login руководителя в той же таблице |
| body.storage.value | str | required | api_confluence page 324382467 | Confluence storage XHTML |
| page_version | int | required | api_confluence version.number | целое; PUT = +1 |

### Выходные контракты

| Поле | Тип | Потребитель (кто получает) | Формат/enum |
|---|---|---|---|
| vestnik_row_theme | str | api_confluence таблица свежего периода | storage: ac:link + ri:page |
| vestnik_row_materials | str | api_confluence таблица свежего периода | один или несколько ac:link + ri:page |
| vestnik_row_author | str | api_confluence таблица свежего периода | ac:link + ri:user ri:userkey |
| vestnik_row_block | str | api_confluence таблица свежего периода | текст отдела или пусто |
| dry_run_preview | str | Telegram / stdout скилла | 6 полей + вкладка + version; без PUT |
| hitl_question | str | Саша (Telegram) | дедуп темы или «контакт не найден в AC и GAL» |
| error.tool | str | ErrorBus | VestnikTheme |
| error.source_kind | enum[skill] | ErrorBus | skill |

### Зависимости

- Получает от: [ConfluenceSync, AnywhereContacts, api_confluence, api_exchange, tutu-confluence-jira]
- Отдаёт: [api_confluence, ErrorBus]

### Breaking changes policy

- Версия ТЗ (`version` во frontmatter) ≠ схема таблицы. Схема таблицы = 6 колонок живой страницы; отдельного `schema_version` файла нет.
- Если GET свежей таблицы даёт ≠ 6 `<th>` — не патчить, ErrorBus, эскалация в ТЗ (breaking UI Вестника).
- Смена макроса вкладок (`horizontal-nav-item` → другой) — breaking для `vestnik_theme_patch.py`, править скрипт + bump version ТЗ.
- `contacts.enc` не мигрировать из этого инструмента.

### Границы («что НЕ трогать»)

- Не менять `login` как ключ AnywhereContacts.
- Не выводить raw email в превью без `render_contact`.
- Не передавать `space` в PUT существующей страницы.
- Не вызывать ExchangeOrgLookup CLI и не писать `contacts.enc` из GAL в v0.1.0.

## Открытые вопросы

Нет открытых (закрыты брифом Саши Q1–Q10).

Отложено вне скоупа, не блокирует v0.1.0: **Q9б** — полноценный импорт/запись контакта из Exchange в `contacts.enc` через `ContactStore.update_contact` / `add_alias` (отдельная задача бэклога).

## Шаги реализации

Каждый шаг проверяем отдельно; реализация — скрипты в `~/.hermes/skills/productivity/tutu-confluence-jira/scripts/` (симлинк на workspace skills). Код в этом ТЗ не пишется.

1. **Каркас CLI.** Добавить `vestnik_theme.py` (`add`, `--page-id` repeatable, `--dry-run` дефолт, `--apply`). Без `--apply` сеть GET разрешена, PUT нет. Проверка: `--help` и dry-run на несуществующем pageId → ошибка без PUT.
2. **Токены.** `load_confluence_token` + `usertools_env` для AC; EWS-креды как у OrgLookup. Проверка: GET `324382467` возвращает title «Вестник Аналитики и Данных».
3. **ParseIntent.** Разбор URL/pageId через `parse_confluence_url`; несколько id → список с сохранением порядка (первый = основная тема). Проверка: три id из брифа → список длины 3.
4. **FetchMaterial.** GET title, space.key, createdBy. Проверка: `517103930` → Шубчик / `shubchik`, space TRAVELCENTER.
5. **userkey_resolve.** GET `/rest/api/user?key=` для createdBy.userKey; пустой ответ → СТОП + ErrorBus. Проверка: ячейка Автора содержит тот же userkey, что API.
6. **ResolveAIDUnit.** AC `get_contact` → walk `reports_to` → набор глав АИД → текст «Блок». Нет контакта → inline EWS ResolveNames (латиница). Нет в GAL → exit с HITL-текстом, PUT нет. Есть человек, нет отдела → warning, блок пустой. Проверка фикстурами: hit AC; miss AC + hit GAL (in-memory); miss оба; hit без reports_to.
7. **SelectFreshTab + schema guard.** Первый `horizontal-nav-item`, таблица после «Итоговый материал», 6 `<th>`. Иначе СТОП + ErrorBus. Проверка: на снятом storage v139 первый name = «Август-Сентябрь 2026» (или актуальный GET).
8. **ComposeRow.** Собрать inner `<tr>`: месяц опционально; блок; тема = ri:page первой; материалы = все ri:page; технологии `<br/>`; автор ri:user. space-key только из GET материала. Проверка: в XML 6 td, нет DATASC если GET сказал другой space.
9. **Dedup.** Сканировать таблицу свежего периода. Все pageId уже есть → no-op success. Тема совпала, pageId другие → HITL, PUT нет. Проверка: повторный `--apply` тех же id не увеличивает число непустых строк.
10. **RowPatch.** Первая пустая `<tr>` (эталон выше); нет пустой — СТОП. Не менять соседние макросы. Проверка: diff storage затрагивает только эту tr.
11. **PUT `--apply`.** Payload без `space`, version+1. 409 → GET + шаги 7–10, ≤2 ретрая. Проверка: version на странице +1 относительно превью.
12. **Verify.** Чеклист шага 10 логики (макросы вкладок, 6 th/td, ссылка, автор, нет brief-leak). Провал → ErrorBus, статус не успех.
13. **ErrorBus Mode A.** Обёртка except/ненулевой verify → `report_error.sh --tool VestnikTheme --source-kind skill --stage <имя шага>`. HITL не слать в шину. Проверка: искусственный 404 материала даёт событие в ErrorBus, страница Вестника без PUT.
14. **Документация скилла.** В `tutu-confluence-jira/SKILL.md` — секция VestnikTheme: триггеры фраз, `--dry-run`/`--apply`, запрет LLM-storage. Крон не описывать. `restore-all-skills.sh` — только при реализации, не в этой записи ТЗ.

## Приложения к ТЗ

Не создаются. Рекон (вкладки, эталон `<tr>`, pageId `310322545`/`383117988`) включён в разделы «Логика» и «Поля таблицы».
