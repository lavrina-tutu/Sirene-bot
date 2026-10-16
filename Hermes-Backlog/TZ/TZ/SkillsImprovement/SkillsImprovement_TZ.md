---
name: SkillsImprovement
description: "Use when: доработка скиллов Hermes после Trisigma, pack --task, патч секции Confluence, план-график из страницы в GS, pmo-charter-fill, page-to-schedule. Зонтичное ТЗ: deep-mine-project + tutu-confluence-jira + два скилла поверх существующих charter/plan-graph паттернов. Не код USERTOOLS, не push Confluence из архитектора."
version: 0.1.0
date: 2026-09-03
status: ready
author: архитектор (cursor-grok-4.6-high, Cursor CLI)
platforms: [linux]
tags: [skills, deep-mine-project, tutu-confluence-jira, confluence, google-sheets, mpp, trisigma, pmo]
tool: SkillsImprovement
last-section-added: 2026-09-03 — v0.1.0 по брифу пост-Trisigma
depends_on:
  - TZ/deep-mine-project >= 0.2.0
  - skill:deep-mine-project
  - skill:tutu-confluence-jira
  - skill:google-workspace
  - skill:pm-briefing
  - USERTOOLS/MppReader
  - USERTOOLS/ConfluenceSync >= 1.0.1
consumers:
  - skill:tz-workflow
  - skill:hermes-feature
  - Cursor CLI (cursor-grok-4.6-high, composer-2.5)
---

# SkillsImprovement — доработка скиллов по итогам Trisigma

## Цель

Сделать так, чтобы следующий проектный цикл (архив → бриф архитектору → устав/план в Confluence/GS) шёл по скиллам без ручных брифов, без журнала компрессора вместо фактов, без PUT всего `body.storage` и без расчёта дат/ceil/бюджета моделью grok.

## Решение о форме ТЗ

Одно зонтичное ТЗ, не три. Области A/B/C — один инцидент («Полное внедрение AB-платформы Trisigma», 02–03.09.2026), один принцип разделения ролей, общие артефакты overlay. Master-файлы существующих инструментов **не переписывать**: после реализации в `TZ/deep-mine-project/deep-mine-project_TZ.md` добавить секцию-ссылку на это ТЗ (без дубля текста). У `tutu-confluence-jira` своего ТЗ нет — контракт патча живёт здесь.

**Reuse-first.** Новых USERTOOLS-пакетов нет. Скрипты — внутри скиллов. Новые скиллы только те, что согласованы брифом 03.09: `pmo-charter-fill`, `page-to-schedule`. Параллельные боевые скиллы `charter-fill`, `project-charter-authoring`, `confluence-doc-edit-cursor`, `confluence-page-editing` **не оставлять рядом** — см. блок B2.

## Входные данные

Источник диагноза: работа над проектом «Полное внедрение AB-платформы Trisigma» (overlay `WorkVault/Projects/TrisigmaFull`, сущность `Entities/trisigma`).

### Диагноз (что сломалось)

| Факт | Следствие |
|---|---|
| `deep-mine-project` собрал overlay/digest, шаги G/H как продукт не использовались | брифы архитектору писали вручную |
| Digest `p514903239`: вместо таблицы 13 фич — журнал компрессора «сжал до 39,8%» | G не может опереться на digest; координатор уходит в L0 вручную |
| Целевые страницы устав `519487958`, сравнение `519489611` нет в seed `PROJECT.yaml` | collect/refresh их не тянет; задача стартует с дырой |
| Исполнитель писал `body.storage` целиком | снесён заголовок секции «Ключевые поставки» |
| 6 замечаний Саши были известны до старта | попали во второй круг вместо чеклиста инвариантов в бриф |
| Маппинг полей плана уточнили после запуска | grok считал длительности/даты; формат GS не канон |

Прецеденты на диске (не менять в этом ТЗ, читать как фикстуры): `Projects/TrisigmaFull/digest/leaves/p514903239.md`; `docs/_charter_draft/`; MPP CSV в `mpp/`; скиллы `charter-fill` / `project-charter-authoring` / `confluence-page-editing` / `confluence-doc-edit-cursor` (паттерны, которые надо собрать, а не размножить).

### Принцип ролей (инвариант всего ТЗ)

