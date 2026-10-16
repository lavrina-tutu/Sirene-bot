---
tool: OKRTool
plan-for-tz: "TZ/OKRTool/OKRTool_TZ.md v0.1.0"
plan-version: "1.1"
author: "Архитектор (claude-sonnet-5-thinking-medium)"
date: 2026-08-06
status: "план — берём в работу"
---

# Пофайловый план реализации OKRTool v0.1.0

Источники: `TZ/OKRTool/OKRTool_TZ.md` (§1-6), скилл `~/.hermes/skills/productivity/tutu-jira-okr/SKILL.md` v2.0.0, паттерн `hermes-feature-cursor` (питфолы Cursor CLI).

**Ревизия 1.1 (thinking-medium):** факты из §0 (существующий `USERTOOLS/OKRTool/`, baseline тестов, `Registries/entities.json`+README, `SRTool/brief.py`/`task_mapper.py`) перепроверены напрямую (`ls`/`pytest`/чтение файлов) — расхождений с диском не найдено. Добавлены сквозные чекбоксы по каждой фазе (файлы + критерий готовности) и master-трекер ниже — по требованию задачи и питфолу `hermes-feature-cursor` Блок 1А «Устойчивость к сбою: `## Прогресс выполнения` с чекбоксами». Автор строки в frontmatter поправлен на `thinking-medium`: именно эта модель фактически читала 5+ файлов контекста и составляла план — `thinking-high` в такой конфигурации по документированному питфолу таймаутится.

## Прогресс выполнения (master-трекер)

- [x] Фаза 0 — Подготовка (бэкап, baseline, «берём в работу»)
- [x] Фаза 1 — Скилл `tutu-jira-okr`: единая абстракция OKR-задачи
- [x] Фаза 2 — `okr_task.py`
- [x] Фаза 3 — `period.py` / `checkin_fields.py` / `md_store.py`
- [x] Фаза 4 — `sr_matcher.py` / `aggregate.py` / `brief.py`
- [x] Фаза 5A — OKRMetricsResolver: конфиг + ядро
- [x] Фаза 5B — Источники метрик (3 адаптера)
- [x] Фаза 6 — Запись чекина в Jira + CLI `checkin`
- [x] Фаза 7 — Клонирование KR
- [x] Фаза 8 — Миграция существующих per-task MD
- [x] Фаза 9 — ТЗ для OKRSheetsExporter
- [x] Фаза 10 — Документация, зависимости, финальная регрессия

Каждый пункт закрывается только когда все чекбоксы внутри соответствующей фазы (файлы + критерий готовности) отмечены.

## 0. Зафиксированные факты (проверено архитектором ДО плана, не предполагать заново)

### 0.1 Существующий скелет `USERTOOLS/OKRTool/` — переиспользуем, не пишем с нуля

Уже есть черновая версия v0.1 (написана до брифа 06.08.2026, флоу не совпадает с финальным ТЗ — там нет чекина/SR/резолвера, только «draft KR из шаблона»). Переиспользуем как фундамент:

| Файл | Что уже есть | Что делаем |
|---|---|---|
| `okrtool/jira.py` | REST-клиент (`get_issue`, `search`, `create_issue`, `edit_issue`, `link_issues`, `transition_issue`, `comment_issue`, `get_versions`, `get_transitions`, `get_user`, `list_children`, `next_kr_number`). Токен собирается в рантайме (защита от маскировщика Hermes) — **не трогать этот приём**. | Используем как есть, точечно добавим `get_issue_link_types`/константы. |
| `okrtool/cache.py` | TTL-кэш 7 дней (versions/transitions/users) в `~/.hermes/profiles/anthropic/state/jira-okr/`. | Используем как есть. |
| `okrtool/drafts.py` | `DraftKR`/`DraftBundle`, сохранение в `state/jira-okr/drafts/*.json`. | Расширяем `DraftKR` под нужды клонирования (см. Фаза 7), либо заводим соседний `CloneDraft` — решение в Фазе 7. |
| `okrtool/synth.py` | `build_from_parent()` — сборка драфтов KR из родителя+шаблона+текста. Уже решает часть задач резолва project/assignee/fixVersion/issuetype. | **Переиспользуем логику резолва fixVersion (id по имени через `cache.versions_map`)** в клонировании (Фаза 7), не дублируем. |
| `okrtool/format_tg.py`, `okrtool/cli.py` | Форматирование в TG-markdown, CLI (`view/draft/create/edit/transition/comment/versions/transitions/user`). | Расширяем `cli.py` новыми подкомандами (`checkin`, `resolve-metric`, `clone`), `format_tg.py` — новыми форматтерами брифа/сверки. |
| `tests/test_jira_smoke.py` | 2 live-теста (нужен `JIRA_TOKEN` + сеть). | Не трогаем; новые тесты — с моками, без сети (см. §0.3). |
| `README.md`, `pyproject.toml` | Описывают старый roadmap (v0.2 Confluence и т.д.) — **устарел относительно текущего ТЗ**. | Переписываем в Фазе 10. |

**Вывод:** это не «новый инструмент с нуля», а **достройка существующего пакета** новыми модулями поверх низкоуровневого Jira-клиента.

### 0.2 Обнаруженные Jira issueLinkType (запрос `GET /rest/api/2/issueLinkType`, 06.08.2026, живой прод) — закрывает открытый вопрос ТЗ §5.1

| name | id | inward | outward |
|---|---|---|---|
| **Contains** | **11400** | is contained in | contains |
| **Link** | **10003** | связано с | связать с |

→ «Contains для OKRS, "связано с" для OKRAID» из ТЗ §5.1 = `link_type_id="11400"` для OKRS, `link_type_id="10003"` для OKRAID. Захардкодить в `okr_task.py` (Фаза 2), не резолвить заново в рантайме.

### 0.3 Baseline тестов ДО начала работы (зафиксировано 06.08.2026)

| Инструмент | Команда | Результат |
|---|---|---|
| ConfluenceSync | `cd ~/USERTOOLS/ConfluenceSync && .venv/bin/python -m pytest -q` | **58 passed** |
| SRTool | `cd ~/USERTOOLS/SRTool && python3 -m pytest -q` (системный `python3` = `hermes-agent/.venv`, НЕ локальный `.venv` — там нет pytest) | **49 passed** |
| MoveFromLoop | `cd ~/USERTOOLS/MoveFromLoop && python3 -m pytest -q` | **98 passed, 8 failed** — все 8 в `tests/test_sync.py` (`ModuleNotFoundError`), **предсуществующее, не наша зона**, не трогаем |
| OKRTool | `cd ~/USERTOOLS/OKRTool && python3 -m pytest -q` | **0 passed, 2 failed** (`test_jira_smoke.py`, требует `JIRA_TOKEN`+сеть) — ожидаемо, не regression |

