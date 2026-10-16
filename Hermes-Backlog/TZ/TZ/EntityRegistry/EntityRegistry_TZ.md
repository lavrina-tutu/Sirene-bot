---
tool: EntityRegistry
status: draft
version: 0.4.0
author: Opus (черновик для Саши)
created: 2026-07-16
updated: 2026-09-29
last-section-added: "Схема v1.2 related_pages/people/loop_channels + backfill 11 проектов + 404-алерт (TZ:patch 29.09.2026, DEV/entities-backfill, t_e1c9acf8)"
# решения зафиксированы 16.07.2026 (бриф с Сашей завершён); схема v1.2 — бриф 21–22.09.2026
---

# EntityRegistry — единый канонический реестр проектов/сущностей

## Приложения к ТЗ

| Файл | Содержание | Дата |
|---|---|---|
| `appendix_tools_registry_22072026.md` | Реестр инструментов (tools): что добавлено в entities.json и что исключено навсегда — итог брифа 22.07.2026 | 22.07.2026 |
| `appendix_entities-schema-v12_brief_20260922.md` | Бриф-исходник схемы v1.2 (бывший неканонический «мастер» `EntitiesSchemaV12_TZ.md`); канон — секция v0.4.0 этого файла | 22.09.2026 / поглощён 29.09.2026 |

## Контракты экосистемы

EntityRegistry — владелец спецификации `entities.schema.json` и канона `entities.json`. Данные мутирует только EntityRegistryCLI. Формат контракта данных: `json:entities_v1`.

### Источник истины
- Владелец спецификации и схемы: EntityRegistry (`WorkVault/Registries/entities.schema.json`)
- Владелец канона данных: EntityRegistry (спецификация `WorkVault/Registries/entities.json`); мутации выполняет EntityRegistryCLI

### Входные контракты
| Поле | Тип | Обязательность | Источник (кто отдаёт) | Формат/enum |
|---|---|---|---|---|

### Выходные контракты
| Поле | Тип | Потребитель (кто получает) | Формат/enum |
|---|---|---|---|
| schema_version | str | EntityRegistryCLI, ProtocolFromSummary, TaskRefresh, workvault-rag, ObsidianFromConfluence, MarkObjectsFromSummary | semver в корне `entities.json`; канон этой работы = `"1.2"` (json:entities_v1) |
| slug | str | EntityRegistryCLI, ProtocolFromSummary, TaskRefresh, workvault-rag | Ключ записи (json:entities_v1), ^[a-z0-9_]+$ |
| kind | enum[project, one_on_one, multisync, sync_aid, unknown, tool] | EntityRegistryCLI, ProtocolFromSummary, TaskRefresh, workvault-rag | Тип сущности |
| parent | str | EntityRegistryCLI, ProtocolFromSummary, TaskRefresh, workvault-rag | slug родителя или null |
| display_name | str | EntityRegistryCLI, ProtocolFromSummary, TaskRefresh, workvault-rag | Отображаемое имя |
| aliases | str | EntityRegistryCLI, ProtocolFromSummary, TaskRefresh, workvault-rag | Список альтернативных имён (JSON array), json:entities_v1 |
| pfs | str | EntityRegistryCLI, ProtocolFromSummary, TaskRefresh | Опциональный блок pfs (json:entities_v1): page_id, tag, page_layout, content_column_index |
| pfs.page_id | str | EntityRegistryCLI, ProtocolFromSummary, TaskRefresh | Confluence pageId (строка цифр) |
| pfs.tag | str | EntityRegistryCLI, ProtocolFromSummary, TaskRefresh | Префикс-тег проекта |
| pfs.page_layout | str | EntityRegistryCLI, ProtocolFromSummary, TaskRefresh | Лейаут страницы Confluence |
| pfs.content_column_index | int | EntityRegistryCLI, ProtocolFromSummary, TaskRefresh | Индекс колонки с контентом |
| related_pages | array | EntityRegistryCLI, ProtocolFromSummary, ObsidianFromConfluence, workvault-rag | v1.2 optional; объекты {page_id, role, primary?, title?}; корень = primary:true |
| related_pages.page_id | str | EntityRegistryCLI | Confluence pageId, pattern ^[0-9]+$ |
| related_pages.role | enum[charter, brief, tasks, report, other] | EntityRegistryCLI | роль связанной страницы |
| related_pages.primary | bool | EntityRegistryCLI | ровно одна true на непустой related_pages |
| people | array | EntityRegistryCLI | v1.2 optional; объекты {login, role?}; только логины, без ФИО |
| people.login | str | EntityRegistryCLI | pattern ^[a-z][a-z0-9._-]*$ |
| loop_channels | array | EntityRegistryCLI, MoveFromLoop, LoopChannelDigest | v1.2 optional; uniqueItems, pattern ^[a-z0-9_-]+$ |

### Зависимости
- Получает от: []
- Отдаёт: [EntityRegistryCLI, ProtocolFromSummary, TaskRefresh, workvault-rag, ObsidianFromConfluence, MarkObjectsFromSummary, ErrorBus]

### Breaking changes policy
- Версионирование формата: semver на поле `schema_version` внутри `entities.schema.json` / `entities.json` (не версия этого ТЗ)
- При breaking change схемы: бамп `schema_version`, уведомить потребителей из «Отдаёт»; CLI валидирует до записи
- v1.1 → v1.2 **не breaking** для читателей: три новых поля optional, доступ через `.get()`; бамп `schema_version` обязателен (пин-тест)

### Границы («что НЕ трогать»)
- Не мутировать `entities.json` из этого инструмента — запись данных только через EntityRegistryCLI; исполнитель `hermes-feature` в этой цепочке в `entities.json` / `EcosystemManifest.json` `tools{}` / `.env` / `jobs.json` **не пишет** (это `ORCH:shared-state`)
- Не менять правила резолва ProtocolFromSummary (`route.py`) и адаптер TaskRefresh — они потребители канона, не владельцы схемы
- Не создавать поля `root_confluence_id`, `completion_report_id`, `start_date`, `end_date`; не вводить status-гварды публикации

