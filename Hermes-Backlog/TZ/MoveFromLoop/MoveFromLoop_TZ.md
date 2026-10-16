---
name: MoveFromLoop
version: 0.4.9
status: draft
date: 2026-07-23
last-section-added: 2026-10-16 — TZ:patch v0.4.9 urgent_channels (DEV/mfl-urgent-channels)
---

# MoveFromLoop — ТЗ

Автор: Opus (по заданию Саши Ткаченко)

## Доработка: MoveFromLoop v1 синк контактов — РЕАЛИЗОВАНО (2026-07-24)

## §1 Цель

Синхронизировать пользовательские контакты из корпоративного Loop (Mattermost, `loop.tutu.ru`) в единый реестр `contacts.enc` через `ContactStore` — по паттерну `MoveFromZulip`, но со своим коннектором `source="loop"`.

## §2 Место в экосистеме

- Класс: connector-инструмент семейства `MoveFrom*` (наряду с `MoveFromZulip`, `MoveFromFF` и др.).
- Источник данных: Loop = Mattermost, self-hosted, base URL `https://loop.tutu.ru`, REST API v4.
- Назначение: `WorkVault/Registries/contacts.enc` через библиотеку `AnywhereContacts` (`ContactStore`).
- Связь с `MoveFromZulip`: инструменты **независимы**, работают параллельно, оба пишут в `contacts.enc`. Идемпотентность обеспечивается тем, что каждый коннектор пишет только в свою секцию `sources[<name>]` и не трогает `CUSTOM_FIELDS`. Дедуп по `login` (см. §3.4).
- Регистрация в `MAIN_TZ_INVENTORY.md` — активный инструмент.

## §3 Входные данные

### 3.1 API endpoints (проверены живым запросом 2026-07-23)

- `GET /api/v4/users/me` — sanity-check токена. **Работает из VM.**
- `GET /api/v4/users?per_page=200&page=N` — постраничный список пользователей. Работает; при `page=0, per_page=5` вернул 5 записей со всеми ожидаемыми полями.

Пагинация: инкрементировать `page` начиная с 0, пока `len(response) > 0`. Максимальный `per_page` по документации Mattermost = 200 (использовать 200). Между запросами пагинации — пауза **0.1 сек** (мягкий rate-limit, чтобы не упереться в лимиты сервера при росте объёма).

Отдельный запрос `/api/v4/bots` **не делаем** — детект бота полностью по эвристике над полями `/api/v4/users` (см. §5 п.4).

### 3.2 Поля, возвращаемые API (подтверждено на живом ответе)

Ключи объекта пользователя из `/api/v4/users`:
`id, username, email, first_name, last_name, nickname, position, auth_data, auth_service, roles, locale, timezone, create_at, update_at, delete_at, disable_welcome_email`.

Из `/api/v4/users/me` дополнительно: `email_verified, notify_props, props` и т.п. — для синка не нужны.

Поле `is_bot` в ответе `/api/v4/users` **не наблюдалось** явно у первых записей (значение `None`). Признак бота детектируется эвристикой по `delete_at`, `roles`, `email` — см. §5 п.4.

### 3.3 Аутентификация

- Bearer token, заголовок `Authorization: Bearer ***`.
- Токен хранится в `.env` в корне USERTOOLS-инструмента: `LOOP_TOKEN=<...>`.
- Не коммитить `.env`; в репозитории — только `.env.example` с пустым значением.

### 3.4 Дедупликация

Ключ дедупа — `login`, где `login = email.split('@')[0].lower()` (та же схема, что в `MoveFromZulip`). Если контакт с таким `login` уже существует в `contacts.enc` (независимо от источника) — считаем это **тем же человеком** и делаем `update_contact`, дополняя недостающие поля. Расхождение `username` в Mattermost vs `login` из email **игнорируется** — истина по email. Ручные alias'ы — через `CUSTOM_FIELDS.aliases` (не трогаем).

## §4 Выходные данные

Обновление `contacts.enc` через `ContactStore` (add / update). Записываемые поля (плоский слой + per-source meta):

| поле contact | источник значения (Loop API) | комментарий |
|---|---|---|
| `login` | `email.split('@')[0].lower()` | ключ дедупликации |
| `fio` | `last_name + " " + first_name` (trim). Если оба пусты — `nickname` или `username` | порядок «Фамилия Имя», как в `MoveFromZulip`. Не затирает существующее непустое значение. |
| `email` | `email` | не затирается пустым |
| `position` | `position` | пустая строка → **не писать** (см. §5 п.6) |
| `sources.loop.username` | `username` | mattermost username, справочно |
| `sources.loop.nickname` | `nickname` | |
| `sources.loop.synced_at` | now (UTC ISO) | |
| `sources.loop.active` | `delete_at == 0` | |

**Инвариант:** `mattermost_id` (поле `id` из API) **никуда не пишется** — ни в схему `contacts.enc`, ни в `sources.loop`. При необходимости связки Loop-аккаунта с контактом ключом служит `email` / `login`.

`CUSTOM_FIELDS` (`aliases, notes, custom_updated_at, project_roles, confluence_login, confluence_userkey, reports_to`) — **никогда** не трогаются. `SOURCE_BASIC_FIELDS` обновляются по общему правилу: **только дополнять, не перезатирать**. Если поле уже заполнено (любым коннектором или вручную) — не трогаем. Если приходит пустое значение из Loop — не трогаем существующее.

## §5 Алгоритм

1. Прочитать `LOOP_TOKEN` из `.env` (`python-dotenv`). Если отсутствует — fail-loud, exit code 2.
2. Sanity-check: `GET /api/v4/users/me` → 200. Иначе — exit code 3, `contacts.enc` не меняется.
3. Постранично тянуть `GET /api/v4/users?per_page=200&page=N`, N = 0, 1, 2, ... пока ответ непустой. Между страницами — `sleep(0.1)`.
4. Фильтрация каждого пользователя (порядок проверок):
   - **Бот** — эвристика: `delete_at > 0` **И** (`roles` содержит `system_bot` **ИЛИ** `email` заканчивается на `-bot@…` / `bot@…`). Совпало — пропустить, `skipped_bot`.
   - **Деактивированный** — `delete_at > 0` и не бот → пропустить, `skipped_deactivated`.
   - **Невалидный** — пустой `email` или `email` без `@` → пропустить, `skipped_invalid`.
5. Маппинг полей по таблице §4. `login = email.split('@')[0].lower()`.
6. Upsert через `ContactStore`:
   - `find_contacts(login=...)` → если найден: `update_contact(login, updates)`. В `updates` кладём **только non-empty** значения; поля, уже имеющие значение в существующем контакте, не перезатираются (правило «дополнять, не перезатирать» реализуется на стороне мэппера — пустые/None ключи выкидываются до передачи в `ContactStore`).
   - Иначе: `add_contact(login, payload)` с `sources.loop`.
7. Retry сетевых вызовов: **3 попытки, back-off 1s / 3s / 9s** на 5xx и `requests.Timeout` / `ConnectionError`. На 4xx — сразу fail (кроме 429 — трактовать как 5xx). После третьей неудачи — прерывание прогона, exit 3, транзакция `contacts.enc` не коммитится.
8. По завершении — атомарная запись `contacts.enc` (одна транзакция на весь прогон, как в `MoveFromZulip`).
9. Лог в stdout: `added=N, updated=M, skipped_bot=K1, skipped_deactivated=K2, skipped_invalid=K3, total_seen=T`.
10. Exit code: 0 — успех, 2 — конфиг, 3 — API/сеть, 4 — ошибка записи `contacts.enc`.

## §6 Файловая структура

```
USERTOOLS/MoveFromLoop/
  movefromloop/
    __init__.py
    config.py         # чтение .env, константы (BASE_URL, PER_PAGE, PAGE_SLEEP, RETRY_BACKOFF)
    loop_client.py    # requests-обёртка над /api/v4/users с пагинацией, retry (1/3/9s), паузой 0.1s
    filters.py        # is_bot / is_deactivated / is_valid
    mapper.py         # Loop user JSON → dict полей contact (drop empty)
    sync.py           # ContactStore add/update, счётчики
    __main__.py       # CLI entry
  scripts/
    sync_contacts.py  # тонкий wrapper: python -m movefromloop
  tests/
    test_filters.py
    test_mapper.py
    test_sync.py      # с mock ContactStore
  README.md
  .env.example        # LOOP_TOKEN=
  pyproject.toml
  requirements.txt    # requests, python-dotenv, anywhere-contacts (editable)
```

Виртуальное окружение — `venv_linux/` (по паттерну `MoveFromZulip`).

## §7 Крон

- Schedule: `30 3 * * 0` — воскресенье 03:30 (следом за/параллельно `MoveFromZulip`; блокировка `contacts.enc` покрыта `ContactStore`).
- Model: **Haiku** (детерминированный скрипт, LLM не нужна; Hermes-обёртка для унификации логов и retry).
- deliver: `local` (в лог-канал Hermes; отдельного TG-уведомления не требуется).
- Команда:
  ```
  cd ~/USERTOOLS/MoveFromLoop && venv_linux/bin/python -m movefromloop
  ```

## §8 Тест-кейсы