После каждой фазы: `python3 -m pytest -q` в `USERTOOLS/OKRTool` (новые тесты) — все зелёные, **без обращения к сети** (кроме `test_jira_smoke.py`, который остаётся отдельным). Финал (Фаза 10) — доп. regression-прогон ConfluenceSync/SRTool/MoveFromLoop (т.к. `okrtool` будет импортировать `confluencesync`/`srtool` напрямую — риск конфликта версий в общем venv).

### 0.4 Состояние существующих per-task MD (для Фазы 8, миграция)

- `WorkVault/Entities/okr/O1_MAS/*.md` — **18 файлов**, старая схема frontmatter (`key/type/period/summary`), период в поле `period`.
- `WorkVault/Entities/okr/{OKRS-Q2-final.md, OKRS-all-OKR-060726.md, okr.md, Pages/instrument-okr_brief.md, OKRS_Dependency_АИД_список.xlsx}` — **не per-task**, сводные/отчётные файлы + index-стаб.
- `WorkVault/Projects/okr-tool/Q3_chekin_july/*.md` — **4 файла**, уже в целевой схеме ТЗ (`key/type/issuetype/status/assignee/fixVersions/okr_type/department/parent_contains/…`), **активно используются прямо сейчас** — у `OKRS-3119` там уже есть частично заполненный чекин-бриф (Блок «Предложение по чекину на основе SR июль 2026»). Это живые данные текущей сессии, не трогать содержимое, только место.
- `WorkVault/Projects/okr.md` — index-стаб (`kind: project`), отдельно от `okr-tool/`.
- **Конфликт:** `OKRS-3119` существует в ОБОИХ местах с разным содержимым. `Projects/okr-tool/Q3_chekin_july/` версия новее (`fetched: 2026-08-06`) и содержит незавершённую работу → это канон, `Entities/okr/O1_MAS/OKRS-3119_*.md` — устаревший дубль.
- `WorkVault/Entities/adm/SR-OKR-matching-Q2-2026.md` — принадлежит домену SR (не per-task OKR), **вне скоупа миграции**, не трогаем без отдельного решения Саши.

### 0.5 Решение по месту хранения конфига OKRMetricsResolver (открытый вопрос ТЗ §5.2 — закрыт здесь)

**`WorkVault/Registries/okr_metrics_map.json`** — по аналогии с `EntityRegistry` (`WorkVault/Registries/entities.json`, ТЗ `EntityRegistry_TZ.md` v0.2.0, уже прод). Обоснование:
- В `WorkVault/Registries/` уже есть прецедент + `README.md`, описывающий назначение папки («канонические реестры сущностей для инструментов Саши») — второй реестр в том же духе, не новая конвенция.
- Данные (не код), должны быть удобны для ручной правки текстом/через Obsidian, не требуют деплоя.
- ENV-override для тестов (`OKR_METRICS_MAP_PATH`) — тот же паттерн, что `ENTITIES_REGISTRY_PATH`.
- Альтернатива «в Hermes» (`~/.hermes/...`) отклонена: там уже живут скиллы/state с TTL-кэшами, это не место для «источника правды» данных, которые Саша может захотеть смотреть/править в Obsidian глазами.

### 0.6 Переиспользуемые паттерны из соседних инструментов (снижает риск дизайна с нуля)

- **`SRTool.brief.BriefSession`** (`srtool/brief.py`) — стейт-машина «следующий промпт → `submit_answer()` → следующий шаг», уже проверена тестами (`tests/test_brief.py`). Использовать как **прямой прототип** для `okrtool/brief.py` (поле-за-полем чекина, KR→Objective), не изобретать новый паттерн диалога.
- **`ConfluenceSync.tasks.parse_tasks_from_page` / `SRTool.confluence_sources.collect_tasks`** — источник данных SR из Confluence-минуток, уже готовая обвязка. `sr_matcher.py` читает **не эти сырые минутки**, а **готовый вывод SRTool** (`WorkVault/Projects/adm/SR/SR Ткаченко/*.md`, путь через `srtool.config.Settings.sr_output_dir`).
- **`SRTool.task_mapper.auto_map`** — гибридный keyword-матчинг (tag-based scoring). Паттерн для `sr_matcher.py` (матчинг по ключевым словам названия KR / номера / метрики), не копия один-в-один (разные структуры данных), но тот же принцип: score по пересечению токенов + explicit fallback bucket + `apply_user_correction`-подобная команда коррекции.
- **MoveFromLoop не имеет отдельного API «метрик команды»** — только сообщения (`digest.py`, `keyword_checker.py`, `mentions_fetcher.py`). Источник `loop_source.py` в OKRMetricsResolver — это **поиск по ключевым словам в сообщениях Loop-канала**, не структурированная метрика. **Пометить в интерфейсе явно `confidence="low"`/`"heuristic"` для этого источника** — риск для плана: если Саша ожидал точных чисел из Loop уровня API, это не так технически возможно сегодня без доработки MoveFromLoop (вне скоупа этого ТЗ).

### 0.7 Важное терминологическое разграничение (зафиксировать явно, чтобы не перепутали на реализации)

`OKRMetricsResolver.resolve()` возвращает `confidence` — это **уверенность в качестве/свежести резолвленных данных** (high/medium/low), НЕ то же самое, что чекин-поле Jira «Уровень уверенности» (customfield_43706, семантика «On Track»/риск по цели). `brief.py` не должен копировать одно в другое автоматически — предложение по чекин-полю «Уверенность» строится из текста SR/риска, а `resolver.confidence` — это только метаданные о надёжности значения метрики (для brief-подсказки «источник надёжный/примерный»).

---

## Общая архитектура после реализации (`USERTOOLS/OKRTool/okrtool/`)

