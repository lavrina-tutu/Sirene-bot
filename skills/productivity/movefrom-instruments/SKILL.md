---
name: movefrom-instruments
description: "Use when: разработка/эксплуатация семейства инструментов MoveFrom* (Fireflies, Exchange, Zulip, Confluence, Jira, Loop) — выгрузка данных из корпоративных сервисов в WorkVault (Obsidian). Общая архитектура, принципы, статусы, ссылки на ТЗ."
version: 2.0.0
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
| **MoveFromExchange** | Exchange (ТУТУ) | 🟡 **v1.0 работает**. Kerberos в домене, PAT не нужен. Крон-путь сломан после миграции (крон удалён). | нет активного | `USERTOOLS/MoveFromExchange/MoveFromExchange_TZ_v1.1.md` (не мигрировано в TZ/) |
| **AnywhereContacts** | (библиотека) | ✅ **v0.1.0** — 2148 контактов в `contacts.enc` (1747 Exchange + 401 Zulip). Schema v2 с sources. | (не крон) | `TZ/AnywhereContacts/AnywhereContacts_TZ.md` v0.1.0 |
| **MarkObjectsFromSummary** | WorkVault | 🟡 **Бриф завершён (A-F+G), ТЗ v0.1 не написано.** БЛОКЕР: нужен письменный список проектов/тем/инициатив с точными названиями и алиасами → `projects.md`. Без него v0.1 (только контакты) написать можно, v0.2+ нельзя. | — | не создан |
| **MoveFromJira** | Jira (ТУТУ) | 🥈 **Приоритет #2**, ТЗ v0.1 (draft). Только OKRAID + OKRS. Доступно без VPN (`dom.tutu.ru`, PAT). | — | `TZ/MoveFromJira/MoveFromJira_TZ.md` v0.1 |
| **ConfluenceSync** | Confluence (`dom.tutu.ru`) | ✅ **v1.0** (28.05.2026). 47/47 тестов ✅. CLI `confluencesync pull/push/resync/log`. Двусторонний. PAT работает из дома без VPN. Скилл: `movefrom-confluence`. | — | `TZ/ConfluenceSync/ConfluenceSync_TZ.md` v1.0 |
| **MoveFromZulip** | Zulip (ТУТУ) | ⏸ **КРОН ОСТАНОВЛЕН** (29.05.2026) — Zulip отключают, переход на Loop. 2148 контактов сохранены. | `vm_movefromzulip` (disabled) | `TZ/MoveFromZulip/MoveFromZulip_TZ.md` v1.0 |
| **MoveFromLoop** | Loop/Mattermost (ТУТУ) | 🆕 **Планируется.** Loop = Mattermost API v4 (`loop.tutu.ru/api/v4`). АКЦ остаётся в Zulip. Нужен PAT: Loop → Настройки → Безопасность → Токены. | — | ещё не создано |

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

**Полная карта полей API + Custom AI Skills:** `references/movefromff-api-fields.md`.

**Ссылки на summary-файлы для Саши в Telegram — ИТОГОВОЕ решение (07.07.2026):**

`obsidian://open?vault=...&file=...` **никогда не кликабелен в Telegram у этого пользователя ни в каком виде** — ни голым текстом, ни в markdown-ссылке `[имя](url)`, никакая комбинация процент-кодирования `_`/`/` не помогает (перепробовано: `safe='/_.'`, `safe=''` с `%5F`/`%2F`, экранирование `\_` в markdown, замена `_` на пробел, .md на конце vs без него). Telegram-клиент просто не линкует кастомные URI-схемы — это архитектурное ограничение клиента, не проблема кодирования. **Не тратить время на новые варианты кодирования.**

Рабочее решение — HTTP-редирект-сервер на ВМ (`~/services/obsidian-redirect/`, systemd --user `obsidian-redirect.service`, порт 8765, ~11 МБ RAM, доступен только из корп-сети tutu.ru). Отдаёт `http://` ссылку (её Telegram линкует нормально) → сервер проверяет HMAC-подпись → 302 на настоящий `obsidian://` URI.

Генерация ссылки — только через хелпер:
```bash
cd ~/services/obsidian-redirect && python3 make_link.py "Meetings/NewMeetings/<filename без .md>"
```
Результат вставлять как обычную markdown-ссылку `[имя файла](http://hermes-agents.devel.tutu.ru:8765/r?...)` — с HTTP-URL это уже работает нормально, конфликтов с `_`/markdown нет.

Безопасность (согласовано с Сашей): HMAC-SHA256 над `vault\nfile`, статичный секрет `~/services/obsidian-redirect/.secret` (chmod 600, **не перегенерировать без разрешения** — инвалидирует все разосланные ссылки); неверная подпись → обычный 404 (как несуществующий путь); 5 неудачных попыток с IP → блок 10 мин; всё логируется в `access.log`. Проверка живости: `systemctl --user status obsidian-redirect.service` (linger включён, переживает ребут). Полный код сервера — `references/obsidian-redirect-server.md`.

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

## Общие питфоллы (все инструменты)

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
- confluence-minutki-protocol-format.md — реальный storage-format страниц "Минутки" (Задачи и договорённости): 2 формата таблиц (2-кол/3-кол), <ac:task> + <ri:user ri:userkey> mention, тег проекта = ручной текстовый префикс (не макрос), дата задачи = inline <time> в теле задачи, фаззи-резолв участника через Haiku как fallback-попытка (одна, не повторяется) когда substring-match в contacts.enc не находит совпадение. Маршрутизация по составу участников (1:1/только-АИД-синк/PMO-смешанные/неразобранное) + итоговый реестр pageId для проектов, 1:1, мультисинков и служебных страниц. Основа для инструмента "Протокол from Summary" (ТЗ v0.7): **инструмент никогда не удаляет ничего в Confluence сам, только копирует** — Саша лично и часто правит опубликованные строки вручную, поэтому каждая строка несёт невидимый `row_anchor` (HTML-комментарий) для надёжной идентификации после ручного редактирования текста; МЕХАНИЗМ А = copy строки между Confluence-страницами без удаления source; МЕХАНИЗМ Б = copy актуальной строки в Obsidian `PreparedProtocols/`; Telegram-уведомления — только через `hermes send`, не прямой Bot API (токен инструменту намеренно недоступен).
- `movefrom-exchange-contacts.md` — MoveFromExchange полное ТЗ + contact-resolution: filters.py (4 правила), маскировка, exchangelib Kerberos-конфиг
- `exchange-version-configuration.md` — детали exchangelib Configuration: version, auth_type, access_type
- `qa-verification-checklist.md` — чек-лист QA против ТЗ (spec-vs-code drift)
- `confluencesync-brief-v1.md` — ConfluenceSync бриф v1 (28.05.2026): архитектура, use cases, режимы вывода, тесты
- `movefromzulip-brief-v1.md` — MoveFromZulip бриф v1: Zulip как основной источник контактов
- `tutu-corporate-integrations.md` — credentials и auth-паттерны для всех сервисов ТУТУ
- `obsidian-redirect-server.md` — HTTP-редирект-сервер для кликабельных Telegram-ссылок на файлы WorkVault (obsidian:// deep link не линкуется в Telegram напрямую)

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