## Цель

Свести три существующих (частично рассинхронизированных) источника данных о проектах/сущностях-темах к **одному** каноническому JSON-реестру, из которого потребители читают данные (никогда не дублируя их у себя):

1. `ProtocolFromSummary/protocolfromsummary/config.py::ROUTES` (16 записей, маршрутизация → Confluence).
2. `WorkVault/Tools/TaskRefresh/project_registry.json` (16 записей, ручное дублирование; используется TaskRefresh для матчинга pageId ↔ slug ↔ tag; загружается `taskrefresh/project_registry.py`).
3. `~/.hermes/skills/research/workvault-rag/SKILL.md::Шаг 3` — сейчас ссылается на `ROUTES` только текстом-инструкцией; в момент выполнения работает по свободному тексту + алиасам, читая `config.py` глазами.

Побочная цель: сделать реестр иерархичным (`parent`) — так, чтобы можно было завести дочерние сущности (`цу` → `devrel`, потенциально `omd` → `ml_platforma` при подтверждении) без ломки текущей маршрутизации PFS.

## Контекст

- **PFS**: прод с 10.07.2026, 135/135 тестов, `route.py` реализует нетривиальные правила резолва (Аралов+Ткаченко → aralov_1on1, fallback по составу участников департамента АиД → sink_aid, «неразобранное» как терминальный fallback). Правила зависят ТОЛЬКО от `ROUTES` через ключи-слуги + поля `page_id/tag/kind/name_match`.
- **TaskRefresh**: прод с 13.07.2026, ставится в общий venv PFS (`/home/tkachenkoav/USERTOOLS/ProtocolFromSummary/.venv`), импортирует `protocolfromsummary.confluence_ext` и `protocolfromsummary.contacts_resolver`. От `ROUTES` **напрямую не зависит** (проверено: `grep ROUTES` в TaskRefresh — нет вхождений). Ведёт свой `project_registry.json`, вручную поддерживаемый в синхроне с `ROUTES` (комментарий в самом JSON это подтверждает).
- **workvault-rag**: агентский скилл; читает файлы через file-tools, работает Sonnet/Opus в момент запроса. JSON-файл — самый удобный формат для агентского чтения.
- **Новые сущности** для ввода в реестр:
  - `devrel` (kind=`project`, БЕЗ Confluence-протокола пока — блок `pfs` отсутствует).
  - `цу` (kind=`project`, `parent="devrel"`, БЕЗ отдельного Confluence-протокола; текущая маршрутизация PFS для встреч ЦУ идёт в «неразобранное» с тегом `ЦУ.` — это отдельная **транспортная** запись `tsu` в ROUTES, её НЕ трогаем).
  - `omd` (OpenMetaData) — самостоятельная запись `kind="tool"`, `parent=null`, БЕЗ блока `pfs` (нет Confluence-протокола, в ROUTES не попадает). Решение Саши 16.07.2026 (см. §Решения Саши, п.2).

## Архитектурное решение

### Формат — JSON

`WorkVault/Registries/entities.json` (новая директория `WorkVault/Registries/` — общая, для будущих канонических реестров; выбор JSON, а не Python-модуля, обоснован тем, что 2 из 3 потребителей — не Python (workvault-rag = агент через file-tools, будущий TaskRefresh продолжит читать JSON), а Python-потребитель (PFS) легко читает JSON через stdlib).

### Схема записи (черновик, финал уточняется на Шаге 1)

```jsonc
{
  "schema_version": "1.0",
  "entities": {
    "trisigma": {
      "kind": "project",           // project | one_on_one | multisync | sync_aid | unknown | tool
      "parent": null,               // slug родителя или null
      "display_name": "Trisigma",
      "aliases": ["trisigma"],      // ← бывший name_match; регистронезависимый матч
      "pfs": {                      // опциональный блок; ЕСТЬ ⇔ сущность попадает в ROUTES
        "page_id": "490170597",
        "tag": "Trisigma.",
        "page_layout": "2col",     // опционально; дефолт "2col"
        "content_column_index": 1  // опционально; для нестандартных таблиц
      }
    },
    "devrel": {
      "kind": "project",
      "parent": null,
      "display_name": "DevRel",
      "aliases": ["devrel", "дев-рел", "девелопер релейшнс"]
      // без блока pfs — нет Confluence-протокола, в ROUTES не попадает
    },
    "cu": {
      "kind": "project",
      "parent": "devrel",
      "display_name": "ЦУ (Central University)",
      "aliases": ["central university", "централ юниверсити"]
      // ВАЖНО: алиасы "цу." / "цу " НЕ дублируем сюда — они принадлежат
      // транспортной записи "tsu" (ниже), которая гарантирует прежнюю
      // маршрутизацию PFS в «неразобранное» с тегом "ЦУ.".
    },
    "tsu": {  // транспортная запись PFS, kind=unknown, поведение PFS ЗАМОРОЖЕНО
      "kind": "unknown",
      "parent": "cu",              // логическая связь для поиска, не для PFS
      "display_name": "ЦУ → неразобранное (маршрут PFS)",
      "aliases": ["цу.", "цу "],
      "pfs": {"page_id": "508804852", "tag": "ЦУ."}
    },
    "omd": {
      "kind": "tool",
      "parent": null,
      "display_name": "OMD (OpenMetaData)",
      "aliases": ["omd", "openmetadata", "кумд"]
      // без блока pfs — нет Confluence-протокола, в ROUTES не попадает
    }
    // ... остальные 15 записей — 1:1 из текущего ROUTES ...
  }
}
```

Инвариант: **набор ключей + значения `pfs.*` + значения `aliases` для всех 16 текущих ROUTES-записей побитово совпадают с текущими значениями `config.py::ROUTES`**. Проверяется автотестом (Шаг 3).