1. **Новый пользователь Loop** → `add_contact`, запись `sources.loop` заполнена, `fio="Фамилия Имя"`, `login` = префикс email.
2. **Существующий контакт (пришёл из Zulip)** с тем же `login` → `email/position` **дополняются, если были пусты**; `sources.zulip` не тронут; `fio` не затирается.
3. **Бот-аккаунт** (`delete_at>0` + `roles=system_bot`, либо `delete_at>0` + email `…-bot@…`) → пропущен, счётчик `skipped_bot`.
4. **Деактивированный человек** (`delete_at > 0`, не подходит под эвристику бота) → пропущен, `skipped_deactivated`.
5. **API 401/403** (протухший токен) → exit 3, `contacts.enc` без изменений.
6. **Сетевая 5xx на странице N** → 3 retry с 1/3/9s; если все три упали — exit 3, транзакция не коммитится.
7. **Пауза между страницами**: при N≥2 страницах фактическая задержка между запросами ≥ 0.1s (проверяется в mock-тесте client'а).
8. **Идемпотентность**: два прогона подряд → второй не даёт diff (кроме `sources.loop.synced_at`).
9. **CUSTOM_FIELDS не тронуты**: `notes`, `reports_to`, `project_roles` до/после прогона идентичны.
10. **Пустое ФИО**: `first_name=""` и `last_name=""` → `fio` = `nickname` или `username`, не пустая строка.
11. **Пустой `position`**: не пишется в контакт; если у существующего контакта уже был `position` — сохраняется.
12. **`mattermost_id` не утекает**: ни в схеме, ни в `sources.loop.*` нет ключа `mattermost_id` / `id`.

## §9 Что НЕ трогать

- Прямая запись в `contacts.enc` в обход `ContactStore`.
- Схема `contacts.enc` (`schema.py`) — новые поля **не добавляем**. `mattermost_id` не пишем вообще.
- `MoveFromZulip`, `MoveFromFF`, `MoveFromJira`, `AnywhereContacts` — их коды и конфиги.
- Каналы, сообщения, посты Mattermost — тянем **только** `/api/v4/users`.
- Endpoint `/api/v4/bots` — не используем.

## §10 Связи с экосистемой

- **Читает:** Loop API v4 (`https://loop.tutu.ru/api/v4/users`, `/users/me`).
- **Пишет:** `WorkVault/Registries/contacts.enc` через `AnywhereContacts.ContactStore`.
- **Зависит от:** `AnywhereContacts` (ContactStore API, schema v2, CUSTOM_FIELDS-контракт).
- **Параллельно с:** `MoveFromZulip`, `MoveFromFF (contacts побочно)`, `MoveFromJira` — общий `contacts.enc`, изоляция через `sources[<name>]`.
- **Не зависит от:** `MoveFromFF` pipeline, `MOFS`, `ProtocolFromSummary`, `EntityRegistry`.

## §11 Решения брифа (23.07.2026)

Ниже — принятые Сашей решения по открытым вопросам первого черновика. Все они уже интегрированы в §3–§5; раздел оставлен как справка о происхождении требований.

1. **Детект ботов** — эвристика по `/api/v4/users`: `delete_at > 0` **И** (`roles` содержит `system_bot` **ИЛИ** `email` заканчивается на `-bot@…` / `bot@…`). Отдельный `/api/v4/bots` не запрашиваем. (§3.1, §5 п.4)
2. **`mattermost_id`** — **не писать** ни в `contacts.enc` (схема), ни в `sources.loop`. Связка — по `email`/`login`. (§4, §9)
3. **Дедупликация** — по `login = email.split('@')[0].lower()`, как в `MoveFromZulip`. Совпадение login → тот же контакт, `update_contact`. (§3.4, §5 п.6)
4. **Порядок ФИО** — `«Фамилия Имя»` (`last_name + ' ' + first_name`), как в `MoveFromZulip`. (§4)
5. **Пустые поля** — общее правило «**только дополнять, не перезатирать**». Пустой `position` не пишется; поле, уже заполненное другим коннектором, не трогается. (§4, §5 п.6)
6. **Retry** — 3 попытки, back-off `1s / 3s / 9s` на 5xx и таймауты/ConnectionError; 4xx (кроме 429) — сразу fail. (§5 п.7)
7. **Пауза между страницами** — `sleep(0.1)` между запросами пагинации. (§3.1, §5 п.3)

## §12 Критерии успеха (v0.2)

- [ ] Прогон на живом Loop проходит с exit 0.
- [ ] В `contacts.enc` появляются записи с `sources.loop` у активных пользователей.
- [ ] Боты (по эвристике §5 п.4) и деактивированные пользователи не попадают в `contacts.enc`.
- [ ] `login` формируется из email, дедуп с `MoveFromZulip` работает (нет дублей у сотрудников, пришедших из обоих источников).
- [ ] Ни в одной записи нет `mattermost_id` (ни в top-level, ни в `sources.loop`).
- [ ] Порядок ФИО — «Фамилия Имя».
- [ ] Пустые значения из Loop не перезатирают существующие поля.
- [ ] Повторный прогон не даёт diff, кроме `sources.loop.synced_at`.
- [ ] `CUSTOM_FIELDS` побайтово идентичны до и после прогона.
- [ ] Тесты `tests/` — зелёные (в т.ч. кейсы 11 и 12).
- [ ] Крон-запись добавлена, лог первого воскресного прогона чистый.

---

## История доработок

- **2026-07-23** — первый черновик (Opus). API проверен из VM: `/users/me` и `/users?per_page=5` отвечают 200, поля подтверждены. Открыты 7 вопросов Саше (§11).
- **2026-07-23** — v0.2.0 (Opus, по брифу Саши). Все 7 открытых вопросов закрыты: детект ботов — эвристика без `/api/v4/bots`; `mattermost_id` не пишется; дедуп по `login` из email; ФИО «Фамилия Имя»; правило «дополнять, не перезатирать» пустыми; retry 1/3/9s на 5xx; пауза 0.1s между страницами. Решения интегрированы в §3–§5, §11 переоформлен как «Решения брифа».
- **2026-07-23** — v0.3.0 (Opus). Добавлена секция «Планируемая доработка: мониторинг сообщений Loop — итерация 1» (§A–§J): два режима (часовой дайджест 8–20 пн-пт + срочный каждые 3 мин 24/7), YAML-конфиг `loop_rules.yaml` с управлением через Сирень, watermark-дедупликация, доставка в топик Messages группы «Сирень Workspace» (-1004300127777). v1-синк контактов не затронут.
- **2026-07-24** — v0.4.0 (Opus). §J переоформлен из «Открытых вопросов» в «Решения брифа §J (24.07.2026)»: закрыты J1 (thread_id=6556, chat_id=-1004300127777, подтверждён тестом), J3 (Hermes deliver, `no_agent: true`, токены=0), J4 (fail-loud при отсутствии username в contacts.enc). J2 (формат ссылки Loop) остаётся единственным открытым — уточнить при реализации. Добавлена секция «Планируемая доработка: архивация переписки Loop — итерация 1.5» (§AA–§AI): ежедневное саммари через Haiku в 20:00 пн–пт, сохранение в `WorkVault/Entities/<slug>/Messages/YYYY-MM-DD.md`, конфиг `archive_channels` в `loop_rules.yaml`, управление через Сирень, скилл саммари вынесен в отдельную итерацию.
- **2026-09-08** — v0.4.5. ContractAssistant не подключать в `mfl_*` (см. Границы).
- **2026-09-18** — v0.4.6. Чёрный список Loop: `blacklist_users` + `blacklist_channels` в `loop_rules.yaml`; дайджест режется всегда; срочный allowlist сильнее blacklist (вариант 3). ТЗ зафиксировано, реализация ждёт «берём в работу». См. §14.
- **2026-10-11** — v0.4.7 (BUGFIX-LIGHT, `DEV/mfl-exchange-lxml`). Крон `f61b26cbbdf5` исполнял `mfl_urgent_check.py` на Python 3.14.7 управляемого venv Hermes, а Exchange-блок хардкодил `site-packages` python3.11 → `No module named 'lxml.etree'` (ErrorBus id 1825). Канон фикса — §15. Код этой фазой не пишется (`HF:impl`).
- **2026-10-12** — v0.4.8 (`DEV/mfl-digest-lxml`). Тот же ABI-разрыв на дайджесте: крон `2865cc674493` гоняет `mfl_digest.py` напрямую на Python 3.14.5, хардкод `python3.11` на строке 73 → ErrorBus id **1828**. Leftover §15 закрывается §16 (паритет urgent: обёртка + `sysconfig.purelib` + правка reference, который учил гибрид). Код этой фазой не пишется (`HF:impl`). `TZ:finalize` 12.10: §16 зафиксирована, версия не бампилась.
- **2026-10-16** — v0.4.9 (`DEV/mfl-urgent-channels`). Секция `urgent_channels` в `loop_rules.yaml`: все посты указанных каналов и их подтопиков доставляются срочными в `mfl_urgent_check` независимо от автора. Дедуп — общий `seen_ids`. См. §17. `TZ:finalize` 16.10: §17 зафиксирована, версия не бампилась.

---

## Планируемая доработка: мониторинг сообщений Loop — итерация 1 (2026-07-23)

### §A Цель

Автоматически отслеживать сообщения в Loop (Mattermost) и доставлять релевантные — по правилам из `loop_rules.yaml` и списку срочных контактов — в топик «Messages» Telegram-группы «Сирень Workspace», чтобы Саша не читал Loop вручную.

### §B Два режима работы

**Режим 1 — Дайджест (раз в час, 8:00–20:00 пн-пт):**
- Собирает сообщения за последние 2 часа по правилам из `loop_rules.yaml`.
- Источники: отслеживаемые каналы (`watch_channels`) + ключевые слова (`keywords`, регистронезависимо).
- Дедупликация по `message_id` через watermark в state-файле.
- **Дедупликация срочный↔дайджест:** срочный режим помечает отправленные посты через `mark_seen(ids)` (TTL 48ч). Дайджест проверяет `is_seen(id)` перед включением поста — пост от urgent-контакта не войдёт в дайджест повторно. Реализовано в `state.py`.
- Если новых сообщений нет → не слать ничего (SILENT).
- Доставка: топик Messages в «Сирень Workspace» (`-1004300127777`).
- Вне рабочих часов и в выходные дайджест не запускается (крон покрывает только 8–20 пн-пт).

**Режим 2 — Срочный (каждые 2–3 минуты, круглосуточно):**
- Проверяет: все DM Саши + все чаты, где он состоит.
- Триггер срочности — сообщение от контакта из `urgent_contacts` **И** выполнено любое из:
  - это DM от него,
  - в нём есть `@tkachenkoav`,
  - в нём есть `@all` в чате, где Саша состоит,
  - это ответ (`root_id`) на сообщение Саши.
- Доставка: тот же топик Messages, немедленно, без группировки.
- Работает всегда — рабочие часы игнорируются.

### §C Конфигурация (`loop_rules.yaml`)

Расположение: `USERTOOLS/MoveFromLoop/loop_rules.yaml` (рядом с `.env`). Формат:

```yaml
# Каналы для дайджеста (имя канала или channel_id)
watch_channels:
  - general
  - pm-team

# Ключевые слова (регистронезависимо)
keywords:
  - ML-платформа
  - Trisigma
  - AB-тест

# Срочные контакты (username в Loop)
urgent_contacts:
  - akalov
  - krivorotov

# Мой username в Loop
my_username: tkachenkoav
```

Управление через Сирень (текстовые команды в чате, без ручного редактирования файла):
- «добавь канал #devops» → добавить в `watch_channels`.
- «следи за словом "релиз"» → добавить в `keywords`.
- «покажи правила» → вывести текущий `loop_rules.yaml` в чат.
- «добавь Аралова в срочные» → Сирень резолвит username через `contacts.enc` (поле `sources.loop.username`) и добавляет в `urgent_contacts`.
- «убери канал X» / «убери слово X» / «убери из срочных X» — симметрично.

Изменения `loop_rules.yaml` подхватываются на следующем запуске крона (перечитывается при каждом запуске, кэша нет).

### §D Алгоритм (детально)

**Дайджест (`digest.py`):**
1. Прочитать `loop_rules.yaml` и `state/watermark.json` (`{last_ts, seen_ids: [...]}`; при отсутствии — `last_ts = now - 2h`, `seen_ids = []`).
2. Для каждого канала из `watch_channels` (если задано имя — сначала резолвить в `channel_id` через `GET /api/v4/teams/{team_id}/channels/name/{name}`): `GET /api/v4/channels/{id}/posts?since={watermark_ts_ms}`.
3. Фильтр сообщения (OR по условиям):
   - текст содержит хотя бы одно ключевое слово из `keywords` (регистронезависимо),
   - автор в `urgent_contacts`,
   - упомянут `@{my_username}`,
   - упомянут `@all`.
4. Дедупликация по `message_id` (пост `id`) — если id уже в `seen_ids`, пропустить.
5. Сортировка хронологически по `create_at`.
6. Форматирование сообщения (см. §формат): первая непустая строка текста + ссылка + `в #<канал> от @<автор>`.
7. Если итоговый список пуст → SILENT (не отправлять ничего). Иначе → отправить одним постом в топик Messages.
8. Обновить `watermark.json`: `last_ts = max(create_at обработанных)`, `seen_ids` дополнить новыми id; удалить из `seen_ids` записи старше 48 часов (TTL).

**Срочный (`urgent_check.py`):**
1. Прочитать `loop_rules.yaml` и `state/urgent_watermark.json` (отдельный state от дайджеста, чтобы не гонять его вперёд на 2 ч).
2. Получить список каналов Саши: `GET /api/v4/users/me/channels` (для всех команд, где он состоит) — фильтр по `type`:
   - `type=D` — DM,
   - `type in {O, P}` — публичные/приватные каналы.
3. Для каждого канала: `GET /api/v4/channels/{id}/posts?since={urgent_watermark_ms}`.
4. Проверка сообщения (по правилам срочности из §B, режим 2). Для проверки «ответ на сообщение Саши» — если `root_id` не пуст, получить `GET /api/v4/posts/{root_id}` и сверить `user_id` с id Саши (закэшировать `me.id` в state).
5. Дедуп через `seen_urgent_ids` в том же state-файле (TTL 24 ч — короче, потому что срочные должны отрабатывать один раз).
6. Каждое найденное сообщение → сразу отдельным сообщением в топик Messages (без группировки, префикс «🔴 СРОЧНО»).
7. Если ничего не найдено → SILENT.
8. Обновить `urgent_watermark.json`.

**Формат сообщения (общий для обоих режимов):**
```
<первая непустая строка текста, обрезать до ~200 символов>
🔗 <ссылка на сообщение или '—' если не удалось>
в #<канал> от @<автор>
```
Для срочных — префикс `🔴 СРОЧНО` первой строкой.

### §E Файловая структура (дополнение к v1)

```
USERTOOLS/MoveFromLoop/
  loop_rules.yaml          # конфиг правил (редактируется через Сирень)
  movefromloop/
    monitor.py             # общий модуль: клиент Loop, чтение rules, фильтры
    urgent.py              # логика срочного режима
    formatter.py           # форматирование сообщений для TG
    delivery.py            # отправка в Telegram топик Messages
  state/
    watermark.json         # {last_ts, seen_ids: [...]} — дайджест
    urgent_watermark.json  # {last_ts, seen_urgent_ids: [...], my_id} — срочный
  scripts/
    digest.py              # точка входа дайджеста
    urgent_check.py        # точка входа срочного режима
```

Существующая структура v1 (`sync.py`, `sync_contacts.py` и т.д. — §6 основного ТЗ) сохраняется без изменений.

### §F Кроны

**Дайджест:**
- Schedule: `0 8-20 * * 1-5` — каждый час 8:00–20:00 пн-пт.
- Script: `scripts/digest.py`.
- Deliver: `telegram:-1004300127777:<thread_id_Messages>`.
- Model: **Haiku** (нужен LLM для аккуратного форматирования / резюме, `no_agent=false`).

**Срочный:**
- Schedule: `*/3 * * * *` — каждые 3 минуты, круглосуточно.
- Script: `scripts/urgent_check.py`.
- Deliver: `telegram:-1004300127777:<thread_id_Messages>`.
- `no_agent: true` — скрипт сам формирует финальный текст, LLM не требуется.

### §G Связи с экосистемой

- **Читает:** Loop API v4 (`https://loop.tutu.ru`) — Bearer token из `.env` (тот же `LOOP_TOKEN`, что для v1).
- **Пишет:** Telegram топик Messages группы «Сирень Workspace» через Hermes deliver.
- **Использует:** `contacts.enc` — Сирень резолвит username по ФИО при команде «добавь X в срочные» (чтение через `AnywhereContacts`, без записи).
- **Зависит от:** `loop_rules.yaml` (конфиг), `state/watermark.json`, `state/urgent_watermark.json`.
- **Параллельно:** MoveFromLoop v1 (синк контактов, крон вс 03:30) — полностью независим, общего state нет, `.env` общий.

### §H Что НЕ входит в итерацию 1

- Ответы на сообщения Loop из Telegram (bi-directional) — итерация 2.
- Чтение вложений/файлов Mattermost.
- Поиск по истории (search API) — только новые сообщения через `since=`.
- Мобильные push-уведомления Loop — не трогаем.
- Реакции (emoji) и редактирования постов.

### §I Тест-кейсы

1. Аралов пишет DM Саше → срочное сообщение в Messages в течение 3 минут.
2. Аралов пишет `@all` в `#general` (Саша состоит) → срочное сообщение.
3. Сообщение в `#pm-team` содержит «ML-платформа» → попадает в ближайший часовой дайджест.
4. Час прошёл, новых сообщений по правилам нет → дайджест SILENT, в Telegram ничего.
5. Аралов пишет в канале без ключевых слов и без тегов → в дайджест не попадает; срочный триггер тоже не срабатывает (нет @tkachenkoav, @all, ответа Саше, и это не DM).
6. Одно и то же сообщение попадает под два правила (ключевое слово + автор в urgent) → в дайджесте только один раз (дедуп по id).
7. Крон перезапустился с ошибкой сети, watermark не обновился → на следующем запуске сообщения не задублируются (проверка `seen_ids`).
8. Команда «покажи правила» → Сирень выводит содержимое `loop_rules.yaml` в чат.
9. Команда «добавь Аралова в срочные» → в файле появляется `akalov` (резолв через contacts.enc), файл валидный YAML.
10. Суббота 15:00 — крон дайджеста не запускается; крон срочного — работает.

### §J Решения брифа §J (24.07.2026)

1. **J1 — Топик Messages в Telegram:** ✅ зафиксирован. `chat_id = -1004300127777`, `thread_id = 6556`. Топик создан вручную, подтверждён тестовым сообщением 24.07.2026. Значения прописать в конфигах кронов дайджеста и срочного режима.
2. **J2 — Формат ссылки на сообщение Loop:** ✅ **закрыт 24.07.2026**. Реальный формат подтверждён на живом посте: `https://loop.tutu.ru/{team}/pl/{post_id}` (пример: `https://loop.tutu.ru/tutu/pl/hpu6jmh7w7g8m8ht1hcy8xuuqw`). Команда `tutu`, `pl/{post_id}` — прямая ссылка на пост. Использовать в `formatter.py`.
3. **J3 — Доставка срочных:** ✅ через Hermes deliver, `no_agent: true`. Скрипт `urgent_check.py` сам формирует финальный текст сообщения, LLM в цепочке не вызывается, расход токенов = 0. Единообразие с дайджестом по инфраструктуре, задержка < 30 сек считается приемлемой.
4. **J4 — Резолв username для срочных:** ✅ fail-loud. Если запрошенного контакта нет в `contacts.enc` (нет `sources.loop.username`) — команда «добавь X в срочные» не добавляет запись, а возвращает ошибку в лог и сообщение в Telegram-чат Сирени с подсказкой сначала запустить синк контактов (`MoveFromLoop` v1). Мониторинг с несогласованным `urgent_contacts` не запускается.

---

## Планируемая доработка: архивация переписки Loop — итерация 1.5 (2026-07-24)

### §AA Цель

Ежедневное саммари переписки по подключённым каналам Loop через Haiku — сохранение в `WorkVault/Entities/<slug>/Messages/YYYY-MM-DD.md`. Не заменяет мониторинг (итерация 1), а дополняет его: мониторинг — про «что мне читать сейчас», архивация — про «что было в канале за день, для истории и последующего поиска».

### §AB Принципы

- Не архивируем сырые сообщения — только саммари через Haiku (компактно, без утечки всего сырого потока в WorkVault).
- Один файл на день на канал (`Messages/YYYY-MM-DD.md`).
- Если за день не было сообщений в канале → файл **не создаётся** (пустых заглушек нет).
- Скилл саммари (промпт Haiku) — **отдельная итерация**, оттачивается независимо. В этой итерации промпт — заглушка/MVP.
- Матчинг «канал Loop → сущность WorkVault» — через Сирень командой в чате («подключи #канал к Trisigma»), а не редактированием YAML руками.

### §AC Содержание саммари

Haiku извлекает из переписки за день по каналу четыре блока:

- **Что обсуждали** — темы, ключевые треды.
- **Проблемы** — что не работает, кто где застрял.
- **Риски** — что может стрельнуть, оценки сроков.
- **Решения** — что решили, что закоммитили, action items.

Финальный формат Markdown-файла — задача отдельного скилла (см. §AH).

### §AD Конфигурация (дополнение к `loop_rules.yaml`)

К существующему `loop_rules.yaml` (см. §C) добавляется секция:

```yaml
# Каналы для архивации (канал → slug сущности)
archive_channels:
  pm-team: trisigma
  general-aid: adm
  # канал: slug
```

Управление через Сирень (текстовые команды, без ручной правки файла):

- «подключи канал #pm-team к Trisigma» → Сирень резолвит slug `trisigma` через `WorkVault/Entities/entities.json`, добавляет пару `pm-team: trisigma` в `archive_channels`.
- Если slug сущности не найден в `entities.json` → Сирень **спрашивает подтверждения** («сущности `trisigma` в реестре нет — создать?») и, только по явному ответу, эскалирует до создания.
- «отключи канал #pm-team» → удалить запись из `archive_channels`.
- «покажи архивацию» → вывести текущий `archive_channels` в чат.

### §AE Алгоритм

1. Раз в день в 20:00 пн-пт крон запускает `daily_archive.py`.
2. Для каждого `channel: slug` из `archive_channels`:
   - `GET /api/v4/channels/{id}/posts?since={начало_текущего_дня_ms}` — все посты за сегодня (00:00 локально → мс).
   - Если постов нет → пропустить канал, файл не создавать.
   - Собрать тексты постов (с автором и временем) в единый входной блок.
   - Передать блок в Haiku через промпт саммари (скилл `loop-channel-summary`, см. §AH).
   - Записать результат в `WorkVault/Entities/<slug>/Messages/YYYY-MM-DD.md` (перезаписывая, если файл за сегодня уже был — прогон повторяется идемпотентно).
3. Итоговый лог: `channels_processed=N, files_written=M, skipped_empty=K`.

### §AF Файловая структура (дополнение)

```
USERTOOLS/MoveFromLoop/
  movefromloop/
    archiver.py       # логика саммари по каналу (сборка постов за день, вызов summarizer, запись файла)
    summarizer.py     # промпт Haiku + вызов LLM (тонкая обёртка)
  scripts/
    daily_archive.py  # точка входа крона
  skills/
    loop-channel-summary/
      SKILL.md        # скилл саммари (промпт) — отдельная итерация
```

Существующая структура итераций 1 (мониторинг) и v1 (синк контактов) сохраняется без изменений.

### §AG Крон архивации

- Schedule: `0 20 * * 1-5` — 20:00 пн-пт.
- Script: `scripts/daily_archive.py`.
- Model: **Haiku** — LLM нужен для саммари.
- Deliver: `local` — результат прогона это файлы в `WorkVault/Entities/<slug>/Messages/`, отдельного сообщения в TG не требуется. В лог-канал Hermes уходит статистика прогона.
- `no_agent: false` — LLM участвует.

### §AH Что НЕ входит в итерацию 1.5

- Запрос саммари за произвольный период («покажи, что было в pm-team за неделю») из Telegram → **итерация 2**.
- Сохранение результата такого запроса в `Entities/<slug>/Messages/` → итерация 2.
- Собственно скилл саммари (`skills/loop-channel-summary/SKILL.md`) с оттачиванием промпта — **отдельная задача**, идёт параллельно. В 1.5 промпт — MVP-заглушка «сделай четыре раздела: что обсуждали / проблемы / риски / решения».
- Архивация вложений и файлов Mattermost.
- Индексация архива для поиска.

### §AI Связи с экосистемой

- **Читает:** Loop API v4 (`/api/v4/channels/{id}/posts?since=…`), тот же `LOOP_TOKEN` из `.env`.
- **Пишет:** `WorkVault/Entities/<slug>/Messages/YYYY-MM-DD.md`.
- **Использует:** Haiku LLM для саммари; `WorkVault/Entities/entities.json` — Сирень читает для резолва slug при команде «подключи канал».
- **Зависит от:** `loop_rules.yaml` (секция `archive_channels`), `entities.json` (резолв slug), готовой структуры `WorkVault/Entities/` (миграция `EntitiesMigration` выполнена 24.07.2026 — путь уже существует).
- **Параллельно с:** MoveFromLoop v1 (синк контактов), итерация 1 (мониторинг). Общий `.env` (`LOOP_TOKEN`), общий `loop_rules.yaml`, отдельный крон и state.

## Доработка: Exchange keyword-фильтрация — РЕАЛИЗОВАНО (2026-07-27)

**Проблема.** ExchangeMonitor фильтровал письма только по отправителю (`urgent_contacts` → email через ContactStore). Автоматические уведомления JIRA / систем от роботов-отправителей не проходили person-check и терялись, хотя содержали ключевые ссылки (например, тикеты `ADD-613444`) в теле письма.

**Решение.** Параллельный keyword-путь в срочном режиме: если тело письма содержит любую из фраз `exchange_urgent_keywords`, письмо считается срочным независимо от отправителя и без person-check.

### Изменения

- **`~/USERTOOLS/MoveFromLoop/loop_rules.yaml`** — добавлены секции:
  - `exchange_urgent_keywords:` со стартовым значением `https://hq.tutu.ru/browse/ADD-613444`
  - `exchange_digest_keywords:` (закомментирована, резерв)
- **`~/USERTOOLS/ExchangeMonitor/exchangemonitor/config.py`** (это фактический код Exchange-мониторинга; в задании назван как `movefromloop/rules.py` — уточнение в лог) — в `ExchangeRules` добавлены поля `urgent_keywords: List[str]`, `digest_keywords: List[str]`; в `load_rules()` — чтение `exchange_urgent_keywords` / `exchange_digest_keywords`.
- **`~/USERTOOLS/ExchangeMonitor/exchangemonitor/fetcher.py`** — в `.only(...)` добавлено поле `"body"` (HTML-only письма JIRA без него давали `text_body=None`).
- **`~/USERTOOLS/ExchangeMonitor/exchangemonitor/urgent.py`** —
  - keyword-путь параллельно контактам: `body = (item.text_body or "") + " " + str(getattr(item, "body", "") or "")`, `any(kw.lower() in body.lower() for kw in rules.urgent_keywords)`;
  - при keyword-совпадении не выполняется проверка `email in urgent_emails` и `is_real_person`;
  - `xs.is_seen(...)` работает по обоим путям — дублей с urgent_contacts не будет;
  - ранний return при пустом `urgent_emails` теперь пропускается, если `urgent_keywords` непустой.

Форматирование выхода — обычный urgent (`format_email` + OWA-ссылка), без отдельного тега.

## Доработка: Exchange-мониторинг inbox — РЕАЛИЗОВАНО (2026-07-27)

Пакет `movefromloop` расширен интеграцией с Exchange (EWS) — параллельная ветка к Loop-мониторингу, использующая тот же `State` (watermark + seen_ids) и общий формат Telegram-уведомления.

**Новые модули:**
- `movefromloop/exchange_client.py` — `make_account(password)`, 3 варианта username, `autodiscover=False`, `access_type=DELEGATE`.
- `movefromloop/exchange_fetcher.py` — `fetch_exchange_messages(account, since_dt, limit, folder)` с `is_read=False`, `.only(...)` (включая `message_class`), сортировка asc, лимит.
- `movefromloop/exchange_filter.py` — `should_skip(item)` = True для `IPM.Schedule.Meeting.Resp.Pos` (принятие встречи). Отклонения/tentative/counter — пересылаем как обычные письма.
- `movefromloop/exchange_formatter.py` — `compute_tag()` `(приватное)/(личное)/""`, `format_exchange_message()` в формате `📧 (тег) от {ФИО} [DD.MM HH:MM МСК]\n{тема — тело ≤150}\n🔗 OWA`.
- `movefromloop/exchange_urgent.py` — оркестратор: watermark `exchange_urgent_last_dt` (ISO), два параллельных пути (`urgent_contacts` по email/имени + `urgent_keywords` в теле+HTML), бизнес-правило `should_skip` для принятий встреч от срочных контактов, dedup через `state.is_seen/mark_seen`.

**Изменённые:**
- `movefromloop/rules.py` — поля `exchange_enabled/inbox_folder/urgent_limit/digest_limit/urgent_contacts/urgent_keywords/digest_keywords`. `exchange_urgent_contacts` наследует `urgent_contacts`, если не задан явно.
- `scripts/urgent_check.py` — читает `TUTU_DOMAIN_PASSWORD` из `~/.config/hermes/.env`, после Loop зовёт `run_exchange_urgent()`, объединяет блоки через `\n\n`.

**Тесты:** 102/102 базовых + 4 новых на `should_skip` (test_sync.py пропускается из-за отсутствия модуля `anywhere_contacts`, не относится к Exchange).

**Как проверить:**
```bash
source ~/USERTOOLS/MoveFromLoop/venv_linux/bin/activate
cd ~/USERTOOLS/MoveFromLoop && python3 scripts/urgent_check.py
```

## Багфикс v0.4.2 — Устойчивость к outage Loop API и корректная загрузка .env (2026-08-07)

### Проблема (root cause)

Крон «MoveFromLoop — срочные сообщения» (`mfl_urgent_check.py`) упал с `exit code 1`. Цепочка отказа:

1. Loop API (`loop.tutu.ru`) вернул `502 Bad Gateway` одновременно на всех эндпоинтах.
2. `LoopClient.users_by_usernames()` → 502 → исключение поймано `except Exception` в `urgency_checker.resolve_urgent_user_ids()` (строки ~70-71): резолв одного контакта не удался, но 5 остальных отдались из `state.user_cache` (TTL 24ч) → возвращённый `urgent_ids` непустой, выполнение продолжилось.
3. `fetch_mentions()` → `client.channel_members(team_id)` → 502 → **не поймано** нигде в цепочке (`mentions_fetcher.py:18`, вызывается из `urgent.py:51` без try/except) → `LoopApiError` пробрасывается до `mfl_urgent_check.py`, где ловится общим `except Exception` и приводит к `sys.exit(1)`.

Итог: единичный сбой инфраструктуры Loop (не Hermes, не MoveFromLoop) превратился в аварийное завершение крона с ненулевым кодом возврата вместо ожидаемого поведения «нет данных в этом прогоне — тихо подождать следующего».

Диагностика вскрыла ещё 8 смежных проблем в той же зоне ответственности (загрузка `.env`, устойчивость к сетевым отказам, консистентность `watermark.json`), которые не проявились сегодня, но создают риск таких же тихих потерь данных или гонок записи. Их устранение включено в этот же багфикс, т.к. правки затрагивают те же файлы и логически неразделимы с задачей «не падать на 5xx Loop API».

### Изменяемые файлы

1. `~/.hermes/scripts/mfl_urgent_check.py`
2. `~/.hermes/scripts/mfl_digest.py`
3. `~/USERTOOLS/MoveFromLoop/movefromloop/urgent.py`
4. `~/USERTOOLS/MoveFromLoop/movefromloop/digest.py`
5. `~/USERTOOLS/MoveFromLoop/movefromloop/state.py`
6. `~/USERTOOLS/MoveFromLoop/movefromloop/loop_api.py`
7. `~/USERTOOLS/ExchangeMonitor/exchangemonitor/config.py`

### Описание изменений

**1. `fetch_mentions()` без try/except (`urgent.py:51`, `digest.py:34`) — критично, сегодняшний баг.**
Обернуть вызов `fetch_mentions(client, rules.team_id, since_ms)` в `try/except LoopApiError` (и `requests.RequestException` на случай необёрнутых сетевых ошибок) в обоих оркестраторах. При отказе:
- залогировать `warning` в stderr (`[urgent] Loop API unavailable: {exc} — watermark not advanced`);
- **не двигать** watermark (см. п.4 — политика единая: полный отказ резолва/фетча = watermark замер);
- вернуть `None` (SILENT) без исключения, чтобы `mfl_urgent_check.py` / `mfl_digest.py` завершились с `exit 0`.
Блок ExchangeMonitor (уже в своём try/except в `mfl_*` скриптах) эту правку не затрагивает и продолжает пытаться отработать независимо.

**2. Загрузка `.env` из устаревшего пути.**
`mfl_urgent_check.py` и `mfl_digest.py` грузят только `~/.hermes/profiles/anthropic/.env`. Переменная `TUTU_DOMAIN_PASSWORD` (нужна `ExchangeMonitor.config.load_password()`) лежит только в `~/.config/hermes/.env`, который никогда не грузится → `RuntimeError` из `load_password()` гасится try/except в `mfl_*` (см. п.7) → Exchange-мониторинг тихо не работает при каждом прогоне.
Решение: в обоих скриптах после текущей загрузки `~/.hermes/profiles/anthropic/.env` добавить загрузку `~/.config/hermes/.env` через `load_dotenv(path, override=False)` (не перетирать уже загруженные значения при пересечении ключей). Порядок: сначала anthropic-профиль (текущее поведение), затем `~/.config/hermes/.env` — добавляет недостающие ключи, не ломает существующие.

**3. `CONTACTS_ENCRYPTION_KEY` / `CONTACTS_PATH` не заданы ни в одном загружаемом `.env`.**
Следствие п.2: `resolve_urgent_user_ids()` в `urgency_checker.py` получает `contacts_path=None` (из `os.environ.get("CONTACTS_PATH", "")` → пусто), проверка через `contacts.enc` в `_get_known_loop_usernames()` не выполняется — эффект: только менее информативные сообщения об ошибке в stderr, на резолв через API/кеш не влияет. Действие в рамках багфикса — **документирование**: если после добавления загрузки `~/.config/hermes/.env` (п.2) эти переменные там не появятся, зафиксировать факт отсутствия в комментарии кода `urgency_checker.py` (какая переменная ожидается, откуда должна браться) и в отчёте о реализации — без придумывания значения переменной за пользователя.

**4. Watermark при полном отказе резолва/фетча — не двигать.**
Текущее поведение — при пустом `urgent_ids` (`urgent.py:44-47`) watermark сдвигается вперёд (`state.set_urgent_watermark(now_ms())`) даже если причина пустоты — полный отказ API (протухший кеш **и** Loop недоступен), а не «нет срочных контактов в конфиге». Это тихая потеря срочных сообщений за окно outage.
Различить два случая:
- `rules.urgent_contacts` пуст (конфиг) → это не ошибка, watermark двигать, как сейчас.
- `rules.urgent_contacts` непуст, но `resolve_urgent_user_ids()` вернул пустой набор **из-за ошибки API** → не двигать watermark, `warning` в stderr, вернуть `None`.
Для различения `resolve_urgent_user_ids()` должен дать вызывающему коду сигнал «резолв не удался из-за API-ошибки» (например, поднять специфичное исключение `ResolutionFailedError` при `except Exception` на `client.users_by_usernames()`, вместо тихого возврата пустого `resolved`, если *ни один* username не резолвился ни из кеша, ни из API). Если хотя бы один контакт резолвился (частичный успех, как в сегодняшнем инциденте) — это не сбой, работать с тем, что есть (текущее поведение сохраняется).
То же правило применить к п.1 (`fetch_mentions` failure) — уже покрыто там.

**5. Race condition при записи `watermark.json`.**
`urgent` и `digest` кроны читают/пишут один файл `state/watermark.json` через `State.save()` (atomic replace, но без блокировки между читающим и пишущим процессом). При пересечении по времени поздний `save()` перезатирает `seen_ids`/watermark более раннего прогона, читавшего файл до его изменения → риск дублей в Telegram.
Добавить файловую блокировку в `state.py`:
- `State.load()` — `fcntl.flock(fd, LOCK_SH)` на время чтения.
- `State.save()` — `fcntl.flock(fd, LOCK_EX)` на отдельном lock-файле (`watermark.json.lock`, не на самом JSON, чтобы не мешать atomic replace) перед записью, снять после.
- Обе операции — неблокирующие первую попытку (`LOCK_NB`), при занятости — retry с интервалом до 10 секунд суммарно (например, 10 попыток по 1с).
- Если за 10 секунд блокировка не освободилась — `warning` в stderr (`[state] lock timeout, watermark not saved`), `save()` завершается **без записи файла** (не бросать исключение — вызывающий код уже прошёл свою бизнес-логику, потеря одной записи предпочтительнее падения крона).
- Формат самого `watermark.json` не меняется (см. «Что НЕ трогать»).

**6. `urgency_checker.py:80-81` — `except Exception` гасит любую ошибку API молча.**
Средний приоритет, не блокирует критичный фикс, но обосновывает п.4: чтобы вызывающий код (`urgent.py`) мог отличить «частичный успех» от «API упал для всех», `resolve_urgent_user_ids()` должен возвращать/пробрасывать информацию об ошибке, а не только пустой/непустой `Set[str]`. Реализация — на усмотрение исполнителя (доп. флаг в возвращаемом значении, либо исключение при полном отказе, см. п.4); текстовые сообщения в stderr, которые уже пишутся построчно, сохранить как есть.

**7. `run_urgent_exchange` / `run_exchange_urgent` в `mfl_*.py` молча гасят `RuntimeError`.**
`mfl_urgent_check.py` (строки ~34-38) и `mfl_digest.py` (аналогично) ловят `Exception` вокруг вызова ExchangeMonitor и просто присваивают `ex_block = ""` без логирования. Пользователь не узнаёт, что Exchange-мониторинг не отработал (например, из-за отсутствия `TUTU_DOMAIN_PASSWORD`, п.2).
Добавить `print(f"[{имя_скрипта}] Exchange FAIL: {exc}", file=sys.stderr)` **перед** `ex_block = ""` (сообщение уже частично есть в `urgent_check.py` — проверить и привести к единому виду в обоих файлах, добавить, если отсутствует в `mfl_digest.py`).

**8. `RETRY_BACKOFF = (1, 3, 9)` в `loop_api.py` — последний бэкофф не применяется.**
Низкий приоритет. В `_request()` (`loop_api.py:41-68`) на последней попытке (`attempt == len(RETRY_BACKOFF)`) код сразу поднимает исключение без `time.sleep(backoff)`, т.е. реальное окно retry ≈ 1с+3с = 4с вместо документированных ~13с (1+3+9). Не критично для сегодняшнего инцидента (502 держался дольше любого разумного окна retry), но вводит в заблуждение при чтении кода/логов.
Варианты решения (на выбор исполнителя, зафиксировать в отчёте о реализации):
- (a) убрать `9` из документации/докстринга, оставить фактическое поведение (окно ~4с) — минимальное изменение;
- (b) исправить логику, чтобы 9с реально применялись перед финальным падением (тогда реальное окно retry вырастет до ~13с — учитывать в частоте крона `*/3 * * * *`, чтобы retry одного прогона не пересекался со стартом следующего).
Рекомендация архитектора: (a), т.к. увеличение окна retry до 13с при частоте крона 3 минуты не даёт ощутимого выигрыша, а увеличивает риск наложения прогонов (усиливает актуальность п.5).

**9. Дубликаты `JIRA_TOKEN` в `~/.hermes/profiles/anthropic/.env`.**
Низкий приоритет, не относится к коду MoveFromLoop/ExchangeMonitor напрямую — файл `.env` вне зоны ответственности этих инструментов. Зафиксировать находку в отчёте о реализации; исправление (удаление дубликата) — по решению пользователя, не выполнять автоматически в рамках этого багфикса (внешний конфиг, см. «Что НЕ трогать»).

### Критерии успеха

- [ ] `mfl_urgent_check.py` при 502 (или любой 5xx после исчерпания retry) на любом Loop-эндпоинте: `exit 0`, `state/watermark.json` (поле `urgent_last_ts`) не изменился, в stderr есть `warning` с текстом ошибки.
- [ ] `mfl_digest.py` при тех же условиях: `exit 0`, `digest_last_ts` не изменился.
- [ ] Запуск без `TUTU_DOMAIN_PASSWORD` в окружении: `ExchangeMonitor`-блок пропущен (`ex_block=""`), в stderr — `warning` с упоминанием отсутствующей переменной, общий `exit 0` (если Loop-часть отработала штатно).
- [ ] `~/.config/hermes/.env` теперь загружается обоими `mfl_*.py`-скриптами (проверяется наличием `TUTU_DOMAIN_PASSWORD` в `os.environ` после импорта, без падения при отсутствии файла).
- [ ] Смоделированное пересечение `urgent`+`digest` (два параллельных вызова `State.save()` на один файл): второй процесс ждёт блокировку до 10с; если первый не освободил её — `warning` в stderr, файл **не перезаписан** (сравнить содержимое до/после — байт-в-байт идентично записи первого процесса).
- [ ] Частичный резолв срочных контактов (часть из кеша, часть — API-ошибка) не блокирует обработку — поведение как в сегодняшнем инциденте (это не баг, а ожидаемое поведение, регресс не допустить).
- [ ] Полный отказ резолва (0 контактов резолвлено, `urgent_contacts` в конфиге непустой) → watermark не двигается, отличимо от случая «`urgent_contacts` пуст в конфиге» (который watermark двигает, как раньше).
- [ ] `cd ~/USERTOOLS/MoveFromLoop && venv_linux/bin/python -m pytest -q` — все тесты зелёные (включая новые на пп. 1, 4, 5).
- [ ] `cd ~/USERTOOLS/ExchangeMonitor && <venv>/bin/python -m pytest -q` — все тесты зелёные.
- [ ] Формат `state/watermark.json` (набор ключей, типы) не изменился — diff схемы отсутствует.

### Что НЕ трогать

- `loop_rules.yaml` — конфиг правил, схема и текущие значения не меняются.
- Формат/схема `state/watermark.json` — меняется только *поведение* записи (блокировка, условия пропуска), не структура данных.
- Бизнес-логика `ExchangeMonitor` (`fetcher.py`, `person_checker.py`, `tagger.py`, `owa.py`, `urgent.py`/`digest.py` оркестраторы) — правки только в `config.py`, только в части загрузки `.env`/пароля.
- `movefromloop/channel_resolver.py`, `formatter.py`, `mapper.py`, `filters.py`, `keyword_checker.py`, `sync.py`, `__main__.py` — не участвуют в багфиксе.
- `~/.hermes/profiles/anthropic/.env`, `~/.config/hermes/.env` — содержимое (значения переменных) не редактируется; разрешено только чтение (загрузка) из второго файла в скриптах п.2. Дубликат `JIRA_TOKEN` (п.9) — только зафиксировать, не исправлять автоматически.
- Любой код вне 7 файлов, перечисленных в «Изменяемые файлы».
- Расписание кронов (`*/3 * * * *` и т.д.) — не меняется в рамках этого багфикса (см. п.8 — рекомендация против увеличения retry-окна именно чтобы не создавать давление на пересмотр расписания).

## Багфикс v0.4.3 — Принятие встреч от срочных контактов не фильтруется в фактическом Exchange-пути (2026-08-07)

### Проблема (root cause)

Крон «MoveFromLoop — срочные сообщения» (`mfl_urgent_check.py`) пересылает в Telegram письма-принятия встреч (`meeting accept`, EWS `message_class = "IPM.Schedule.Meeting.Resp.Pos"`) от контактов из `urgent_contacts`, хотя правило «принятие встречи → skip silently» уже сформулировано, реализовано и покрыто тестами — но в **другом, фактически не подключённом к крону модуле**.

Диагностика (по коду, не по ТЗ):

1. `mfl_urgent_check.py` вызывает Exchange-логику через `from exchangemonitor.urgent import run_urgent_exchange` — это единственный реально работающий Exchange-путь (пакет `~/USERTOOLS/ExchangeMonitor`, см. `ExchangeMonitor_TZ.md` §3.3, патч интеграции).
2. Модуль `movefromloop/exchange_urgent.py` (описанный в разделе «Доработка: Exchange-мониторинг inbox — РЕАЛИЗОВАНО» выше и упомянутый в `MAIN_TZ_INVENTORY.md` как «+ бизнес-правило `should_skip`») — **не вызывается entry-скриптом ни разу**. Это параллельная, полностью корректная реализация (`movefromloop/exchange_filter.py::should_skip()`, `MEETING_ACCEPT_CLASSES = {"IPM.Schedule.Meeting.Resp.Pos"}`, 4 зелёных теста в `tests/test_exchange.py`, поле `message_class` уже есть в `.only(...)` её собственного `exchange_fetcher.py`), но она — мёртвый код относительно реального крона.
3. Фактически работающий `exchangemonitor/urgent.py` (`_run_urgent()`) вообще не содержит понятия «принятие встречи»: цикл по письмам делает только keyword-match (`kw_hit`) и person-check по `urgent_emails`, без единой проверки `message_class`.
4. Его фетчер `exchangemonitor/fetcher.py::fetch_inbox_since()` не запрашивает поле `message_class` в `.only(...)` — даже если бы проверка появилась в `urgent.py`, `item.message_class` был бы всегда `None`, и любая проверка `mc in MEETING_ACCEPT_CLASSES` была бы всегда `False`.

Итог: `message_class` не включён в `.only(...)` фетчера (`exchangemonitor/fetcher.py`) → `item.message_class` всегда `None` → проверка на принятие встречи (которую предстоит добавить в `urgent.py`, реюзнув готовый `should_skip`) всегда даёт `False`. Проявление: 8 из 9 Telegram-уведомлений за 04.08–07.08 — принятия встреч, которые должны были быть отфильтрованы согласно уже согласованному и протестированному правилу.

### Изменяемые файлы

1. `~/USERTOOLS/ExchangeMonitor/exchangemonitor/fetcher.py` — добавить `"message_class"` в `.only(...)` внутри `fetch_inbox_since()`.
2. `~/USERTOOLS/ExchangeMonitor/exchangemonitor/urgent.py` — добавить импорт и вызов `should_skip(item)` (реюз из `movefromloop.exchange_filter`, модуль уже на `sys.path` — см. строки 10-15) в `_run_urgent()`, в ветке urgent-контакта (не keyword-пути).

### Описание изменений

**Реюз, а не дублирование.** `should_skip()` уже правильно реализован и протестирован в `movefromloop/exchange_filter.py` (не трогать, см. «Что НЕ трогать»). `exchangemonitor/urgent.py` уже добавляет `MoveFromLoop` в `sys.path` (строки 10-15) для импорта `movefromloop.state` — по той же схеме добавить `from movefromloop.exchange_filter import should_skip`.

Место вставки — ветка `if not kw_hit:` (после `is_real_person(...)`, до вычисления `fio`/форматирования): если письмо прошло person-check как urgent-контакт **и** `should_skip(item)` возвращает `True` → `continue`, письмо не добавляется в `lines`, но помечается `xs.mark_seen(state, item.id, ts_ms)` (иначе принятие будет заново проверяться на каждом тике до истечения TTL дедупа — не приводит к повторным уведомлениям, но не даёт state «остыть»).

Правило применяется **только** к urgent-контакт-пути, не к keyword-пути (`kw_hit`) — по аналогии с уже принятым и протестированным решением в `movefromloop/exchange_urgent.py:70` (`if is_urgent_sender and should_skip(msg)`). Обоснование: совпадение по ключевому слову в теле авто-письма о принятии встречи крайне маловероятно на практике, но если оно всё же случится — лучше переслать, чем тихо потерять потенциально релевантное совпадение.

### Критерии успеха

- [ ] `should_skip()` (импортированный из `movefromloop.exchange_filter`, без изменений в самой функции) корректно возвращает `True` для `message_class = "IPM.Schedule.Meeting.Resp.Pos"` в контексте `exchangemonitor/urgent.py` — регресс уже существующих тестов `test_exchange.py` не допустить.
- [ ] `exchangemonitor/fetcher.py::fetch_inbox_since()` запрашивает и возвращает элементы с непустым `message_class` (проверяется unit-тестом на мок-`QuerySet`/`SimpleNamespace`, без реального EWS).
- [ ] Принятия встреч (`IPM.Schedule.Meeting.Resp.Pos`) от контактов из `urgent_contacts` **не попадают** в Telegram-блок срочных Exchange-уведомлений.
- [ ] Отклонения (`IPM.Schedule.Meeting.Resp.Neg`), тентативные (`IPM.Schedule.Meeting.Resp.Tent`) и контр-предложения (`IPM.Schedule.Meeting.Counter`) встреч от срочных контактов — **проходят** как обычные срочные письма (регресс не допустить).
- [ ] Обычные письма (`IPM.Note`) от срочных контактов и keyword-путь (`kw_hit`) — поведение не изменилось.
- [ ] `cd ~/USERTOOLS/ExchangeMonitor && <venv>/bin/python -m pytest -q` — все тесты зелёные, включая новые тест-кейсы на `should_skip` внутри `urgent.py` (мок-письмо с `message_class="IPM.Schedule.Meeting.Resp.Pos"` и контрольные кейсы decline/tentative/counter/note).
- [ ] `cd ~/USERTOOLS/MoveFromLoop && venv_linux/bin/python -m pytest -q` — все тесты зелёные, без регресса (`movefromloop/exchange_filter.py` и `tests/test_exchange.py` не менялись).

### Что НЕ трогать

- Бизнес-логику `should_skip()` в `movefromloop/exchange_filter.py` — она уже правильная и протестирована; только импортировать в `exchangemonitor/urgent.py`, не переопределять и не копировать её тело.
- Форматирование сообщений (`exchangemonitor/formatter.py`: `format_email`, `format_urgent_ex`, `format_digest_ex`) — правило работает на уровне фильтрации до форматирования, форматтер `message_class` не касается.
- Конфиг `loop_rules.yaml` и `exchangemonitor/config.py` (`ExchangeRules`, `load_rules`, `load_password`) — правило безусловное, не параметризуется.
- `movefromloop/exchange_urgent.py`, `exchange_fetcher.py`, `exchange_filter.py`, `exchange_formatter.py`, `exchange_client.py` — уже корректны, но не запускаются кроном; консолидация/удаление этого дохлого кода — отдельный техдолг, вне рамок этого багфикса (зафиксировать в отчёте о реализации).
- `exchangemonitor/person_checker.py`, `tagger.py`, `owa.py`, `digest.py`, `client.py` — не участвуют в этом багфиксе; правило касается только срочного пути (`urgent.py`), дайджест (`digest.py`) не покрыт этой задачей.
- `MAIN_TZ_INVENTORY.md` — запись о том, что «бизнес-правило `should_skip` реализовано» (внесена 2026-07-27) факту не соответствует применительно к реально работающему кроновому пути; исполнителю править её текст не нужно, актуализация — задача архитектора при обновлении инвентаря по этому багфиксу.
- Любые другие файлы, кроме 2, перечисленных в «Изменяемые файлы».

### История доработок

- **2026-08-07** — v0.4.2 (багфикс). Диагностика падения крона «MoveFromLoop — срочные сообщения» (502 Bad Gateway на Loop API, необработанный `fetch_mentions()` → `exit 1`). Устранение 9 сгруппированных проблем: необработанные исключения `fetch_mentions()` в `urgent.py`/`digest.py`; загрузка `~/.config/hermes/.env` для `TUTU_DOMAIN_PASSWORD`; политика «не двигать watermark при полном отказе API»; файловая блокировка `state.py` против гонки `urgent`↔`digest`; логирование гашения ошибок ExchangeMonitor; ревизия `RETRY_BACKOFF` в `loop_api.py`. Реализация — по отдельному «берём в работу».
- **2026-08-07** — v0.4.3 (багфикс). Диагностика: реально работающий Exchange-путь крона `mfl_urgent_check.py` — пакет `exchangemonitor` (`~/USERTOOLS/ExchangeMonitor`), а не `movefromloop/exchange_urgent.py`, где правило «принятие встречи → skip silently» уже правильно реализовано и протестировано, но не подключено к кронy. Исправление: `message_class` добавлен в `.only(...)` `exchangemonitor/fetcher.py`; в `exchangemonitor/urgent.py` добавлен реюз `should_skip()` из `movefromloop.exchange_filter` для urgent-контакт-пути. Зафиксирован техдолг — два параллельных Exchange-пути в экосистеме, консолидация не входит в этот багфикс. Реализация — по отдельному «берём в работу».

## §13. Доработка 02.09.2026 — bk-NEW: группировка по каналу + новый формат

### Задача
Полная переписка по каждому каналу Loop в хронологическом порядке за период. **НЕ** схлопывание. В дайджесте и срочных.

### Группировка (`formatter.py`)
- `group_posts_by_channel()` — по `channel_id`; внутри канала сортировка по `create_at` asc; каналы — по времени первого поста.
- `format_channel_block()` — заголовок `#channel`, лимит 10 постов + `…ещё K`.

### Формат карточки `format_post`
```
📅 {время}
от @{author}
{суть}
🔗 {link}
```
Канал **не** в карточке (только в заголовке секции).

### `digest.py` / `urgent.py`
Группировка по каналу, секции, без collapse. `mark_seen` / watermark по всем постам.

### Изменяемые файлы
| Файл | Что |
|---|---|
| `movefromloop/formatter.py` | `group_posts_by_channel`, `format_channel_block`, новый `format_post` |
| `movefromloop/digest.py` | Группировка по каналу, секции |
| `movefromloop/urgent.py` | Группировка по каналу, секции |
| `tests/test_formatter.py` | Группировка, лимит 10+K |
| `tests/test_urgent.py` | Секции по каналам в urgent |
| `tests/test_digest.py` | 3 поста DM не схлопываются |

### Тесты (инварианты)
- Посты одного канала — в одной секции, хронологически.
- Каналы упорядочены по первому посту.
- Лимит 10 + `…ещё K` при переполнении.
- 3 поста в DM — три отдельные карточки (без схлопывания).

### Верификация
```
cd /home/tkachenkoav/USERTOOLS/MoveFromLoop
python3 -m pytest -q
```
Итог реализации: **23 passed**.


---

## §14. Доработка 18.09.2026 — чёрный список Loop (вариант 3)

**Статус:** ТЗ зафиксировано (Саша, 18.09.2026). Реализация ждёт отдельного «берём в работу». Код в этой секции не описывается как уже сделанный.

**Цель.** Пользователи и/или чаты Loop, сообщения от которых неинтересны в принципе (в том числе DM), не попадают в часовой дайджест; срочные алерты при этом остаются первостепенными и пробивают чёрный список, если автор есть в `urgent_contacts`.

Расширяет §C (`loop_rules.yaml`) и оркестраторы итерации 1 (`digest.py` / `urgent.py`). Синк контактов v1, Exchange-контур и кроны не входят.

### 14.1 Решения брифа (закрыты 18.09.2026)

1. **Ключ идентификации** — в YAML хранить `username` (пользователь) и имя/`channel_id` (канал), как у `urgent_contacts` / `watch_channels`. На рантайме фильтровать по `user_id` / `channel_id`. Display-name («ДВИЖ-bot Туту», «AI-АналИтик») — **не ключ**, только lookup при добавлении.
2. **Приоритет — вариант 3.** Срочность сильнее чёрного списка. Дайджест чёрный список режет всегда.
3. **Два списка** с первого дня: `blacklist_users` и `blacklist_channels`.
4. **Ботов через `contacts.enc` не резолвить** (синк v1 их отфильтровывает). Lookup — Loop API.
5. **`user_id` в YAML и в `contacts.enc` не писать** (инвариант §4 / §9).

Открытых вопросов нет.

### 14.2 Модель данных

Секции в `~/USERTOOLS/MoveFromLoop/loop_rules.yaml` (единственный источник правды правил мониторинга):

```yaml
# Пользователи: username Loop (не display-name).
# Резолв → user_id как у urgent_contacts (state.user_cache TTL 24ч → POST /api/v4/users/usernames).
blacklist_users:
  - dvizhbot          # ДВИЖ-bot Туту
  - ai-analitik       # AI-АналИтик  (username — пример; перед первым add подтвердить lookup)

# Чаты целиком: имя без # либо channel_id 26 символов. Как watch_channels.
blacklist_channels: []
  # - noisy-bots
```

| Что хранить | Почему |
|---|---|
| **username** в YAML | Как `urgent_contacts`; читаемо; mattermost `id` в конфиг не пишем. |
| **`user_id` на рантайме** | Пост несёт `user_id`; username может смениться; display-name у ботов ≠ username и не уникален. |
| **Канал: name или 26-символьный id** | Как `watch_channels` + существующий `ChannelResolver.resolve_id()`. |

В датаклассе `Rules` (`movefromloop/rules.py`): поля `blacklist_users: List[str]`, `blacklist_channels: List[str]` (default `[]`). `load_rules` / `save_rules` пишут оба ключа **явно** (иначе мутаторы не сохранят). Round-trip ruamel чужие ключи (exchange-поля) не затирает.

Display-name с кавычками/юникодом в YAML как значение списка запрещён. В комментарии к username — можно. Два одинаковых display-name (два «ДВИЖ-bot Туту») — два разных username; add по подстроке запрещён.

### 14.3 Правило приоритета (вариант 3)

Срочность первостепенна. Дайджест чёрный список режет **всегда**.

| Кто / где | Дайджест | Срочный (🔴) |
|---|---|---|
| Только `blacklist_users` | вырезан | молчит (нет в `urgent_contacts`) |
| `urgent_contacts` **и** `blacklist_users` | вырезан | **уходит** |
| Пост в `blacklist_channels`, автор не urgent | вырезан | молчит (нет в allowlist) |
| Пост в `blacklist_channels`, автор ∈ `urgent_contacts` | вырезан | **пробивается** |
| Keyword-hit от blacklist-user | вырезан | не относится (urgent не смотрит keywords) |
| Только `my_username` | как сейчас, отдельный skip | как сейчас |

Формула:

- **Digest:** `user_id ∈ blacklist_user_ids` ∨ `channel_id ∈ blacklist_channel_ids` → drop. Присутствие автора в `urgent_contacts` **не** спасает дайджест.
- **Urgent:** drop по чёрному списку **только если** `user_id ∉ urgent_user_ids`. Автор из allowlist не глушится ни как пользователь, ни из‑за чёрного канала.

Следствие: дайджест **не страховка**, если срочный крон не доставил пост человека, который одновременно в обоих списках. Это сознательный выбор варианта 3.

При `add_blacklist_user`, если username уже в `urgent_contacts`: предупредить («дайджест отрежет, 🔴 останется»), из urgent **не удалять**. Списки ортогональны.

DM бота, которого нет в `urgent_contacts`: полностью молчит (дайджест режет; срочный и так не берёт). Это целевой кейс названных ботов.

### 14.4 Точки фильтрации

Сейчас дайджест мержит mentions (`mention_count > 0`, это и есть DM) и watched+keywords; автора режет только `my_username` на этапе форматирования. Urgent — allowlist `user_id ∈ urgent_user_ids`. Чёрного списка нет.

Чистый предикат:

```python
def is_blacklisted(post, user_ids: set[str], channel_ids: set[str]) -> bool:
    uid = post.get("user_id") or ""
    cid = post.get("channel_id") or ""
    return (uid and uid in user_ids) or (cid and cid in channel_ids)
```

Политика варианта 3 (оркестраторы вызывают только её, не голый `is_blacklisted` на urgent-пути):

```python
def should_drop_by_blacklist(
    post, *, bl_user_ids, bl_channel_ids, urgent_user_ids, mode: "digest" | "urgent",
) -> bool:
    if mode == "urgent" and (post.get("user_id") or "") in urgent_user_ids:
        return False
    return is_blacklisted(post, bl_user_ids, bl_channel_ids)
```

На текущем `urgent.py` после `is_urgent` все посты уже от `urgent_user_ids`, поэтому `mode="urgent"` для них всегда False (и для user-, и для channel-blacklist). Вызов всё равно обязателен: явно фиксирует правило и не даёт съесть 🔴 в чёрном канале, если urgent когда-нибудь расширят.

**Дайджест (`digest.py`):** после merge/dedup/`is_seen`, **до** проверки «пусто» и **до** форматирования.

```
fetch mentions
fetch watched + keywords
merge + dedup + is_seen
★ resolve blacklist_users → bl_user_ids   (reuse resolve_urgent_user_ids; contacts.enc=None)
★ resolve blacklist_channels → bl_channel_ids  (ChannelResolver.resolve_id)
★ drop if should_drop(..., mode="digest")   # urgent_user_ids дайджест не спасают
if empty → watermark + SILENT
resolve authors → format (my_username как сейчас)
```

Так режутся **оба ведра** (mentions/DM и keyword/watched). Не резать только в цикле `format_post`: при пустом `users_map` автор становится `"unknown"` и username-фильтр молча пропускает.

**Срочный (`urgent.py`):** после `is_urgent ∧ not seen` вызвать `should_drop(..., mode="urgent")`. Не вызывать голый `is_blacklisted` до exemption.

Резолв username→id: существующий `resolve_urgent_user_ids` (кэш `state.user_cache` → `POST /api/v4/users/usernames`). Нерезолвнутый username: **fail-open** (пост не режется) + stderr. Канал, который не резолвится: stderr, эта запись списка не действует в этом прогоне.

Watermark дайджеста: окно из одних чёрных постов → пусто → watermark едет, SILENT. Urgent watermark свой, не зависит.

Фильтр — по **id поста автора/канала**, не по display-name и не по строке `author` после `users_by_ids`.

### 14.5 CLI и управление

`python -m movefromloop` не расширять (это синк контактов, требует `LOOP_TOKEN` + `CONTACTS_ENCRYPTION_KEY`).

Мутаторы в `movefromloop/rules.py` (идемпотентны, как `add_urgent` / `remove_urgent`):

- `add_blacklist_user(path, username)` / `remove_blacklist_user(path, username)`
- `add_blacklist_channel(path, channel)` / `remove_blacklist_channel(path, channel)`

`add-user` принимает только `[A-Za-z0-9._-]+` (как `alekseeva.ym`). Иначе отказ.

Опциональный тонкий CLI (не блокирует v1, рекомендуется для lookup ботов):

```
python -m movefromloop.rules_cli blacklist list
python -m movefromloop.rules_cli blacklist add-user <username>
python -m movefromloop.rules_cli blacklist remove-user <username>
python -m movefromloop.rules_cli blacklist add-channel <name-or-id>
python -m movefromloop.rules_cli blacklist remove-channel <name-or-id>
python -m movefromloop.rules_cli blacklist lookup "<term>"
```

`lookup` — единственная команда с Loop API (`POST /api/v4/users/search`, при необходимости `GET /api/v4/bots`): печать `username | first_name | last_name | is_bot | id`. В YAML не пишет. Аргумент с пробелом/кириллицей/кавычками = display-name → только lookup, не add. Если кандидатов > 1 — не добавлять молча.

Команды Сирени (дополнение к §C; ботов **не** резолвить через `contacts.enc`, в отличие от «добавь X в срочные» / §J4):

- «добавь в чёрный список ДВИЖ-bot Туту» → lookup → 1 кандидат: add username; >1: спросить.
- «убери из чёрного списка X»
- «покажи чёрный список»

Крон перечитывает YAML каждый запуск, рестарт не нужен. Новых кронов нет.

### 14.6 Изменяемые файлы (план реализации)

| Файл | Что |
|---|---|
| `loop_rules.yaml` | секции + комментарии |
| `movefromloop/rules.py` | поля, load/save, 4 мутатора |
| `movefromloop/blacklist.py` | **новый:** `is_blacklisted`, `should_drop_by_blacklist` |
| `movefromloop/digest.py` | резолв + `should_drop(..., mode="digest")` после merge |
| `movefromloop/urgent.py` | `should_drop(..., mode="urgent")` после `is_urgent` |
| `tests/test_digest.py` | mentions + keywords режутся; urgent-автор вырезан из дайджеста; watermark при «всё чёрное» |
| `tests/test_urgent.py` | urgent∩blacklist → 🔴 есть; только blacklist → нет 🔴; чёрный канал + urgent-автор → 🔴 есть |
| `tests/test_blacklist.py` | **новый:** предикаты по режимам |
| `tests/test_rules.py` | **новый:** load/add/remove, идемпотентность |

По желанию, не в минимальный контур: `users_search` в `loop_api.py`, `rules_cli.py`, скилл `mfl-mfe-urgent-contacts` / README. `mentions_fetcher.py`, `formatter.py`, `urgency_checker.py` трогать не обязательно (`resolve_urgent_user_ids` переиспользовать как есть).

`my_username` с blacklist не сливать.

### 14.7 Тест-кейсы

1. Mention / DM от пользователя только в `blacklist_users` → нет в дайджесте; urgent молчит.
2. Keyword-hit от blacklist-user в watched-канале → drop в дайджесте (blacklist сильнее keywords).
3. Автор в `urgent_contacts` ∩ `blacklist_users` → дайджест drop, urgent **не** drop.
4. Канал в `blacklist_channels`, автор обычный → дайджест drop.
5. Канал в `blacklist_channels`, автор ∈ `urgent_contacts` → дайджест drop, urgent **пробивается**.
6. Не-чёрный пост в том же прогоне дайджеста остаётся.
7. Нерезолвнутый username → дайджест этот пост **не** режет (fail-open).
8. `should_drop(..., mode="urgent")` для `user_id ∈ urgent_user_ids` — всегда False, даже при совпадении канала.
9. `add_blacklist_user` дважды не дублирует строку.
10. Кавычки/юникод в **комментарии** YAML не ломают ruamel round-trip.

Верификация после реализации:

```
cd /home/tkachenkoav/USERTOOLS/MoveFromLoop
python3 -m pytest -q
```

### 14.8 Риски

| Риск | Mitigation |
|---|---|
| На urgent вызвать голый `is_blacklisted` | Съест 🔴 в чёрном канале. Только `should_drop(..., mode="urgent")`. Тесты 5 и 8 обязательны. |
| Дайджест не страхует urgent∩blacklist | Сознательный выбор варианта 3. |
| Смена username бота | В yaml старый ключ; кэш 24ч. Передобавить через lookup. |
| Display-name как ключ / два бота с одним именем | Запретить runtime-сравнение `first_name`; add только точный username после lookup. |
| `users_by_usernames` не находит бота | Fail-open: бот останется в дайджесте, не наоборот. |
| Ботов нет в `contacts.enc` | Ожидаемо; резолв только Loop API. |
| DM как канал `id1__id2` | В `blacklist_users`, не в `blacklist_channels`. |
| Watermark дайджеста после «всё чёрное» | Окно не вернётся, если потом убрать из списка. Для «навсегда» ок. |
| `save_rules` подменяет list-node | Inline-комментарии могут поехать (как у `add_urgent`). Допустимо; Сирень может править YAML руками. |

### 14.9 Связи с экосистемой

- **Читает:** `loop_rules.yaml` (новые ключи), Loop API v4 (`/users/usernames`; lookup — `/users/search` и опционально `/bots`), `state/watermark.json` (`user_cache`).
- **Пишет:** только `loop_rules.yaml` (мутаторы/CLI). Watermark — существующее поведение дайджеста/urgent. `contacts.enc` **не пишет** и для blacklist **не читает**.
- **Зависит от:** итерация 1 мониторинга (уже в проде). Не зависит от LoopChannelDigest (on-demand, другой жизненный цикл — `LoopChannelDigest_TZ.md`).
- **Параллельно:** ExchangeMonitor / `exchange_*` в пакете `movefromloop` — **не применяют** этот чёрный список (свои BOT_MARKERS).
- **Новых сущностей, кронов, `.env`-ключей нет.** Reuse существующего `resolve_urgent_user_ids` и `ChannelResolver`.

Нет новых внешних контрактов сверх уже описанных в «Контракты экосистемы»: потребитель по-прежнему `api_telegram` (топик Messages). Схема `watermark.json` не меняется.

### 14.10 Что НЕ трогать

- Синк контактов v1 (`sync.py`, `filters.py`, `mapper.py`, `__main__.py`, крон вс 03:30).
- Инвариант «не писать `mattermost_id`» (§4, §9).
- Exchange-контур (`movefromloop/exchange_*.py`, пакет `~/USERTOOLS/ExchangeMonitor`, jobs `mfl_*` в части Exchange).
- Расписание и job_id кронов `f61b26cbbdf5` / `2865cc674493`.
- ContractAssistant в `mfl_*` (Границы v0.4.5).
- `formatter.py` (формат карточки), `mentions_fetcher.py` (контракт fetch).
- LoopChannelDigest, архивация итерации 1.5.
- Содержимое `.env` / `contacts.enc`.
- Грязное дерево: текущие незакоммиченные правки `formatter.py` / `loop_rules.yaml` в эту фичу не смешивать.

### 14.11 Критерии успеха

- [ ] В `loop_rules.yaml` есть `blacklist_users` / `blacklist_channels`; пустые списки = поведение как до фичи.
- [ ] DM/mention от blacklist-only user не попадает в stdout `scripts/digest.py`.
- [ ] Тот же user, добавленный в `urgent_contacts`, даёт 🔴 в `scripts/urgent_check.py` (Loop-часть) и по-прежнему отсутствует в дайджесте.
- [ ] Пост urgent-контакта в `blacklist_channels` даёт 🔴 и не входит в дайджест.
- [ ] Keyword-совпадение от blacklist-user не входит в дайджест.
- [ ] Pytest в `~/USERTOOLS/MoveFromLoop` зелёный, включая кейсы 14.7.
- [ ] Кроны не менялись; новые job не созданы.

---

## §15. Багфикс v0.4.7 — ABI lxml: крон urgent vs venv_linux (2026-10-11)

Пакет `DEV/mfl-exchange-lxml` (BUGFIX-LIGHT). Карточка `TZ:patch` `t_1669df09`; план утверждён на `GATE:diagnose-review` (`t_2978a416`) по `_fix_plan_20261011.md` (`BUG:diagnose` `t_978ca85d`). Код на этой фазе **не** меняется — реализация `HF:impl`. Версия корпуса бампнута 0.4.6→0.4.7 во frontmatter этим `TZ:patch`; `TZ:finalize` пакета повторно не повышает, если frontmatter уже 0.4.7.

Источник фактов: `_fix_plan_20261011.md` (репродукция подтверждена). ErrorBus id **1825**, `dedup_key=ef15bf6a4d35e643`, `tool=MoveFromLoop`, `stage=exchange`, `severity=critical`, `status=open` (на `TZ:patch`: `count=123`, `first_seen=2026-10-11 12:06:45`).

### I1 / I2 (current → target)

**I1 (критический).** `current`: крон-джоб `f61b26cbbdf5` (`no_agent`, `script=mfl_urgent_check.py`, `*/3 * * * *`) исполняется интерпретатором управляемого venv Hermes — Python **3.14.7** (`cron/scheduler_script.py::_posix_cron_script_argv()` → `project_python(repo)`). Функция оборачивает только `.py` через `-c _POSIX_SCRIPT_BOOTSTRAP`; shebang `#!/usr/bin/env python3` не действует.  
`target`: тот же job исполняет `mfl_urgent_check.py` на `~/USERTOOLS/MoveFromLoop/venv_linux/bin/python3` (**3.11.13**), где ABI `lxml` совпадает. Выбран **вариант а** плана: wrapper `~/.hermes/scripts/mfl_urgent_check_cron.sh` + смена поля `script` у существующего job. Вариант б (re-exec в `main()`) **не** брать: импорт `movefromloop.urgent` уже на уровне модуля (до `main()`); паттерн экосистемы для чужого venv — `.sh` (`ofc_sync.sh`, `mofs_run_cron.sh`).

**I2.** `current`: `mfl_urgent_check.py:66-70` жёстко кладёт в `sys.path`  
`~/USERTOOLS/MoveFromLoop/venv_linux/lib/python3.11/site-packages`, где `lxml` — бинарь `etree.cpython-311-*.so` (lxml 6.1.1, exchangelib 5.6.0). Процесс на 3.14 → `ModuleNotFoundError: No module named 'lxml.etree'`.  
`target`: хардкода `python3.11` нет. Site-packages резолвятся от **активного** интерпретатора. Формула плана `Path(sys.executable).parent.parent / "site-packages"` для POSIX-venv **неверна** (`bin/python3` → корень venv, там нет `site-packages`). Канон: `sysconfig.get_path("purelib")` (stdlib), запасной —  
`Path(sys.executable).resolve().parent.parent / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"`.  
После П.1 этот путь уже на `sys.path` интерпретатора; вставка остаётся защитной, без литерала версии.

Почему сломалось 11.10.2026: `venv_linux` пересобран под 3.11.13 (~02:03), управляемые venv Hermes пересозданы на 3.14 (~15:06–17:41). Линии разошлись. Управляемый venv Hermes — исполнитель крона, не venv инструмента; `lxml`/`exchangelib` в нём нет. Гибрид «процесс 3.14 + site-packages 3.11» недопустим.

Ответ на вопрос диагноза «какой venv у ExchangeMonitor»: собственный venv инструмента — `~/USERTOOLS/MoveFromLoop/venv_linux` (проверено: import под `venv_linux/bin/python3` → `OK lxml 6.1.1`).

### Решение П.1…П.4 (реализация — HF:impl)

**П.1 — интерпретатор = venv_linux (вариант а).**  
Новый `~/.hermes/scripts/mfl_urgent_check_cron.sh`: `set -euo pipefail`; `exec`  
`~/USERTOOLS/MoveFromLoop/venv_linux/bin/python3 ~/.hermes/scripts/mfl_urgent_check.py "$@"`.  
В `~/.hermes/cron/jobs.json` у job `f61b26cbbdf5` поле `script` → `mfl_urgent_check_cron.sh`. Это правка **существующего** job, не новый крон и не «ставь кроны». `id`, `schedule` (`*/3 * * * *`), `no_agent`, `deliver` (`telegram:-1004300127777:6556`), `workdir`, `enabled` — без изменений. Gateway не рестартовать.

**П.2 — убрать хардкод чужого venv.**  
В Exchange-блоке `mfl_urgent_check.py` (строки 66–77): `_EXM` (путь пакета `~/USERTOOLS/ExchangeMonitor`) остаётся. `_EXM_VENV` с литералом `python3.11` заменить на резолв из I2. Импорт `exchangemonitor.urgent.run_urgent_exchange` и `except` → ErrorBus (`stage=exchange`, `--tool MoveFromLoop`, `--job-id f61b26cbbdf5`) не менять.

**П.3 — профилактика (не блокер, не пересборка Hermes).**  
Правило в комментарии wrapper: инструмент с собственным venv крон исполняет **через этот venv**; `project_python` управляемого venv Hermes не исполнитель таких `.py`. Пересоздавать `~/.hermes/installs/.../venv` и править `scheduler_script.py` **этим пакетом нельзя** (вне 3 файлов, ядро). Расхождение Hermes 3.14 vs tool 3.11 допустимо, пока wrapper изолирует процесс.

**П.4 — контрольный прогон и закрытие id 1825.**  
2–3 ручных прогона wrapper/`venv_linux/bin/python3 ~/.hermes/scripts/mfl_urgent_check.py` и 2–3 тика крона `f61b26cbbdf5`. В stderr нет `Exchange FAIL` / `No module named 'lxml.etree'`. `count` id 1825 не растёт после фикса. `status=resolved` — `error_bus_cli.py resolve 1825` **или** `auto_resolve_recovered` на следующем `reconcile` после успешного прогона job (ErrorBus §3.6; без `DELETE`). Бизнес-`deliver` `:6556` не меняется: при непустом stdout (Loop и/или Exchange) — доставка в Messages; SILENT при пустом — штатно. `README` / `diagnose_exchange.py` в пакет **не** входят (бюджет ≤3 файла).

### Затронутые файлы (только они в HF:impl)

| # | Файл | Что |
|---|---|---|
| 1 | `~/.hermes/scripts/mfl_urgent_check.py` | Exchange-блок 66–77: резолв site-packages (П.2) |
| 2 | `~/.hermes/cron/jobs.json` | у `f61b26cbbdf5` только поле `script` (П.1) |
| 3 | `~/.hermes/scripts/mfl_urgent_check_cron.sh` | **новый** wrapper, вариант а (П.1 + комментарий П.3) |

Объём = 3 файла, вне shared-модулей USERTOOLS. Факт для канона LIGHT, не команда skip фаз.

### IAC (план = `_fix_plan_20261011.md` / эта секция)

| IAC | path | verify | depends | covers |
|---|---|---|---|---|
| **IAC-01** | `mfl_urgent_check_cron.sh` + `jobs.json` (`f61b26cbbdf5.script`) | `bash ~/.hermes/scripts/mfl_urgent_check_cron.sh` запускает процесс, у которого `sys.executable` = `venv_linux/bin/python3` и `sys.version` начинается с `3.11.13`; в job `script=mfl_urgent_check_cron.sh`, `id`/`schedule`/`deliver` те же | — | П.1, AC-001 |
| **IAC-02** | `mfl_urgent_check.py` Exchange-блок | `rg -n 'python3\\.11' ~/.hermes/scripts/mfl_urgent_check.py` → 0; под `venv_linux/bin/python3` `import lxml.etree, exchangelib` без исключения | IAC-01 | П.2, AC-002, AC-003 |
| **IAC-03** | крон `f61b26cbbdf5` + ErrorBus 1825 | 2–3 ручных + 2–3 крон-прогона: stderr без `lxml.etree` / `Exchange FAIL`; `SELECT count,status,last_seen FROM errors WHERE id=1825` — `count` не растёт после первого успешного тика; `status=resolved` либо сразу, либо после reconcile | IAC-01, IAC-02 | П.4, AC-004, AC-005 |

Нет `depends: operator:` (класс S). Живой EWS и наличие срочных писем не обязательны: успех Exchange-блока = нет исключения импорта/ABI, не «обязательно непустой stdout».

### Критерии приёмки (AC)

Только этот пакет. Наблюдаемое поведение / артефакт. Класс S (поезд не ждёт Сашу).

### AC-001 — крон исполняет urgent на venv_linux 3.11.13

У job `f61b26cbbdf5` `script` = `mfl_urgent_check_cron.sh`. Wrapper делает `exec` `~/USERTOOLS/MoveFromLoop/venv_linux/bin/python3` → `~/.hermes/scripts/mfl_urgent_check.py`. Процесс прогона: `sys.version` начинается с `3.11.13`, `sys.executable` указывает в `venv_linux`. `id`, `schedule` `*/3 * * * *`, `no_agent=true`, `deliver=telegram:-1004300127777:6556` не изменены. Нового job нет.

### AC-002 — нет хардкода python3.11 site-packages

В `~/.hermes/scripts/mfl_urgent_check.py` нет литерала `python3.11` и нет абсолютного `.../lib/python3.11/site-packages`. Резолв — `sysconfig.get_path("purelib")` или запасной Path из I2. Путь пакета `~/USERTOOLS/ExchangeMonitor` в `sys.path` сохраняется.

### AC-003 — `lxml.etree` импортируется тем же интерпретатором, что крон

Команда  
`~/USERTOOLS/MoveFromLoop/venv_linux/bin/python3 -c "import lxml.etree, exchangelib; from exchangemonitor.urgent import run_urgent_exchange"`  
(с `sys.path`, как в скрипте) завершается кодом 0. Тот же import через wrapper — код 0. Нет `ModuleNotFoundError: No module named 'lxml.etree'`.

### AC-004 — ErrorBus id 1825 перестаёт расти и закрывается

После первого успешного прогона фикса: повторные тики `f61b26cbbdf5` не инкрементят `errors.count` у id 1825 и не создают новую строку с `dedup_key=ef15bf6a4d35e643` / message `ExchangeMonitor urgent failed` / detail с `lxml.etree`. `status` id 1825 = `resolved` (`error_bus_cli.py resolve 1825` или auto-resolve ErrorBus). История строки не `DELETE`.

### AC-005 — бизнес-доставка и Loop-путь живы

`deliver` job остаётся `telegram:-1004300127777:6556`. Loop-ветка `run_urgent` не менялась. Если Exchange-блок вернул текст — он в stdout (склейка `\n\n` как сейчас) и уходит в Messages; если срочных писем нет — SILENT, без `Exchange FAIL` в stderr. Техника ошибок по-прежнему через `report_error.sh` (ErrorBus Mode A), не через `deliver`.

### AC-006 — границы diff

Diff пакета содержит только 3 пути из таблицы выше. Нет правок `mfl_digest.py`, `scheduler_script.py`, `~/USERTOOLS/MoveFromLoop/**` (кроме чтения venv), `~/USERTOOLS/ExchangeMonitor/**`, `loop_rules.yaml`, `watermark.json`, ядра ErrorBus (`_db.py` и пр.), манифеста, `.env`. Gateway не рестартован. Управляемые venv Hermes не пересозданы.

### Что НЕ трогать

- `mfl_digest.py` и job `2865cc674493` — тот же хардкод `python3.11` (строки 70–75); **sibling-риск**, не этот пакет (ErrorBus 1825 = urgent). Отдельный багфикс.
- `~/hermes-agent/cron/scheduler_script.py`, `_posix_cron_script_argv`, `project_python` — ядро.
- Управляемые venv `~/.hermes/installs/**` — не пересобирать «для синхронизации с 3.11».
- Пакет `~/USERTOOLS/ExchangeMonitor` (`urgent.py`, `fetcher.py`, зависимости).
- Код `~/USERTOOLS/MoveFromLoop/movefromloop/**`, `loop_rules.yaml`, `state/watermark.json`.
- Расписание, `job_id`, `deliver`, `no_agent`, `workdir` у `f61b26cbbdf5`; весь job `2865cc674493`.
- Новый крон / «ставь кроны»; рестарт Gateway.
- ContractAssistant в `mfl_*` (Границы v0.4.5). Вырез v0.4.5 «job … не трогать» для этого пакета сужается до: не трогать кроме поля `script` у `f61b26cbbdf5`.
- §14 чёрный список Loop; синк контактов v1; архивация §AA–§AI.
- Схема `events.db`, `report_error.sh`, `instrumentation_registry.json` (режим `self` у `f61b26cbbdf5` остаётся).
- Содержимое `.env` / `contacts.enc`.
- `README` / `diagnose_exchange.py` (П.4 плана «при необходимости» — вне бюджета).

### Связи с экосистемой

- **Читает:** `venv_linux` MoveFromLoop (интерпретатор + site-packages); пакет `ExchangeMonitor` (import `run_urgent_exchange`); `loop_rules.yaml` / `state/watermark.json` — как сейчас.
- **Пишет:** поле `script` существующего job `f61b26cbbdf5`; stdout → Hermes `deliver` `:6556` (бизнес, ErrorBus §1 не трогает); при сбое Exchange — `report_error.sh` → ErrorBus (`tool=MoveFromLoop`, `stage=exchange`).
- **Зависит от:** ErrorBus Mode A (`instrumentation_registry.json` → `f61b26cbbdf5: self`); канон закрытия — ErrorBus §3.5 `resolve` / §3.6 `auto_resolve_recovered`.
- **Параллельно:** ExchangeMonitor (draft usertool, App:Outlook/Exchange); Loop-мониторинг итерации 1; digest-крон — не в пакете.
- **Не зависит от:** манифеста, `EcosystemConfig.yaml`, новых сущностей, новых `.env`-ключей.
- **Новых внешних контрактов нет.** Выход `text` → `api_telegram` (`:6556`) и `tool`/`message` → ErrorBus — без изменения схемы.

### Риски пакета

| Риск | Mitigation |
|---|---|
| Раннер начнёт оборачивать и `.sh` через `project_python` | Сейчас `_posix_cron_script_argv` только для `.py` (докстринг). Если обёртка внезапно пойдёт через 3.14 — IAC-01 красный; тогда отдельный баг ядра, не этот пакет. |
| `parent.parent / "site-packages"` из плана | Зафиксирован канон I2; не копировать формулу плана дословно. |
| Digest (`mfl_digest.py`) останется на 3.14+хардкод 3.11 | Сознательно вне LIGHT. Зафиксировать в отчёте `HF:impl` как leftover. |
| Пересборка Hermes venv «для П.3» | Запрещена. П.3 = изоляция через wrapper. |
| Пустой stdout примут за провал Exchange | Успех = нет ABI-исключения, не обязательное письмо. |
| `jobs.json` как файл ORCH | BUGFIX-LIGHT без `ORCH:shared-state`; оркестратор явно включил 1 поле существующего job в 3 файла `HF:impl`. Новый job / манифест — нет. |
| count 1825 уже 123 и растёт до impl | Базовая линия = `count` на момент первого успешного тика после фикса, не «вернуть к 90». |

Открытых вопросов Саше нет. Реализация не начинается этой фазой.

---

## §16. Багфикс v0.4.8 — ABI lxml: крон digest vs venv_linux (2026-10-12)

Пакет `DEV/mfl-digest-lxml`. Карточка `TZ:patch` `t_31bddadd`; план утверждён на `GATE:diagnose-review` по `_fix_plan` / body `BUG:diagnose` `t_d17bad47`. Код на этой фазе **не** меняется — реализация `HF:impl`. Версия корпуса бампнута 0.4.7→0.4.8 во frontmatter этим `TZ:patch`; `TZ:finalize` пакета повторно не повышает, если frontmatter уже 0.4.8.

Закрывает leftover §15: «`mfl_digest.py` и job `2865cc674493` — sibling-риск, не этот пакет». Тот же ABI-разрыв, тот же канон (обёртка + динамический purelib). Фикс urgent 20261011 до digest не доехал: не было ни (a) shell-обёртки, ни (b) замены хардкода `python3.11` на `sysconfig.get_path("purelib")`.

Источник фактов: план `BUG:diagnose` (репродукция подтверждена). ErrorBus id **1828**, `dedup_key=af5514e5180bbf39`, `tool=MoveFromLoop`, `stage=exchange`, `script=mfl_digest.py`, `status=open` (на диагнозе: `count=3`, `first_seen=2026-10-12 05:00:58`, `last_seen=2026-10-12 07:00:59`). Detail: `[digest] Exchange FAIL: No module named 'lxml.etree'`. Крон при этом `last_status=ok` (исключение ловится `mfl_digest.py:78-82`, `exit 0`) — `ok` **не** равен успеху Exchange-блока.

### I1 / I2 (current → target)

**I1 (критический).** `current`: крон-джоб `2865cc674493` (`no_agent=true`, `script=mfl_digest.py`, `0 8-20 * * 1-5`, `deliver=telegram:-1004300127777:6556`, `workdir=~/USERTOOLS/MoveFromLoop`) исполняется интерпретатором управляемого venv Hermes — Python **3.14.5** на репродукции 12.10 (`cron/scheduler_script.py::_posix_cron_script_argv()` → `project_python(repo)`). Функция оборачивает только `.py`; shebang `#!/usr/bin/env python3` не действует.  
`target`: тот же job исполняет `mfl_digest.py` на `~/USERTOOLS/MoveFromLoop/venv_linux/bin/python3` (**3.11.13**), где ABI `lxml` совпадает. Канон = **паритет §15 вариант а**: wrapper `~/.hermes/scripts/mfl_digest_cron.sh` + смена поля `script` у существующего job. `sysconfig.purelib` **сам по себе** на cron-пути digest недостаточен: под текущим интерпретатором 3.14 он резолвится в site-packages управляемого venv Hermes, где `lxml` нет. lxml существует только как ABI 3.11 в `venv_linux` → процесс обязан быть 3.11, и только тогда purelib ABI-согласован. Гибрид «процесс 3.14 + site-packages 3.11» недопустим (как в urgent).

**I2.** `current`: `mfl_digest.py:73` жёстко кладёт в `sys.path`  
`~/USERTOOLS/MoveFromLoop/venv_linux/lib/python3.11/site-packages`, где `lxml` — бинарь `etree.cpython-311-*.so` (lxml 6.1.1, exchangelib 5.6.0; venv пересобран 2026-10-11). Процесс на 3.14 → `ModuleNotFoundError: No module named 'lxml.etree'`. Репродукция: тот же sys.path-блок под `hermes-agent/.venv/bin/python3` (3.14.5) → та же ошибка; под `venv_linux/bin/python3` (3.11.13) → `OK lxml.etree 6.1.1`.  
`target`: хардкода `python3.11` нет. Блок идентичен `mfl_urgent_check.py:69-83`: `sysconfig.get_path("purelib")`, запасной —  
`Path(sys.executable).resolve().parent.parent / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"`.  
Формула `Path(sys.executable).parent.parent / "site-packages"` **неверна** (уже отвергнута в §15 I2). После П.1 этот путь уже на `sys.path` интерпретатора; вставка остаётся защитной, без литерала версии. Путь пакета `_EXM = ~/USERTOOLS/ExchangeMonitor` сохраняется. Импорт — `exchangemonitor.digest.run_digest_exchange` (не urgent).

Почему urgent-фикс не закрыл digest: (a) `mfl_urgent_check_cron.sh` + `f61b26cbbdf5.script` — только urgent; (b) динамический purelib — только в `mfl_urgent_check.py`. Digest-джоб вызывает `mfl_digest.py` напрямую.

### Решение П.1…П.5 (реализация — HF:impl / HF:docs-handoff)

**П.1 — интерпретатор = venv_linux (обязательно).**  
Новый `~/.hermes/scripts/mfl_digest_cron.sh` по образцу `mfl_urgent_check_cron.sh`: `set -euo pipefail`; `exec`  
`~/USERTOOLS/MoveFromLoop/venv_linux/bin/python3 ~/.hermes/scripts/mfl_digest.py "$@"`.  
Комментарий-профилактика как у urgent: инструмент с собственным venv крон исполняет **через этот venv**; `project_python` управляемого venv Hermes не исполнитель таких `.py`.

**П.2 — поле `script` существующего job.**  
В `~/.hermes/cron/jobs.json` у job `2865cc674493` поле `script` → `mfl_digest_cron.sh`. Это правка **существующего** job, не новый крон и не «ставь кроны». `id`, `schedule` (`0 8-20 * * 1-5`), `no_agent=true`, `deliver` (`telegram:-1004300127777:6556`), `workdir`, `enabled` — без изменений. Gateway не рестартовать. Раннер для `.sh` запускает bash+exec; stdout preserved (как urgent).

**П.3 — убрать хардкод чужого venv.**  
В Exchange-блоке `mfl_digest.py` (строки 67–82): `_EXM` остаётся. Строку 73 с литералом `python3.11` заменить на резолв из I2; добавить `import sysconfig`. `except` → ErrorBus (`stage=exchange`, `--tool MoveFromLoop`, `--job-id 2865cc674493`, `--script mfl_digest.py`) не менять. Loop-ветка `run_digest` и загрузка `.env` не меняются.

**П.4 — синхронизировать reference (профилактика повтора).**  
Файл `~/.hermes/skills/devops/usertools-llm-integration/references/usertools-cron-venv-syspath.md` сейчас **учит сломанный гибрид**: хардкод `.../lib/python3.11/site-packages` как «фикс-паттерн»; shell-обёртку называет «менее предпочтительной» и «ломает no_agent». Это ложно: urgent уже в проде через `.sh`, `no_agent` жив; гибрид 3.14+cp311 и есть id 1825/1828.  
Канон файла после правки: MoveFromLoop имеет **два** cron-entry — urgent `f61b26cbbdf5` (`mfl_urgent_check_cron.sh`) и digest `2865cc674493` (`mfl_digest_cron.sh`); оба обязаны исполняться через свою venv_linux-обёртку; ни один новый `.py`-джоб, импортирующий инструмент с собственным venv, не должен вызывать крон на сырой скрипт. Проверочная команда «гонять через `hermes-agent/.venv/bin/python`» — запрещена (это и есть баг). Питфолл 2 (`message_class` / `item_class` в exchangelib 5.6.0) **не** переписывать. Фаза: `HF:docs-handoff` (reference, не runtime).

**П.5 — контрольный прогон и закрытие id 1828.**  
`venv_linux/bin/python3 -c "import exchangemonitor.digest, lxml.etree"` → ok (под интерпретатором обёртки, с `sys.path` как в скрипте). Сухой `bash ~/.hermes/scripts/mfl_digest_cron.sh` → exit 0; SILENT при отсутствии сообщений; Exchange-блок не фейлит (нет `lxml.etree` / `Exchange FAIL` в stderr). Разовый/штатный тик крона: `count` id 1828 не растёт; `status=resolved` — `error_bus_cli.py resolve 1828` **или** `auto_resolve_recovered` на следующем `reconcile` (ErrorBus §3.5 / §3.6; без `DELETE`). Прогон через штатный крон-интерпретатор 3.14 **не** таргет. Бизнес-`deliver` `:6556` не меняется.

### Затронутые файлы

| # | Файл | Что | Фаза |
|---|---|---|---|
| 1 | `~/.hermes/scripts/mfl_digest.py` | Exchange-блок ~73: резолв site-packages + `import sysconfig` (П.3) | `HF:impl` |
| 2 | `~/.hermes/cron/jobs.json` | у `2865cc674493` только поле `script` (П.2) | `HF:impl` |
| 3 | `~/.hermes/scripts/mfl_digest_cron.sh` | **новый** wrapper, паритет urgent (П.1) | `HF:impl` |
| 4 | `~/.hermes/skills/devops/usertools-llm-integration/references/usertools-cron-venv-syspath.md` | инверсия канона: обёртка, не гибрид (П.4) | `HF:docs-handoff` |

`HF:impl` = 3 runtime-файла, вне shared-модулей USERTOOLS (паритет §15). Четвёртый файл — skill-reference, не код инструмента; кладётся на уже существующую `HF:docs-handoff`. **Факт объёма для оркестратора, не команда skip / LIGHT / смены кейса.**

### IAC (план = body `BUG:diagnose` / эта секция)

| IAC | path | verify | depends | covers |
|---|---|---|---|---|
| **IAC-01** | `mfl_digest_cron.sh` + `jobs.json` (`2865cc674493.script`) | `bash ~/.hermes/scripts/mfl_digest_cron.sh` запускает процесс, у которого `sys.executable` = `venv_linux/bin/python3` и `sys.version` начинается с `3.11.13`; в job `script=mfl_digest_cron.sh`, `id`/`schedule`/`deliver`/`no_agent`/`workdir` те же | — | П.1, П.2, AC-001 |
| **IAC-02** | `mfl_digest.py` Exchange-блок | `rg -n 'python3\\.11' ~/.hermes/scripts/mfl_digest.py` → 0; под `venv_linux/bin/python3` `import lxml.etree, exchangelib; from exchangemonitor.digest import run_digest_exchange` без исключения | IAC-01 | П.3, AC-002, AC-003 |
| **IAC-03** | крон `2865cc674493` + ErrorBus 1828 | сухой wrapper + 1–2 крон-прогона: stderr без `lxml.etree` / `Exchange FAIL`; `SELECT count,status,last_seen FROM errors WHERE id=1828` — `count` не растёт после первого успешного тика; `status=resolved` либо сразу, либо после reconcile | IAC-01, IAC-02 | П.5, AC-004, AC-005 |
| **IAC-04** | `usertools-cron-venv-syspath.md` | файл называет оба entry (`f61b26cbbdf5` через `mfl_urgent_check_cron.sh`, `2865cc674493` через `mfl_digest_cron.sh`); нет рекомендации хардкода `python3.11` site-packages как фикса; снято «обёртка ломает no_agent»; проверочная команда не гоняет `hermes-agent/.venv`; питфолл 2 (`message_class`) сохранён | — | П.4, AC-007 |

Нет `depends: operator:` (класс S). Живой EWS и наличие писем в дайджест-окне не обязательны: успех Exchange-блока = нет исключения импорта/ABI, не «обязательно непустой stdout».

### Критерии приёмки (AC)

Только этот пакет. Наблюдаемое поведение / артефакт. Класс S (поезд не ждёт Сашу).

### AC-001 — крон исполняет digest на venv_linux 3.11.13

У job `2865cc674493` `script` = `mfl_digest_cron.sh`. Wrapper делает `exec` `~/USERTOOLS/MoveFromLoop/venv_linux/bin/python3` → `~/.hermes/scripts/mfl_digest.py`. Процесс прогона: `sys.version` начинается с `3.11.13`, `sys.executable` указывает в `venv_linux`. `id`, `schedule` `0 8-20 * * 1-5`, `no_agent=true`, `deliver=telegram:-1004300127777:6556`, `workdir` не изменены. Нового job нет.

### AC-002 — нет хардкода python3.11 site-packages в digest

В `~/.hermes/scripts/mfl_digest.py` нет литерала `python3.11` и нет абсолютного `.../lib/python3.11/site-packages`. Резолв — `sysconfig.get_path("purelib")` или запасной Path из I2. Путь пакета `~/USERTOOLS/ExchangeMonitor` в `sys.path` сохраняется.

### AC-003 — `lxml.etree` импортируется тем же интерпретатором, что крон

Команда  
`~/USERTOOLS/MoveFromLoop/venv_linux/bin/python3 -c "import lxml.etree, exchangelib; from exchangemonitor.digest import run_digest_exchange"`  
(с `sys.path`, как в скрипте) завершается кодом 0. Тот же import через wrapper — код 0. Нет `ModuleNotFoundError: No module named 'lxml.etree'`. Штатный крон-интерпретатор 3.14 как таргет проверки **не** использовать.

### AC-004 — ErrorBus id 1828 перестаёт расти и закрывается

После первого успешного прогона фикса: повторные тики `2865cc674493` не инкрементят `errors.count` у id 1828 и не создают новую строку с `dedup_key=af5514e5180bbf39` / message `ExchangeMonitor digest failed` / detail с `lxml.etree`. `status` id 1828 = `resolved` (`error_bus_cli.py resolve 1828` или auto-resolve ErrorBus). История строки не `DELETE`. Базовая линия `count` = значение на момент первого успешного тика после фикса, не «вернуть к 3».

### AC-005 — бизнес-доставка и Loop-путь живы

`deliver` job остаётся `telegram:-1004300127777:6556`. Loop-ветка `run_digest` не менялась. Если Exchange-блок вернул текст — он в stdout (склейка `\n\n` как сейчас) и уходит в Messages; если писем нет — SILENT, без `Exchange FAIL` в stderr. Техника ошибок по-прежнему через `report_error.sh` (ErrorBus Mode A, `instrumentation_registry.json` → `2865cc674493: self`), не через `deliver`. `--script mfl_digest.py` в self-report не переименовывать в имя обёртки.

### AC-006 — границы diff runtime (`HF:impl`)

Diff `HF:impl` содержит только 3 пути: `mfl_digest.py`, `mfl_digest_cron.sh`, `jobs.json` (одно поле). Нет правок `mfl_urgent_check.py` / `mfl_urgent_check_cron.sh` / job `f61b26cbbdf5`, `scheduler_script.py`, `~/USERTOOLS/MoveFromLoop/**` (кроме чтения venv), `~/USERTOOLS/ExchangeMonitor/**`, `loop_rules.yaml`, `watermark.json`, ядра ErrorBus (`_db.py` и пр.), манифеста, `.env`. Gateway не рестартован. Управляемые venv Hermes не пересозданы.

### AC-007 — reference больше не учит гибрид

`usertools-cron-venv-syspath.md` (фаза `HF:docs-handoff`): оба MoveFromLoop cron-entry названы с обёртками; хардкод `python3.11` site-packages снят как рекомендуемый фикс; утверждение «shell-обёртка ломает no_agent» снято; verify-команда не использует `hermes-agent/.venv`. Питфолл 2 (exchangelib `message_class` / `item_class`) без регрессии текста.

### Что НЕ трогать

- Job `f61b26cbbdf5`, `mfl_urgent_check.py`, `mfl_urgent_check_cron.sh` — уже канон §15; регресс urgent запрещён.
- `~/hermes-agent/cron/scheduler_script.py`, `_posix_cron_script_argv`, `project_python` — ядро.
- Управляемые venv `~/.hermes/installs/**` и `~/hermes-agent/.venv` — не пересобирать «для синхронизации с 3.11».
- Пакет `~/USERTOOLS/ExchangeMonitor` (`digest.py`, `fetcher.py`, зависимости).
- Код `~/USERTOOLS/MoveFromLoop/movefromloop/**`, `loop_rules.yaml`, `state/watermark.json`.
- Расписание, `job_id`, `deliver`, `no_agent`, `workdir` у `2865cc674493`; весь job `f61b26cbbdf5`.
- Новый крон / «ставь кроны»; рестарт Gateway.
- ContractAssistant в `mfl_*` (Границы v0.4.5). Вырез «job … не трогать» для этого пакета сужается до: не трогать кроме поля `script` у `2865cc674493`.
- §14 чёрный список Loop; синк контактов v1; архивация §AA–§AI; §15 runtime urgent.
- Схема `events.db`, `report_error.sh`, `instrumentation_registry.json` (режим `self` у `2865cc674493` остаётся). Таблица ErrorBus §11.2 по-прежнему пишет имя скрипта `mfl_digest.py` — leftover чужого ТЗ (ключ реестра = `job_id`, Mode A не ломается); ErrorBus master-ТЗ этим пакетом не править.
- Содержимое `.env` / `contacts.enc`.
- Питфолл 2 в том же reference (`message_class` / `item_class`).

### Связи с экосистемой

- **Читает:** `venv_linux` MoveFromLoop (интерпретатор + site-packages); пакет `ExchangeMonitor` (import `run_digest_exchange`); `loop_rules.yaml` / `state/watermark.json` — как сейчас.
- **Пишет:** поле `script` существующего job `2865cc674493`; stdout → Hermes `deliver` `:6556` (бизнес, ErrorBus §1 не трогает); при сбое Exchange — `report_error.sh` → ErrorBus (`tool=MoveFromLoop`, `stage=exchange`).
- **Зависит от:** ErrorBus Mode A (`instrumentation_registry.json` → `2865cc674493: self`); канон закрытия — ErrorBus §3.5 `resolve` / §3.6 `auto_resolve_recovered`. Паритет канона §15 (urgent-обёртка уже в проде).
- **Параллельно:** ExchangeMonitor (draft usertool, App:Outlook/Exchange); Loop-мониторинг итерации 1; urgent-крон §15 — не в runtime-diff этого пакета.
- **Не зависит от:** манифеста, `EcosystemConfig.yaml`, новых сущностей, новых `.env`-ключей.
- **Новых внешних контрактов нет.** Выход `text` → `api_telegram` (`:6556`) и `tool`/`message` → ErrorBus — без изменения схемы.

### Откат

Вернуть `jobs.json[2865cc674493].script = mfl_digest.py` (или выключить джоб). Правка `mfl_digest.py` (П.3) обратносовместима: при интерпретаторе обёртки (и при любом 3.x venv инструмента) purelib резолвится корректно. Ядро / venv Hermes не пересобираются.

### Риски пакета

| Риск | Mitigation |
|---|---|
| Раннер начнёт оборачивать и `.sh` через `project_python` | Сейчас `_posix_cron_script_argv` только для `.py`. Если обёртка внезапно пойдёт через 3.14 — IAC-01 красный; тогда отдельный баг ядра, не этот пакет. |
| `purelib` без обёртки (только П.3) | На 3.14 резолвится в Hermes venv без lxml. П.1 обязателен; П.3 без П.1 = не фикс. |
| `parent.parent / "site-packages"` из сырого плана | Зафиксирован канон I2 / §15; копировать блок `mfl_urgent_check.py:69-83`, не укороченную формулу. |
| `last_status=ok` при растущем 1828 | Исключение глотается. Успех = нет ABI в stderr + count 1828 не растёт, не поле крона `ok`. |
| Reference оставить «как есть» | Он учит гибрид — источник следующего sibling. IAC-04 / AC-007 обязательны. |
| Пересборка Hermes venv «для П.3» | Запрещена. Изоляция через wrapper. |
| Пустой stdout примут за провал Exchange | Успех = нет ABI-исключения, не обязательное письмо. |
| `jobs.json` как файл ORCH | Правка 1 поля существующего job в 3 runtime-файлах `HF:impl` (как §15). Новый job / манифест — нет. |
| count 1828 растёт до impl (крон каждый час 8–20) | Базовая линия = `count` на момент первого успешного тика после фикса. |
| Регресс urgent | `f61b26cbbdf5` / urgent-файлы в «НЕ трогать». |

Открытых вопросов Саше нет. Реализация не начинается этой фазой.

---

## TZ:finalize 2026-10-12 — digest-lxml

Версия корпуса **не** бампится повторно: frontmatter уже **0.4.8** с `TZ:patch` 2026-10-12 (`DEV/mfl-digest-lxml`, leftover §15). Пакет: крон `2865cc674493` исполняет digest на `venv_linux/bin/python3` (3.11.13) через wrapper `mfl_digest_cron.sh`; хардкод `python3.11` site-packages в `mfl_digest.py` снят (`sysconfig.get_path("purelib")`); reference `usertools-cron-venv-syspath.md` перестаёт учить гибрид. Дельта `TZ:patch` (§16) включена без правок канона.

Чеклист качества (Шаг 4 `tz-workflow`):

- [x] Цель одним предложением (§16 I1: digest-крон на ABI venv_linux 3.11, не на Hermes 3.14)
- [x] Входы и выходы явны (job `2865cc674493`, wrapper, ErrorBus id 1828, `deliver :6556`; контракты без новых внешних полей)
- [x] Шаги impl атомарны (П.1…П.5; runtime `HF:impl` = 3 файла, reference = `HF:docs-handoff`)
- [x] Критерии успеха проверяемы (IAC-01…04, AC-001…007)
- [x] «Что НЕ трогать» заполнено (§16)
- [x] Связи с экосистемой (§16 + контракты: ErrorBus Mode A, ExchangeMonitor import, `api_telegram :6556`)
- [x] Контракты по стандарту (раздел «Контракты экосистемы»; новых внешних контрактов нет)
- [x] Открытые вопросы закрыты
- [x] I1 / I2 `current` / `target` в §16
- [x] AC только пакета, класс S, нет `depends: operator:`

AC-001…007 (класс S) уже в §16; показ в origin на `GATE:take-into-work` (auto-pass `ac-shown`). Operator-hold нет.

Reuse-first: паритет канона §15 (urgent-обёртка уже в проде), тот же `venv_linux`, тот же job id, ErrorBus `resolve` / `auto_resolve_recovered`. Новых сущностей, кронов, `.env`-ключей, записей манифеста нет.

Объём runtime = 3 файла вне shared-модулей USERTOOLS — **факт для оркестратора**, не команда skip / LIGHT / смены кейса (G5). Состав хвоста графа — оркестратор.

Открытых вопросов Саше нет. Реализация не начинается этой фазой — ждёт `GATE:take-into-work` и хвост графа (`HF:impl`).

---

## §17. Доработка 16.10.2026 — срочные каналы (urgent_channels)

Пакет `DEV/mfl-urgent-channels` (CHANGE, аддитивная секция). Карточка `TZ:patch`. Код на этой фазе **не** меняется — реализация `HF:impl`. Версия корпуса бампнута 0.4.8→0.4.9 во frontmatter этим `TZ:patch`; `TZ:finalize` пакета повторно не повышает, если frontmatter уже 0.4.9.

Требование Саши: отслеживать новости канала
`https://loop.tutu.ru/tutu/channels/ai-analitik-multiagentnaya-sistema-aid`
во всех его подтопиках как срочные. Объект (факт): канал `ai-analitik-multiagentnaya-sistema-aid`, `id=jqhs9np3i3nj7qxh3e4hm6ox1r`, type=OPEN; `GET /api/v4/channels/{id}/topics` → 15 подтопиков, у всех `parent_id` = этот канал.

Расширяет §C (`loop_rules.yaml`) и оркестратор срочного режима (`urgent.py` / `mfl_urgent_check`). Дайджест, синк контактов v1, Exchange-контур и кроны не входят.

### Цель

Доставлять **все** новые посты указанных каналов Loop и всех их подтопиков в топик Messages как срочные (`mfl_urgent_check`), независимо от автора.

### I1 / I2 (current → target)

**I1 (критический).** `current`: срочный путь (`urgent.py`) тянет только mentions (`fetch_mentions`, `mention_count > 0`) и оставляет пост, если `user_id ∈ urgent_user_ids` (`is_urgent`). Канал AID и его 15 подтопиков без меншна Саши и без автора из `urgent_contacts` в 🔴 не попадают. `watch_channels` кормит только дайджест.  
`target`: ключ `urgent_channels` в `loop_rules.yaml` (имя или 26-символьный id, как `watch_channels` / §14). На каждом тике срочного крона: резолв каждого элемента в `channel_id` + все подтопики `GET /api/v4/channels/{id}/topics`; `posts_since` по **всем** резолвленным id (включая сам канал); все полученные посты — 🔴, без фильтра автора.

**I2.** `current`: пустой `urgent_contacts` → `run_urgent` сразу двигает `urgent_last_ts` и SILENT (ранний выход до fetch).  
`target`: этот shortcut **только** если пусты оба списка (`urgent_contacts` и `urgent_channels`). Непустой `urgent_channels` при пустых контактах — штатный прогон channel-пути.

### 17.1 Модель данных

Секция в `~/USERTOOLS/MoveFromLoop/loop_rules.yaml` (единственный источник правды правил мониторинга):

```yaml
# Срочные каналы: имя без # либо channel_id 26 символов. Как watch_channels (§C / §14).
# Резолв → channel_id + все подтопики GET /api/v4/channels/{id}/topics.
# Все посты этих id уходят 🔴 независимо от автора (отдельный allowlist, не urgent_contacts).
urgent_channels:
  - ai-analitik-multiagentnaya-sistema-aid  # id=jqhs9np3i3nj7qxh3e4hm6ox1r OPEN
```

| Что хранить | Почему |
|---|---|
| **Имя канала или 26-символьный id** | Как `watch_channels` + существующий `ChannelResolver.resolve_id()`. Display-name («AI-АналИтик…») — не ключ. |
| **Не список подтопиков** | Подтопики резолвятся на рантайме; YAML не дублирует 15 id и не устаревает при появлении нового topic. |
| **Пустой список / ключ отсутствует** | Поведение как до фичи. |

В датаклассе `Rules` (`movefromloop/rules.py`): поле `urgent_channels: List[str]` (default `[]`). `load_rules` / `save_rules` пишут ключ **явно** (иначе round-trip ruamel его потеряет — урок §14). Чужие ключи (exchange-поля) не затираются.

Мутаторы (идемпотентны, как `add_channel` / `add_blacklist_channel`): `add_urgent_channel(path, channel)` / `remove_urgent_channel(path, channel)`. Новый CLI / новые команды Сирени **не** в минимальный контур: seed пишет `HF:impl` в YAML; «покажи правила» (§C) уже показывает файл. `user_id` / `mattermost_id` в YAML и в `contacts.enc` не писать (инвариант §4 / §9).

Новых сущностей, кронов, `.env`-ключей нет.

### 17.2 Алгоритм (срочный путь)

Дополнение `run_urgent` (`movefromloop/urgent.py`). Контакт-путь (`fetch_mentions` + `is_urgent` + `should_drop(..., mode="urgent")`) **не переписывается**. Channel-путь — отдельное ведро, merge по `post.id`.

```
load rules + state (watermark.json, prune как сейчас)
if urgent_contacts пуст AND urgent_channels пуст:
    watermark → now; SILENT                    # бывший shortcut, сужен
# контакт-путь — как сейчас (если urgent_contacts непуст)
# ★ channel-путь (если urgent_channels непуст):
★ для каждого name_or_id в urgent_channels:
    cid = ChannelResolver.resolve_id(name_or_id)   # имя или 26-char id
    если не резолвится → stderr, этот элемент YAML skip в этом прогоне
    parent_ids += {cid}
    GET /api/v4/channels/{cid}/topics → взять id каждого элемента
    (наблюдаемо: 15 штук, parent_id = cid; рекурсию topics-of-topics не делать)
    ошибка topics → stderr, ведро = {cid} (fail-open на детях, родитель остаётся)
★ resolved = parent ∪ topic ids
★ для каждого id: LoopClient.posts_since(id, urgent_watermark)   # reuse fetcher
    ошибка одного id → stderr, skip этот id (паттерн fetch_watched / mentions_fetcher)
★ channel_posts = все посты; фильтр автора НЕТ
★ drop if state.is_seen(id)                                    # общий seen_ids
★ merge с контакт-путём по post.id (один пост — один раз)
★ my_username на этапе format — как сейчас (свои посты не алертим)
format_urgent → mark_seen(ids) → urgent_last_ts как сейчас
```

Дедуп: существующий `State.is_seen` / `mark_seen` (ключ `seen_ids` в `state/watermark.json`, TTL 48 ч). Отдельного `seen_urgent_ids` / нового state-файла нет (исторический `urgent_watermark.json` из §D давно сведён в общий watermark; новый ключ не вводить). Дайджест уже проверяет `is_seen` — пост, ушедший 🔴, в часовой дайджест не дублируется.

Reuse-first: `posts_since` уже в `LoopClient`; `fetch_watched` умеет тянуть список id. Новый код — резолв topics + merge ведра. Метод `channel_topics(channel_id)` в `loop_api.py` (тот же endpoint, что LoopChannelDigest; curl-клиент LCD **не** импортировать). Расширение `ChannelResolver` — `resolve_id` + topics → `set[str]` id.

Первый прогон: окно = текущий `get_urgent_watermark()` (default lookback 10 мин). Отдельного backfill истории канала нет.

### 17.3 Приоритет относительно чёрного списка (§14) и urgent_contacts

`urgent_channels` — **отдельный channel-allowlist**, ортогональный `urgent_contacts` (user-allowlist). Доставляет **все** посты резолвленных id независимо от автора: и бот `ai-assistant` (уже в `blacklist_users`), и человек не из `urgent_contacts`. Срочность канала первостепенна, как вариант 3 для контактов.

Контакт-путь по-прежнему вызывает `should_drop(..., mode="urgent")` без изменения предиката §14. Channel-ведро **не** пропускать через `should_drop_by_blacklist` (bucket isolation): иначе blacklist-user / blacklist-channel съест новости AID. Предикат §14 не переписывать.

| Кто / где | Дайджест | Срочный 🔴 |
|---|---|---|
| Автор ∈ `urgent_contacts`, канал обычный | как §14 | **уходит** (контакт-путь) |
| Автор ∉ `urgent_contacts`, канал ∈ `urgent_channels` (или его topic) | как сейчас (keywords/mentions/blacklist) | **уходит** (channel-путь) |
| Автор ∈ `blacklist_users` (напр. `ai-assistant`), канал ∈ `urgent_channels` | вырезан (§14) | **уходит** |
| Канал одновременно в `blacklist_channels` и `urgent_channels` | вырезан (§14) | **уходит** (channel-allowlist сильнее) |
| Автор ∈ `urgent_contacts` ∩ пост в `urgent_channels` | как §14 | **уходит** один раз (merge по id) |
| `urgent_channels` пуст | без изменений | без изменений (только контакт-путь) |
| Только `my_username` | как сейчас | как сейчас (format skip) |

Формула срочного:

- контакт-ведро: `is_urgent ∧ ¬seen ∧ ¬should_drop(..., mode="urgent")` — канон §14;
- channel-ведро: `channel_id ∈ resolved(urgent_channels ∪ topics) ∧ ¬seen` — автор и blacklist **не** фильтр;
- union по `post.id`.

Списки ортогональны: канал в `urgent_channels` **не** удалять из `watch_channels` / `blacklist_*` автоматически.

### 17.4 Изменяемые файлы (план реализации)

| Файл | Что |
|---|---|
| `loop_rules.yaml` | ключ `urgent_channels` + seed `ai-analitik-multiagentnaya-sistema-aid` (комментарий с id) |
| `movefromloop/rules.py` | поле, load/save явно, 2 мутатора |
| `movefromloop/loop_api.py` | `channel_topics(channel_id)` → `GET /api/v4/channels/{id}/topics` |
| `movefromloop/channel_resolver.py` | expand: `resolve_id` + topics → set id (родитель ∪ дети, без рекурсии) |
| `movefromloop/urgent.py` | сузить empty-contacts shortcut; channel-ведро; merge; `mark_seen` общий |
| `tests/test_rules.py` | load/save/add/remove, default `[]`, round-trip ruamel |
| `tests/test_urgent.py` | посты без urgent-автора из канала/topic → 🔴; blacklist-user в urgent-канале → 🔴; `is_seen` глушит повтор; пустой ключ = старое поведение; пустые contacts + непустые channels ≠ ранний SILENT |
| `tests/test_channel_resolver.py` или `test_loop_api.py` | topics → 15+1 id; 404/ошибка topics → только родитель |

`mentions_fetcher.fetch_watched` можно reuse после expand (список уже id). `blacklist.py` / предикат §14 **не** трогать при bucket isolation. `digest.py` не менять: дедуп через уже существующий `is_seen`. `mfl_urgent_check.py` и job `f61b26cbbdf5` не менять (вход — тот же `run_urgent`).

Объём runtime > 3 файлов USERTOOLS — **факт для оркестратора**, не команда skip / LIGHT / смены кейса (G5).

### 17.5 Что НЕ трогать

- Синк контактов v1 (`sync.py`, `filters.py`, `mapper.py`, `__main__.py`, крон вс 03:30).
- Инвариант «не писать `mattermost_id`» (§4, §9).
- `digest.py` и job `2865cc674493` (дайджест не становится каналом доставки этой фичи).
- Exchange-контур (`movefromloop/exchange_*.py`, пакет `~/USERTOOLS/ExchangeMonitor`).
- Расписание, `job_id`, `script`, `deliver`, `no_agent` кронов `f61b26cbbdf5` / `2865cc674493`. Новый крон / «ставь кроны» / рестарт Gateway — нет.
- Предикат `should_drop_by_blacklist` и канон варианта 3 (§14) — не переписывать; channel-ведро его просто не вызывает.
- `formatter.py` (формат карточки / `🔴 СРОЧНО`), `urgency_checker.is_urgent` (остаётся user-allowlist).
- LoopChannelDigest (on-demand, свой curl-клиент; Q2 LCD: не импортировать его клиент в крон MFL).
- Архивация §AA–§AI; ContractAssistant в `mfl_*` (Границы v0.4.5).
- Схема `watermark.json` (новых ключей seen/watermark нет). Содержимое `.env` / `contacts.enc`.
- §15 / §16 runtime (venv-обёртки).

### 17.6 Связи с экосистемой

- **Читает:** `loop_rules.yaml` (новый ключ), Loop API v4 (`/teams/{team}/channels/name/{name}`, `/channels/{id}`, `/channels/{id}/topics`, `/channels/{id}/posts?since=`), `state/watermark.json` (`urgent_last_ts`, `seen_ids`, кэши).
- **Пишет:** `loop_rules.yaml` (seed + мутаторы); `seen_ids` / `urgent_last_ts` — существующее поведение urgent. `contacts.enc` не читает и не пишет (в отличие от `urgent_contacts`).
- **Зависит от:** итерация 1 мониторинга (уже в проде), `ChannelResolver`, `LoopClient.posts_since`, общий `State`. Endpoint topics — тот же, что LoopChannelDigest; реализация — в `LoopClient` этого пакета.
- **Параллельно:** дайджест (дедуп через `seen_ids`); ExchangeMonitor / `exchange_*` — **не** применяют `urgent_channels`; LCD — не крон.
- **Не зависит от:** манифеста, `EcosystemConfig.yaml`, новых сущностей, новых `.env`-ключей.
- **Новых внешних контрактов нет.** Потребитель по-прежнему `api_telegram` (топик Messages, `deliver=telegram:-1004300127777:6556`). Поле `text` без изменения схемы. `GET /topics` — тот же `api_loop`, не новый контракт.

### 17.7 IAC / AC и тест-кейсы

Нет `depends: operator:` (класс S). Seed канала в YAML пишет `HF:impl`, не глагол Саши.

| IAC | path | verify | depends | covers |
|---|---|---|---|---|
| **IAC-01** | `loop_rules.yaml` + `movefromloop/rules.py` | `load_rules` видит `urgent_channels`; seed содержит `ai-analitik-multiagentnaya-sistema-aid` или id `jqhs9np3i3nj7qxh3e4hm6ox1r`; default без ключа = `[]`; `save_rules` ключ не теряет; add/remove идемпотентны. `cd ~/USERTOOLS/MoveFromLoop && python3 -m pytest -q tests/test_rules.py` | — | 17.1, AC-001 |
| **IAC-02** | `loop_api.py` + `channel_resolver.py` + `urgent.py` (channel-ведро) | mock `GET .../topics` → 15 объектов с `parent_id`=родитель; resolved = 16 id; `posts_since` вызван по каждому; пост автора ∉ `urgent_contacts` из родителя и из topic попадает в результат `run_urgent`; ошибка topics → fetch только родителя. pytest `test_urgent` / resolver | IAC-01 | 17.2, AC-002 |
| **IAC-03** | `urgent.py` + `state.seen_ids` | blacklist-user (`ai-assistant`) в urgent-канале → 🔴 есть; повторный прогон того же `post.id` → SILENT (`is_seen`); пустой `urgent_channels` + непустой `urgent_contacts` = поведение до фичи; пустой contacts + непустой channels ≠ ранний SILENT; job `f61b26cbbdf5` `id`/`schedule`/`script`/`deliver` без diff. `python3 -m pytest -q tests/test_urgent.py` | IAC-01, IAC-02 | 17.3, AC-003 |

### Критерии приёмки (AC)

Только этот пакет. Наблюдаемое поведение / артефакт. Класс S (поезд не ждёт Сашу).

### AC-001 — ключ YAML и seed канала AID

В `loop_rules.yaml` есть `urgent_channels` со значением имени `ai-analitik-multiagentnaya-sistema-aid` и/или id `jqhs9np3i3nj7qxh3e4hm6ox1r`. `Rules.urgent_channels` читается и пишется явно. Пустой список = фича выключена. Новых `.env`-ключей и job нет.

### AC-002 — все посты канала и подтопиков, независимо от автора

Один прогон `run_urgent`: резолв seed-канала даёт родитель + подтопики из `/topics`; `posts_since` по всем id с `urgent_last_ts`. Пост в родителе и пост в подтопике от автора, которого нет в `urgent_contacts`, оба дают 🔴 (формат `format_urgent` как сейчас). Авторский фильтр `is_urgent` на это ведро не действует.

### AC-003 — доставка, дедуп, blacklist, границы

Выход по-прежнему stdout `run_urgent` → существующий `mfl_urgent_check` → `deliver :6556`. Доставленный `post.id` в `seen_ids`; второй тик его не повторяет; дайджест с тем же state его не берёт (`is_seen`). Пост blacklist-user в urgent-канале уходит 🔴. Diff не трогает кроны, `digest.py`, Exchange, `contacts.enc`, предикат §14, схему watermark. Gateway не рестартован.

Тест-кейсы (инварианты, pytest):

1. Пост в seed-канале от неизвестного автора → 🔴.
2. Пост в подтопике (`parent_id` = seed) от того же неизвестного → 🔴.
3. Пост от `ai-assistant` (blacklist) в seed-канале → 🔴.
4. Тот же `post.id` на втором прогоне → нет 🔴.
5. `urgent_channels: []` → `run_urgent` совпадает с контуром до фичи (только contacts/mentions).
6. `urgent_contacts: []` + непустой `urgent_channels` → нет раннего SILENT, channel-ведро работает.
7. Нерезолвнутое имя в YAML → stderr, остальные элементы списка живы.
8. `/topics` 5xx после retry → родитель всё равно fetch, дети skip.
9. `add_urgent_channel` дважды не дублирует строку.
10. Контакт-путь §14 не регрессирует (`test_urgent` / `test_blacklist` зелёные).

Верификация после реализации:

```
cd /home/tkachenkoav/USERTOOLS/MoveFromLoop
python3 -m pytest -q
```

### 17.8 Риски

| Риск | Mitigation |
|---|---|
| Ранний SILENT при пустых contacts съест channel-ведро | I2 + тест 6 обязательны. |
| Вызвать `should_drop` на channel-ведре | Съест бота AID. Только bucket isolation. Тест 3. |
| Рекурсия topics-of-topics | Не делать: факт = 1 уровень, 15 детей. |
| 16× `posts_since` каждые 3 мин | Reuse клиента с retry/pause; ошибка одного id не валит прогон. |
| LCD curl-клиент в крон | Запрещено §AH/LCD Q2. Только `LoopClient`. |
| Backfill всей истории канала | Нет: окно = текущий urgent watermark. |
| Дайджест как страховка | Не цель пакета. Дедуп `seen_ids` как сейчас. |

Открытых вопросов Саше нет. Реализация не начинается этой фазой.

---

## TZ:finalize 2026-10-16 — urgent-channels

Версия корпуса **не** бампится повторно: frontmatter уже **0.4.9** с `TZ:patch` 2026-10-16 (`DEV/mfl-urgent-channels`, REV:tz APPROVE). Пакет: секция `urgent_channels` в `loop_rules.yaml` — все посты указанных каналов и их подтопиков (`GET /api/v4/channels/{id}/topics`) доставляются 🔴 срочно независимо от автора; отдельный channel-ведро, bucket isolation от §14, общий `seen_ids`, merge по `post.id`. Seed `ai-analitik-multiagentnaya-sistema-aid` (id `jqhs9np3i3nj7qxh3e4hm6ox1r`, 15 подтопиков). Дельта `TZ:patch` (§17) включена без правок канона.

Чеклист качества (Шаг 4 `tz-workflow`):

- [x] Цель одним предложением (§17 Цель: все посты указанных каналов и подтопиков → Messages как срочные, независимо от автора)
- [x] Входы и выходы явны (`loop_rules.yaml`, Loop API topics/posts_since, `run_urgent` → `deliver :6556`; контракты без новых внешних полей)
- [x] Шаги impl атомарны (§17.2 алгоритм + таблица 17.4)
- [x] Критерии успеха проверяемы (IAC-01…03, AC-001…003)
- [x] «Что НЕ трогать» заполнено (§17.5)
- [x] Связи с экосистемой (§17.6 + контракты: api_loop, api_telegram `:6556`, ErrorBus Mode A без смены схемы)
- [x] Контракты по стандарту (раздел «Контракты экосистемы»; новых внешних контрактов нет)
- [x] Открытые вопросы закрыты
- [x] I1 / I2 `current` / `target` в §17
- [x] AC только пакета, класс S, нет `depends: operator:`

AC-001…003 (класс S) уже в §17; показ в origin на `GATE:take-into-work` (auto-pass `ac-shown`). Operator-hold нет.

Reuse-first: `ChannelResolver`, `LoopClient.posts_since`, общий `State.seen_ids`; endpoint topics — тот же, что LoopChannelDigest, реализация в `LoopClient` этого пакета (curl-клиент LCD не импортировать). Новых сущностей, кронов, `.env`-ключей, записей манифеста нет.

Объём runtime > 3 файлов USERTOOLS — **факт для оркестратора**, не команда skip / LIGHT / смены кейса (G5). Состав хвоста графа — оркестратор.

Открытых вопросов Саше нет. Реализация не начинается этой фазой — ждёт `GATE:take-into-work` и хвост графа (`HF:impl`).

---

## Контракты экосистемы

### Источник истины
- Владелец записи: MoveFromLoop (`loop_rules.yaml` для правил, `state/watermark.json` для состояний)
- Владелец контактов: AnywhereContacts (`contacts.enc`, MoveFromLoop — только поставщик `sources.loop`)

### Входные контракты
| Поле | Тип | Обязательность | Источник (кто отдаёт) | Формат/enum |
|---|---|---|---|---|
| id | str | required | api_loop | ID пользователя/сообщения в Loop |
| username | str | required | api_loop | Имя пользователя в Loop |
| email | str | required | api_loop | Валидный email пользователя |
| first_name | str | optional | api_loop | Имя |
| last_name | str | optional | api_loop | Фамилия |
| position | str | optional | api_loop | Должность |

### Выходные контракты
| Поле | Тип | Потребитель (кто получает) | Формат/enum |
|---|---|---|---|
| login | str | AnywhereContacts (ContactStore) | login = email до "@" |
| fio | str | AnywhereContacts (ContactStore) | "Фамилия Имя" |
| sources.loop.username | str | AnywhereContacts (ContactStore) | Имя пользователя в Loop |
| sources.loop.nickname | str | AnywhereContacts (ContactStore) | Никнейм в Loop |
| sources.loop.synced_at | datetime(iso8601) | AnywhereContacts (ContactStore) | Время синхронизации |
| sources.loop.active | bool | AnywhereContacts (ContactStore) | Флаг активности аккаунта |
| tool | str | ErrorBus | "MoveFromLoop" |
| message | str | ErrorBus | Сообщение об ошибке |
| text | str | api_telegram | Уведомление о срочном сообщении/дайджест |

### Зависимости
- Получает от: [api_loop, api_exchange]
- Отдаёт: [AnywhereContacts, ErrorBus, api_telegram]

### Breaking changes policy
- Версионирование формата: версионирование полей `sources.loop` внутри `contacts.enc` под управлением `AnywhereContacts`.
- При breaking change API Loop: адаптация коннектора в `USERTOOLS/MoveFromLoop`.

### Границы («что НЕ трогать»)
- Не писать `mattermost_id` в `contacts.enc`.
- Не затирать существующие непустые поля в `contacts.enc` (принцип «только дополнять»).
- Не перетирать `CUSTOM_FIELDS` в `contacts.enc`.
- Не подключать ContractAssistant в `mfl_urgent_check.py` / `mfl_digest.py` (похожий источник ≠ общий процесс; паттерн ExchangeMonitor сюда не копировать). Job `f61b26cbbdf5` / `2865cc674493` не создавать заново и не менять, кроме поля `script` (обёртки venv_linux — §15 / §16).
- Чёрный список Loop (`blacklist_users` / `blacklist_channels`, §14) не применяется к Exchange-контуру и не пишется в `contacts.enc`.