| Роль | Модель / средство | Делает | Не делает |
|---|---|---|---|
| Архитектор | `cursor-grok-4.6-high` | формулировки, смысл полей, группировка WBS, оценка «чего не хватает» текстом | даты, ceil, бюджет, календарь, storage XML, PUT, резолв userkey, заливка GS |
| Компрессор | `composer-2.5` | факты страницы в digest по контракту | журнал процесса, анализ «что делать проекту» |
| Исполнитель/скрипт | Python внутри скилла + при необходимости `composer-2.5` как оператор CLI | CSV-экстракт таблиц, pack, section-patch, verify skeleton, userkey-resolve, complexity→duration, working calendar, GS write | переформулировать смысл полей |
| Координатор | Сирень | оркестрация, заполнение чеклиста инвариантов **до** запуска grok, приёмка GET | смешивать модели в одном `agent -p` |

Инвариант: один `agent -p` = одна модель = одна роль (как в `tz-workflow` / `hermes-feature` / `deep-mine-project` v0.2.0).

### Приоритеты

P0 — блокер следующего цикла, делать первым. P1 — сразу после P0 в той же области. P2 — после P0 своей области; `pmo-charter-fill` не начинать, пока B0 (section-patch + verify) не зелёный.

---

## Функциональные блоки

### Область A — доработка `deep-mine-project`

Новый скилл **не нужен**. Канон: `~/hermes-workspace/skills/research/deep-mine-project/` (+ симлинк default). CLI `deep_mine.py`. Overlay `WorkVault/Projects/<Slug>/`.

#### A0 (P0). Контракт digest — запрет журнала компрессора

**Проблема.** Компрессор пишет в тело листа ход работы («Сначала посмотрю структуру…», «Digest записан… ~39,8%»), а не факты L0. Тест `test_digest_contract.py` сейчас проверяет только frontmatter + блок «Источники» первым — журнал проходит.

**Контракт тела digest (дополнить `project-context-compressor-prompt.md` §6–11 и `references/overlay-contract.md`):**

Обязательно в теле после «Источники»:
- факты страницы: решения, цифры, даты, имена, ID, статусы, SLA, милестоуны;
- таблицы L0 — как markdown-таблица **или** ссылка на CSV-экстракт (A1), не как «таблица сжата»;
- именованные сущности страницы (full-coverage).

Запрещено в теле (режект файла, `digest_status: rejected`, лист не `fresh`):
- журнал компрессора: «сжал до», «% от L0», «Digest записан», «Сначала посмотрю», «Создаю digest», «Самопроверка инвентаря» как отчёт о процессе;
- дамп YAML-frontmatter внутри тела;
- инструкции автору («не копировать», «уточнить до ПК») — это бриф G, не digest.

Скрипт `digest_io` / новый `digest_validate.py` (внутри скилла): после записи листа — regex-блоклист + проверка «есть ли хотя бы одна markdown-таблица, если в L0 была `<table>` / markdown-таблица». Fail-loud: exit ≠ 0, status не `fresh`.

Правка промпта: `~/WorkVault/Registries/project-context-compressor-prompt.md`. Файл `tz-compressor-prompt.md` не трогать.

Регрессия: фикстура = текущий `p514903239.md` (журнал) → `rejected`; эталон = сжатые факты таблицы «Фичи только у Trisigma» без журнала → `fresh`.

#### A0 (P0). Шаблон брифа архитектора

Файл скилла: `references/architect-brief.template.md`.

Секции шаблона (заполняет координатор **до** `agent -p` grok, не grok сам):
1. Роль / цель пачки (одно предложение).
2. Запреты: не писать в Confluence; не считать даты/ceil/бюджет; не генерировать storage XML.
3. Чеклист инвариантов (известные до старта правила Саши) — каждый пункт `да/нет/нп`, пустой чеклист = нельзя запускать G. Для Trisigma-класса минимум: ceil дней вверх; пилот не в полях кроме явно разрешённого; источник = актуальный MPP/страница задачи, не пилотный план; формат как шаблон; бюджет = договор вендора + ФОТ MPP×ставка; сроки реализации = `<time datetime>`.
4. Список входных путей pack (A0 команда), не «прочитай весь overlay».
5. Список полей/вопросов пачки и формат ответа (markdown полей, не XML).
6. Открытые пробелы («уточнить», не выдумывать ФИО/КБК).

Шаги G/H скилла обязаны стартовать с этого шаблона. Ручной бриф в чате — обход, запрещён в SKILL.md.

#### A0 (P0). Команда `pack --task`

Новая подкоманда CLI:
```bash
~/hermes-agent/.venv/bin/python3 \
  ~/hermes-workspace/skills/research/deep-mine-project/scripts/deep_mine.py \
  pack --slug <Slug> --task <task_id>
```
`task_id` — ключ из `PROJECT.yaml` (`charter`, `feature_compare`, …) или явный `--page-id`.