```
okrtool/
  jira.py              # (существует) REST-клиент
  cache.py             # (существует) TTL-кэш
  drafts.py            # (существует, расширяем) DraftKR/DraftBundle
  synth.py             # (существует) сборка драфтов из шаблона
  format_tg.py         # (существует, расширяем) TG-форматтеры
  cli.py               # (существует, расширяем) CLI: view/draft/create/edit/... + checkin/resolve-metric/clone
  okr_task.py          # НОВОЕ (Фаза 2) — единая абстракция OKR-задачи OKRS/OKRAID
  period.py            # НОВОЕ (Фаза 3) — период/fixVersion, "следующий квартал"
  checkin_fields.py    # НОВОЕ (Фаза 3) — карта customfield ID + get/set чекин-полей
  md_store.py          # НОВОЕ (Фаза 3) — per-task MD: имя файла, frontmatter, save/load
  sr_matcher.py         # НОВОЕ (Фаза 4) — гибридный матчинг SR → OKR-задача
  aggregate.py          # НОВОЕ (Фаза 4) — агрегация KR → Objective
  brief.py              # НОВОЕ (Фаза 4) — бриф-стейт-машина поле-за-полем
  metrics_sources/
    __init__.py         # НОВОЕ (Фаза 5A) — MetricResult, интерфейс источника
    srtool_source.py     # НОВОЕ (Фаза 5B)
    loop_source.py        # НОВОЕ (Фаза 5B)
    confluence_source.py  # НОВОЕ (Фаза 5B)
  metrics_resolver.py   # НОВОЕ (Фаза 5A) — OKRMetricsResolver.resolve(key)
  sync_jira.py          # НОВОЕ (Фаза 6) — запись чекина в Jira + верификация
  clone_kr.py           # НОВОЕ (Фаза 7) — клонирование KR в новый период
tests/
  test_jira_smoke.py    # (существует, не трогать)
  test_okr_task.py, test_period.py, test_checkin_fields.py, test_md_store.py,
  test_sr_matcher.py, test_aggregate.py, test_brief.py,
  test_metrics_resolver.py, test_metrics_sources_srtool.py,
  test_metrics_sources_loop.py, test_metrics_sources_confluence.py,
  test_sync_jira.py, test_cli_checkin.py,
  test_clone_kr.py, test_cli_clone.py,
  test_migrate_okr_md.py
scripts/
  migrate_okr_md.py     # НОВОЕ (Фаза 8) — разовая миграция per-task MD
```

Все тесты новых модулей — **без сети**, мокают `okrtool.jira` через `unittest.mock` (см. паттерн `SRTool/tests/conftest.py::fake_jira_client`).

---

## Питфолы Cursor CLI, учтённые в разбиении на фазы

- **composer-2.5 таймаутится на промптах >4K токенов / 12+ файлов** → каждая фаза ≤ 6 файлов (создание+тесты), фазы 5A/5B разнесены отдельно вместо одной «Фазы 5».
- **thinking-high таймаутится при чтении 5+ файлов** → всё чтение контекста (ТЗ, скилл, существующий код, живой Jira issueLinkType) уже сделано архитектором на этапе планирования и зафиксировано в §0 — исполнителю (composer-2.5) в промпте передаются готовые факты текстом, а не «прочитай эти 10 файлов сам».
- **Когда Cursor CLI таймаутится — не писать код самому** — если composer-2.5 не укладывается 2+ раза на фазе — дробить фазу на 2-3 файла, эскалировать Саше при повторном сбое, не переходить к прямой правке архитектором.
- Каждая фаза = отдельный вызов исполнителя с промптом, содержащим: ссылку на этот план + номер фазы + полный текст соответствующего раздела ниже (не пересказ).

---

## Фаза 0 — Подготовка (без кода)

- [ ] Бэкап создан: `~/.hermes/_Archives/hermes-backup-YYYYMMDD-HHMMSS/` (снапшот `USERTOOLS/OKRTool/`, `~/.hermes/skills/productivity/tutu-jira-okr/`, `WorkVault/Entities/okr/`, `WorkVault/Projects/okr-tool/`, `WorkVault/Registries/`).
- [ ] Baseline тестов (§0.3) зафиксирован в чате/этом файле — done выше.
- [ ] Этот план сохранён по пути `TZ/OKRTool/_okrtool_v010_plan.md` (этот файл) — done.
- [ ] Получено явное «берём в работу» от Саши по всему плану.

**Критерий готовности:** явное «берём в работу», бэкап существует на диске.

---

## Фаза 1 — Скилл `tutu-jira-okr`: единая абстракция OKR-задачи

*Не Python-код → делается через Cursor CLI (архитектор, `claude-sonnet-5-thinking-high`), справочник паттернов — `hermes-agent-skill-authoring`. ТЗ-файл не нужен (правило Блока 1А: «ТЗ-файл только для задач с Python-кодом»), но пункт плана здесь — обязателен, т.к. это явный пункт 1 задачи.*

### Файлы

- [ ] `~/.hermes/skills/productivity/tutu-jira-okr/SKILL.md` — **изменить**.

### Что добавить (новая секция, после «Оргструктура», до «Правило №0»)

Секция **«Единая абстракция «OKR-задача» (OKRS/OKRAID)»**:
- Таблица различий по типу проекта:

| Параметр | OKRS | OKRAID |
|---|---|---|
| Link type Objective→KR (клонирование, новые связи) | `Contains` (id=`11400`) | `Link` / «связано с» (id=`10003`) |
| Обязательные поля Objective при создании | `project, issuetype=6, summary, description, assignee, reporter` | то же + `customfield_10007` («Epic Name», обязателен — иначе `400`) |
| `Тип OKR` (customfield_43701) у KR | обычно пусто | всегда пусто (не пытаться заполнить) |
| Иерархия чтения | `issuelinks` Contains (см. существующий питфол выше в файле) | `issuelinks` Contains ЛИБО Link — обе связи резолвить при обходе, не только Contains |

- Явная формулировка: «При работе с OKR-задачей сначала определить `project_key` из ключа (`OKRS-*`/`OKRAID-*`), затем резолвить нужный link type / обязательные поля по таблице выше — не считать поведение OKRS универсальным для OKRAID (уже есть частичный питфол об этом ниже по Epic Name — расширить его ссылкой на новую секцию, не дублировать текст).»
- Ссылка на функцию-источник правды в коде: `okrtool.okr_task.LINK_TYPE_BY_PROJECT` / `okrtool.okr_task.REQUIRED_FIELDS_BY_PROJECT` (после Фазы 2) — «код и скилл держат одну и ту же карту, при расхождении — код авторитетен, скилл обновляется вручную».
- Обновить существующий питфол про Epic Name (§«Создание новых KR/Objective») — заменить дублирующийся текст ссылкой на новую секцию.
- Bump `version: 2.0.0` → `2.1.0` в frontmatter.

### Проверка

- [ ] Секция добавлена, нет дублирования текста про Epic Name (старый питфол ссылается на новый, не повторяет).
- [ ] `version: 2.1.0` в frontmatter.
- [ ] После правки — **Hermes-ассистент** (не Cursor) запускает `cd ~/hermes-workspace && bash restore-all-skills.sh`.
- [ ] Верификация: `hermes --profile tz-dev skills list | grep tutu-jira-okr` — версия 2.1.0 видна.

- [ ] **Критерий готовности фазы:** скилл обновлён, симлинки синхронизированы, дублирования нет.

---

## Фаза 2 — `okr_task.py`: унифицированный Python-слой абстракции OKR-задачи

### Файлы (2)

- [ ] `okrtool/okr_task.py` — **новый**.
- [ ] `tests/test_okr_task.py` — **новый**.

### Контракт `okr_task.py`

