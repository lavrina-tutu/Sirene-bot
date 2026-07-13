---
name: movefrom-instruments
description: "Use when: разработка/эксплуатация семейства инструментов MoveFrom* (Fireflies, Exchange, Zulip, Confluence, Jira, Loop) — выгрузка данных из корпоративных сервисов в WorkVault (Obsidian). Общая архитектура, принципы, статусы, ссылки на ТЗ."
version: 2.1.0
author: agent
license: MIT
tags: [workvault, obsidian, sync, pipeline, jira, confluence, exchange, zulip, fireflies, loop]
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [workvault, movefrom, sync, pipeline, contacts, fireflies, exchange, zulip, confluence, jira, loop]
    related_skills: [hermes-feature, tz-workflow, movefrom-confluence, hermes-agent-skill-authoring]
---

# MoveFrom* — инструменты выгрузки данных в WorkVault

Семейство Python-инструментов: выгрузка данных из корпоративных сервисов в локальный Obsidian vault (`WorkVault`). Каждый инструмент — поставщик данных для конвейера обработки.

## Overview

- **Слой 0 — Сбор (MoveFrom*):** сырые данные из источников, без обработки смысла
- **Слой 1 — Резолвер сущностей:** Exchange GAL как «золотые записи» людей; email = универсальный ключ связи между источниками
- **Слой 2 — Структурирование (MarkObjects*/ProcessFrom*):** извлечение сущностей, YAML-frontmatter
- **Слой 3 — Аналитика (PMBOK + риски):** сигналы из реального потока данных

**Распределение ответственности:** Fireflies и внешние сервисы — дешёвая первичная обработка 24/7 (STT, черновые таски). MoveFrom* — минимальный транспорт, не оценивает качество источника. Entity Resolver + Opus — качественная обработка только на уже структурированных данных.

## Принципы (обязательны для всех инструментов)

1. **Минимум файлов на единицу данных** — количество файлов определяется ценностью, не полнотой. Не добавлять файлы ради полноты.
2. **Идемпотентность через `_registry.json`** — не качать повторно уже загруженное.
3. **Никакой постобработки** — это зона следующих инструментов конвейера (MarkObjectsFromSummary и др.).
4. **Минимальная статусная машина загрузки:** `pending` / `completed` / `error`.
5. **`_registry.md`** — рендерится из JSON через Jinja2, без доп. запросов к API.
6. **TG-алерты только при ручном запуске** с ошибкой. Cron — тишина, всё в `_log.md`.
7. **Атомарная запись:** `tmp + os.replace` для файлов и реестра.
8. **Разработка и ТЗ — только через Opus** (`delegate_task model=claude-opus-4-7` или cronjob).

## Структура инструмента (шаблон)

```
MoveFrom<Service>/
├── movefrom<service>/
│   ├── __main__.py      ← CLI: preflight → ping → skip-or-download → finalize
│   ├── config.py        ← Settings из .env (pydantic Settings, НЕ модульные os.getenv!)
│   ├── client.py        ← API клиент (requests + tenacity retry)
│   ├── schema.py        ← Pydantic модели данных
│   ├── writer.py        ← атомарная запись, rollback при ошибке
│   ├── renderer.py      ← _registry.md из JSON через Jinja2
│   ├── registry.py      ← _registry.json: load/save/migrate, portalocker
│   ├── lock.py          ← portalocker single-instance guard
│   ├── logger.py        ← _log.md (одна строка/запуск) + jsonl events
│   ├── tg.py            ← TG-алерты (только manual; cron молчит)
│   └── templates/
│       ├── registry.md.j2
│       └── *.md.j2
├── tests/
├── .env
└── .venv/
```

Пример MoveFromFF: 2 файла на встречу (transcript + summary). `actions.md` — дубль Action Items из summary, не создаётся (финальное решение май 2026).

## Стандарты CLI

**Коды выхода:** `0` успех / `1` частичный успех / `2` lock/preflight / `3` сервис/auth / `4` фатально.

**⚠️ Питфолл крон-промпта: exit code 1 НЕ всегда означает «нет новых встреч» — иногда это необработанный traceback.** Прецедент 13.07.2026 (`vm_movefromff`): формулировка в промпте крона «если exit code 0 или 1 — нет новых встреч, шли [SILENT]» заставила модель молчать несколько часов подряд, хотя `1` был реальным `pydantic.ValidationError` traceback от сломанного реестра, а не штатным «частичный успех». Различать по СОДЕРЖИМОМУ вывода, не только по коду: если stdout/stderr содержит `Traceback`, `Error`, `Exception` — это сбой, треб��ющий алерта, независимо от exit code. Штатный «нет новых» узнаётся по строке `[*] Summary: downloaded=0, skipped=N, errors=0` в выводе, не по голому коду возврата.

**Режимы:**
- `--mode test` — последние 5 дней
- `--mode cron` — новые с `_last_sync - overlap`
- `--mode manual --from-date ... --to-date ...` — произвольный период

## Приоритеты и цели

**🎯 Все проекты — кусочки для целей департамента Аналитики и данных (ТУТУ).** Цели фиксируются в Jira проекте **OKRAID**, проекты — **OKRS**.

**Приоритет инструментов (пересмотрено 22.05.2026):**
1. **MoveFromExchange (contacts/GAL)** — эталонный справочник людей (email = ключ)
2. **MoveFromJira (только OKRAID + OKRS)** — цели департамента и проекты. Нужен для быстрой постановки задач через TG.
3. **Быстрая постановка задачи через TG** — после п.1 и п.2.

Если предлагается разработка другого инструмента раньше — напомнить про порядок.

**Постановка задачи через TG:** пользователь наговаривает → Сирень показывает «кому/что/срок» → задаёт по одному: 1) к какой цели департамента (OKRAID), 2) к какому проекту (OKRS) → подтверждение → публикация. Когда OKRAID+OKRS в кэше — предлагать сама, не спрашивать каждый раз.

## Железное правило публикации

Система **никогда не публикует автономно** в Jira, мессенджеры и публичные каналы. Только через человека: система нашла → пишет в TG → пользователь подтверждает/правит → публикация.