Выход (только overlay, не L0):
```
Projects/<Slug>/docs/_inbox/<task_id>/
  PACK.md              # индекс: page_id, version, digest, L0 path, CSV extracts
  BRIEF.md             # шаблон брифа, поля 1–6 заполнены координатором/скриптом-скелетом
  extracts/*.csv       # A1; может быть пусто до A1
```
Pack кладёт в `PACK.md` пути: leaf-digest (если `fresh`), L0 `local_path`, theme-digest'и по `themes` YAML (если есть), MPP CSV если задача про план/устав. **Не** кладёт сырые тела всех страниц overlay. Если целевой `page_id` нет в MANIFEST — fail-loud с текстом «добавь в task_pages и collect», не молчаливый skip.

G читает только каталог pack. H читает выход G + pack. Это и есть продукт шагов G/H.

#### A1 (P1). CSV-экстракт таблиц (не LLM)

Скрипт внутри скилла (`scripts/deepmine/table_extract.py`): L0 `index.md` → `extracts/<pageId>__<slug>.csv` на каждую markdown/HTML-таблицу страницы. Без `agent -p`. Детерминированный парсер (существующий markdown/bs4 стек ConfluenceSync, не новый пакет).

Когда: `collect` / `refresh` / `pack` для страниц из `task_pages` и по флагу `--extract-tables`. Архитектор получает CSV, не просит grok «вытащи таблицу».

Инвариант: если в L0 есть таблица, а CSV нет — pack для этой страницы не `ok`.

#### A1 (P1). `task_pages` в `PROJECT.yaml`

Расширение схемы `PROJECT.yaml` (`schema_version` overlay остаётся `"1.0"`, новое поле optional для старых overlay; для нового collect — required если есть задача вне seed):
```yaml
task_pages:
  - page_id: "519487958"
    role: charter_draft
    space: PMO
  - page_id: "519489611"
    role: feature_gap
  - page_id: "514903239"
    role: feature_compare
```
`collect`/`refresh` pull'ят `task_pages` так же, как `pmo_seeds` (`--no-recursive --resync`), даже если страница не потомок `root_page_id`. TrisigmaFull: добавить три pageId выше + шаблон устава пилота `490167911` уже в `pmo_seeds` (не дублировать).

#### A2 (P2). Theme-digest'ы как продукт pack

Каталог `digest/themes/<theme>.md` уже в контракте overlay v0.2.0, на практике pack/G их не требуют. После A0: `pack --task` включает релевантные themes из `PROJECT.yaml.themes`. Theme строится из **листьев**, не из сырого L0. Компрессор тем — тот же контракт «нет журнала». Не блокирует P0.

---

### Область B — Confluence: `tutu-confluence-jira` + `pmo-charter-fill`

#### B0 (P0). Патч по секции, не PUT всего body

Место: скилл `tutu-confluence-jira` (канон корп. Confluence/JIRA). Скрипт скилла, не доработка пакета ConfluenceSync.

Атомарно:
1. GET `?expand=body.storage,version` → файл (не inline stdout).
2. Найти секцию по маркеру-заголовку (текст заголовка поля шаблона ПРО, напр. «Ключевые поставки и сроки»).
3. Заменить **только внутренность секции** (ячейки/таблица/абзацы между этим заголовком и следующим заголовком того же уровня). Заголовок секции и пояснение под ним («Прописываем в том случае…») не входят в replace-span.
4. PUT с `title` дословно + `type:page` + `version.number+1` + полный body, в котором изменена одна секция. Параллельная правка человека: если version уехала — GET заново, не затирать.
5. `space` в PUT существующей страницы не передавать.

Запрет: LLM (grok/composer) генерирует `body.storage.value` целиком или «на глаз» собирает XHTML. Выход grok — markdown/текст поля. В storage вставляет **только скрипт** (шаблоны макросов `<time datetime>`, `<ri:user>`, таблиц — из эталона GET, не из модели).

Composer-2.5 как оператор может **вызвать** скрипт; не имеет права `write` storage руками в промпте.

#### B0 (P0). Verify skeleton