### Разделение ролей полей

- `aliases` — для матчинга **и** в PFS (`route.py:_match_by_name`), **и** в workvault-rag (Шаг 3).
- `pfs.*` — только для PFS. Сущности без блока `pfs` в `ROUTES` не попадают вовсе.
- `parent`, `kind`, `display_name` — для workvault-rag (иерархическая навигация, «покажи всё по DevRel» = DevRel + ЦУ + …) и для UI/логов.

### Как PFS начинает потреблять реестр

`config.py::ROUTES` превращается в **тонкую функцию-обёртку**: при импорте модуля один раз читает `entities.json` и собирает словарь той же структуры, что и сейчас (только записи с блоком `pfs`, преобразованные к текущей форме `{page_id, tag, kind, name_match}`, где `name_match = aliases`). Всё остальное в `config.py` (`PILOT_ROUTES = ROUTES`, `EXCLUDED_PAGE_ID_OBSHY_SPISOK`, `SINK_AID_ENTITY`, `VSTRECHI_NERAZOBRANNOE_ENTITY`, `VSTRECHI_PRO_ENTITY`, `ARALOV_1ON1_ENTITY`, `DEFAULT_ASSIGNEE_LOGIN`, `DEADLINE_FALLBACK_DAYS`) остаётся как есть, ниже нового кода загрузки.

`route.py` — **не трогаем**. Он видит `ROUTES` того же вида, никаких сигнатур/поведения не меняем.

### Как TaskRefresh начинает потреблять реестр

Решение Саши (16.07.2026, §Решения Саши, п.1) — **вариант A, сразу переключить**. `taskrefresh/project_registry.py::ProjectRegistry.load()` дорабатывается: основной источник — `entities.json` (адаптер сворачивает записи с блоком `pfs` к текущему формату `{pageIds:[…], tag}`); старый `WorkVault/Tools/TaskRefresh/project_registry.json` остаётся как **legacy-fallback** на переходный период (используется, только если `entities.json` не найден/битый), в его `_comment` фиксируется, что source of truth — `entities.json`. Ручное поддержание legacy-файла в синхроне более не требуется; удаление файла — после 1–2 недель прод-наблюдения (отдельный follow-up).

### Как workvault-rag начинает потреблять реестр

Раздел «Шаг 3 — проект/тема» в SKILL.md переписывается: канонический источник — `WorkVault/Registries/entities.json`. Порядок матчинга проекта в запросе / названии встречи:
1. Прочитать `entities.json`.
2. Пройтись по `entities[*].aliases` (регистронезависимо, substring/startswith по правилам, аналогичным `route.py:_match_by_name`).
3. При множественных матчах — выбирать по `kind` (`project` > `multisync` > `unknown`), при неоднозначности спрашивать Сашу.
4. Если нет совпадения — прямо отметить Саше «проекта нет в реестре, кандидат на добавление» (текущее поведение сохраняется).

## Шаги реализации

**Шаг 0. Заморозка baseline (защита от регрессии).**
- Зафиксировать текущий SHA файла `config.py`.
- Прогнать `pytest` PFS: должно быть 135/135. Записать в CI-артефакт baseline-снимок `ROUTES` (сериализация `repr(sorted(ROUTES.items()))`) — референс для diff-теста.
- Прогнать `pytest` TaskRefresh — зафиксировать текущий счёт (для проверки, что мы его тоже не сломали).

**Шаг 1. Схема + пустой реестр.**
- Создать `WorkVault/Registries/entities.json` (пока без записей, только `{"schema_version": "1.0", "entities": {}}`).
- Создать `WorkVault/Registries/README.md` с описанием схемы (перенести из этого ТЗ раздел «Схема записи»).
- Опционально: JSON Schema (`entities.schema.json`) для валидации.

**Шаг 2. Наполнение реестра — миграция 16 записей ROUTES 1:1 + новые.**
- Скопировать 16 записей ROUTES в `entities.json`, приведя к новой схеме (`name_match` → `aliases`, вложить `page_id/tag/kind/…` в блок `pfs`).
- Добавить сущности БЕЗ блока `pfs`: `devrel`, `cu` (parent=devrel).
- Добавить `omd` как `kind="tool"`, `parent=null`, `aliases=["omd","openmetadata","кумд"]`, БЕЗ блока `pfs` (решение Саши, §Решения Саши, п.2).
- Ручная сверка diff'ом: должно ровно соответствовать текущему `config.py::ROUTES` + 2 новые записи.

**Шаг 3. Тесты на сам реестр (независимо от потребителей).**
- `tests/test_entities_registry.py`:
  - JSON парсится, схема валидна.
  - Уникальность `slug`.
  - Все `parent` указывают на существующий `slug`.
  - Для всех записей с блоком `pfs`: `page_id` — строка из цифр, `tag` — строка или `None`, `kind ∈ {project, one_on_one, multisync, sync_aid, unknown}` (для записей БЕЗ блока `pfs` допустим также `kind=tool`).
  - Уникальность пары `(pfs.page_id, pfs.tag)` для всех записей с блоком `pfs` (решение Саши, §Решения, п.7; валидные дубли page_id между разными tag — допустимы).
  - **Baseline-инвариант**: словарь, собранный из записей с `pfs` в форму текущих ROUTES, побитово равен baseline из Шага 0 (за исключением новых записей без `pfs`).