```python
LINK_TYPE_BY_PROJECT: dict[str, str]  # {"OKRS": "11400", "OKRAID": "10003"}
LINK_TYPE_NAME_BY_PROJECT: dict[str, str]  # {"OKRS": "Contains", "OKRAID": "Link"}

def project_of(key: str) -> str: ...       # "OKRS-3119" -> "OKRS"
def link_type_for(project_key: str) -> str: ...  # -> "11400" | "10003", raise на неизвестном проекте
def required_fields_for_objective(project_key: str) -> dict[str, Any]: ...
    # OKRAID -> {"customfield_10007": "<summary>"} (заполнить = summary, как в питфоле скилла)
    # OKRS -> {}

@dataclass
class OkrTask:
    key: str
    project: str          # "OKRS" | "OKRAID"
    issuetype: str         # "Objective" | "KR" | "Dependency" | "unknown"
    is_objective: bool
    is_kr: bool
    fields: dict[str, Any]  # сырые fields из Jira get_issue

def classify(issue_data: dict) -> OkrTask: ...
    # issuetype.id == "6" -> Objective; issuetype.name == "UserStory" -> KR;
    # иначе -> "unknown" (см. питфол "SR-задачи затесались в Contains")

def list_children_unified(parent_key: str) -> list[str]: ...
    # обходит ОБА link type (Contains id=11400 + Link id=10003) через jira.get_issue(issuelinks),
    # не только jira.list_children() (который жёстко на 11400)
```

### Тесты (`test_okr_task.py`)

- `test_project_of_okrs` / `test_project_of_okraid` / `test_project_of_unknown_raises`.
- `test_link_type_for_okrs_is_contains` (`== "11400"`).
- `test_link_type_for_okraid_is_link` (`== "10003"`).
- `test_required_fields_okraid_includes_epic_name`.
- `test_required_fields_okrs_empty`.
- `test_classify_objective` / `test_classify_kr` / `test_classify_unknown_sr_task` (issuetype постороннее → `unknown`, повторяет питфол «SR-задачи затесались»).
- `test_list_children_unified_merges_both_link_types` — мок `jira.get_issue`, issuelinks содержит и Contains, и Link записи, обе попадают в результат.

- [ ] **Критерий готовности:** `pytest tests/test_okr_task.py -q` зелёный, без сети. `okr_task.LINK_TYPE_BY_PROJECT` совпадает с §0.2.

---

## Фаза 3 — Учётный слой чекина: `period.py` / `checkin_fields.py` / `md_store.py`

### Файлы (6)

- [ ] `okrtool/period.py` — новый.
- [ ] `okrtool/checkin_fields.py` — новый.
- [ ] `okrtool/md_store.py` — новый.
- [ ] `tests/test_period.py` — новый.
- [ ] `tests/test_checkin_fields.py` — новый.
- [ ] `tests/test_md_store.py` — новый.

### `period.py`

```python
def normalize_period(raw: str) -> str: ...      # "q3 2026" / "Q3-2026" -> "Q3 2026"; "2026фг" -> "2026 ф.г."
def next_quarter(period: str) -> str: ...        # "Q3 2026" -> "Q4 2026"; "Q4 2026" -> "Q1 2027"
def is_annual(period: str) -> bool: ...          # "2026 ф.г." -> True
def jql_fixversion_clause(period: str) -> str: ...  # 'fixVersion = "Q3 2026"'
```
Тесты: нормализация разных написаний, переход через границу года (Q4→Q1 след. год), ValueError на нераспознанном формате.

### `checkin_fields.py`

Единая карта — **источник правды в коде**, продублирована человекочитаемо в скилле (Фаза 1 ссылается сюда):

```python
CHECKIN_FIELDS = {
    "confidence":        "customfield_43706",  # Уровень уверенности
    "what_done":         "customfield_43822",  # Что было сделано
    "risk":              "customfield_43717",  # Описание риска/проблемы
    "metric_current":    "customfield_43713",  # Текущее значение метрики
    "metric_planned":    "customfield_43711",  # Плановое значение метрики
    "progress_pct":      "customfield_43782",  # % выполнения
    "progress_date":     "customfield_43715",  # Дата обновления %
    "metric_name":       "customfield_43739",  # Метрика (название, ед.изм.)
}
NUMERIC_FIELDS = {"metric_current", "metric_planned", "progress_pct"}  # передавать числом, не строкой (питфол скилла)

def get_checkin(issue_data: dict) -> dict[str, Any]: ...   # логическое имя -> значение, из fields
def build_checkin_payload(values: dict[str, Any]) -> dict[str, Any]: ...
    # логическое имя -> customfield ID; NUMERIC_FIELDS -> float/int, не строка;
    # значения None НЕ включать в payload (питфол "пусто ≠ 0" из скилла)
```

Тесты: маппинг известных полей, `NUMERIC_FIELDS` кастуются в число, `None`-поля исключены из payload целиком (а не переданы как `null`), неизвестный ключ → `KeyError`/явная ошибка.

### `md_store.py`

```python
FILENAME_SUFFIX_LEN = 80  # закреплено ТЗ §2 "первые ~80 символов" + текущая практика Q3_chekin_july

def okr_root(workvault_path: Path | None = None) -> Path: ...  # WorkVault/Projects/okr-tool
def period_dir(period: str, workvault_path: Path | None = None) -> Path: ...  # .../okr-tool/<period>/
def task_filename(key: str, summary: str) -> str: ...  # "<KEY>_<summary[:80] sanitized>.md"

@dataclass
class TaskMdFrontmatter:
    key: str
    type: str              # "Objective" | "KR"
    issuetype: str
    status: str
    assignee: str
    fixVersions: str
    okr_type: str | None
    department: str | None
    parent_contains: str | None
    children_contains: str | None
    source: str
    fetched: str            # ISO date

def find_existing(key: str, workvault_path: Path | None = None) -> Path | None: ...
    # Правило №0: поиск по ключу во ВСЕХ period_dir под okr_root — если найден, вызывающий код
    # НЕ должен идти в Jira (это решает вызывающий модуль, md_store только ищет и сообщает)
def save_task_md(fm: TaskMdFrontmatter, body: str, workvault_path: Path | None = None) -> Path: ...
def load_task_md(path: Path) -> tuple[TaskMdFrontmatter, str]: ...  # frontmatter (YAML) + тело
```

Схема frontmatter — **1:1 копия уже используемой** в `Projects/okr-tool/Q3_chekin_july/*.md` (см. §0.4), не изобретаем новую.

Тесты (`tmp_path` фикстура, без реального WorkVault):
- `test_task_filename_sanitizes_unsafe_chars` (`/\:*?"<>|` → `_`, обрезка длины ПОСЛЕ добавления `KEY_` префикса — питфол скилла).
- `test_task_filename_truncates_at_80`.
- `test_save_and_load_roundtrip` — сохранить → загрузить → frontmatter идентичен.
- `test_find_existing_returns_none_when_absent`.
- `test_find_existing_finds_across_period_dirs`.
- `test_save_task_md_creates_period_dir_if_missing`.