После каждого PUT — повторный GET (координатор, не самоотчёт исполнителя). Чеклист (фиксировать в `tutu-confluence-jira` + копировать в бриф):
1. `version` = ожидание или честно подхвачена ручная правка.
2. Счёт `ac:structured-macro` не изменился без явной причины в брифе.
3. Каждый целевой **заголовок секции** на месте (поиск по маркеру заголовка, не по данным таблицы).
4. Удаляемые значения отсутствуют (`kw not in body`).
5. Нет дубля `<table>` под одним заголовком.
6. Нет служебного текста брифа в теле: «Не копировать», «Уточнить до ПК», «источник:», «см. бриф».
7. Число `<td>` в затронутой таблице = эталону шаблона.

Провал любого пункта = не «успех», откат к GET-до или повторный патч той же секции.

Регрессия: фикстура «таблица поставок без заголовка секции» → fail verify.

#### B0 (P0). Чеклист инвариантов в бриф

Тот же чеклист, что A0-шаблон, обязан попасть в бриф **исполнителю патча** и **архитектору полей**. Известные до старта замечания Саши не откладывать на второй круг: координатор не запускает пачку, пока чеклист не заполнен.

#### B1 (P1). Батч-резолв ФИО (userkey → username)

Эндпоинты уже в `tutu-confluence-jira` (точечный GET `/rest/api/user?key=`). Батч = скрипт: извлечь все `ri:userkey` со страницы-источника → уникальный список → резолв каждого **один раз** с кэшем на сессию → `{userkey, username, displayName}`.

Писать найденные `confluence_login` / `confluence_userkey` **только** в `contacts.enc` через `ContactStore` (AnywhereContacts). Plaintext-реестры запрещены (правило скилла, 07.2026).

Не выдумывать ФИО «Неизвестный пользователь». Глобальный `/user/search` по-прежнему 404 — не использовать. CQL `user.fullname` — только если userkey нет.

Grok получает уже резолвнутую таблицу роль→displayName/mention; сам REST не дергает.

#### B2 (P2). Скилл `pmo-charter-fill` — после зелёного B0

**Согласовано брифом 03.09** (не переоткрывать факт нового скилла). Reuse-first: это **консолидация**, не пятый параллельный скилл.

Влить и декомиссовать как отдельные entry (SKILL.md → redirect «use `pmo-charter-fill`» + `disable` в профиле после синка):
- `charter-fill`
- `project-charter-authoring`
- `confluence-doc-edit-cursor`

`confluence-page-editing`: секция page-edit → B0 в `tutu-confluence-jira`; секция план-график → C2 `page-to-schedule`. После переноса — тот же redirect.

Структура `pmo-charter-fill`:
```
productivity/pmo-charter-fill/
  SKILL.md                          # оркестрация пачек, триггеры
  references/pro-field-catalog.md   # каталог полей шаблона ПРО
  references/invariants-checklist.md
  references/architect-brief.template.md  # может symlink на deep-mine шаблон
```
Каталог полей ПРО (фиксированный, как в боевом уставе): Параметры (сроки = `<time datetime>`); Контекст; Что получит Туту; Если проекта не будет; Как заказчик поймёт; Цель; Финмодель; Описание и границы; КТ; Критерии приёмки; ИСР; Календарный план; Ресурсный план; Ключевые поставки и сроки; Бюджет; Реестр стейкхолдеров; Матрица коммуникаций; Допущения; Ограничения; Реестр угроз и рисков.

Оркестрация:
1. Вход: `page_id` драфта + `page_id` шаблона + pack `--task charter` + MPP CSV.
2. Три пачки grok (не 17 вызовов): MPP-поля / стратегические / контекстные.
3. Цифры: скрипт — ceil дней, ФОТ (`assignments.work` парсить `"80.0 h"`), бюджет = внешние (страница договора) + внутренние (ставка × часы). Ставка по умолчанию `3000` ₽/ч (протокол Trisigma); иное — явно в брифе.
4. Вставка: только B0 section-patch + B0 verify. Grok не PUT.

«Переформулировать» = переписать под логику **нового** проекта, не скопировать пилот.

---

### Область C — план-график: `page-to-schedule`

#### C0 (P0). Маппинг полей + словарь сложности **до** запуска grok

Нельзя стартовать архитектора, пока координатор не зафиксировал в pack/брифе:
```yaml
# Projects/<Slug>/docs/_inbox/<task_id>/FIELD_MAP.yaml
source_page_id: "519489611"
columns:
  feature: "Название задачи"
  gap: "Текст1"
  complexity: "Длительность"   # через словарь, не через grok
resource_name: "Гладких Юрий"
start_date: "2026-09-07"       # ISO; календарь считает скрипт
```
Словарь сложности (канон из боевого прогона, файл скилла `references/complexity-map.yaml`, overlay может переопределить):