## Резолвер сущностей — правила (22.05.2026)

**Три состояния:**
- `resolved` — точное совпадение с `canonical_name`/`aliases` или email из Exchange GAL
- `ambiguous` — суффикс `(?)` в тексте (сигнал для ручного ревью в Obsidian)
- `unknown` — сущность не тронута, оставлена сырым текстом

**Главное: не угадывать.** Лучше пропустить чем соврать.

**Ключи сущностей:** контакт → `email` (Exchange GAL); проект → `canonical_name` + `aliases` в файле проекта. В ТУТУ за 5 лет не повторилось ни одного проекта → коллизии крайне маловероятны, реестр aliases пополняется, процент авторезолва растёт сам.

**Исключение:** один термин может означать разные сущности («АБ платформа» = старая ТУТУ или новая Trisigma) → `ambiguous`, не угадывать по контексту.

## Wiki-ссылки и карточки контактов (24.05.2026)

Все сущности в frontmatter summary.md — wiki-ссылки Obsidian:
```yaml
contacts:
  - "[[Иван Иванов]]"
projects:
  - "[[Тризигма]]"
```

Формат имени контакта: `[[Имя Фамилия]]` (без отчества). Для каждого смэтченного контакта создаётся/обновляется `Contacts/Иван Иванов.md` (иначе Obsidian покажет сломанную ссылку). MarkObjectsFromSummary создаёт файлы автоматически из contacts.enc.

**Источник правды — `contacts.enc`.** Карточка `.md` — только отображение, генерируется автоматически. Карточка НЕ удаляется инструментом — только создаётся/обновляется. Старые файлы (до перехода на contacts.enc) удаляет пользователь вручную.

**Проекты тоже wiki-ссылки** — файл проекта создаётся отдельным инструментом (не MarkObjectsFromSummary v0.1). В v0.1 — только контакты.

## Архитектура хранилища сущностей

- **Хранилище + редактирование** → `.md` файлы в WorkVault с YAML frontmatter (Obsidian)
- **Аналитика и запросы** → Obsidian Dataview plugin (SQL-подобный синтаксис по frontmatter)
- **Один источник правды** — никакой параллельной БД рядом с `.md` файлами

Почему не SQLite: два источника правды сложнее поддерживать. `.md`+Dataview — нативно для Obsidian, уже установлен.

## Две страницы проекта (22.05.2026)

| Тип | Где | Назначение |
|---|---|---|
| **Локальная** | WorkVault (Obsidian) | Черновик, обновляется автоматически из всех источников. Только для нас двоих. |
| **Публичная** | Confluence | Видит команда. Публикуется только по команде Саши после просмотра локальной. |

**Шаблон:** Название / Цель / Ближайшие задачи / 🔴 Critical (не понимаем как) / Открытые вопросы / Ключевые решения / Всё остальное. Сверху — что нужно сейчас, снизу — архив. Critical ≠ Открытые вопросы: Critical = не знаем как или активный конфликт мнений.

Ориентир: `personal-ai-assistant-master@79d67c32f4c/workflows/PROJECT_ONBOARDING_WORKFLOW.md`.

Классификация встреч по проектам: не требует ручной разметки. LLM читает саммари → определяет контекст → пользователь правит. Реестр проектов с `aliases` подаётся как контекст резолверу.

## Статус инструментов (актуализировано 06.07.2026)

**Единая точка правды ТЗ:** `WorkVault/Hermes-Backlog/TZ/<Tool>/<Tool>_TZ.md` — реестр `MAIN_TZ_INVENTORY.md`. Правила именования/архивации — скилл `tz-workflow` и `TZ/_TZ-WORKFLOW-RULES.md`.

| Инструмент | Сервис | Статус | Крон (job_id) | Актуальное ТЗ |
|---|---|---|---|---|
| **MoveFromFF** | Fireflies.ai | ✅ **v2.2 в проде** (2026-07-05). Реализованы: reconciliation, backfill (newest-first, лимит 50/прогон), обрезка длины имени файла (XFS 255B), apps-preview-summary. 83+ теста ✅. | `vm_movefromff` — пн–пт 10,12,14,16,18,20 МСК | `TZ/MoveFromFF/MoveFromFF_TZ.md` v2.2 |
| **MoveFromExchange** | Exchange (ТУТУ) | ⛔ **Decommissioned (подтверждено 09.07.2026)** — физического кода не существует (`find ~ -iname "*exchange*"` не находит `USERTOOLS/MoveFromExchange`). Заменён инструментом **ExchangeOrgLookup** (`~/USERTOOLS/OrgLookup`, пакет `orglookup`) — контакт-резолв через Exchange GAL/EWS; с 09.07.2026 умеет также выгружать список переговорных комнат (`orglookup rooms` → `WorkVault/Contacts/meeting-rooms.md`, 31 комната, реальные Room Lists API сработал без фоллбэка). | нет — см. ExchangeOrgLookup | `TZ/ExchangeOrgLookup/ExchangeOrgLookup_TZ.md` |
| **AnywhereContacts** | (библиотека) | ✅ **v0.1.0** — 2148 контактов в `contacts.enc` (1747 Exchange + 401 Zulip). Schema v2 с sources. | (не крон) | `TZ/AnywhereContacts/AnywhereContacts_TZ.md` v0.1.0 |
| **MarkObjectsFromSummary** | WorkVault | 🟡 **Бриф завершён (A-F+G), ТЗ v0.1 не написано.** БЛОКЕР: нужен письменный список проектов/тем/инициатив с точными названиями и алиасами → `projects.md`. Без него v0.1 (только контакты) написать можно, v0.2+ нельзя. | — | не создан |
| **MoveFromJira** | Jira (ТУТУ) | 🥈 **Приоритет #2**, ТЗ v0.1 (draft). Только OKRAID + OKRS. Доступно без VPN (`dom.tutu.ru`, PAT). | — | `TZ/MoveFromJira/MoveFromJira_TZ.md` v0.1 |
| **ConfluenceSync** | Confluence (`dom.tutu.ru`) | ✅ **v1.0** (28.05.2026). 47/47 тестов ✅. CLI `confluencesync pull/push/resync/log`. Двусторонний. PAT работает из дома без VPN. Скилл: `movefrom-confluence`. | — | `TZ/ConfluenceSync/ConfluenceSync_TZ.md` v1.0 |
| **MoveFromZulip** | Zulip (ТУТУ) | ⏸ **КРОН ОСТАНОВЛЕН** (29.05.2026) — Zulip отключают, переход на Loop. 2148 контактов сохранены. | `vm_movefromzulip` (disabled) | `TZ/MoveFromZulip/MoveFromZulip_TZ.md` v1.0 |
| **MoveFromLoop** | Loop/Mattermost (ТУТУ) | 🆕 **Планируется.** Loop = Mattermost API v4 (`loop.tutu.ru/api/v4`). АКЦ остаётся в Zulip. Нужен PAT: Loop → Настройки → Безопасность → Токены. | — | ещё не создано |
| **ProtocolFromSummary** | Confluence (`dom.tutu.ru`) | ✅ v1.2 в проде (с 10.07.2026) — публикует "Минутки" по всем 16 протоколам реестра (проекты/1:1/мультисинки/fallback) из MoveFromFF summary. anchor-макрос + Content Property (row_anchor), МЕХАНИЗМ А (copy между Confluence-страницами) и МЕХАНИЗМ Б (copy в Obsidian) реализованы. Автоматический крон НЕ включён — blocking-требование: нужен batch-раннер (CLI поддерживает только один файл за вызов), пока обработка новых встреч только вручную. | нет активного (требует batch-раннера) | `TZ/ProtocolFromSummary/ProtocolFromSummary_TZ.md` v1.2 |
| **TaskRefresh** | Confluence (`dom.tutu.ru`), `<ac:task>` по всем страницам с `label="_aid"` | ✅ Первый прод-кейс 13.07.2026 — живой CQL-скан задач Саши (F1-F6 фильтры: исполнитель/проект/дедлайн/дата/статус), диалоговый read→apply→confirm, точечная правка текст/исполнитель/дедлайн/статус прямо на странице-источнике. W4 (закрыть/открыть) включён в MVP по факту первого использования. | не крон — интерактивный CLI по запросу | `TZ/TaskRefresh/TaskRefresh_TZ.md` v1.0, §14-15 — баги первого прод-прогона |