**Шаг 4. PFS — подключение реестра (ноль изменений в `route.py`).**
- В `config.py` заменить литерал `ROUTES = {...}` на функцию `_load_routes_from_registry()` + `ROUTES = _load_routes_from_registry()`.
- `PILOT_ROUTES = ROUTES` — сохранить.
- Все прочие константы (`EXCLUDED_PAGE_ID_OBSHY_SPISOK`, `SINK_AID_ENTITY`, `VSTRECHI_NERAZOBRANNOE_ENTITY`, `VSTRECHI_PRO_ENTITY`, `ARALOV_1ON1_ENTITY`, `DEFAULT_ASSIGNEE_LOGIN`, `DEADLINE_FALLBACK_DAYS`) — оставить как есть.
- Путь к реестру: `Path("/home/tkachenkoav/WorkVault/Registries/entities.json")` — константа в верху `config.py`, с ENV-override для тестов (`ENTITIES_REGISTRY_PATH`).
- **Проверка:** прогон всех тестов PFS → 135/135 без изменений в тестах.
- Diff `repr(sorted(ROUTES.items()))` с baseline из Шага 0 → пустой.

**Шаг 5. TaskRefresh — полное подключение к реестру (вариант A, решение Саши).**
- Переписать `taskrefresh/project_registry.py::ProjectRegistry.load()`: основной источник — `WorkVault/Registries/entities.json`. Реализовать адаптер, преобразующий записи с блоком `pfs` из `entities.json` к текущему внутреннему формату TaskRefresh (`{slug: {pageIds:[…], tag, …}}`). Путь к реестру — константа с ENV-override (`ENTITIES_REGISTRY_PATH`), симметрично PFS.
- Legacy-fallback: если `entities.json` недоступен/битый — читать старый `WorkVault/Tools/TaskRefresh/project_registry.json` (текущий код-путь как safety-net на переходный период). Обновить `_comment` в старом файле: «legacy fallback, source of truth — WorkVault/Registries/entities.json, ручная синхронизация не требуется».
- Регрессионный тест эквивалентности: unit-тест «набор `(slug, pageIds, tag)`, полученный из `entities.json` через адаптер, эквивалентен содержимому legacy `project_registry.json`» — валидатор рассинхрона на время переходного периода, пока legacy-файл ещё лежит рядом.
- **Полный regression-прогон:** все существующие тесты TaskRefresh (`pytest`) — 100% зелёных ПОСЛЕ рефакторинга `ProjectRegistry.load()` (не просто baseline count из Шага 0, а именно новый прогон против переработанного кода).
- **Smoke-тест CLI:** прогнать реальный TaskRefresh CLI (не только pytest) — как минимум `taskrefresh --dry-run` / эквивалент по 2–3 проектам, чтобы убедиться, что интеграция с прод-Confluence/Tracker не сломана (см. §Регрессионный риск).
- Удаление legacy-файла — вне scope этого ТЗ, отдельный follow-up после 1–2 недель прод-наблюдения.

**Шаг 6. workvault-rag — обновление SKILL.md.**
- Переписать раздел «Шаг 3 — проект/тема»: указать `WorkVault/Registries/entities.json` как канонический источник; описать порядок матчинга (см. выше).
- Раздел «Definition of Done» — обновить пункты про `ROUTES`, заменив на `entities.json`.
- Bump `version: 2.0.0` → `2.1.0`.

**Шаг 7. Документация и cleanup.**
- В `ProtocolFromSummary_TZ.md` §1.3: добавить ссылку «источник данных — `WorkVault/Registries/entities.json`, схема — `WorkVault/Registries/README.md`».
- В `WorkVault/Tools/TaskRefresh/project_registry.json` — добавить в поле `_comment` пометку «legacy, source of truth — WorkVault/Registries/entities.json» (или удалить файл на этапе A — по решению).
- Обновить `MAIN_TZ_INVENTORY.md` — добавить EntityRegistry.

## Критерии успеха

- PFS: `pytest` → 135/135, `route.py` не тронут ни на строку.
- PFS: `repr(sorted(ROUTES.items()))` побитово совпадает с baseline из Шага 0.
- TaskRefresh: `ProjectRegistry.load()` читает `entities.json` как основной источник; все существующие тесты зелёные ПОСЛЕ рефакторинга; добавлен регрессионный тест эквивалентности legacy↔entities.json; прогнан smoke-тест CLI на 2–3 проектах.
- workvault-rag: SKILL.md ссылается на `entities.json`, «Шаг 3» описывает матчинг по алиасам с явной иерархией `parent`.
- Новые сущности `devrel`, `cu` в реестре присутствуют, находятся workvault-rag'ом по алиасам, **не** попадают в `ROUTES` (нет блока `pfs`).
- Новая сущность `omd` (kind=`tool`, parent=`null`) присутствует в реестре, находится workvault-rag'ом по алиасам `["omd","openmetadata","кумд"]`, **не** попадает в `ROUTES`.
- Транспортная запись `tsu` в `ROUTES` сохранена без изменений (page_id="508804852", tag="ЦУ.", kind="unknown", aliases=["цу.", "цу "]).
- Добавление новой сущности = ОДИН файл-правка (`entities.json`), без изменений кода PFS/TaskRefresh, без ручной синхронизации legacy `project_registry.json`.

## Что НЕ трогать

- `route.py` (весь файл целиком) — правила резолва по составу участников (Аралов+Ткаченко → `aralov_1on1`, департамент АиД → `sink_aid`, fallback → `vstrechi_nerazobrannoe`), матчинг `_match_by_name`, обработку `page_layout`. Это **поведение**, а не источник данных.
- Поведение записи `tsu` в PFS (текущая маршрутизация встреч с «ЦУ.» в неразобранное — осознанное решение Саши, вне scope этого ТЗ).
- `contacts.enc` / `AnywhereContacts` / оргструктуру (`reports_to`, `find_subordinates`) — люди отдельно, сущности отдельно.
- Все константы в `config.py`, не относящиеся к `ROUTES` (`EXCLUDED_PAGE_ID_OBSHY_SPISOK`, `SINK_AID_ENTITY`, `VSTRECHI_NERAZOBRANNOE_ENTITY`, `VSTRECHI_PRO_ENTITY`, `ARALOV_1ON1_ENTITY`, `DEFAULT_ASSIGNEE_LOGIN`, `DEADLINE_FALLBACK_DAYS`, пути, ENV-логика, telegram-константы) — остаются как есть.
- Формат `page_layout` / фикс BUG-1 для `ai_analitik` (комментарий в config.py сохраняется, но уже не актуален как код — просто исторический комментарий, если Саша захочет — оставить в README реестра).
- MoveFromFF / MoveFromJira / MoveFromZulip / прочие инструменты — они не читают ROUTES; в scope этого ТЗ не входят.