| Сложность на странице | Длительность |
|---|---|
| менее 1 недели | 3 дня |
| 1 неделя | 5 дней |
| 1–2 недели | 10 дней |
| пусто | не угадывать: fail-loud или явная оценка Саши в брифе |

Grok не переводит сложность в дни.

#### C0 (P0). Канон колонок mpp→GS

Источник истины формата дат/длительностей/предшественников — `USERTOOLS/MppReader/push_to_gs.py` и `gantt_csv_to_gs.py`. Не изобретать третий набор.

Два согласованных профиля (не смешивать в одном листе):
**Профиль import (страница → GS → потом mpp)** — рабочий, 8 колонок (как в `confluence-page-editing/references/plan-graph-workflow.md`):
`No | Название задачи | Длительность | Названия ресурсов | Текст1 | Начало | Окончание | Предшественники`

**Профиль export (mpp → GS)** — полный, колонки `push_to_gs.py`:
`№ | % завершения | Название задачи | Длительность | Названия ресурсов | Предшественники | Начало | Окончание | Отклонение окончания | Базовое окончание | Текст1 | Текст2 | Текст3 | Текст4 | Текст5 | Текст6`

Правила ячеек (оба профиля):
- Длительность: `N дней` / `N дня` / `N день` (как `gantt_csv_to_gs.fmt_dur`), **не** `Nд`.
- Даты: `пн 07.09.26` (день недели + `%d.%m.%y`).
- Предшественники: номера задач `3`, `16;5`, без скобок и пробелов.
- Summary: длительность = сумма детей (считает скрипт), ресурс пусто.
- Лист по умолчанию русской локали: `Лист1`, не `Sheet1`. Диапазон записи `A1:<col><N+1>`.

#### C1 (P1). Скрипт complexity→duration + календарь (не grok)

Скрипт внутри будущего скилла (до появления скилла — в `tutu-confluence-jira/scripts/` временный путь запрещён: ждать C2 или класть сразу в `page-to-schedule/scripts/` при создании скилла).

Вход: CSV экстракта таблицы фич + `FIELD_MAP.yaml` + `complexity-map.yaml` + `start_date` + `resource_name`.
Выход: CSV профиля import с заполненными No, длительностью, Начало/Окончание, предшественниками (последовательность по WBS, которую grok мог **предложить** деревом, но даты ставит скрипт).

Календарь: рабочие дни Пн–Пт. Праздники РФ — таблица в `references/rf-holidays.yaml` (годы покрытия: 2026–2028 минимум). Не считать «архитектором в уме». Предупреждение в `PACK.md`: если задача пересекает 31.12–08.01 — явная пометка.

Ceil: любая дробная длительность из MPP/расчёта → вверх до целого дня (`361.875 → 362`).

#### C2 (P2). Скилл `page-to-schedule`

**Согласовано брифом 03.09.** Триггеры: «план-график из страницы», «залей фичи в GS как mpp», pageId сравнения фич.

Пайплайн:
1. `confluencesync pull <pageId> --resync` + pack `--task` (A).
2. CSV-экстракт таблицы (A1) — не LLM.
3. FIELD_MAP + словарь сложности (C0) — стоп, если нет.
4. Grok (опционально): только группировка WBS/названия summary-строк, не даты.
5. Скрипт C1 → CSV.
6. Заливка GS: `google-workspace` / Sheets API по паттерну `MppReader/push_to_gs.py` (OAuth, share-список не хардкодить в новом месте — reuse констант MppReader или параметр `--share`). Не invent отдельный OAuth.

Не пишет .mpp (MppReader на Linux .mpp не пишет). Цель — GS, который Саша/Юра переносят в Project.

---

## Критерии успеха

Проверяемые. Регрессии — pytest в соответствующем скилле, маркер `not live` для unit; live — только при VPN и явной команде.

### A
1. Фикстура-журнал `p514903239` (фразы «сжал до», «Digest записан») → `rejected`, не `fresh`.
2. Эталонный digest страницы с таблицей содержит markdown-таблицу или ссылку на CSV; журнал процесса отсутствует.
3. `pack --task feature_compare --slug TrisigmaFull` создаёт `docs/_inbox/feature_compare/{PACK.md,BRIEF.md}` со ссылками на digest **и** L0; в `BRIEF.md` чеклист инвариантов не пустой.
4. `PROJECT.yaml` с `task_pages` для `519487958` / `519489611` / `514903239`: `collect`/`refresh` тянет их в L0+MANIFEST.
5. Для страницы с таблицей pack без CSV-экстракта завершается ошибкой (после A1).
6. Существующие команды `mine|refresh|digest|analyze|document` живы; 31 текущих тестов deep-mine не краснеют из-за A0 (допускается расширение набора).