Детали Loop API — `references/loop-mattermost-api.md`.
Детали Confluence — `references/movefrom-confluence.md`, `references/confluencesync-brief-v1.md`, `references/confluence-obsidian-storage-design.md`.
Детали Zulip — `references/movefromzulip-brief-v1.md`.

## Корпоративные credentials

Единая доменная учётка `tkachenkoav@tutu.ru` работает для Confluence, Jira, Exchange, Zulip. **Хранить только как Personal Access Token, не пароль.** PAT можно отозвать не меняя пароль.

- Confluence/Jira: профиль → Personal Access Tokens → Create (админ не нужен)
- Zulip: Settings → Your account → API key
- Exchange: on-premise → Kerberos в домене (пароль в .env не нужен, `TUTU_PASSWORD=***` — плейсхолдер), `access_type=DELEGATE` обязателен, версию exchangelib НЕ указывать явно (мешает Kerberos negotiate). Дома без VPN — не работает. Детали: `references/exchange-version-configuration.md`. Полный auth-паттерн: `references/tutu-corporate-integrations.md`.

**В `.env` каждого проекта:**
```
TUTU_USERNAME=tkachenkoav@tutu.ru
TUTU_TOKEN=<personal_access_token>
TUTU_BASE_URL=https://dom.tutu.ru
TG_ALERT_CHAT_ID=400307920
```

`redact_secrets: true` в Hermes config уже включён — токены в логах маскируются.

## Правила разработки (ОБЯЗАТЕЛЬНО)

- **ТЗ пишет и правит только Opus** (`delegate_task model=claude-opus-4-7`). Даже мелкие правки. Haiku для ТЗ недопустим.
- **После правки ТЗ — Opus проверяет все смежные ТЗ** на непротиворечивость (смежные = читают/пишут общие файлы или вызывают друг друга).
- **Код пишет Opus.**
- **Финальная проверка кода — Haiku:** читает код и ТЗ, находит расхождения.
- **Справочные вопросы** («как работает X», «что написано в ТЗ») → Haiku с fallback на Sonnet.
- **⛔ Разработку любого инструмента запускать ТОЛЬКО по ТЗ и ТОЛЬКО после явного «ок, берём в работу» от Саши в TG.** Никакой реализации «по ходу».
- **Делегирование на Opus длинных задач (>5 мин) — через cronjob, не delegate_task.** `delegate_task` с Opus (reasoning_effort=high, child_timeout=1200) держит родительский стрим и вызывает gateway-зависания. `delegate_task` — только для коротких задач на Sonnet/Haiku.

## Распределение моделей

- **Opus** — анализ, разработка, планирование, глубокие вопросы, все ТЗ и код
- **Sonnet** — основное общение с Сашей
- **Haiku** — простые терминальные задачи (git push, cp, ls), шутки, справочные вопросы, финальная проверка кода

## Стиль работы с Сашей

Диалог с уточняющими вопросами — по одному, не монолог. Вопросы помогают отрезать лишнее и двигаться к сути. При постановке задачи через TG — всегда спрашивать 1) цель департамента, 2) проект. Когда OKRAID+OKRS в кэше — предлагать сама. Лишний раз не переспрашивать если можно догадаться.

## Инструмент-специфичные ноды

### MoveFromFF

**Что качать:** ✅ summary (основной материал), ✅ transcript (архив). ❌ actions.md — дубль Action Items из summary, финальное решение май 2026.

**Роль Fireflies:** только STT + первичная разметка спикеров. Саммари и таски — черновик, не финал. Fireflies не знает оргструктуру → кривые таски. После Exchange GAL точность резолвера вырастет автоматически.

**reconciliation + backfill (27.05.2026):** `reconcile_registry()` в `registry.py` при каждом синке проверяет completed-записи на наличие файлов на диске — если удалён, сбрасывает в `pending`. Backfill второй проход в `__main__.py`: после `fetch_range` делает `fetch_meeting(id)` для pending с известным ID, лимит 50/прогон, newest-first (`reverse=True`). Rate limit → прерывает backfill, остальные подхватятся на следующем cron. Rate limit FF сбрасывается **00:00 UTC** каждые сутки.