- [ ] **Критерий готовности:** все 3 модуля + тесты зелёные; `task_filename()` на реальных данных из `OKRS-3119` (см. §0.4) даёт то же имя файла, что уже используется на диске (регресс-проверка вручную одной строкой в тесте).

---

## Фаза 4 — SR-матчинг + агрегация + бриф-диалог

### Файлы (6)

- [ ] `okrtool/sr_matcher.py` — новый.
- [ ] `okrtool/aggregate.py` — новый.
- [ ] `okrtool/brief.py` — новый.
- [ ] `tests/test_sr_matcher.py` — новый.
- [ ] `tests/test_aggregate.py` — новый.
- [ ] `tests/test_brief.py` — новый.

### `sr_matcher.py`

Читает уже готовый вывод SRTool (не сырые Confluence-минутки — см. §0.6):

```python
def load_sr_period(period: str, owner_userkey: str | None = None) -> str:
    # читает файл(ы) из srtool.config.Settings().sr_output_dir за период, возвращает сырой текст SR
def extract_okr_mentions(sr_text: str) -> list[dict]:
    # регэксп по паттерну "OKR – OKRS-XXXX" / "OKR – OKRAID-XXXX" (см. пример SR-37492 §Поле 3) -> [{key, context_text}]
def match_sr_to_tasks(sr_mentions: list[dict], okr_keys: list[str]) -> dict[str, list[dict]]:
    # ключ по прямому упоминанию OKR-ключа — точный матч (confidence=high);
    # если явного ключа нет в тексте пункта SR — keyword-скоринг по названию KR (аналог SRTool.task_mapper._score_criterion),
    # неподтверждённые (score ниже порога) -> в bucket "unmatched" на ручной бриф (закрытое решение ТЗ §4.2)
```

Тесты: точный матч по явному «OKR – OKRS-XXXX», keyword-fallback матч, неоднозначный случай → `unmatched`, пустой SR → пустой результат без ошибки.

### `aggregate.py`

```python
def aggregate_kr_to_objective(kr_checkins: list[dict]) -> dict:
    # progress_pct = arithmetic mean по всем KR (закрытое решение ТЗ §4.3)
    # what_done, risk = текстовая конкатенация (не переписывание) всех непустых значений KR
```

Тесты: среднее по 2-3 KR (в т.ч. с пустыми % → исключить из знаменателя или трактовать как 0 — **явно протестировать оба варианта и задокументировать выбор в docstring**, дефолт — исключать пустые из знаменателя, т.к. пустой чекин ≠ 0% по факту), конкатенация текста с разделителем, все KR пустые → Objective-поле тоже пустое (не выдумывать текст).

### `brief.py`

Стейт-машина **по прямому образцу `SRTool.brief.BriefSession`** (см. §0.6) — `next_prompt()`/`submit_answer()`, порядок KR→Objective (закрытое решение ТЗ §2, шаг 3):

```python
@dataclass
class BriefPrompt:
    step_type: str        # "field"
    task_key: str
    field_name: str        # "confidence"|"what_done"|"risk"|"metric_current"|"progress_pct"
    proposed_value: Any
    source_hint: str | None  # ссылка на SR / metrics_resolver, для показа пользователю

class BriefSession:
    def __init__(self, tasks: list[str], proposals: dict[str, dict]): ...
    def next_prompt(self) -> BriefPrompt | None: ...   # None = бриф завершён
    def submit_answer(self, answer: str) -> None:
        # "ок" -> принять proposed_value; иначе -> текст = новое значение;
        # "посмотри в <источник>" -> НЕ обрабатывается здесь (semantic, эскалация вызывающему коду CLI/агенту)
    def applied_values(self) -> dict[str, dict]: ...    # task_key -> {field: value} для записи в MD
```

Тесты (по образцу `test_brief.py` SRTool): порядок полей/задач (все поля одного KR подряд, затем следующий KR, затем Objective последним), `"ок"` принимает предложение, произвольный текст — правку, `applied_values()` после полного прохода содержит все задачи.

- [ ] **Критерий готовности:** 3 модуля покрыты тестами; `brief.py` явно **не** делает сетевых вызовов и не пишет в Jira (это Фаза 6).

---

## Фаза 5A — OKRMetricsResolver: конфиг + ядро

### Файлы (5)

- [ ] `WorkVault/Registries/okr_metrics_map.json` — новый (данные).
- [ ] `WorkVault/Registries/README.md` — **изменить** (добавить раздел про новый реестр).
- [ ] `okrtool/metrics_sources/__init__.py` — новый.
- [ ] `okrtool/metrics_resolver.py` — новый.
- [ ] `tests/test_metrics_resolver.py` — новый.

### `okr_metrics_map.json` — схема

```jsonc
{
  "schema_version": "1.0",
  "mappings": {
    "OKRS-3119": {
      "metric_name": "% задач аналитика закрытых агентами",
      "source": "srtool",              // "srtool" | "loop" | "confluence"
      "params": {"period": "auto"}      // "auto" = период задачи из fixVersion
    },
    "OKRAID-39": {
      "metric_name": "Этапы проекта Trisigma",
      "source": "confluence",
      "params": {"page_id": "490170597", "table_row": "план-факт"}
    }
  }
}
```

Добавить в `WorkVault/Registries/README.md` раздел **«okr_metrics_map.json»** (по образцу существующего раздела про `entities.json`): назначение, схема, потребитель (`OKRTool.okrtool.metrics_resolver`), ENV-override `OKR_METRICS_MAP_PATH`.

### `metrics_sources/__init__.py` — базовый интерфейс

```python
@dataclass
class MetricResult:
    metric_name: str
    value: Any
    source: str          # "srtool" | "loop" | "confluence"
    confidence: str       # "high" | "medium" | "low" — см. §0.7, НЕ путать с чекин-полем
    period: str | None

class MetricSource(Protocol):
    def fetch(self, key: str, params: dict) -> MetricResult | None: ...
```

### `metrics_resolver.py`

```python
def load_mapping(path: Path | None = None) -> dict: ...  # ENV OKR_METRICS_MAP_PATH -> path -> дефолт Registries/okr_metrics_map.json
def resolve(key: str, mapping: dict | None = None) -> MetricResult | None:
    # 1. mapping.get(key) -> если нет записи -> None (явно, не выдумывать)
    # 2. по source -> диспетчер на конкретный адаптер (srtool_source/loop_source/confluence_source)
    # 3. адаптер кидает исключение сети/данных -> resolve() логирует и возвращает None, не падает всей цепочкой
```