### B
7. Патч секции «Ключевые поставки и сроки» на фикстуре storage: заголовок секции и пояснение на месте, таблица заменена, счёт макросов эталона сохранён.
8. Попытка передать модели сгенерированный полный `body.storage` в обход скрипта — в SKILL.md явный запрет; код патча не принимает storage от stdin модели как единственный путь.
9. Verify skeleton падает, если заголовок секции удалён (регрессия Trisigma).
10. Батч-резолв: N уникальных userkey → N GET, повторный userkey из кэша; запись только в `contacts.enc`.
11. После B2: триггеры «заполни устав» резолвятся в `pmo-charter-fill`; старые четыре скилла не исполняют пайплайн (redirect).

### C
12. Без `FIELD_MAP.yaml` и словаря сложности CLI/скилл не вызывает grok (fail-loud).
13. «1 неделя» → длительность `5 дней` скриптом, не моделью.
14. CSV/GS профиля import: 8 колонок в каноническом порядке; даты `пн DD.MM.YY`; длительность с словом «день/дня/дней».
15. Запись в лист `Лист1` (не `Sheet1`) на типичном OAuth-аккаунте; диапазон `A1:H<N+1>`.
16. Праздник из `rf-holidays.yaml` не становится рабочим стартом задачи.

### Сквозной
17. В логе координации сессии «устав + план» нет `agent -p` grok, в промпте которого просят посчитать даты, ceil, ФОТ или собрать XHTML storage.
18. Повтор Trisigma-класса: замечания из чеклиста инвариантов не появляются как «второй круг» (проверяется процессом: чеклист заполнен до первого grok).

---

## Что НЕ трогать

- Код и ТЗ **ConfluenceSync** (`--with-attachments` по-прежнему не здесь).
- `tz-compressor-prompt.md`; порог `compression.threshold`.
- Канон L0: не копировать тела `WorkVault/Confluence/`, `Meetings/`, `Entities/` в overlay.
- Транскрипты встреч в overlay.
- Gateway не рестартить. Кроны не ставить (нет слота в этом ТЗ).
- `ConfluenceSync push` из шагов A–C; запись в Confluence — только B0 по явной задаче «внеси в устав», не из grok.
- Пакеты **ProtocolFromSummary**, **TaskRefresh**, **SRTool**, **OFC**, **MofsIndex** схема БД — не «заодно».
- **AnywhereContacts** схема: не плодить plaintext-контакты; новые поля userkey — только если уже есть в `CUSTOM_FIELDS`, иначе отдельный вопрос (не блокер B1: писать в существующие custom-поля).
- **MppReader**: не менять `read_mpp.py` / запись .mpp; C только читает канон колонок и reuse заливки GS.
- Overlay TrisigmaFull как боевые данные: не пересобирать mine «чтобы проверить ТЗ»; фикстуры копировать в `tests/fixtures`.
- Профили Hermes кроме default; `restore-all-skills.sh` — после реализации скиллов, не в сессии ТЗ.
- Master-ТЗ других инструментов не переписывать текстом A/B/C; только короткая секция-ссылка в `deep-mine-project_TZ.md` после реализации.
- Не создавать USERTOOLS-пакет SkillsImprovement / DeepMine / CharterFill.

---

## Связи с экосистемой