**Форсированный пересбор:** переименовать файл (`... - summary.md_old`), `reconcile_registry()` сбросит в pending, запустить `--mode manual --from-date --to-date`. Побочный эффект: writer атомарен, transcript тоже перезапишется.

**Массовая историческая загрузка:** помесячно через `--mode manual`, пауза 10 сек между месяцами (`sleep 10`), можно цепочкой `&&`. Timeout 600 сек на 12 месяцев. Первый месяц с данными = месяц начала использования сервиса.

**Обрезка длины имени файла (XFS 255B, 05.07.2026):** `sanitize_title()` в `filename.py` обрезает title-часть (не суффикс/расширение) по границе UTF-8-символа при `MAX_FILENAME_BYTES > 255`. Ключ реестра — `meeting_id`, не имя файла — обрезка не создаёт дублей.

**Полное удаление личной/ошибочно попавшей встречи из всей цепочки (закреплено 13.07.2026)** — когда пользователь просит убрать конкретную встречу целиком (личная тема, случайно попала в рабочий Fireflies-аккаунт), она обычно оставила след в НЕСКОЛЬКИХ независимых местах, каждое нужно закрыть отдельно — удаление только файла НЕ останавливает пайплайн от повторной публикации/скачивания:
1. **Confluence** (если уже опубликована) — прочитать страницу (`GET .../content/<pageId>?expand=body.storage`), найти `<tr>` с нужным `row_anchor`/`pfsrow-*`, вырезать ровно этот `<tr>` (regex по границам тега, не текстом), `PUT` с `version.number` = текущая+1. Проверить после — GET и убедиться, что маркер строки больше не встречается в body.
2. **ProtocolFromSummary `_registry.json`** — не удалять запись целиком, пометить `"entity": "excluded_personal"`, `"last_action": "excluded_personal"`, `"historical_no_reload": true`, обнулить `page_id`/`row_anchor`/`row_task_ids`/`published_at` — штатный guard от повторной публикации (`registry.get(meeting_id) is not None`) продолжает защищать без правки кода. Это поле у ProtocolFromSummary — свободная строка (не строгий pydantic-enum), значение `excluded_personal` там безопасно.
3. **MoveFromFF `_registry_meet.json` — ⚠️ ПРОВЕРЕННЫЙ РАБОЧИЙ ПАТТЕРН (исправлено 13.07.2026 после реального прод-инцидента):** `MeetingRecord.status` в `registry.py` — строгий pydantic enum, допустимые значения ТОЛЬКО `pending`/`completed`/`error`/`duplicate`. **НИКОГДА не вписывать `excluded_personal` или любую другую произвольную строку в `status`** — `load_registry()` упадёт с `pydantic.ValidationError` на самой первой невалидной записи, инструмент перестаёт видеть вообще ВСЕ встречи (не только исключённую), и это тихо: крон-промпт трактует результирующий exit code 1 как «нет новых встреч» и молчит несколько часов вместо алерта. Прецедент 13.07.2026: ровно так и произошло, синк молчал с 10:00 до 14:00.
   Правильный паттерн — `status: "completed"` + `files: {"transcript": "", "summary": ""}` (непустой словарь с пустыми СТРОКОВЫМИ значениями, не `{}`!). Почему именно так: `reconcile_registry()` проверяет `missing = [fn for fn in rec.files.values() if fn and not (path/fn).exists()]` — пустая строка `fn=""` даёт `if fn` → `False` → пропускается в missing, значит проверка "все файлы на месте" проходит без реальных файлов на диске и запись НЕ сбрасывается обратно в `pending` при следующем синке. `files: {}` (пустой словарь) для этого не годится — `reconcile_registry()` считает `completed` без файлов аномалией и всё равно сбрасывает в `pending`. Проверено реальным прогоном `movefromff --mode cron` после правки — статус устоял. Официально закреплено как штатный способ по решению Саши («давай и далее исключать записи подобным образом», 13.07.2026) — использовать этот паттерн для всех будущих подобных случаев без повторного изобретения.
4. **WorkVault summary/transcript файлы** — удалить физически, только после того как шаги 1-3 закрыты (иначе можно потерять контекст до правки Confluence/реестров).
5. **Бэкап перед правкой любого `_registry*.json`** — `cp file.json file.json.bak-<YYYYMMDD>-<purpose>` — оба реестра простые JSON без версионирования, откат вручную иначе невозможен.
6. `systemctl --user start --no-block owncloud-sync.service` в конце.

Разовое исключение (одна конкретная встреча) vs общее правило (тип встречи навсегда вне пайплайна, напр. регулярная личная 1-1) — уточнять явно у пользователя, это меняет объём работы (одна запись vs изменение маршрутизации `route.py`/фильтров MoveFromFF).

**Полная карта полей API + Custom AI Skills:** `references/movefromff-api-fields.md`.

**Ссылки на summary-файлы для Саши в Telegram — ИТОГОВОЕ решение (обновлено 09.07.2026, заменяет прежний вариант с редирект-сервером):**

`obsidian://open?vault=...&file=...` **никогда не кликабелен в Telegram у этого пользователя ни в каком виде** — ни голым текстом, ни в markdown-ссылке `[имя](url)`, никакая комбинация процент-кодирования `_`/`/` не помогает (перепробовано: `safe='/_.'`, `safe=''` с `%5F`/`%2F`, экранирование `\_` в markdown, замена `_` на пробел, .md на конце vs без него). Telegram-клиент просто не линкует кастомные URI-схемы — архитектурное ограничение клиента, не проблема кодирования. **Не тратить время на новые варианты кодирования.**

**HTTP-редирект-сервер (порт 8765, systemd) был построен, протестирован и затем полностью демонтирован по прямому решению пользователя 07.07.2026** ("убирай сервер с ВМ как будто бы и небыло") — домен резал нестандартный порт даже изнутри корп-сети, а после проверки оказалось, что `obsidian://` ссылка и так открывается корректно при ручной вставке в браузер. Не поднимать редирект-сервер заново без нового явного запроса.

