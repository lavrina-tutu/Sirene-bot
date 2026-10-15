---
tool: TelegramGroupTopics
type: infra_plan
title: "Единый модуль настройки/восстановления топиков TG «Сирень Workspace» + BUGFIX inbound"
version: 0.3.0
date: 2026-09-16
status: approved
author: архитектор (cursor-grok-4.6-high, Cursor CLI)
last-section-added: 2026-09-16 — TZ:patch v0.3.0: канон 8→7, Hermes DEV (:4) исключён (удалён давно); yaml/скрипт/skills → HF:impl следующий цикл
workspace: ~/hermes-agent
diagnose: ~/hermes-agent/_fix_plan_20260916.md
depends_on:
  - ~/hermes-agent (gateway telegram adapter)
  - TZ/ErrorBus/ErrorBus_TZ.md (токен poller vs YAML; топик Errors :11112)
  - skills/devops/tutu-telegram-delivery (каталог топиков / правило бота группы)
reuse_first: "не USERTOOL и не новый скилл; снимок+скрипт-применялка внутри существующего tutu-telegram-delivery; патч allowlist .env + unify bot token + WARNING на silent drop; контракт env-over-YAML не ломать"
---

# TelegramGroupTopics — инфраструктурный план ядра + модуль восстановления топиков

## Форма ТЗ (reuse-first)

Это **инфраструктурный план**, не USERTOOL и не master-ТЗ всего `hermes-agent`. Новый пакет / `HERMES_*` / второй адаптер **не вводятся**. Новая сущность на согласование Саши **не предлагается**: модуль живёт внутри уже существующего скилла `tutu-telegram-delivery` (каталог топиков уже там).

Прецедент учёта правок ядра — строка **KanbanCore hardening** в `MAIN_TZ_INVENTORY.md` (путь `~/hermes-agent`, без ТЗ-файла). Отличие: KanbanCore записан **post-hoc** (status `done`). Этот кейс — spec **до** `HF:impl`, поэтому канон `TZ/<Topic>/<Topic>_TZ.md` обязателен.

v0.1.0 (16.09, `approved` на узкой постановке) зафиксировал BUGFIX inbound П.1–П.5. v0.2.0 **расширяет** ту же позицию новой вводной Саши (единый модуль восстановления). `TZ:finalize` 16.09: Q1 закрыт вариантом 1, status `approved`. v0.3.0 (`TZ:patch` 16.09, CHANGE-LIGHT): канон топиков 8→**7** — «Hermes DEV» (`:4`) исключён (давно удалён в группе). Реализация yaml/скрипт/скиллов — `HF:impl` следующего цикла, не эта фаза.

Эта фаза (`TZ:patch`) пишет только этот файл и инвентарь. Код/.env/yaml/скиллы не трогать.

## Цель

Сократить время восстановления маршрутизации топиков Telegram до одной команды `apply` (снимок «как было» → рабочие файлы), чтобы при полном крахе и в частном случае инцидента 16.09 (тишина inbound группы «Сирень Workspace» `-1004300127777` при живом DM) не править файлы руками, не ломая env-over-YAML и не трогая forum-роутинг.

## Root cause инцидента 16.09 (подтверждён `BUG:diagnose`)

После апдейта ядра (FF `main` → `52ecd71c`, 12:54) и planned-restart gateway (13:11) адаптер **получает** апдейты группы (poller = бот `863022…`, admin группы), но **молча дропает** их на allowlist-гейте.

| Слой | Факт |
|---|---|
| YAML `telegram.allowed_chats` | `400307920,-1004300127777` (группа есть) |
| `.env` `TELEGRAM_ALLOWED_CHATS` | только `400307920` (обе копии: `~/.hermes/.env` и `~/.hermes/profiles/default/.env`) |
| Контракт после `3dedb71f2f` (13.09) | env-over-YAML: непустой env **побеждает** YAML extra |
| До рестарта | процесс на `d01cc6276c`: YAML extra **первый**, узкий `.env` не мешал |
| DM `400307920` | жив: private chat этот гейт не проходит |
| Тишина | `_gate_or_observe` → `_should_process_message` False → `return` **без лога**; inbound группы в `gateway.log` нет |

Не причины (опровергнуты диагнозом): сломанный forum `thread_id`, prune `sessions.json`, второй `getUpdates`/multiplex, миграция `_config_version` 33→44.

Диагноз (read-only): `~/hermes-agent/_fix_plan_20260916.md`.

Системная причина повторных крахов (новая вводная): канон топиков/allowlist/бота **размазан** по `.env` (две копии), `config.yaml`, скиллу `tutu-telegram-delivery`, `hermes-gateway-setup` (таблица без Errors), hardcoded ErrorBus `:11112`, `jobs.json` `deliver`. Починка = поиск по файлам. Модуль делает снимок «как было» и применяет его одной точкой входа.

## Срез инцидента 16.09 — план П.1–П.5 (v0.1.0, не отменён)

Узкий BUGFIX остаётся верным. Для `HF:impl` его шаги **поглощаются** модулем (см. П.1'–П.7' ниже). Здесь — канон инцидента, чтобы не потерять решения.