## Решения Саши (бриф завершён 16.07.2026)

Все семь вопросов первичной версии ТЗ (0.1.0) закрыты решениями Саши. Ниже — принятые решения, а не рекомендации. Пункты 1 и 2 — расхождение с рекомендациями Opus: победило решение Саши.

1. **TaskRefresh — подключение к реестру: вариант A (сразу переключить).** ⚠️ Отклонение от рекомендации Opus (была вариант B: только регрессионный тест эквивалентности, полный переход в follow-up через 2–4 недели). Финальное решение Саши: `taskrefresh/project_registry.py::ProjectRegistry.load()` дорабатывается СЕЙЧАС и читает `entities.json` напрямую как основной источник. Старый `WorkVault/Tools/TaskRefresh/project_registry.json` становится legacy-fallback на переходный период (safety-net при сбое чтения `entities.json`), `_comment` в нём обновляется. Обоснование Саши: единый источник правды важнее краткосрочной осторожности; лучше сразу зафиксировать архитектурный контракт, чем оставлять два JSON'а и жить на ручной синхронизации с CI-контролем. Влияние на план: Шаг 5 переписан (см. выше) — теперь это полноценное подключение + полный regression `pytest TR` + smoke-тест CLI, а не просто CI-проверка эквивалентности.

2. **OMD (OpenMetaData) — самостоятельная запись `kind="tool"`, БЕЗ `parent`.** ⚠️ Отклонение от рекомендации Opus (была: пока НЕ добавлять `omd`, отложить до появления реальных встреч с примерами; альтернативы с конкретным `parent` — `ml_platforma`/`ai_ready` — тоже не выбраны). Финальное решение Саши: добавить `omd` сразу как самостоятельную запись `kind="tool"`, `parent=null`, `aliases=["omd","openmetadata","кумд"]`, БЕЗ блока `pfs`. Обоснование Саши: OMD — самостоятельный инструмент, а не составная часть какого-то одного проекта, привязывать к `parent` искусственно — некорректно; пусть workvault-rag просто находит его по алиасам, а иерархия появится, только если реально понадобится. Влияние: пример записи `omd` добавлен в §«Схема записи» и в Шаг 2; критерии успеха расширены пунктом про `omd`.

3. **Формат реестра — JSON.** Совпадает с рекомендацией Opus. Зафиксировано как принятое решение (не открытый вопрос). Обоснование — см. §«Формат — JSON».

4. **Расположение файла — `WorkVault/Registries/entities.json`.** Совпадает с рекомендацией Opus. Зафиксировано. Обоснование — вне репозиториев инструментов, единый путь для всех потребителей, ENV-override для тестов.

5. **Схема Confluence-полей — вложенный блок `pfs`.** Совпадает с рекомендацией Opus. Зафиксировано. Обоснование — «есть блок `pfs`» = «сущность попадает в ROUTES», элегантный инвариант.

6. **JSON Schema — сразу, на Шаге 1.** Совпадает с рекомендацией Opus. Зафиксировано. Обоснование — реестр критичный, ошибка в схеме положит PFS-прод; дешевле поймать на Шаге 1, чем разбирать инцидент.

7. **Валидация уникальности — пара `(page_id, tag)`.** Совпадает с рекомендацией Opus. Зафиксировано. Обоснование — есть валидные дубли `page_id` между разными записями (`trisigma`/`ab_platforma` → `490170597`; `vstrechi_nerazobrannoe`/`tsu` → `508804852`), уникальность одного `page_id` невозможна и ломала бы миграцию. Проверка уникальности пары `(page_id, tag)` вынесена в Шаг 3 (тесты реестра).

8. **Зонтичные проекты (umbrella) — политика.** Сущности типа `adm`, `okr`,
   объединяющие разнородные по сути под-темы в один протокол, — штатный,
   легитимный паттерн; разделение по сути НЕ требуется и не является
   ограничением схемы. Механизм: широкие `aliases` внутри одной записи +
   один `pfs.tag`. Схема (`entities.schema.json`) изменений не требует —
   зонтичность не вводит новых полей, полностью выражается существующими
   `aliases`. Уникальность `(page_id, tag)` (см. п.7 выше) продолжает
   действовать без исключений и не связана с этим решением — она про случаи,
   когда РАЗНЫЕ slug делят одну страницу (например `sr`/`adm` — независимые
   проекты на одной странице с разными тегами, НЕ пример зонтичности).
   Детали разбора и прецедент — см. `ProtocolFromSummary_TZ.md` §19.

## Точки проверки (сводно)

| Шаг | Что проверяем | Как |
|---|---|---|
| 0 | Baseline | `pytest PFS` → 135/135; snapshot `repr(ROUTES)` |
| 1 | Схема | JSON Schema валидируется |
| 2 | Наполнение | Ручной diff с текущим ROUTES + отчёт новых записей |
| 3 | Инварианты реестра | Новые unit-тесты (парсинг, уникальность slug, parent-refs, kind, уникальность пары `(page_id, tag)`) |
| 4 | PFS не сломан | `pytest PFS` → 135/135; `repr(ROUTES)` == baseline |
| 5 | TaskRefresh переключён на `entities.json` | `pytest TR` → 100% зелёных ПОСЛЕ рефакторинга `ProjectRegistry.load()` (не только baseline count); новый тест эквивалентности legacy↔entities.json; smoke-тест реального CLI на 2–3 проектах |
| 6 | workvault-rag | Ручной smoke-запрос к скиллу: «что по ЦУ», «что по DevRel», «что по ML-платформе» — все резолвятся по реестру |
| 7 | Doc | `MAIN_TZ_INVENTORY.md` обновлён; PFS TZ §1.3 ссылается на реестр |