Тесты: маппинг не найден → `None`; известный `source` диспетчерит на правильный мок-адаптер; неизвестный `source` в конфиге → явная ошибка при загрузке (`ValueError`, не молчаливый скип — валидация конфига); адаптер кинул исключение → `resolve()` не падает, возвращает `None` + залогировано (проверить через `caplog`).

- [ ] **Критерий готовности:** JSON валиден, `resolve()` работает на моках трёх источников (реальные адаптеры — Фаза 5B), README дополнен.

---

## Фаза 5B — Источники метрик (3 адаптера)

### Файлы (6)

- [ ] `okrtool/metrics_sources/srtool_source.py` — новый.
- [ ] `okrtool/metrics_sources/loop_source.py` — новый.
- [ ] `okrtool/metrics_sources/confluence_source.py` — новый.
- [ ] `tests/test_metrics_sources_srtool.py` — новый.
- [ ] `tests/test_metrics_sources_loop.py` — новый.
- [ ] `tests/test_metrics_sources_confluence.py` — новый.

### `srtool_source.py`

Использует `okrtool.sr_matcher.load_sr_period` + `extract_okr_mentions` (Фаза 4) — по сути тонкая обёртка: находит явное упоминание ключа в тексте SR за период, вытаскивает численное значение метрики из контекста (регэксп на число рядом с `%`/явным словом «метрика»), `confidence="high"` при точном совпадении ключа, `"medium"` при keyword-fallback.

### `loop_source.py`

⚠️ Строится на `movefromloop.keyword_checker.matches_keywords` + `loop_api.LoopClient` (прямой импорт пакета `movefromloop`, аналогично тому, как `SRTool` импортирует `confluencesync`). Ищет сообщения в канале команды по ключевым словам из `params` конфига (`params: {"channel_id": "...", "keywords": [...]}`), берёт последнее релевантное сообщение, **`confidence` всегда `"low"`** (см. §0.6 — нет структурированного API метрик, только keyword-эвристика по свободному тексту). Явно документировать в docstring это ограничение.

### `confluence_source.py`

Использует `confluencesync.confluence_client.ConfluenceClient` напрямую (прямой импорт, как в SRTool) — читает страницу по `page_id` из `params`, парсит таблицу план-факт (BeautifulSoup, аналогично `confluencesync.tasks`), ищет строку по `table_row`/ключу задачи, `confidence="medium"` (структурные данные, но зависят от формата таблицы конкретной страницы, который может меняться).

### Тесты (все 3, без сети — моки `LoopClient`/`ConfluenceClient`/`srtool.config.Settings`)

- Успешный резолв → корректный `MetricResult`.
- Источник не нашёл данные (пусто/страница не содержит строку) → `None`, не исключение.
- Сетевая ошибка адаптера → исключение наверх (ловит `metrics_resolver.resolve()`, не сам адаптер).

- [ ] **Критерий готовности:** `pytest tests/test_metrics_sources_*.py -q` зелёный; `pyproject.toml` пока не трогаем (зависимости добавим в Фазе 10 одним разом — `confluencesync`, `srtool`, `movefromloop` как editable-зависимости, если ещё не в общем venv).

---

## Фаза 6 — Запись чекина в Jira + верификация + CLI `checkin`

### Файлы (4)

- [ ] `okrtool/sync_jira.py` — новый.
- [ ] `okrtool/cli.py` — **изменить** (добавить подкоманды).
- [ ] `tests/test_sync_jira.py` — новый.
- [ ] `tests/test_cli_checkin.py` — новый.

### `sync_jira.py`

```python
def write_checkin(key: str, values: dict[str, Any]) -> None:
    # checkin_fields.build_checkin_payload(values) -> jira.edit_issue(key, payload)
def verify_checkin(key: str, expected: dict[str, Any]) -> dict[str, bool]:
    # GET issue -> checkin_fields.get_checkin() -> сравнить поле-в-поле с expected -> {field: bool совпало}
def write_and_verify_batch(items: dict[str, dict[str, Any]]) -> dict[str, dict[str, bool]]:
    # для каждой задачи: write_checkin -> verify_checkin; агрегированный отчёт по всем задачам сразу
```

### `cli.py` — новые подкоманды

- `okrtool checkin propose --period "Q3 2026"` — оркестрирует: JQL-поиск задач пользователя за период (`assignee = currentUser()` + `period.jql_fixversion_clause`) → `md_store.find_existing`/`save_task_md` (Правило №0 — если MD уже есть и пользователь явно не просил «обнови из Jira», не ходить в Jira повторно) → `sr_matcher` → `metrics_resolver` → печать предложений в TG-формате (не запись).
- `okrtool checkin brief --period "Q3 2026"` — запускает `brief.BriefSession`, читает ответы построчно из stdin (для ручного прогона/теста CLI), пишет `applied_values()` в MD через `md_store.save_task_md`.
- `okrtool checkin push --period "Q3 2026"` — **финальный шаг**, требует явного флага `--confirm` (защита от случайной записи без «запиши в Jira» от пользователя — закрытое требование ТЗ §2 шаг 4), вызывает `sync_jira.write_and_verify_batch`, печатает отчёт + ссылки.

### Тесты

- `test_sync_jira.py`: `write_checkin` формирует корректный payload (мок `jira.edit_issue`), `verify_checkin` детектирует расхождение поля (мок `jira.get_issue` возвращает не то же значение → `False` в отчёте).
- `test_cli_checkin.py`: `checkin push` без `--confirm` → выход с ошибкой/подсказкой, ничего не пишет (мок `jira.edit_issue` не вызван — `assert_not_called()`); `checkin propose` при существующем MD (Правило №0) не дёргает `jira.search`/`jira.get_issue` вообще (мок `assert_not_called()`).

- [ ] **Критерий готовности:** запись в Jira технически возможна только через явный `--confirm`; Правило №0 проверено тестом (не просто задокументировано).

---

## Фаза 7 — Блок «Клонирование KR»

### Файлы (4)

- [ ] `okrtool/clone_kr.py` — новый.
- [ ] `okrtool/cli.py` — **изменить** (добавить подкоманду `clone`).
- [ ] `tests/test_clone_kr.py` — новый.
- [ ] `tests/test_cli_clone.py` — новый.

### `clone_kr.py`