| Компонент | Роль | Как вызывать | Ограничение |
|---|---|---|---|
| **deep-mine-project** | A: digest, pack, task_pages, CSV-таблицы | `deep_mine.py collect\|refresh\|digest\|pack` | не новый скилл |
| **project-context-compressor-prompt.md** | A0 контракт тела | `composer-2.5` | запрет журнала; не tz-compressor |
| **tutu-confluence-jira** | B0 патч/verify, B1 резолв, auth Confluence/JIRA | скрипты скилла + REST Bearer | не PUT из grok |
| **ConfluenceSync** | pull L0, клиент GET page | `python3 -m confluencesync pull` | не дорабатывать пакет |
| **pmo-charter-fill** | B2 оркестрация устава | новый скилл после B0 | консолидация трёх старых |
| **page-to-schedule** | C пайплайн страница→CSV/GS | новый скилл | не пишет .mpp |
| **MppReader** | канон колонок, fmt дат/длительности, образец GS | `read_mpp.py`, `push_to_gs.py` | Linux: .mpp read-only |
| **google-workspace** | OAuth Sheets/Drive | `gws` / `google_api.py` | лист `Лист1` |
| **pm-briefing** | формат вопросов Саше, если всплывёт OQ | 1 вопрос, варианты, рекомендация | не заменяет чеклист инвариантов |
| **AnywhereContacts** | хранение userkey/username | `ContactStore` / `contacts.enc` | не plaintext |
| **tz-workflow / hermes-feature** | реализация после записи ТЗ | Cursor CLI | бриф 03.09: реализация без доп. апрува содержания; кроны всё равно только по «ставь кроны» |
| **EcosystemManifest** | регистрация двух новых скиллов | координатор, `render_manifest.py` | механика, не этот файл |

Существующие скиллы `charter-fill`, `project-charter-authoring`, `confluence-doc-edit-cursor`, `confluence-page-editing` — доноры текста, не целевая архитектура.

---

## Контракты экосистемы

### Источник истины
- Владелец overlay/digest/pack: `deep-mine-project` (`WorkVault/Projects/<Slug>/`).
- Владелец тел страниц Confluence: `api_confluence`; L0 — ConfluenceSync.
- Владелец патча секции: скрипт `tutu-confluence-jira` (запись в Confluence только через него в рамках B).
- Владелец канона колонок GS/дат/длительностей: MppReader (`push_to_gs.py` / `gantt_csv_to_gs.py`).
- Владелец контактов userkey: AnywhereContacts (`contacts.enc`).
- Владелец словаря сложности и FIELD_MAP задачи: overlay `docs/_inbox/<task_id>/` + дефолт скилла `page-to-schedule`.

### Входные контракты

| Поле | Тип | Обязательность | Источник (кто отдаёт) | Формат/enum |
|---|---|---|---|---|
| slug | str | required | PROJECT.yaml | латиница overlay (`TrisigmaFull`) |
| task_id | str | required | pack CLI / PROJECT.yaml | ключ задачи (`charter`, `feature_compare`) |
| page_id | str | required | PROJECT.yaml task_pages / бриф | ID Confluence |
| role | str | optional | PROJECT.yaml task_pages | `charter_draft` / `feature_gap` / `feature_compare` / иное |
| digest_status | enum[fresh,stale,missing_remote,rejected] | required | deep-mine digest_validate | rejected = журнал компрессора или дыра контракта |
| local_path | str | required | ConfluenceSync / MANIFEST | путь L0 `index.md` |
| section_heading | str | required | каталог полей ПРО / бриф патча | маркер заголовка секции дословно |
| version.number | int | required | api_confluence GET | текущая версия страницы |
| userkey | str | optional | body.storage `ri:userkey` | hex/opaque ключ Confluence Server |
| complexity_label | str | optional | таблица страницы-источника | ключ словаря (`1 неделя`, `менее 1 недели`) |
| start_date | datetime(iso8601) | required | FIELD_MAP / бриф Саши | дата старта плана, календарь считает скрипт |
| resource_name | str | required | FIELD_MAP | отображаемое имя ресурса в GS |
| share_email | str | optional | MppReader / параметр CLI | email для Drive share |
| fot_rate_rub | int | optional | бриф устава | дефолт 3000 |

### Выходные контракты

| Поле | Тип | Потребитель (кто получает) | Формат/enum |
|---|---|---|---|
| pack_dir | str | архитектор G, pmo-charter-fill, page-to-schedule | `Projects/<Slug>/docs/_inbox/<task_id>/` |
| digest_status | enum[fresh,stale,missing_remote,rejected] | pack, шаг G | G не берёт rejected |
| extract_csv_path | str | page-to-schedule, архитектор | CSV UTF-8, заголовок из таблицы L0 |
| patched_section | str | verify skeleton | имя секции, которая одна изменена |
| skeleton_ok | bool | координатор | true только если чеклист B0 пройден |
| username | str | pmo-charter-fill, mention в storage | Confluence username ≠ корп. login |
| displayName | str | реестр стейкхолдеров | ФИО из API |
| duration_label | str | GS import | `N день` / `N дня` / `N дней` |
| gs_profile | enum[import,export] | google-workspace / MppReader | import=8 кол., export=колонки push_to_gs |
| sheet_title | str | Sheets API | дефолт `Лист1` |
| spreadsheet_id | str | Саша / исполнитель плана | ID созданного GS |