**Финальный рабочий формат — copy-on-tap через `inline code`, без сервера.** Полная процедура, готовый пример кода и питфоллы — отдельный скилл **`get-obsidian-link`**: название файла обычным текстом сверху, `obsidian://` URL снизу в одинарных обратных кавычках (тап в Telegram копирует его в буфер, пользователь вставляет в адресную строку браузера вручную).

### MoveFromExchange (маскировка PII, 27.05.2026)

Правило для `contacts.jsonl` и TG-отображения:
- **ФИО:** первые 2 + последняя открыты, середина `**` → `Ив**в Ал**р`
- **Email:** первые 2 + последняя до `@` открыты, домен открыт → `iv**v@tutu.ru`
- **Логин:** аналогично email → `iv**v`
- **Telegram handle:** `@iv**v`

TG-поиск контактов: по имени/фамилии, до 5 результатов, поля ФИО/email/логин/отдел/команда/должность/алиасы/мессенджеры — все с маскировкой.

**XLSX-экспорт убран (v1.1):** никаких выгрузок PII в открытый файл. `contacts.enc` остаётся (AES-256-GCM). Восстановление — пересинхронизация из Exchange (кастомные поля теряются, приемлемо).

**Переговорки не синхронизируем:** `fetch_rooms()` убрать из scope.

Полное ТЗ + resolution API: `references/movefrom-exchange-contacts.md`.

### AnywhereContacts

Общая библиотека для всех коннекторов MoveFrom*. Первичный ключ — `login` (не email), Schema v2 с `sources`, общий lock `WorkVault/Contacts/.contacts.enc.lock`. Полная архитектура + PII masking + список полей: `references/anywhere-contacts-architecture.md`.

**⚠️ ЖЕЛЕЗНОЕ ПРАВИЛО (07.2026, дословно от пользователя): «Все контакты храним только в одном месте и все энкриптед».** `contacts.enc` — единственное разрешённое хранилище контактов. Никогда не создавать/расширять параллельный незашифрованный `.md`-реестр контактов (напр. `tutu-contacts.md`, `external-contacts.md` как основной справочник) — даже если кажется удобнее для быстрого просмотра/грепа в моменте задачи. Прецедент: в рамках задачи "Протокол from Summary" агент по ошибке завёл/разросил plaintext `WorkVault/Contacts/tutu-contacts.md` (добавил колонки `confluence_login`/`confluence_userkey` для ~38 контактов) вместо того чтобы сразу писать в `contacts.enc` через `ContactStore` — пользователь потребовал перенести всё в `contacts.enc` и удалить plaintext-файл. Новые поля, которых ещё нет в исходной схеме (напр. `confluence_login`/`confluence_userkey`), добавлять в `schema.py` → `CUSTOM_FIELDS` (не перезаписываются синком коннекторов), затем писать через `store.update_contact(login, {...})`. Чтение/резолв — `ContactStore(path, encryption_key).read()` / `get_contact()` / `get_contact_by_email()` / `find_contacts()`, см. `store.py`. Ключ шифрования — `CONTACTS_ENCRYPTION_KEY` в `USERTOOLS/AnywhereContacts/.env`; при `source .env` в bash-подпроцессе для `execute_code`/`terminal` использовать `set -a; source .env; set +a`, иначе переменная не экспортируется и `os.environ[...]` внутри python падает `KeyError`.

**⚠️ Питфолл batch-миграции в ContactStore: не мешать `update_contact()` (пер-запись read-modify-write) с одним финальным `store.write(data)` на устаревшей копии `data`.** При переносе множества контактов из внешнего источника (напр. старого plaintext-реестра) в `contacts.enc` — либо (а) вызывать `store.update_contact(login, {...})` для каждой записи по отдельности (каждый вызов сам делает свой read+write, безопасно, но медленнее на больших объёмах), либо (б) сделать **один** `data = store.read()` в начале, мутировать `data["contacts"][login]` **напрямую в памяти** для всех записей, и **один** `store.write(data)` в конце. Смешивание способов — вызвать `update_contact()` несколько раз (каждый раз читает актуальный файл и сразу пишет), а затем ещё раз `store.write(data)` со старой переменной `data`, прочитанной до этих вызовов — **затирает все точечные правки** удалённым старым состоянием. Признак бага: после миграции новые поля (`confluence_login` и т.п.) физически отсутствуют в файле, хотя лог скрипта показывает "Updated: N". Всегда выбирать один паттерн (single-read-mutate-write для батчей — предпочтительно) и не смешивать с `update_contact()` в том же скрипте.

**⚠️ Питфолл batch-миграции #2: Confluence username ≠ корпоративный login → дубли записей вместо обновления существующей.** Когда переносишь пачку контактов, ключуясь по корпоративному `login` (напр. из старого `tutu-contacts.md`), а целевой `contacts.enc` уже содержит тех же людей под другим ключом (Confluence-резолвленным `username`, отличающимся от корп. login — типично «фамилия без первой буквы имени»: `isereda`→`sereda`, `dnabiev`→`nabieva`, `kkrivorotov`→`krivorotov`, `azhirov`→`zhirov`) — прямой if login in contacts: update else: create создаёт дубль вместо обновления существующей записи. Починка: перед батч-миграцией собрать явный dup_map (corp_login → confluence_username) для всех известных расхождений (резолвить через CQL fullname-поиск, см. `tutu-confluence-jira` → «Резолв пользователя Confluence»), брать целевой ключ через dup_map.get(corp_login, corp_login). Если дубли уже созданы — не чинить точечными patch на дубле, а слить его поля в оригинал (store.update_contact(target_login, merged_fields)), затем удалить дубль из data["contacts"] и сделать один финальный store.write(data), с явной верификацией после.

### MarkObjectsFromSummary (архитектура брифа 24.05.2026)

**Область v0.1:** только матчинг контактов (email из participants → contacts.enc → wiki-ссылки в frontmatter + карточки Contacts/).