## Регрессионный риск — оценка

- **Средний.** Относительно версии 0.1.0 риск вырос: по решению Саши (§Решения, п.1) теперь трогается code path `ProjectRegistry.load()` в TaskRefresh — в v0.1.0 TR не трогали вообще. Поведение `route.py` PFS по-прежнему не трогается. Основные риски:
  1. JSON битый / файл не найден → PFS падает при импорте. Митигация: unit-тест «файл читается на старте», абсолютный путь + fallback на встроенный snapshot (опция; спросить Сашу).
  2. Порядок ключей в `ROUTES` (dict в Python 3.7+ упорядочен) — если тесты полагаются на порядок, миграция должна сохранить его. Митигация: JSON тоже упорядочен + Шаг 3 сравнивает `sorted`-версию, а если найдём тест, полагающийся на порядок — сохраним порядок вставки идентичный текущему литералу.
  3. **TaskRefresh — рефакторинг `ProjectRegistry.load()`** (новый риск, вариант A). Возможные регрессии: (а) адаптер `entities.json → внутренний формат TR` теряет/искажает поле по сравнению с legacy-JSON (например, тип `pageIds` как список vs строка, отсутствие поля `tag`, обработка `None`); (б) legacy-fallback триггерится по ошибке и молча даёт устаревшие данные; (в) ENV-override пути расходится с PFS и в проде читаются разные файлы. Митигация: (1) полный regression `pytest TR` ПОСЛЕ рефакторинга, (2) регрессионный тест эквивалентности legacy↔entities.json (Шаг 5), (3) **обязательный smoke-тест реального TaskRefresh CLI на 2–3 проектах** (не только pytest — pytest не ловит проблемы интеграции с прод-Confluence/Tracker), (4) явный лог-warning при срабатывании legacy-fallback, чтобы факт не остался незамеченным.
  4. **`omd` в реестре как `kind="tool"`** (новый риск, минимальный). Тесты Шага 3 должны допускать `kind=tool` для записей БЕЗ блока `pfs` — иначе валидация упадёт. Митигация: явно расширенный whitelist `kind` в JSON Schema и в unit-тесте (см. Шаг 3).

## Схема v1.2 — related_pages / people / loop_channels + backfill + 404-алерт (v0.4.0)

**TZ:patch 29.09.2026 (v0.4.0).** Карточка t_e1c9acf8, кейс CHANGE, цепочка
`DEV/entities-backfill`. Бриф Саши 21–22.09.2026. Исходник секционного брифа —
`appendix_entities-schema-v12_brief_20260922.md`. Открытых вопросов нет.
Код схемы/CLI/алерта на диске уже частично есть; этот раздел фиксирует канон
в единственном master-ТЗ инструмента `entity_registry`. Данные backfill
дописывает только `ORCH:shared-state` (не исполнитель `hermes-feature`).

**Цель.** Зафиксировать канон схемы `entities.json` v1.2 (`related_pages` /
`people` / `loop_channels`), таблицу backfill 11 проектов и 404-алерт
PFS+OFC в единственном master-ТЗ EntityRegistry.

**Маркер I1.** `current` = master EntityRegistry v0.3.1 описывает схему записи
как черновик 1.0 (`pfs` / `aliases` / `parent`, без `related_pages` / `people` /
`loop_channels`). Параллельно существовал неканонический файл
`TZ/EntitiesSchemaV12/EntitiesSchemaV12_TZ.md` (не в `tools{}` манифеста;
`emit-prompt --tool EntitiesSchemaV12` → `[FAIL] инструмент не найден в
манифесте`, exit 1). На диске на момент патча: `entities.schema.json` уже
содержит три поля v1.2; `entities.json` `schema_version: "1.2"`; 11 проектов
имеют неполный `related_pages` (корень с `role: other` + часть report/brief;
не хватает tasks-страниц таблицы 21.09); пин
`ProtocolFromSummary/tests/test_entities_registry.py:27` уже `== "1.2"`;
CLI `tests/test_schema_v12.py` и инварианты `validator.py` есть; PFS 404-алерт
в `pipeline.py` (`_report_pfs_route_dead`); OFC-агрегация not_found —
`scripts/ofc_sync.py` + `ofc_error_bus.report_ofc_not_found_batch`.
`target` = эта работа: канон схемы v1.2 живёт **только** в этом master-ТЗ;
A свёрнут в appendix + заглушку superseded; полный backfill 11 проектов по
таблице page_id→role (primary выделен); 404-алерт PFS+OFC зафиксирован живыми
точками кода; границы записи `entities.json`; читатели не меняют поведение
на отсутствующих полях; AC-001…006.

---

### Владелец мастер-документа схемы (развилка A/B) — решение

Выбран **вариант B.** Мастер схемы `entities.json` = этот файл
(`TZ/EntityRegistry/EntityRegistry_TZ.md`). Файл A
(`TZ/EntitiesSchemaV12/EntitiesSchemaV12_TZ.md`) **не мастер**: сведён к
бриф-исходнику `appendix_entities-schema-v12_brief_20260922.md`; на прежнем
пути оставлена заглушка `status: superseded`.

Обоснование (не переопределение рекомендации карточки):

1. **Гейт emit-prompt** резолвит инструмент только по `tools{}` манифеста.
   Ключа `EntitiesSchemaV12` нет → `--tool EntitiesSchemaV12` не вызывает
   `agent -p`. Рабочий ключ схемы — `entity_registry` (`name` EntityRegistry,
   `tz_ref` → этот файл).
2. Manifest `tools.entity_registry.purpose` **уже** = «Спецификация единого
   реестра entities.json (схема v1.2: related_pages/people/loop_channels;
   корень = related_pages.primary)». Инвентарный sync `purpose` на
   `ORCH:shared-state` не требует новой tools-записи; не плодить
   `tools.EntitiesSchemaV12`.