```python
@dataclass
class ClonePlan:
    source_key: str
    target_project: str
    target_fixversion_name: str
    new_summary: str          # текст с заменённым кварталом (Q3->Q4 и т.п.)
    new_description: str
    parent_key: str | None     # родительская Objective для новой связи
    link_type_id: str          # okr_task.link_type_for(target_project)
    fields_to_copy: dict       # assignee, priority, metric_planned — из образца
    fields_left_empty: list[str]  # все чекин-поля — пусто, не 0 (питфол скилла)

def build_clone_plan(source_key: str, target_period: str) -> ClonePlan:
    # 1. md_store.find_existing(source_key) — читает исходник ИЗ MD, не из Jira, если MD есть (Правило №0)
    # 2. period.next_quarter() или явный target_period, если передан
    # 3. okr_task.project_of/link_type_for — резолв связи по ПРОЕКТУ НАЗНАЧЕНИЯ (может отличаться от исходного,
    #    напр. клонирование OKRS KR в OKRAID-ветку — редкий, но явно обрабатываемый случай)
    # 4. summary/description: regex-замена Q{n} -> Q{n+1} (или год), не трогать остальной текст

def apply_clone(plan: ClonePlan) -> str:
    # создание в 2 шага (как в скилле "Создание новых KR/Objective"):
    # 1) POST /issue минимальным набором полей
    # 2) transition в рабочий статус
    # 3) PUT дозаполнение fixVersions/метрика/плановое значение (числом!)
    # 4) POST /issueLink с plan.link_type_id
    # 5) финальный GET-сверка с планом
    # возвращает key новой задачи
```

**Ручная проверка в брифе перед записью в Jira** (закрытое требование ТЗ §5.1): `apply_clone()` вызывается CLI-командой ТОЛЬКО после явного подтверждения — симметрично Фазе 6 (`--confirm`).

### `cli.py` — подкоманда

- `okrtool clone --key OKRS-3119 --to "Q4 2026"` — печатает `ClonePlan` в TG-формате (`format_tg.py`, добавить `clone_plan()`), **не создаёт задачу**.
- `okrtool clone-apply --plan-file <path> --confirm` — выполняет `apply_clone`.

### Тесты

- `test_clone_kr.py`: план строится из MD (не дёргает Jira, если MD найден — мок `jira.get_issue` не вызван); Q3→Q4 замена в тексте; Q4→Q1 следующего года; клонирование OKRS→OKRAID резолвит `link_type_id="10003"`; чекин-поля в `fields_left_empty`, не в `fields_to_copy`.
- `test_cli_clone.py`: `clone-apply` без `--confirm` не вызывает `jira.create_issue`.

- [ ] **Критерий готовности:** план клонирования воспроизводим и детерминирован (одинаковый вход → одинаковый план), запись в Jira только через explicit apply.

---

## Фаза 8 — Миграция существующих per-task MD

### Файлы (2 кода + операционные шаги)

- [ ] `scripts/migrate_okr_md.py` — новый (dry-run по умолчанию, `--apply` для реального применения).
- [ ] `tests/test_migrate_okr_md.py` — новый (тестирует только логику классификации/периода, БЕЗ реальных файловых операций на настоящем WorkVault — `tmp_path`).

### `migrate_okr_md.py` — логика

```python
def classify_file(path: Path) -> str:
    # "per_task" (frontmatter содержит key: OKRS-*/OKRAID-*) | "report" (нет key) | "index_stub" (kind: project)

def extract_period(frontmatter: dict) -> str | None:
    # читает "period" ИЛИ "fixVersions" (обе схемы существуют на диске, см. §0.4) -> period.normalize_period()

def plan_migration(entities_okr_dir: Path, projects_okr_tool_dir: Path) -> MigrationPlan:
    # per_task файлы Entities/okr/O1_MAS/*.md -> сгруппировать по key
    # если key уже есть в Projects/okr-tool/<любой period>/ -> conflict, action="archive_entities_version"
    #   (Projects-версия новее по "fetched" — см. §0.4, канон)
    # если key отсутствует в Projects/ -> action="move", target = Projects/okr-tool/<extract_period()>/
    # report/index_stub файлы -> action="flag_manual_review" (НЕ авто-перенос, см. §0.4)

def apply_migration(plan: MigrationPlan) -> None:
    # выполняет move/archive согласно plan.actions; ничего не удаляет физически (archive = переименование
    # в WorkVault/Projects/okr-tool/_archived_pre_migration/<original_name>)
```

### Тесты (`test_migrate_okr_md.py`, только логика на `tmp_path`)

- `test_classify_per_task_vs_report_vs_index_stub`.
- `test_extract_period_from_period_field` / `test_extract_period_from_fixversions_field`.
- `test_plan_migration_detects_conflict_and_prefers_newer` — синтетические 2 файла с одним `key`, разный `fetched`, план выбирает более новый как канон.
- `test_plan_migration_flags_reports_for_manual_review` (не авто-перенос).
- `test_apply_migration_dry_run_does_not_touch_disk`.

### Операционные шаги (выполняются архитектором/Сашей вручную после прогона `--apply`, не автоматизируются кодом)

- [ ] Прогнать `python3 scripts/migrate_okr_md.py --dry-run` на реальном WorkVault, вручную сверить план с §0.4 (18 файлов O1_MAS → распределены по периодам, `OKRS-3119` → `archive_entities_version`).
- [ ] Прогнать `--apply`.
- [ ] Обработать `report`/`index_stub` файлы вручную (не в скрипте, требует решения человека):
  - `Entities/okr/{OKRS-Q2-final.md, OKRS-all-OKR-060726.md, OKRS_Dependency_АИД_список.xlsx, Pages/instrument-okr_brief.md}` — предложение: перенести в `Projects/okr-tool/_reports/`, подтвердить у Саши перед переносом (это не входит в явное решение ТЗ §4.1, которое говорит только про **per-task** MD).
  - `Entities/okr/okr.md` — index-стаб; после переноса per-task файлов папка `Entities/okr/O1_MAS/` опустеет — удалить пустую папку, `okr.md` либо удалить, либо превратить в редирект-заметку на `Projects/okr-tool/`.
  - `Entities/adm/SR-OKR-matching-Q2-2026.md` — **вне скоупа**, не трогать (домен SR, §0.4).
- [ ] Grep по всему WorkVault на wiki-ссылки `[[...Entities/okr/O1_MAS...]]` / `[[OKRS-...]]`, обновить пути после переноса (см. питфол скилла про переименование при смене N — тот же принцип: обновить ВСЕ ссылки разом).
- [ ] `rclone sync` WorkVault после переноса (конвенция скилла).

- [ ] **Критерий готовности:** dry-run план вручную сверен и одобрен ДО `--apply`; после `--apply` — `Entities/okr/O1_MAS/` не содержит per-task файлов с дублирующимся `key` относительно `Projects/okr-tool/`; ни один файл не удалён физически (только перемещён/заархивирован).

---

## Фаза 9 — ТЗ для OKRSheetsExporter (отдельный документ, не код)

### Файлы (1)

- [ ] `TZ/OKRSheetsExporter/OKRSheetsExporter_TZ.md` — новый.

### Структура документа (по образцу `OKRTool_TZ.md`/`EntityRegistry_TZ.md`)