**Отдельный реестр `_mark_objects_registry.json`** — не трогать `_registry.json` MoveFromFF:
```json
{"schema_version": "1.0",
 "meetings": {"<id>": {"processed_at": "...", "status": "ok",
   "contacts_matched": 3, "contacts_unmatched": 1,
   "unmatched_speakers": ["Speaker 1"],
   "files": {"summary": "path/to/summary.md"}}}}
```

**Статусы:** `ok` / `empty` (без слов) / `no_participants` / `error`. Пустые/без участников не пропускать — фиксировать.

**Классификация контактов:** внутренние домены `@tutu.ru`, `@tutu.tech` (пополнять из Exchange). Внешние → `contacts.enc` с `is_internal: false`. Служебные (`noreply@`, `vendor@`) → игнорировать. Внутренний не в GAL → статус `undefined`. Speaker без email → `unmatched_speakers`, не в contacts. `ignore: true` в contacts.enc → навсегда пропускать.

**Крон:** сразу после MoveFromFF (каждые 2ч пн–пт 10–20 МСК). Папки по МСК (Europe/Moscow). Уведомления: нет, только лог.

**Режим `--rematch`:** `--meeting-id` / `--from`/`--to` / `--all`. Нужен когда контакт добавлен задним числом.

**Жизненный цикл заготовки:** «готова» после MoveFromExchange, но функционально рабочая как только матчим на неё задачи из summary.

**БЛОКЕР для v0.2+:** Саша передаёт письменный `projects.md` со списком проектов/тем/инициатив с точными названиями и алиасами.

### ConfluenceSync / MoveFromConfluence

**Чтение страниц в контекст агента (`--to-context`):** при получении ссылки на Confluence — `confluencesync pull <url> --to-context --no-recursive`, вывод в контекст. Пользователь спросил «о чём здесь речь?» — читать через инструмент, не браузер. Если конвертер даёт ошибку — прямой REST API через `execute_code` (urllib + json + regex для strip HTML).

**Confluence Keycloak SSO:** в браузере — SSO/Kerberos в домене, 2FA дома. **PAT через REST API работает из дома без VPN** (проверено 28.05.2026, HTTP 200).

**Питфолл:** передавать конкретный URL страницы (pageId или /display/SPACE/Title), не корень домена.

### MoveFromJira / MoveFromLoop

Jira: PAT + `dom.tutu.ru` работают из дома без VPN. См. ТЗ `TZ/MoveFromJira/MoveFromJira_TZ.md` v0.1 (draft).

Работа с целями OKR (проект OKRS, иерархия Objective/KR, JQL-паттерны, формат отчёта закрытия периода) — отдельный скилл `tutu-jira-okr`, не завязан на MoveFromJira.

Loop = Mattermost API v4 (`loop.tutu.ru/api/v4`). PAT: Настройки → Безопасность → Токены. Полная карта API + маппинг полей: `references/loop-mattermost-api.md`.

### TaskRefresh (первый прод-кейс 13.07.2026)

Инструмент для гибкого извлечения `<ac:task>` из Confluence по фильтрам (исполнитель/проект/дедлайн/дата/статус — F1-F6) и точечного редактирования этих же задач в диалоговом режиме. Не крон — интерактивный CLI, вызывается по запросу Саши в духе «выведи список моих задач»/«N и M надо закрыть». Venv: используется общий `~/USERTOOLS/ProtocolFromSummary/.venv/` (там уже установлены editable `anywhere_contacts` + `taskrefresh`) — у самого TaskRefresh своего venv нет.

**Рабочий паттерн (подтверждён Сашей как штатный):**
1. `taskrefresh read --assignee <login> --status incomplete --deadline "<range>"` → нумерованный бриф по проектам, сохраняет сессию (`WorkVault/Tools/TaskRefresh/session/current.json`).
2. Саша называет номера + действие текстом ("16 и 18 закрыть", "#1 дедлайн 31.07") — не жди формального синтаксиса от него, сама переводи в команду `apply`.
3. `taskrefresh apply "<команда>"` → preview "было→станет" по каждой задаче — **всегда показать это Саше** (или свериться самому) перед `confirm`, даже если он уже назвал номера — номера в его словах могут не совпадать с внутренней позицией сессии (см. питфолл ниже).
4. `taskrefresh confirm` — только после явного ОК/после того как preview подтверждён как соответствующий тому, что просили.
5. Живая проверка (`GET` страницы после `PUT`) перед финальным отчётом Саше — не доверять коду вслепую, даже с зелёными тестами.

**⚠️ КРИТИЧНЫЙ питфолл — номер #N в тексте, который ты показываешь Саше, ДОЛЖЕН совпадать с #N, которое использует `apply`/`task_by_number`.** До фикса 13.07.2026 бриф (`format_brief`) группировал/сортировал задачи для отображения, а сессия (`save_session`) хранила исходный порядок сканирования страниц — из-за этого `apply "#1 ..."` могла провзаимодействовать с другой задачей, чем показанная под #1. Если ты (или другой агент) формируешь текстовый список задач Саше **вручную, не через сам `format_brief`** — например, самостоятельно перегруппировав вывод по проекту как в этой сессии — **обязательно свериться с реальной позицией в `current.json` перед `apply`**, а не полагаться, что видимый порядок совпадает с внутренним:
```bash
python3 -c "import json; d=json.load(open('.../session/current.json')); [print(i, t['project_tag'], t['text_clean'][:60]) for i,t in enumerate(d['tasks'],1)]"
```
Актуальная версия кода (после 13.07.2026) уже гарантирует совпадение через `formatter.order_tasks_for_display()`, вызываемую один раз в `pipeline.run_read()` перед сохранением сессии — но после ЛЮБОЙ доработки инструмента заново `read` перед следующим `apply`, не переиспользовать сессию, сохранённую другой версией кода.