### Зависимости
- Получает от: [deep-mine-project, ConfluenceSync, api_confluence, MppReader, google-workspace, AnywhereContacts, Registries/project-context-compressor-prompt.md]
- Отдаёт: [pmo-charter-fill, page-to-schedule, Cursor CLI архитектор, Cursor CLI исполнитель, Сирень, Саша]

### Breaking changes policy
- Версионирование формата: `schema_version` в `PROJECT.yaml` / MANIFEST (`"1.0"`) и во frontmatter digest.
- Добавление `task_pages` — non-breaking (optional). Смена смысла `digest_status` (новый `rejected`) — minor: потребители G/pack обязаны не читать rejected как fresh.
- Смена порядка колонок GS import — breaking: уведомить page-to-schedule и concfluence-page-editing (пока жив).
- При breaking: `migrate_vN_to_vN+1()` в скриптах скилла, уведомить «Отдаёт».

### Границы («что НЕ трогать»)
- Не менять ключ страницы MANIFEST с `confluence_id` на title.
- Не считать выход grok входным контрактом storage.
- Не писать userkey/username в markdown-реестры Contacts.
- Не менять CLI ConfluenceSync как часть реализации.
- Не отдавать шаг G сырой журнал компрессора.

---

## Открытые вопросы

Блокирующих нет: бриф 03.09 закрыл состав областей, приоритеты и факт двух новых скиллов. Ниже — не блокируют P0.

### OQ-1. Источник праздников РФ для C1
Календарь рабочих дней нужен скрипту, grok его не считает.
**Рекомендация:** 1 — YAML `rf-holidays.yaml` в скилле на 2026–2028 (детерминировано, без Exchange).
1. Хардкод YAML в скилле на 2026–2028, обновление раз в год вручную
2. Тянуть производственный календарь из Exchange (зависимость MeetingScheduler/EWS, хрупко без VPN)
3. Не вычитать праздники, только Пн–Пт (как сейчас в боевом прогоне — с предупреждением)
Дефолт до ответа Саши: **1**, P1 не стопается: файл завести списком известных дат 2026–2028.

### OQ-2. Регистрация в EcosystemManifest
Два новых скилла после реализации.
**Рекомендация:** 1 — координатор правит манифест в той же волне hermes-feature, что и SKILL.md.
1. В волне реализации скиллов
2. Отдельной задачей после приёмки P0
Не блокер написания ТЗ.

### Закрыты брифом 03.09 (не переоткрывать)
1. Одно ТЗ-зонтик, не три.
2. A = доработка `deep-mine-project`, не новый скилл.
3. B0 в `tutu-confluence-jira` (патч секции, verify, запрет LLM→storage).
4. `pmo-charter-fill` и `page-to-schedule` — новые скиллы после P0; реализация без доп. содержательного апрува.
5. Grok = смысл; скрипт = даты, ceil, бюджет, календарь, storage-патч, резолв, GS.
6. Консолидация старых charter/edit скиллов в B2/C2 — решение архитектора по reuse-first внутри уже согласованных имён.

---

## Порядок реализации (атомарно, hermes-feature)

Не код в этой сессии. Порядок для исполнителя:
1. A0 digest-контракт + валидатор + правка компрессор-промпта + шаблон брифа + `pack --task`.
2. B0 section-patch + verify skeleton + запрет LLM→storage в `tutu-confluence-jira`.
3. C0 FIELD_MAP + словарь + канон колонок в references (можно до скилла как файлы `page-to-schedule`).
4. A1 CSV-экстракт + `task_pages`.
5. B1 батч-резолв.
6. C1 скрипт календаря.
7. A2 themes в pack.
8. B2 `pmo-charter-fill` + redirect старых скиллов + `restore-all-skills.sh`.
9. C2 `page-to-schedule` + redirect plan-graph из `confluence-page-editing`.
10. Секция-ссылка в `deep-mine-project_TZ.md`; строка в `MAIN_TZ_INVENTORY.md`; скиллы в EcosystemManifest.

Кроны не создавать.

## Приложения к ТЗ

| Файл | Содержание |
|---|---|
| — | нет; бриф 03.09 — вход этой сессии, не копировать в `TZ/SkillsImprovement/` как appendix |

## Статус

Ready v0.1.0 (2026-09-03). Содержание согласовано брифом Саши. Реализация без доп. апрува, по скиллам/паттернам. Gateway не рестартить. Кроны не ставить.