- Frontmatter: `tool: OKRSheetsExporter, version: "0.1.0", status: draft`.
- §1 Философия: ручной мини-инструмент, «экспортируй OKR за `<период>` в Sheets» (ТЗ OKRTool §5.3), никогда не часть основного чекин-флоу.
- §2 Флоу: читает per-task MD из `Projects/okr-tool/<period>/` (Правило №0 — никогда не ходит в Jira напрямую, только уже выгруженные MD, это единственный источник) → строит сводную таблицу (Objective, KR, %, уверенность, риски, что сделано) → push в Google Sheets через скилл `google-workspace` (переиспользовать нюансы уже задокументированные в `tutu-jira-okr` SKILL.md: локализованное имя листа, диапазон без префикса листа, venv/интерпретатор явным путём, `sheets get` после `update` для верификации).
- §3 Зависимости: OKRTool (данные), скилл `google-workspace`.
- §4 Формат сводной таблицы (колонки, источник каждой колонки — цитата на конкретное frontmatter/секцию per-task MD).
- §5 Открытые вопросы (для брифа с Сашей): формат листа (один лист на период / отдельные вкладки), нужна ли выгрузка Dependency-задач, автоссылка на Jira-ключ в ячейке.
- §6 Ближайшие шаги: бриф с Сашей → пофайловый план (по аналогии с этим документом) → реализация.

- [ ] **Критерий готовности:** документ создан по конвенции остальных ТЗ в `TZ/`, добавлен как `draft` — не реализуется в рамках текущего плана (это отдельный будущий инструмент).

---

## Фаза 10 — Документация, зависимости, финальная регрессия

### Файлы (4)

- [ ] `TZ/OKRTool/OKRTool_TZ.md` — **изменить**: добавить §7 «Решения при реализации v0.1.0» — зафиксировать (а) Jira link type ID (§0.2), (б) место хранения `okr_metrics_map.json` (§0.5), (в) терминологическое разграничение confidence (§0.7), (г) статус миграции. `last-section-added: "§7"`, `status` → `"в реализации"` (финальный `"active"` ставит Саша после прохождения Фазы 3 Блока «Тестирование» из `hermes-feature-cursor`, не архитектор).
- [ ] `USERTOOLS/OKRTool/README.md` — **переписать**: актуальный список модулей (см. «Общая архитектура» выше), актуальные CLI-команды (`checkin propose/brief/push`, `clone`, `clone-apply`, `resolve-metric`), убрать устаревший roadmap «v0.2 Confluence/v0.3 GSheets» (GSheets теперь отдельный инструмент — Фаза 9).
- [ ] `USERTOOLS/OKRTool/pyproject.toml` — **изменить**: добавить зависимости `pyyaml>=6.0` (frontmatter), и editable-зависимости на `confluencesync`, `srtool`, `movefromloop` (если ещё не в общем venv — проверить `pip list`, добавить только отсутствующее; **уточнение по факту проверки 06.08.2026**: `python3 -c "import confluencesync/srtool/movefromloop"` через голый системный `python3` даёт `ModuleNotFoundError` — все три пакета editable-устанавливать явно в venv, где будет жить `okrtool`, не полагаться на «уже стоит»).
- [ ] `TZ/MAIN_TZ_INVENTORY.md` — **изменить**: обновить строку `OKRTool` (версия/статус/комментарий по факту реализации), добавить строку `OKRSheetsExporter` (draft, ссылка на ТЗ из Фазы 9).

### Финальная регрессия

- [ ] `cd ~/USERTOOLS/OKRTool && python3 -m pytest -q` — все новые тесты зелёные (без сети), `test_jira_smoke.py` отдельно (по желанию, с токеном).
- [ ] `cd ~/USERTOOLS/ConfluenceSync && .venv/bin/python -m pytest -q` — по-прежнему **58 passed** (не сломали cross-import).
- [ ] `cd ~/USERTOOLS/SRTool && python3 -m pytest -q` — по-прежнему **49 passed**.
- [ ] `cd ~/USERTOOLS/MoveFromLoop && python3 -m pytest -q` — по-прежнему **98 passed, 8 failed** (те же предсуществующие 8, не больше).
- [ ] Ручной smoke: `okrtool checkin propose --period "Q3 2026"` на реальных данных (с `JIRA_TOKEN`) не падает, использует уже существующие MD из `Projects/okr-tool/Q3_chekin_july/` без обращения к Jira (Правило №0 — проверить по логам, что `jira.search`/`jira.get_issue` не вызывались для уже выгруженных ключей).

**Критерий готовности всей задачи:** все пункты выше отмечены, финальный статус «готово» по всему плану ставит Саша (не архитектор, не исполнитель) — согласно `hermes-feature-cursor` Блок 3.

---

## Сводная таблица фаз и точек проверки

| # | Фаза | Файлов | Ключевой критерий готовности |
|---|---|---|---|
| 0 | Подготовка | 0 | Бэкап + baseline + «берём в работу» |
| 1 | Скилл: абстракция OKR-задачи | 1 | v2.1.0, restore-all-skills.sh прогнан |
| 2 | `okr_task.py` | 2 | link type OKRS=11400/OKRAID=10003 в тестах |
| 3 | `period/checkin_fields/md_store` | 6 | roundtrip save/load MD идентичен, имя файла = текущей практике |
| 4 | `sr_matcher/aggregate/brief` | 6 | brief.py повторяет паттерн SRTool, без сети |
| 5A | Resolver ядро + конфиг | 5 | `okr_metrics_map.json` в Registries, README дополнен |
| 5B | 3 адаптера метрик | 6 | loop_source явно помечен `confidence="low"` |
| 6 | Запись в Jira + CLI checkin | 4 | запись только через `--confirm`, Правило №0 тестом |
| 7 | Клонирование KR | 4 | план детерминирован, apply только через `--confirm` |
| 8 | Миграция per-task MD | 2+операции | dry-run одобрен вручную ДО apply, ничего не удалено физически |
| 9 | ТЗ OKRSheetsExporter | 1 | документ создан, статус draft |
| 10 | Документация + регрессия | 4 | все 4 инструмента regression = без новых падений |

**Итого:** ~41 файловая правка/создание, разбито на 11 фаз по ≤6 файлов на фазу — соответствует питфолу composer-2.5 (>4K токенов / 12+ файлов → таймаут).

---

## Закрытые решения брифа реализации (06.08.2026)

1. **Report/index_stub файлы в Entities/okr/** — переносятся в `Projects/okr-tool/_reports/`. Не per-task MD, а сводные отчёты.
2. **Entities/okr/okr.md** — удалить вместе с папкой O1_MAS после миграции. Папка опустеет, index-стаб не нужен.
3. **loop_source.py confidence=low** — принимается для v0.1.0. Follow-up на доработку MoveFromLoop под реальные метрики — отдельно.
4. **Порядок фаз** — последовательный 1→10, без параллелизации.