**Известная уязвимость XML-структуры (частично исправлена):** часть задач на реально отредактированных вручную (веб-UI) Confluence-страницах имеет `<time>`/mention вложенными глубже, чем прямой потомок `<ac:task-body>` (`<p><span><span>...<time/>...</span></span></p>` — вероятно результат ручного форматирования пользователем через веб-редактор). `rebuild_task_block()` для дедлайна (`new_deadline`/`remove_deadline`) исправлен использовать `body_el.iter()` вместо `body_el.find()` — находит `<time>` на любой глубине. **`_replace_visible_text()` (правка текста задачи, W1) той же проблеме всё ещё подвержена** — если правка текста задачи даст дубль/потерю контента на такой вложенной разметке, чинить по тому же паттерну (`.iter()` вместо `.find()`), см. `TaskRefresh_TZ.md` §14.

Полное описание найденных багов, фиксов и тестов — `WorkVault/Hermes-Backlog/TZ/TaskRefresh/TaskRefresh_TZ.md` §14 (дубль `<time>`) и §15 (рассинхронизация нумерации + W4).

## Общие питфоллы (все инструменты)

- **Никогда не вписывать произвольную строку в enum-поле (`status` и т.п.) любого `_registry*.json` без проверки допустимых значений в pydantic-модели кода.** Невалидное значение ломает `load_registry()` целиком для ВСЕХ записей, не только для одной — инструмент тихо перестаёт видеть вообще все данные, а cron-промпт может ошибочно трактовать результирующий exit code как штатный «нет новых» (см. проверенный паттерн тихого исключения встречи выше в разделе MoveFromFF).
- **`config.py` — модульные `os.getenv(...)` на верхнем уровне запрещены** — выполняются до `load_dotenv()`, значение из `.env` тихо игнорируется. Только pydantic `Settings`.
- **Реальный путь USERTOOLS для cronjob-ов:** `C:\Users\tkachenkoav\Documents\Cursor_projects\hermes-agent\USERTOOLS\` (на VM — переехало в `~/hermes-agent/USERTOOLS/`). НЕ `WorkVault/USERTOOLS/`. WorkVault — только для данных.
- **Не писать ad-hoc скрипты к API** — только через инструмент MoveFrom*. Если сценарий не поддерживается — сначала доработать инструмент.
- **`fetch_gal()` тихо возвращает 0** — причина: голый `except Exception: pass` глотает UnauthorizedError на каждом паттерне wildcards. Всегда логировать исключения в клиентах API.
- **Субагент на Haiku портит `.env` и `contacts.enc`** — при делегировании диагностики Exchange субагент подставлял тестовые credentials и удалял `contacts.enc`. Явно запрещать в промпте: «не удалять contacts.enc и .env».
- **Проверяй что субагент не написал заглушку** — после делегирования разработки API-клиента: `grep -n "return \[\]" client.py` или читать тело метода перед первым боевым тестом.
- **List-запрос не должен тянуть тяжёлые поля** — cost-limit API молча вернёт пустой массив без ошибки. Паттерн: лёгкий list → fetch полных данных только для новых записей (N+1 по числу реально новых).
- **`execute_code` vs `terminal` для Python на Windows:** `python3`/`python3.11` в терминале могут не работать (uv trampoline, MS Store alias). Для быстрых Python-скриптов — `execute_code`.
- **`Configuration(timeout=...)` → TypeError** в новых exchangelib — убрать.
- **`EXCHANGE_PASSWORD=***`** — плейсхолдер, не пароль. Реальная аутентификация через Kerberos.
- **Батч-переименование через bash ломается на пробелах/кириллице** — использовать `execute_code` + Python `os.rename()`. Детали: `references/clean-install-testing.md`.
- **Fireflies сокращает ФИО до формата «Фамилия И.О.» / «Фамилия И.»** (напр. «Ткаченко А.В.», «Аралов А.») в summary/задачах — любой резолвер контактов, использующий substring-поиск (`query in fio`, как `AnywhereContacts.find_contacts`), даёт 0 кандидатов на такой строке: сокращённая форма с точками физически не является подстрокой полного «Фамилия Имя Отчество» в `contacts.enc`. Баг тихий — не exception, а просто «не резолвится», легко принять за «контакта нет в базе». Найдено 13.07.2026 на боевой публикации (все 9 задач встречи «Синк 1-1 Саша - Саша» остались текстом вместо `<ac:link>` меншенов в ProtocolFromSummary). **Фикс-паттерн (не только для ProtocolFromSummary — для любого инструмента, резолвящего Fireflies-текст против contacts.enc):** отдельным шагом до обычного substring-поиска — regex `^([А-ЯЁ][а-яё]+)\s+((?:[А-ЯЁ]\.){1,2})\s*$` разбирает raw на (фамилия, инициалы); ищем кандидатов по одной фамилии (`find_contacts(surname)`), затем среди них оставляем только тех, у кого второе (и третье) слово `fio` начинается с этих же инициалов по порядку; 0 совпадений после фамилии → падать в обычный путь (substring по всей строке raw); >1 совпадений с одинаковыми инициалами → неоднозначность, оставлять текстом, не гадать. Рабочая реализация с тестами — `USERTOOLS/ProtocolFromSummary/protocolfromsummary/contacts_resolver.py` (`_split_surname_initials`/`_initials_match`).

## QA-верификация проектов против ТЗ

При обновлении ТЗ (особенно mid-version addenda) — систематически проверить все MoveFrom* по чек-листу `references/qa-verification-checklist.md`: фазы поиска ТЗ, spec-vs-code drift (версии, флаги API, переменные), common pitfalls (exchangelib version, custom fields merge, `is_internal`, TG alerts в cron), шаблон audit-отчёта.

**exchangelib питфолл (25.05.2026):** Explicit `Version(build=Build(15,2,1544,14))` может противоречить ТЗ (auto-discovery). Старый workaround для 401 — обновлённое ТЗ предпочитает автоматику. При конфликте: убрать build spec, добавить комментарий с датой.

**Iron rule:** кастомные поля (не из API-источника) не перезаписываются при синке — `aliases`, `messenger_ids`, `notes`, `custom_updated_at` в MoveFromExchange правятся только вручную через `/contact edit`.

## Ежедневный self-check Сирени

Крон `vm_selfcheck` (сб 03:30 МСК, Opus): проверяет консистентность скиллов и настроек, аудит распределения задач по моделям, новые коммиты в hermes-agent, ищет улучшения на hermes-agent.nousresearch.com, сохраняет отчёт `WorkVault/Hermes-Backlog/self-check-YYYY-MM-DD.md`.

## References

- `movefromff-api-fields.md` — полная карта Fireflies GraphQL API, Custom AI Skills, питфолл config.py, интроспекция схемы
- `anywhere-contacts-architecture.md` — общая библиотека контактов: schema v2, PII masking, merger, lock, что переезжает/остаётся
- `file-structure-migration.md` — реорганизация WorkVault/USERTOOLS, суффиксы `_meet`/`_cont`/`_proj`/`_task`, чеклист стадий миграции
- `clean-install-testing.md` — тестирование в свежем venv, `--override-ini`, `--timeout-method=thread`, батч-переименование через Python
- `loop-mattermost-api.md` — Loop = Mattermost API v4, эндпоинты, аутентификация, маппинг полей
- `confluence-obsidian-storage-design.md` — архитектура хранения Confluence в Obsidian: папки, frontmatter, кросс-ссылки, питфоллы имён
- `movefrom-confluence.md` — MoveFromConfluence полное ТЗ: двусторонняя синхронизация, CLI, TG-команды, парсинг action items/@mention/таблиц
- confluence-minutki-protocol-format.md — реальный storage-format страниц "Минутки" (Задачи и договорённости): 2 формата таблиц (2-кол/3-кол), <ac:task> + <ri:user ri:userkey> mention, тег проекта = ручной текстовый префикс (не макрос), дата задачи = inline <time> в теле задачи, фаззи-резолв участника через Haiku как fallback-попытка (одна, не повторяется) когда substring-match в contacts.enc не находит совпадение. Маршрутизация по составу участников (1:1/только-АИД-синк/PMO-смешанные/неразобранное) + итоговый реестр pageId для проектов, 1:1, мультисинков и служебных страниц. Основа для инструмента "Протокол from Summary" (ТЗ v1.2, active, прод-эксплуатация с 10.07.2026): **инструмент никогда не удаляет ничего в Confluence сам, только копирует** — Саша лично и часто правит опубликованные строки вручную, поэтому каждая строка несёт невидимый `row_anchor` — **anchor-макрос** `<ac:structured-macro ac:name="anchor">` (НЕ HTML-комментарий — тот вариант проверен и отклонён, Confluence сам вырезает HTML-комментарии на PUT), реально подтверждён переживающим ручное редактирование Сашей через веб-UI; МЕХАНИЗМ А = copy строки между Confluence-страницами без удаления source (anchor идентичен на всех копиях встречи); МЕХАНИЗМ Б = copy актуальной строки в Obsidian `PreparedProtocols/`; Telegram-уведомления — через `no_agent` cron script + `deliver="telegram:..."` с Markdown-ссылками (не HTML `<a href>`, не рендерится; итоговое решение, не `hermes send`). Прод-хотфиксы первого дня эксплуатации (таймзона UTC→МСК контракта MoveFromFF, N-колоночный layout, fallback резолва на дефолтного исполнителя, blocking-требование batch-раннера перед авто-кроном) — в конце того же reference-файла, применимы к любому инструменту цепочки MoveFromFF→X. **Также содержит зафиксированное решение (13.07.2026): republish сбрасывает `notified=False` безусловно, даже для чисто технических правок — это сознательное решение Саши («важно видеть когда правишь контент»), не баг, код менять не нужно.**
- `movefrom-exchange-contacts.md` — MoveFromExchange полное ТЗ + contact-resolution: filters.py (4 правила), маскировка, exchangelib Kerberos-конфиг
- `exchange-version-configuration.md` — детали exchangelib Configuration: version, auth_type, access_type
- `qa-verification-checklist.md` — чек-лист QA против ТЗ (spec-vs-code drift)
- `confluencesync-brief-v1.md` — ConfluenceSync бриф v1 (28.05.2026): архитектура, use cases, режимы вывода, тесты
- `movefromzulip-brief-v1.md` — MoveFromZulip бриф v1: Zulip как основной источник контактов
- `tutu-corporate-integrations.md` — credentials и auth-паттерны для всех сервисов ТУТУ

## Verification Checklist

Проверяется после применения паттерна (конкретные критерии, не общие фразы).

- [ ] Инструмент следует всем 8 принципам (минимум файлов / идемпотентность / без постобработки / 3-статусная машина / рендер registry.md из JSON / TG молчит в cron / атомарная запись / Opus для ТЗ и кода).
- [ ] CLI поддерживает все три режима (`test`/`cron`/`manual --from-date --to-date`) и коды выхода 0–4.
- [ ] Все конфиги — pydantic `Settings`, никаких модульных `X = os.getenv(...)` на верхнем уровне.
- [ ] Атомарная запись через `tmp + os.replace`, `portalocker` single-instance lock есть.
- [ ] Регистр (`_registry_meet.json`/`_registry_cont.json`/…) назван с правильным суффиксом сущности.
- [ ] Если инструмент пишет контакты — использует `AnywhereContacts.store`, ключ = `login`, `mask_contact()` вызывается **перед** любым выводом в TG/CLI.
- [ ] Если инструмент пишет в WorkVault — есть триггер `systemctl --user start --no-block owncloud-sync.service` после успешного синка.
- [ ] `_registry.md` собирается только из JSON через Jinja2, без обращений к API.
- [ ] TG-алерты пишутся только при `--mode manual` с ошибкой; cron молчит и всё пишет в `_log.md`.
- [ ] Актуальное ТЗ лежит в `WorkVault/Hermes-Backlog/TZ/<Tool>/<Tool>_TZ.md` и записано в `MAIN_TZ_INVENTORY.md`.
- [ ] Crontab `job_id` в этой таблице совпадает с `cronjob(action='list')` (при изменении крона — обновить статус-таблицу).
- [ ] Перед реализацией новой фичи по MoveFrom* сделан живой запрос к API — реальная схема совпала с ТЗ (или отклонение зафиксировано в отчёте Opus).
- [ ] Кастомные поля (`aliases`/`messenger_ids`/`notes`/`custom_updated_at`) не перезаписываются коннектором.
- [ ] Разработка запущена только после явного «ок, берём в работу» от Саши в TG.