Контракт env-over-YAML **не ломать** (намеренный, #108440). UNION yaml∪env запрещён.

### П.1 — allowlist (достаточный фикс inbound)

**Выбрано — П.1б** (явный env-override):

В обоих файлах `~/.hermes/.env` и `~/.hermes/profiles/default/.env`:

```
TELEGRAM_ALLOWED_CHATS=400307920,-1004300127777
```

После правки — рестарт gateway (dotenv читается на старте). Рестарт — только в `HF:impl` по «берём в работу» / «поднимай», не из этой фазы.

**П.1а (не этот проход, эквивалент):** удалить ключ `TELEGRAM_ALLOWED_CHATS` из обеих копий `.env` → `extra_or_secret` возьмёт YAML. Канон проекта «`.env` = только секреты»; `hermes setup` этот ключ не перезаписывает. Функционально то же, что П.1б. Не смешивать с П.1б в одном проходе.

Не добавлять группу через новый ключ / второй адаптер / `guest_mode`.

### П.2 — один bot token (снятие мины, не блокер П.1)

Оставить poller = `863022` (`sirene_vm_bot`, admin группы) = `TELEGRAM_BOT_TOKEN`.

**Выбрано:** заменить `gateway.telegram.token` (`882117`, не в группе) на тот же токен, что poller. Не добавлять `882117` в группу «чтобы завелось». Второй бот — только отдельный профиль со своим токеном и членством, либо не использовать.

Согласуется с ErrorBus решение №11: приоритет `TELEGRAM_BOT_TOKEN` (`sirene_vm_bot`); YAML-бот в группе не состоит.

### П.3 — лог на silent drop (код, маленький, не блокер П.1)

Файл: `~/hermes-agent/plugins/platforms/telegram/adapter.py` (`_gate_or_observe` / reject по `allowed_chats`).

Один WARNING на `(chat_id, thread_id)` при drop: group chat не в `TELEGRAM_ALLOWED_CHATS` (env, N ids); YAML extra проигнорирован. Без новых env/ключей. Класс бага «тихий allowlist», не только этот инцидент.

### П.4 — 409 poll conflict

Не менять `drop_pending_updates=True` на conflict-retry (#75017) без отдельного воспроизведения. Пока gateway в polling — не дергать ручной `getUpdates` на том же токене. Второй poller в этом процессе не найден.

### П.5 — не делать (срез v0.1.0)

- Не чинить forum `_effective_message_thread_id` / session keys.
- Не откатывать prune `sessions.json`.
- Не выключать `multiplex_profiles` из-за этой регрессии.
- Не UNION yaml∪env для allowlist (сломает «env = сузить список»).
- Не новый core tool / `HERMES_*` для чатов.
- Не откатывать `3dedb71f2f` / `extra_or_secret`.
- Не трогать `TELEGRAM_ADDITIONAL_STARTUP_CHANNELS` как allowlist (это не inbound-гейт).

---

## Единый модуль настройки/восстановления топиков TG

### Назначение

Один артефакт «известное исправное состояние» маршрутизации топиков группы «Сирень Workspace» + одна команда, которая (a) применяет его в рабочие файлы Hermes и (b) проверяет, что факт на диске совпадает со снимком.

Цель Саши (16.09, дословно по смыслу): при полном крахе работы с топиком — **подключить модуль → маршрутизация как была раньше**, без долгой починки по файлам. Экономия — минуты на apply+рестарт вместо расследования allowlist/токена/каталога.

### Границы модуля

Модуль восстанавливает **конфиг маршрутизации** (какие чаты слушать, какой бот поллит, какие thread_id каноничны, какие профили синхронизировать). Он **не** является:

- новым USERTOOL / пакетом Python в `~/USERTOOLS/`;
- новым скиллом (reuse `tutu-telegram-delivery`);
- роутером forum-сообщений внутри `adapter.py`;
- создателем топиков в Telegram (топики уже существуют в группе);
- постановщиком кронов и редактором `jobs.json`;
- хранилищем секретов (полный токен в снимок не пишется).

### Что хранит (снимок, без секретов)

| Слой | Поля снимка | Зачем |
|---|---|---|
| Группа / DM | `chat_id=-1004300127777`, `dm_chat_id=400307920` | allowlist inbound + deliver-адреса |
| Топики (канон Саши 16.09; Q1 вариант 1 + Q2) | **ровно 7:** General=1, Tools=3, WorkVault=5, Backlog=6, Monitoring=7, Errors=11112, Personal=8; **без** `:6556` и **без** Hermes DEV (`:4`, удалён давно) | единый каталог имён→`thread_id` |
| Allowlist | CSV `TELEGRAM_ALLOWED_CHATS` = `400307920,-1004300127777` | П.1б; обе копии `.env` |
| YAML extra | `telegram.allowed_chats` тот же CSV; `require_mention: false`; `guest_mode: false` | не побеждает env, но не должен разъехаться |
| Токен (идентичность, не секрет) | poller = env `TELEGRAM_BOT_TOKEN`, bot id prefix `863022`, username `sirene_vm_bot`; YAML `gateway.telegram.token` **должен совпасть** с этим значением (П.2) | dual-token мина ErrorBus №11 |
| Профили | список путей: `~/.hermes/.env`, `~/.hermes/profiles/default/.env` | обе копии, иначе default снова узкий |
| Startup notify | `TELEGRAM_ADDITIONAL_STARTUP_CHANNELS=-1004300127777:1` (General) | не allowlist; часть «как было» |
| Deliver-форма | `telegram:-1004300127777:<thread>` | канон для людей/скиллов; `jobs.json` этим проходом не переписывать |

Канон снимка — **ровно эти 7** топиков (Q1 вариант 1 + Q2, Саша 16.09). Топик `:6556` (Messages, mattermost-loop-api, 24.07.2026) в снимок **не входит** и остаётся только в `jobs.json` как есть; `apply`/`check` его не создают, не удаляют и не считают drift. Топик «Hermes DEV» (`:4`) в канон **не входит** (давно удалён в группе); `apply` его не создаёт.

Полный токен — только в `.env` (уже лежит). Снимок хранит **имя ключа** и **bot id prefix**, apply копирует значение env → YAML, не наоборот.

`channel_directory.json` и `sessions.json` — runtime, не источник истины, модуль их не восстанавливает.

### Единая точка входа

Одна команда из корня скилла (имена — ориентир для `HF:impl`, не код):

```
<skill>/scripts/restore_telegram_topics.sh  apply|check|dry-run
```

- `dry-run` — показать diff снимок vs диск, ничего не писать.
- `apply` — бэкап трёх файлов (`.env` ×2, `config.yaml`) → записать allowlist/YAML-extras/unify token → печать «нужен рестарт gateway».
- `check` — exit 0 только если диск = снимок (allowlist обеих копий, YAML `allowed_chats`, YAML-токен prefix = `863022`, каталог **ровно 7** топиков на месте). `jobs.json` не читает: `:6556` там — не drift.

Скилл `tutu-telegram-delivery` в шапке указывает **только эту** команду как способ восстановить маршрутизацию. Диагностический текст скилла (причины 1–3 тишины) остаётся, но фикс = apply, не ручной grep.

### Как модуль связан с П.1–П.5

| Срез v0.1.0 | Роль модуля |
|---|---|
| П.1б allowlist в обеих `.env` | **Поглощает и автоматизирует.** Это первый payload `apply`. |
| П.2 unify YAML-токена с poller | **Поглощает и автоматизирует.** `apply` копирует `TELEGRAM_BOT_TOKEN` → `gateway.telegram.token`. |
| П.3 WARNING в `adapter.py` | **Не поглощает.** Разовый патч кода ядра; скрипт конфиг не регенерирует. Остаётся П.5' этого плана. |
| П.4 409 / `drop_pending_updates` | **Документирует как запрет.** Скрипт не вызывает `getUpdates` и не меняет этот флаг. |
| П.5 список «не делать» | **Расширяет** (см. «Не делать лишнего»): плюс не плодить cron, не переписывать forum-роутинг, не ломать env-over-YAML. |

Итого: модуль — **снимок + применялка конфига** поверх уже принятого BUGFIX. Он не заменяет патч лога и не отменяет запреты. Повторный крах того же класса (узкий `.env` после апдейта ядра) лечится `apply` + рестарт, без нового расследования.

---

## Форма модуля (варианты)

| # | Форма | Плюсы | Минусы |
|---|---|---|---|
| **1** | Декларативный снимок (YAML без секретов) + скрипт `apply`/`check`/`dry-run` рядом со скиллом `tutu-telegram-delivery` | Одна точка входа; проверка машиночитаемая; reuse существующего скилла; нет новой сущности; `apply` закрывает П.1б+П.2 за секунды | Нужно держать скилл-таблицу зеркалом снимка (или генерировать таблицу из YAML) |
| 2 | Отдельный USERTOOL / пакет `TelegramGroupTopics` в `~/USERTOOLS/` | «Настоящий» модуль, тесты как у инструментов | Новая сущность (reuse-first: только с согласования Саши); избыточно для ~20 констант и записи трёх файлов; разъедется со скиллом |
| 3 | Только документированная константа/таблица в скилле (как сейчас `tutu-telegram-delivery` + кусок `hermes-gateway-setup`) | Уже есть, ноль кода | **Сегодняшний провал:** таблица не применяется. Починка снова руками по `.env`/`config.yaml`. Не выполняет «подключил → восстановилось» |

**Выбрано — вариант 1** (Саша финализирует этот план 16.09). Вариант 3 оставить как человекочитаемое зеркало (скилл читает/совпадает со снимком), не как механизм restore. Вариант 2 не предлагать, пока Саша явно не попросит отдельный USERTOOL.

Константа в смысле Саши = поля снимка (chat, thread_id, CSV allowlist, bot prefix). Скрипт = единственный способ подключить эту константу к диску.

---

## Принцип «подключил → восстановилось»

Что именно восстанавливается одним `apply` (после рестарта gateway):

1. Inbound группы: эффективный allowlist содержит `-1004300127777` (П.1б).
2. Poller = бот группы (`863022` / `sirene_vm_bot`), YAML-токен не `882117` (П.2).
3. YAML extras группы: `allowed_chats`, `require_mention: false` (как до 13:11).
4. Каталог 7 топиков доступен как константа (имена→thread_id) для людей и будущих читателей.
5. Startup-notify в General `:1` (ключ env, не гейт inbound).

Что **не** обещается одним подключением: ответы forum-хелпера, содержимое `sessions.json`, расписание кронов, членство бота в группе (это Telegram, не файл), создание отсутствующего топика в группе.

### Шаги восстановления (оператор, минуты)

1. `HF:backup` (или сам `apply`: копия трёх файлов в `~/.hermes/_Archives/hermes-backup-YYYYMMDD-HHMMSS/`).
2. `restore_telegram_topics.sh dry-run` — увидеть расхождение.
3. `restore_telegram_topics.sh apply`.
4. Рестарт gateway — **только** по «поднимай» / шагу `HF:impl`, скрипт сам gateway не трогает (инвариант `hermes-gateway-setup`: no cron restart).
5. `restore_telegram_topics.sh check` → exit 0.
6. Smoke: сообщение в топик Backlog `:6` без @mention → inbound в `gateway.log` + ответ в том же `message_thread_id`; DM `400307920` жив; опционально `sendMessage` в Errors `:11112` с `TELEGRAM_BOT_TOKEN` (`ok:true`).

Критерий «быстро»: apply+check без расследования файлов; рестарт — единственная пауза. Повторный инцидент класса 16.09 не требует нового `BUG:diagnose`, если `check` показывает узкий allowlist или чужой YAML-токен.

### Как проверяется

| Проверка | Ожидание |
|---|---|
| `check` | exit 0; иначе список drift (какой файл, какой ключ; без полного токена) |
| `getChatMember` poller-бота | member/administrator в `-1004300127777` |
| `gateway.log` | `inbound message: … chat=-1004300127777` после сообщения в топик |
| reply | тот же `message_thread_id` |
| ErrorBus-канон | Errors = `11112` в снимке совпадает с `ErrorBus_TZ` / `_db.py` (этот проход код ErrorBus не меняет) |

---

## Не делать лишнего (границы)

- Не переписывать forum-роутинг (`_effective_message_thread_id`, session keys, `group_sessions_per_user`).
- Не ломать env-over-YAML / `extra_or_secret` (`3dedb71f2f`). Не UNION yaml∪env.
- Не плодить cron (ни restore, ни restart gateway). `jobs.json` не редактировать этим планом (в т.ч. не трогать `:6556`).
- Не включать в снимок топики вне канона 7 имён (Q1 вариант 1 + Q2: без `:6556` / Messages и без Hermes DEV `:4`).
- Не новый USERTOOL / скилл / `HERMES_*`.
- Не класть полный токен в снимок, ТЗ, логи, git.
- Не использовать `TELEGRAM_ADDITIONAL_STARTUP_CHANNELS` как inbound-allowlist.
- Не переписывать ErrorBus / USERTOOLS hardcoded `:11112` в этом проходе (снимок обязан **совпадать** с ними; импорт снимка в ErrorBus — отдельная доработка).
- Не восстанавливать `channel_directory.json` / `sessions.json`.
- Не откатывать `drop_pending_updates`, prune, multiplex.
- Не вызывать `getUpdates` из скрипта (409).
- Gateway не рестартовать из `TZ:patch` / `TZ:finalize`.

---

## План П.1'–П.7' (для `HF:impl`, заменяет П.1–П.5 как очередь работ)

П.1–П.5 остаются спецификацией инцидента. Очередь реализации — эта нумерация.

### П.1' — канонический снимок

YAML (без секретов) в `~/.hermes/skills/devops/tutu-telegram-delivery/references/sirene-workspace-topics.yaml` (путь-ориентир): chat, DM, **ровно 7** топиков Саши (Q1 вариант 1 + Q2, без `:6556`, без Hermes DEV `:4`), CSV allowlist, bot prefix/username/имя env-ключа, список профилей `.env`, `require_mention`, startup-channels. `schema_version: "1.0"` внутри снимка. Выравнивание диска со спекой v0.3.0 — `HF:impl`, не этот `TZ:patch`.

### П.2' — единая точка входа (вариант 1)

Скрипт `apply|check|dry-run` в том же скилле. SKILL.md: команда restore в шапке; таблица топиков = зеркало снимка (не второй канон). После правки скилла — `restore-all-skills.sh` в `ORCH:shared-state`, не исполнителем.

### П.3' — `apply` поглощает П.1б + П.2

Пишет `TELEGRAM_ALLOWED_CHATS` в обе копии `.env`; выравнивает YAML `telegram.allowed_chats` и `require_mention`; копирует значение `TELEGRAM_BOT_TOKEN` в `gateway.telegram.token`. Остальные ключи `.env` не трогать. Перед записью — бэкап.

### П.4' — `check` / dry-run

Машиночитаемый drift. Инварианты: обе `.env` содержат группу; YAML-токен prefix `863022`; снимок содержит **ровно** канон 7 топиков (Q1 вариант 1 + Q2 — **без** `:6556`, **без** Hermes DEV `:4`). `check` не читает `jobs.json`: наличие `:6556` там не drift. Рестарт не входит в `check`.

### П.5' — WARNING на silent drop (бывший П.3)

Разовый патч `adapter.py`. Скрипт restore его не повторяет.

### П.6' — связь с каталогом и ErrorBus

Снимок Errors=11112 **должен** совпасть с ErrorBus решение №11 / `message_thread_id=11112`. Скилл `tutu-telegram-delivery` — человекочитаемый каталог. `hermes-gateway-setup` (таблица топиков без Errors) этим проходом не переписывать целиком: одна строка-указатель «канон — tutu-telegram-delivery / снимок», чтобы не плодить третий канон.

### П.7' — не делать

Объединяет бывшие П.4+П.5 и границы модуля выше. В том числе: forum, UNION, cron, `getUpdates`, правка `jobs.json`, новый пакет.

---

## Входные данные

- `~/.hermes/.env` и `~/.hermes/profiles/default/.env`: `TELEGRAM_ALLOWED_CHATS` (сейчас `400307920`), `TELEGRAM_BOT_TOKEN` (poller prefix `863022`), `TELEGRAM_ADDITIONAL_STARTUP_CHANNELS` (`-1004300127777:1`).
- `~/.hermes/config.yaml`: `telegram.allowed_chats` (группа уже есть), `telegram.require_mention: false`, `gateway.telegram.token` (prefix `882117`, не в группе).
- `~/hermes-agent/plugins/platforms/telegram/adapter.py`: `_gate_or_observe` / `_should_process_message`.
- Скилл `~/.hermes/skills/devops/tutu-telegram-delivery/SKILL.md` (каталог 7 топиков + dual-token; на диске v1.2.0 ещё зеркало v0.2.0 из 8 — выравнивание в `HF:impl`).
- ErrorBus: топик Errors `:11112`, решение №11 (токен).
- Диагноз (read-only): `~/hermes-agent/_fix_plan_20260916.md`.

## Выходные артефакты

- Снимок YAML (без секретов) + скрипт `apply|check|dry-run` внутри `tutu-telegram-delivery`.
- SKILL.md: единая команда restore; таблица топиков совпадает со снимком.
- Обе копии `.env`: `TELEGRAM_ALLOWED_CHATS=400307920,-1004300127777` (после `apply`).
- `config.yaml`: `gateway.telegram.token` = значение `TELEGRAM_BOT_TOKEN` (prefix `863022`; полный токен не в коммите/логе); `telegram.allowed_chats` выровнен со снимком.
- `adapter.py`: один WARNING на `(chat_id, thread_id)` при drop по allowlist (П.5').
- Бэкап: `~/.hermes/_Archives/hermes-backup-YYYYMMDD-HHMMSS/`.
- Тесты: инварианты DoD, green (temp `HERMES_HOME` + unit на `check`/`apply` без живого Telegram).
- Runtime после рестарта: inbound `chat=-1004300127777` в `gateway.log` + ответ в том же `message_thread_id`; DM без регрессии.

## Шаги реализации (атомарно, для `HF:impl`)

1. Бэкап трёх файлов (`~/.hermes/.env`, `~/.hermes/profiles/default/.env`, `~/.hermes/config.yaml`) → `~/.hermes/_Archives/hermes-backup-YYYYMMDD-HHMMSS/`.
2. П.1': записать снимок YAML (**ровно 7** топиков, без `:6556`, без Hermes DEV `:4`; allowlist, bot identity, профили, startup-channels). На диске после v0.2.0 — ещё 8 имён; вычеркнуть Hermes DEV в `HF:impl` v0.3.0.
3. П.2': скрипт `dry-run|apply|check`; точка входа в SKILL.md; таблица скилла = зеркало снимка.
4. П.3': прогнать `apply` (или эквивалент тех же записей) — allowlist обе `.env` + unify token + YAML extras.
5. П.5': в `adapter.py` (`_gate_or_observe`) — один WARNING на drop по allowlist.
6. Юнит-тесты: env-over-YAML (узкий env → group False); после apply/снимка group True; `check` exit≠0 на узком allowlist; `check` не печатает полный токен.
7. Рестарт gateway (явный шаг `HF:impl` / «поднимай», не из `TZ:finalize`, не из скрипта).
8. E2E: сообщение в топик `:6` без @mention → inbound в логе + ответ в том же `message_thread_id`; проверка DM `400307920`; `check` exit 0.
9. `ORCH:shared-state`: `restore-all-skills.sh` после правки скилла (не исполнитель).

## Definition of done

**Инцидент 16.09 (как v0.1.0):**

- В `gateway.log` после сообщения в топик группы: `inbound message: … chat=-1004300127777`.
- Ответ уходит в тот же `message_thread_id`.
- DM `400307920` без регрессии.
- `getChatMember` poller-бота в группе = member/administrator.
- На drop по allowlist (если воспроизвести узкий env) — WARNING, не тишина.

**Модуль восстановления (v0.2.0, канон топиков v0.3.0):**

- Существует одна команда `apply|check|dry-run`; в скилле нет второго «ручного» канона, расходящегося со снимком.
- `apply` на заведомо узком allowlist восстанавливает CSV с группой в **обеих** копиях `.env` и выравнивает YAML-токен на prefix `863022`.
- `check` exit 0 на совпадении; exit ≠0 и список ключей при drift; полный токен в выводе отсутствует.
- Снимок содержит канон **ровно 7** топиков: General=1, Tools=3, WorkVault=5, Backlog=6, Monitoring=7, Errors=11112, Personal=8.
- Снимок **не** содержит `:6556`; `check` не трактует `:6556` в `jobs.json` как drift.
- Снимок **не** содержит Hermes DEV (`:4`); топик давно удалён в группе; `apply` его не создаёт.
- Errors=11112 в снимке совпадает с ErrorBus.
- Повторный restore того же класса не требует правок forum-кода и не создаёт cron.
- Выравнивание yaml/скрипт/skills со спекой v0.3.0 — очередь `HF:impl` (2026-09-16, следующий цикл), не этот `TZ:patch`.

Тесты (инварианты, не change-detector; temp `HERMES_HOME`, реальный `load_gateway_config` + adapter, без мока `extra_or_secret`):

- Env `TELEGRAM_ALLOWED_CHATS=400307920` + YAML extra с группой → `_should_process_message` для supergroup `-100…` is False, для private is True (контракт env-over-YAML).
- После П.3' (env с группой) → group True.
- `check` на фикстуре узкого `.env` → non-zero; после `apply` по той же фикстуре → zero.

E2E ручной: сообщение в топик `:6` без @mention → inbound в логе и ответ в том же `message_thread_id`.

## Что НЕ трогать

- Контракт env-over-YAML / `extra_or_secret` (`3dedb71f2f`).
- Forum helpers, session prune, multiplex.
- `drop_pending_updates` на 409; ручной `getUpdates` на токене poller.
- USERTOOLS, кроны, `jobs.json` (включая `:6556` / Messages — не в снимок, не удалять, не «вычищать»), код ErrorBus (кроме сверки канона `:11112`).
- Gateway из фаз `TZ:*`.
- Полные токены в ТЗ/логах/снимке/коммитах (только bot id prefix).
- `channel_directory.json` / `sessions.json` как «бэкап топиков».

## Связи с экосистемой

| Что | Связь |
|---|---|
| `~/hermes-agent` | код адаптера / allowlist / dual-token (П.5', П.3') |
| KanbanCore hardening | тот же класс: патч ядра, не USERTOOL; там post-hoc без ТЗ-файла |
| ErrorBus | dual-token решение №11; канон топика Errors `-1004300127777:11112`; прямая HTTP-отправка `TELEGRAM_BOT_TOKEN` (не `deliver`) |
| `tutu-telegram-delivery` | **дом модуля**: каталог 7 топиков, правило «группа = `TELEGRAM_BOT_TOKEN`», диагностика тишины; сюда же снимок+скрипт |
| `hermes-gateway-setup` | дубль таблицы топиков **без Errors**; YAML extras группы; запрет cron-рестарта gateway; startup-channels `:1` |
| `config.yaml` `telegram.allowed_chats` | уже содержит группу; после env-over-YAML не побеждает, пока ключ в `.env` узкий |
| Сирень Workspace `-1004300127777` | группа + топики; `require_mention: false` — как до 13:11 |
| `jobs.json` `deliver` | потребители thread_id (`:6` Backlog, `:7` Monitoring, `:11112` Errors, `:6556` Messages и др.); **не** переписываются модулем; `:6556` не в снимке (Q1 вариант 1) |
| `channel_directory.json` | runtime-зеркало сессий, не канон |

## Контракты экосистемы

### Источник истины

- Владелец allowlist **гейта inbound** после `3dedb71f2f`: env `TELEGRAM_ALLOWED_CHATS`, если ключ задан и непустой; иначе YAML `telegram.allowed_chats`.
- Владелец poller-токена при живом `.env`: `TELEGRAM_BOT_TOKEN` (перезаписывает `PlatformConfig.token`).
- Владелец **каталога топиков** после v0.3.0: снимок модуля (`schema_version` внутри YAML). Скилл `tutu-telegram-delivery` — человекочитаемое зеркало. ErrorBus остаётся владельцем своего канала доставки в `:11112` (код шины не подчиняется снимку, снимок обязан совпасть).

### Входные контракты

| Поле | Тип | Обязательность | Источник (кто отдаёт) | Формат/enum |
|---|---|---|---|---|
| TELEGRAM_ALLOWED_CHATS | str | optional | `~/.hermes/.env` / `profiles/default/.env` | CSV chat_id, без пробелов; непустой → YAML extra не читается |
| telegram.allowed_chats | str | optional | `~/.hermes/config.yaml` | CSV chat_id; действует только если env-ключ отсутствует/пуст |
| TELEGRAM_BOT_TOKEN | str | required | `~/.hermes/.env` | токен poller; bot id `863022…` (sirene, admin группы) |
| gateway.telegram.token | str | optional | `~/.hermes/config.yaml` | YAML-токен; после П.3' = тот же, что env; сейчас `882117…` (не в группе) |
| TELEGRAM_ADDITIONAL_STARTUP_CHANNELS | str | optional | `~/.hermes/.env` | `chat_id:thread_id`; сейчас `-1004300127777:1`; не allowlist |
| snapshot.chat_id | str | required | снимок модуля | `-1004300127777` |
| snapshot.dm_chat_id | str | required | снимок модуля | `400307920` |
| snapshot.topics | enum[General,Tools,WorkVault,Backlog,Monitoring,Errors,Personal] | required | снимок модуля | ровно 7 имён→thread_id: 1,3,5,6,7,11112,8; **без** `:6556` (Q1 вариант 1) и **без** Hermes DEV `:4` (Q2) |
| snapshot.schema_version | str | required | снимок модуля | semver внутри YAML, старт `"1.0"` |

### Выходные контракты

| Поле | Тип | Потребитель (кто получает) | Формат/enum |
|---|---|---|---|
| inbound group pass/drop | bool | TelegramAdapter `_should_process_message` | True только если `chat_id` в эффективном allowlist; DM гейт чата не проходит |
| drop WARNING | str | `gateway.log` (после П.5') | один WARNING на `(chat_id, thread_id)`; без полного токена |
| inbound log line | str | оператор / DoD | после pass: `inbound message: … chat=-1004300127777` |
| reply thread | int | топик группы Telegram | тот же `message_thread_id`, что у inbound |
| restore check exit | int | оператор / DoD модуля | 0 = диск совпал со снимком; иначе drift |
| deliver target | str | скилл / люди (не jobs.json этим проходом) | `telegram:-1004300127777:<thread>` |

### Зависимости

- Получает от: [конфиг/env Hermes, Telegram Bot API getUpdates, скилл tutu-telegram-delivery как дом модуля]
- Отдаёт: [сессии топиков группы, ErrorBus-топик как один из потребителей inbound, каталог thread_id для скиллов]

### Breaking changes policy

- Контракт env-over-YAML не менять этим планом.
- П.3' синхронизирует env с YAML; при будущем сужении списка — править **снимок**, затем `apply` (править env руками — путь к новому drift).
- Версия формата снимка: `schema_version` внутри YAML, не версия этого ТЗ. Breaking change каталога (смена thread_id) → bump `schema_version`, обновить зеркало скилла, сверить ErrorBus.

### Границы («что НЕ трогать»)

- Не UNION yaml∪env.
- Не использовать `TELEGRAM_ADDITIONAL_STARTUP_CHANNELS` как allowlist.
- Не откатывать `3dedb71f2f`.
- Не писать полный токен в снимок.
- Не менять `jobs.json` и код ErrorBus в этом проходе.
- Не включать `:6556` (Messages) в снимок.
- Не включать Hermes DEV (`:4`) в снимок (Q2; топик давно удалён).

## Риски

| Риск | Комментарий |
|---|---|
| П.1 / `apply` включает ответы во **все** топики группы | `require_mention: false` — так было до 13:11. Узкий набор топиков — `allowed_topics` / `free_response_topics`, отдельное решение. |
| Узкий `.env` снова разъедется с YAML | Пока ключ задан, env всегда победит. `check` ловит drift; `apply` чинит обе копии. |
| Dual-token | Исчезновение `TELEGRAM_BOT_TOKEN` из процесса → poller `882117` → группа снова невидима даже с широким allowlist. Снимается П.3'. |
| 409 + drop_pending | Кратковременная потеря очереди; не путать с этим багом. Скрипт `getUpdates` не вызывает. |
| Два канона (скилл vs снимок) | П.2'/П.6': таблица скилла = зеркало; третий канон в `hermes-gateway-setup` не расширять. |
| Топик вне канона (`:6556` Messages в `jobs.json`) | **Q1 вариант 1 (закрыт):** не в снимке. `apply`/`check` не трогают `jobs.json`; `:6556` остаётся как есть. |
| Топик «Hermes DEV» (`:4`) в yaml/скилле после v0.3.0 | Спека уже 7; диск до `HF:impl` ещё 8. `check` по старому снимку не ловит drift «лишний :4». Очередь `HF:impl` следующего цикла. |
| «Подключил модуль» без рестарта | dotenv/YAML читаются на старте процесса — без «поднимай» inbound не оживёт. Скрипт обязан печатать этот факт, не рестартовать сам. |

## Решённые вопросы (TZ:finalize 2026-09-16, Q2 — TZ:patch 2026-09-16)

Открытых вопросов нет.

**Q1. Включать ли топик `:6556` (Messages) в снимок модуля?** **Закрыт 16.09.2026 — вариант 1 (Саша).** В `jobs.json` / `channel_directory.json` есть топик `:6556` (скилл mattermost-loop-api: «Messages», 24.07.2026), которого нет в каноне Саши 16.09. Решение: **не включать**. Снимок = ровно 7 топиков канона: General=1, Tools=3, WorkVault=5, Backlog=6, Monitoring=7, Errors=11112, Personal=8 (счётчик и состав — Q2). `:6556` остаётся только в `jobs.json` как есть. `apply`/`check` не создают, не удаляют и не считают `:6556` drift. Расширение каталога — отдельный `TZ:patch`.

Варианты, которые **не** выбраны: (2) extra outbound-only `Messages=6556`; (3) отдельно выяснять, жив ли топик, и вычищать `deliver` позже.

**Q2. Исключить ли «Hermes DEV» (`:4`) из канона снимка?** **Закрыт 16.09.2026 — TZ:patch v0.3.0 (Саша).** Топик давно удалён в группе «Сирень Workspace». Канон = **ровно 7** (General=1, Tools=3, WorkVault=5, Backlog=6, Monitoring=7, Errors=11112, Personal=8). Q1 (без `:6556`) не отменяется. Реализация в yaml / скрипт / skills — `HF:impl` следующего цикла (2026-09-16), не этот `TZ:patch`.

Прочие развилки закрыты этим текстом: форма модуля = вариант 1; П.1б+П.2 поглощаются `apply`; П.3 кода остаётся разовым; env-over-YAML / forum / cron — запреты.

## Статус

`approved` — `TZ:patch` v0.3.0 2026-09-16. Q1 без `:6556` держится; Q2: канон=7, «Hermes DEV» (`:4`) удалён давно. Открытых вопросов нет. Спека yaml/скрипт/skills до `HF:impl` следующего цикла — согласование ≠ реализация. Поставка модуля v0.2.0 — §Реализация ниже.

---

## Реализация (HF:docs-handoff, 16.09.2026)

**Зафиксировано после `HF:impl` / `HF:test` / live `apply` 16.09.** Версия master-ТЗ на тот момент — **0.2.0** (инфра-план); bump только у скилла.

| Пункт | Факт |
|---|---|
| Скилл `tutu-telegram-delivery` | **v1.2.0** — `~/.hermes/skills/devops/tutu-telegram-delivery/SKILL.md` |
| Снимок | `references/sirene-workspace-topics.yaml` — 8 топиков (поставка v0.2.0), `schema_version: "1.0"`, без `:6556` |
| Точка входа | `scripts/restore_telegram_topics.sh` → `apply\|check\|dry-run` |
| Ядро | `~/hermes-agent/plugins/platforms/telegram/adapter.py` — WARNING на silent allowlist-drop группы (П.5') |
| Тесты ядра | `tests/plugins/platforms/telegram/test_allowlist_env_over_yaml.py` |
| Тесты скрипта | `~/.hermes/skills/devops/tutu-telegram-delivery/tests/test_restore_telegram_topics.py` |
| Runtime | `.env` (обе копии) + `config.yaml` выровнены через `apply`; рестарт gateway — отдельно по «поднимай» |
| Указатель gateway-setup | одна строка под «Топики Сирень Workspace» → снимок / restore (таблица 7 строк без Errors не расширялась) |

**Вне этой фазы (ORCH:shared-state):** `EcosystemManifest.json`, `restore-all-skills.sh`, digest. **`jobs.json` / ErrorBus-код не менялись** (`:6556` Messages остаётся только в jobs).

---

## Патч v0.3.0 (TZ:patch, 2026-09-16) — канон 7 топиков

**Вводная Саши:** топик «Hermes DEV» (`:4`) давно удалён в группе «Сирень Workspace». Канон снимка: **ровно 7** — General=1, Tools=3, WorkVault=5, Backlog=6, Monitoring=7, Errors=11112, Personal=8. Q1 (без `:6556`) не отменяется.

**Эта фаза пишет только** `TelegramGroupTopics_TZ.md` + строку в `MAIN_TZ_INVENTORY.md`. Новая сущность **не** заводится: модуль остаётся внутри `tutu-telegram-delivery`.

**Не в этой фазе (очередь `HF:impl`, 2026-09-16, следующий цикл):** `references/sirene-workspace-topics.yaml`, `restore_telegram_topics.py` / `.sh`, `SKILL.md`, `hermes-gateway-setup`, `jobs.json`, `.env` / `config.yaml`, `adapter.py`. На диске после поставки v0.2.0 снимок ещё содержит 8 имён, включая Hermes DEV — drift относительно этой спеки до `HF:impl`.

**Для `HF:impl`:** вычеркнуть Hermes DEV из YAML-снимка и зеркала скилла; `check`/`apply`/тесты — канон **ровно 7**; `apply` не создаёт топик `:4` в Telegram; bump `schema_version` снимка — по правилу breaking change каталога (§Контракты). Forum / env-over-YAML / cron / `jobs.json` / ErrorBus-код — по-прежнему не трогать.