3. EntityRegistry — канонический владелец `entities.schema.json` /
   `entities.json` (этот документ, раздел «Контракты экосистемы»). CLI,
   PFS, OFC, TaskRefresh, MOFS — потребители этого контракта, не второго
   «мастера».
4. `EntitiesSchemaV12` в `MAIN_TZ_INVENTORY.md` не регистрировался; в
   EcosystemIntegration §9.2 он в `SKIP_TZ_DIRS` как non-index. Заглушка
   держит skip тихим, пока `ORCH:shared-state` не снимет skip (не в этой
   фазе). Не регистрировать A как инструмент.

`emit-prompt` на этой карточке — `--tool entity_registry`.

---

### Схема v1.1 → v1.2 (три поля в `properties` записи сущности)

Bump корневого `schema_version` `"1.1"` → `"1.2"`. Пин-тест:
`~/USERTOOLS/ProtocolFromSummary/tests/test_entities_registry.py:27` —
`assert registry["schema_version"] == "1.2"`.

JSON Schema Draft-07, фрагменты в `properties` записи
(`entities.schema.json`). Поля optional (нет в `required` записи:
`kind`, `parent`, `display_name`, `aliases` без изменений).

```json
"related_pages": {
  "type": "array",
  "items": {
    "type": "object",
    "required": ["page_id", "role"],
    "properties": {
      "page_id": {"type": "string", "pattern": "^[0-9]+$"},
      "role": {"enum": ["charter", "brief", "tasks", "report", "other"]},
      "primary": {"type": "boolean"},
      "title": {"type": "string"}
    },
    "additionalProperties": false
  }
},
"people": {
  "type": "array",
  "items": {
    "type": "object",
    "required": ["login"],
    "properties": {
      "login": {"type": "string", "pattern": "^[a-z][a-z0-9._-]*$"},
      "role": {"enum": ["customer", "pm", "sponsor", "team", "other"]}
    },
    "additionalProperties": false
  }
},
"loop_channels": {
  "type": "array",
  "items": {"type": "string", "pattern": "^[a-z0-9_-]+$"},
  "uniqueItems": true
}
```

Правила (решения Саши 22.09.2026):

- Корень проекта **не** отдельное поле `root_confluence_id`. Корень = элемент
  `related_pages` с `primary: true`. `role` корня в брифе не задан отдельно;
  допустим `other` (не дублировать `charter.confluence_id` в `related_pages`).
- `completion_report_id` — не создавать. `start_date` / `end_date` — не
  создавать.
- `status`-гварды публикации — запрет Саши («так не делаем»).
- `additionalProperties: false` у объекта people — ПДн-гвард: **только
  логины**, поле `fio` / ФИО отвергается схемой.
- `charter.confluence_id` не трогать и не копировать в `related_pages`.

Инварианты `entityregistrycli/validator.py` (не JSON Schema; коды как на
диске):

| Код | Правило |
|---|---|
| `related_pages_multi_primary` | при непустом `related_pages` — не больше одной `primary: true`; канон брифа — **ровно одна** primary на непустом массиве |
| `related_page_dups_pfs` | `related_pages[].page_id` не равен `pfs.page_id` той же записи |
| `forbidden_related_page_id` | запрещены page_id `523032632`, `432316254`, `331125844` (площадка/исключённые страницы PFS) |

---

### CLI (EntityRegistryCLI)

`SchemaIntrospector` строит флаги `add` из схемы в рантайме.
`--allow-new-field` для трёх полей v1.2 **не нужен** (поля уже в схеме).

**Квирк `--related-pag`.** В `cli.py:_build_add_parser` для array:
`singular = field[:-2] if field.endswith("es") else field.rstrip("s")`.
Для `related_pages` это даёт флаг `--related-pag` (не `--related-pages`).
`people` → `--people`; `loop_channels` → `--loop-channel`. Канон
документации квирка: `~/USERTOOLS/EntityRegistryCLI/references/flags-reference.md`
(раздел «Квирк флагов массивов объектов (v1.2)»). Не «чинить» эвристику в
этом CHANGE.

Заполнение массивов объектов — не через repeatable-флаг `add`, а:

```bash
entity-registry edit <slug> related_pages --value-json '[...]' -y
entity-registry edit <slug> people --value-json '[...]' -y
entity-registry edit <slug> loop_channels --value-json '["ch"]' -y
```

Проверка: `add` / `edit` / `validate` не падают на sample с новыми полями
(`tests/test_schema_v12.py`).

---

### Backfill (данные сессии 21.09.2026, Confluence pageId → role)

Пишет **только** `ORCH:shared-state` после `HF:docs-handoff` / done цепочки.
Исполнитель `hermes-feature` в `entities.json` не пишет.

Канон 11 проектов. Колонка **primary** — корень (`primary: true`). Колонка
**related_pages** — остальные элементы (primary:false). Остальные ~36
сущностей **не** backfill (канбан-карточка t_4b7cc2ff, вне скоупа).

| slug | primary (корень) | related_pages (role, page_id) |
|---|---|---|
| trisigma | 480923430 | report 523010358 |
| ai_analitik | 480905784 | — |
| ml_platforma | 487934086 | — |
| metroteka | 418568780 | tasks 444141522 |
| ai_ready | 490149042 | tasks 499570832 |
| vestnik | 324382467 | tasks 519474299 |
| atribuciya | 347445612 | tasks 519474257; brief 449571537; tasks 487924720 (приёмка) |
| cu | 469658375 | tasks 519474213; report 480922695 (дипломные проекты) |
| devrel | 480930821 | tasks 519474160 |
| parsing | 439235729 | tasks 439235748; report 477048493 (ЖД завершён); report 446995783 (ЖД протоколы) |
| antibot | 410783702 | tasks 439235653; report 449567776; report 441304017 (результаты) |

Дельта диска на 29.09.2026 (не полный канон; `ORCH:shared-state` дописывает
недостающие tasks, не затирая уже лежащие report/brief/primary):

| slug | уже есть | дописать |
|---|---|---|
| trisigma | primary 480923430; report 523010358 | — |
| ai_analitik | primary 480905784 | — |
| ml_platforma | primary 487934086 | — |
| metroteka | primary 418568780 | tasks 444141522 |
| ai_ready | primary 490149042 | tasks 499570832 |
| vestnik | primary 324382467 | tasks 519474299 |
| atribuciya | primary 347445612; brief 449571537; tasks 487924720 | tasks 519474257 |
| cu | primary 469658375; report 480922695 | tasks 519474213 |
| devrel | primary 480930821 | tasks 519474160 |
| parsing | primary 439235729; report 477048493; report 446995783 | tasks 439235748 |
| antibot | primary 410783702; report 449567776; report 441304017 | tasks 439235653 |

`people` и `loop_channels` этим backfill **не** заполняются (нет данных
сессии 21.09).

---

### 404-алерт (PFS + OFC)

Только алерт в ErrorBus → Telegram. Без status-гвардов, без автопереходов
маршрута, без смены `pfs.page_id`.

**PFS.** `~/USERTOOLS/ProtocolFromSummary/protocolfromsummary/pipeline.py`:

- хелпер `_is_http_not_found` / `_report_pfs_route_dead` (около строк 135–172);
- ветка `confluence.get_page` (~503–511);
- ветка `confluence.update_page` (~706–714).

Вызов: `~/.hermes/scripts/report_error.sh --tool ProtocolFromSummary`
(ErrorBus → TG). Текст сообщения:

```
страница протоколов <page_id> 404 → route мёртв, entity <slug>
```

(исторические номера брифа ~239–244 / ~440–445 — сместились после наращивания
`pipeline.py`; канон — функции `_report_pfs_route_dead` и две 404-ветки
get_page/update_page.)

**OFC.** Детектор 404 — `protocolfromsummary/entity_export.py` `sync_entity_protocol`
(~130–141): `action="not_found"`. Агрегация за прогон — **не штучно**:
`scripts/ofc_sync.py` собирает список, один вызов
`ofc_error_bus.report_ofc_not_found_batch` (~97–99) со списком page_id.
Инструмент шины: `ObsidianFromConfluence`.

---

### Тесты

- Пин `schema_version == "1.2"` (`test_entities_registry.py:27`).
- Sample-сущность с `related_pages` / `people` / `loop_channels` проходит
  `entity-registry validate` (Draft-07) — `test_schema_v12.py::test_validate_ok_with_v12_fields`.
- Негатив: `people` с полем `fio` → reject (`additionalProperties`).
- Негатив: два `primary: true` в `related_pages` → reject
  (`related_pages_multi_primary`).
- Дополнительно на диске (сохранить): dup `pfs.page_id`, forbidden page_id,
  `edit … --value-json`, `add` без `--allow-new-field`.

---

### Что НЕ трогать

- Исполнитель `hermes-feature` **не пишет** в `entities.json`,
  `EcosystemManifest.json` `tools{}`, `.env`, `jobs.json`. Данные и
  инвентарный sync манифеста — фаза `ORCH:shared-state` после done.
- `tools.entity_registry.purpose` **уже** отражает v1.2 (related_pages /
  people / loop_channels; корень = related_pages.primary). Карточка
  `ORCH:shared-state` сверяет purpose, не создаёт ключ EntitiesSchemaV12.
- Не менять `route.py`. Не дублировать схему во втором master-файле.

### Связи с экосистемой

- Существующие читатели (ProtocolFromSummary, ObsidianFromConfluence,
  TaskRefresh, MarkObjectsFromSummary) **не меняют поведение** на
  отсутствующих полях: доступ `.get("related_pages")` / `.get("people")` /
  `.get("loop_channels")` (или эквивалент); отсутствие ключа = как до v1.2.
- Запись `entities.json` — только `ORCH:shared-state` после done; исполнитель
  `hermes-feature` в этот файл не пишет.

---

### Критерии приёмки (AC)

Только пакет этой работы (`DEV/entities-backfill`). Нормативный язык —
наблюдаемое поведение / артефакт.

### AC-001 — три поля v1.2 и пин schema_version 1.2

В этом master-ТЗ зафиксированы `related_pages`, `people`, `loop_channels` с
JSON Schema как в подразделе «Схема v1.1 → v1.2»; корневой `schema_version`
канона = `"1.2"`; пин `test_entities_registry.py:27`.

### AC-002 — развилка владельца закрыта, A не мастер

В подразделе «Владелец мастер-документа схемы» выбран B и обоснован.
`EntitiesSchemaV12_TZ.md` — заглушка superseded; бриф-исходник — appendix
в каталоге EntityRegistry. `emit-prompt` этой цепочки — `--tool entity_registry`.

### AC-003 — таблица backfill 11 проектов

Секция Backfill содержит 11 slug, page_id→role, колонка primary выделена;
остальные ~36 сущностей явно вне скоупа (t_4b7cc2ff).

### AC-004 — 404-алерт PFS+OFC

Секция 404 описывает точки кода PFS (`pipeline.py` get_page/update_page +
`_report_pfs_route_dead`) и OFC (`entity_export.py` not_found + batch в
`ofc_sync.py` / `report_ofc_not_found_batch`) и текст алерта PFS.

### AC-005 — границы записи и читатели

Зафиксировано: кто пишет `entities.json` (`ORCH:shared-state`, не HF);
читатели не меняют поведение на отсутствующих полях (`.get()`).

### AC-006 — маркеры I1 и якоря AC

В этой секции есть маркер I1 `current`/`target` и подраздел
`### Критерии приёмки (AC)` с якорями AC-001…AC-006.