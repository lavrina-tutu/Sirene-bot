---
name: fireflies-obsidian-sync
description: "Синхронизация встреч Fireflies.ai → Obsidian WorkVault: инструмент MoveFromFF (Python, GraphQL API, cron, pipeline)."
version: 2.0.0
author: agent
tags: [fireflies, obsidian, sync, meetings, python, workvault, graphql, pipeline]
platforms: [windows]
---

# Fireflies → Obsidian Sync (MoveFromFF)

Инструмент автоматической синхронизации записей встреч из Fireflies.ai в локальный Obsidian vault (`WorkVault`). Является **поставщиком** данных для конвейера обработки встреч.

## Контекст

- **Пользователь:** tkachenkoav (Александр Ткаченко, ТУТУ)
- **Тариф Fireflies:** Pro (нет webhooks, есть AI-саммари и action items)
- **Vault:** `C:\Users\tkachenkoav\WorkVault`
- **Папка назначения:** `WorkVault/Meetings/NewMeetings/` — входная точка конвейера

## Архитектурный принцип (v2.0)

MoveFromFF — **минимальный транспорт**: скачать 2 файла на встречу, не тянуть повторно уже загруженные. Никакой постобработки — это зона следующих инструментов.

**Что входит:** **2 файла** (transcript/summary), `_registry.json` (идемпотентность), `_registry.md` (рендер из JSON через Jinja2 без запросов к FF), статусная машина: `pending/completed/error`. TG-алерт **только при `--mode manual`**; cron молчит.

**actions.md — НЕ скачиваем** (финальное решение, май 2026): дублирует `action_items` из `summary.md`, нулевая добавленная ценность. Убрано из ТЗ v2.0, кода, шаблонов и структуры проекта.

**Код v2.0 написан и работает** (май 2026). Проект: `C:/Users/tkachenkoav/Documents/Cursor_projects/MoveFromFF/`. 48/48 тестов ✅. Крон: пн–пт 10:00/12:00/14:00/16:00/18:00/20:00 МСК (job_id: 1e62e18ae399). Загружено 439 встреч (авг 2025 – май 2026). Два бага исправлены после QA: Speaker N хардкод заменён на `speaker_label(sentence, speaker_map)` через `build_speaker_map()`; убран `.lower()` на participants (ТЗ: "как есть из FF"). Добавлен флаг `--meeting-id` для скачивания одной конкретной встречи по ID.

**Что НЕ входит:** SHA-256, reconciler, actions.md, поля постобработки (`moved_by`, `processing_status`), `--mode deleted-check`.

## ⚠️ Критически важно: API — GraphQL, не REST

Fireflies использует **GraphQL API**:
- **Эндпоинт:** `https://api.fireflies.ai/graphql` (POST)
- **Не** `/v1/meetings` — это распространённое заблуждение
- **Аутентификация:** `Authorization: Bearer <API_KEY>`
- Проверка доступности: `query { user { user_id email } }` (не GET-пинг)

## Когда запускается

1. При запуске Windows (Scheduled Task, триггер `At log on`)
2. Каждые 4 часа работы компьютера (Hermes cron `every 4h`)
3. По команде в Telegram: `обнови fireflies` или `обнови ff` (регистронезависимо)
4. Все три точки входа вызывают один CLI: `python -m movefromff.sync [--source auto|cron|tg]`

## Файловая структура

```
WorkVault/
└── Meetings/
    ├── _registry.json       ← машиночитаемый реестр (источник истины, схема v1)
    ├── _registry.md         ← авто-генерация из JSON для Obsidian (не редактировать)
    ├── _log.md              ← краткий лог (append-only, ротация при >1MB)
    ├── _last_sync.txt       ← ISO 8601 UTC
    ├── _pending_ff.json     ← встречи в статусе Processing на стороне FF
    ├── _sync.lock           ← {pid, started_at, source}
    └── NewMeetings/         ← необработанные встречи (вход конвейера)
        ├── 2026-05-22 14-30 Название - transcript.md
        ├── 2026-05-22 14-30 Название - summary.md
        └── 2026-05-22 14-30 Название - actions.md
```

## Алгоритм (каждый запуск)

**Шаг 0 — Preflight:**
- Создать `_sync.lock` с `{pid, started_at, source}`
- Если lock жив → выйти (`BUSY`). Если lock старше 30 мин (stale) → перезаписать
- Проверить `.env` и `FIREFLIES_API_KEY`. Нет ключа → алерт в TG + выход

**Шаг 1 — Проверка доступности FF:**
- GraphQL `query { user { user_id } }`, таймаут 15с
- Недоступен → лог + выход. TG-алерт **только при ручном запуске** (не спамить из cron)

**Шаг 2 — Загрузка новых встреч (v2.0):**
- GraphQL list-запрос с **лёгкими полями** (`id, title, date, duration, participants`), пагинация limit=50
- Идемпотентность: пропустить `meeting.id` уже в реестре со `status = completed`
- Для каждой **новой** встречи — отдельный `fetch_meeting(id)` с полными полями (transcript, summary, actions)
- Создать 3 файла (`transcript.md`, `summary.md`, `actions.md`), атомарная запись: `tmp + os.replace`
- ⚠️ **Не** тянуть тяжёлые поля в list-запросе — FF молча возвращает `[]` при превышении cost-лимита

**Шаг 4 — Обновление реестра и логов:**
- Реестр обновляется атомарно: загрузить → изменить в памяти → `_registry.json.tmp` → `os.replace`
- File-lock на `_registry.json` через `portalocker` при совместном доступе с агентом
- Сгенерировать `_registry.md`, обновить `_last_sync.txt`, дописать в `_log.md`
- Снять `_sync.lock`

## Реестр `_registry.json` (схема v2.1 — актуальная)

```json
{
  "schema_version": "2.1",
  "updated_at": "2026-05-25T14:30:00Z",
  "last_synced_at": "2026-05-25T14:30:00Z",
  "meetings": {
    "<meeting_id>": {
      "title": "Встреча с клиентом",
      "meeting_date": "2026-05-20T11:30:00Z",
      "duration_minutes": 47,
      "participants": ["a@tutu.ru", "b@example.com"],
      "files": {
        "transcript": "2026-05-20 11-30-00 Встреча - transcript.md",
        "summary":    "2026-05-20 11-30-00 Встреча - summary.md"
      },
      "status": "completed",
      "fetched_at": "2026-05-23T14:30:05Z",
      "first_seen_at": "2026-05-23T14:30:00Z",
      "attempts": 0,
      "next_retry_at": null
    }
  }
}
```

**Новые поля v2.1:**
- `Registry.last_synced_at` — UTC метка конца последнего успешного окна; используется для умного окна cron вместо фиксированных -4.5ч
- `MeetingRecord.attempts` — счётчик попыток `fetch_meeting(id)` для pending-встречи
- `MeetingRecord.first_seen_at` — когда встреча впервые появилась в `fetch_range()`

**Правила:**
- Все даты — UTC ISO-8601 с `Z`
- `files` содержит только `transcript` и `summary` (actions убран в v2.0)
- `status` ∈ {`pending`, `completed`, `error`, `stale`} — `stale` терминальный, синк прекращается
- `participants` — список email как есть из FF (без `.lower()`)
- `meeting_id` — ключ объекта, внутрь не дублировать
- Миграция v2.0 → v2.1 автоматическая (новые поля с дефолтами, `extra="ignore"` в Pydantic)

**Поля v1.0 убраны:** `transfer_status`, `integrity`, `source`, `processing_status`, `moved_by`, `moved_at`, `moved_to`, `errors`, `sha256`, `audio_url`, `last_checked_at`, `keywords`

```json
{
  "version": 1,
  "last_sync_utc": "2026-05-22T11:00:00Z",
  "meetings": {
    "<ff_id>": {
      "id": "<ff_id>",
      "date_local": "2026-05-22T14:30:00+03:00",
      "date_utc": "2026-05-22T11:30:00Z",
      "title": "Встреча по проекту X",
      "participants": ["a@x.ru"],
      "duration_min": 47,
      "files": {
        "transcript": "NewMeetings/2026-05-22 14-30 ... - transcript.md",
        "summary": "...",
        "actions": "..."
      },
      "checksums": {
        "transcript": "sha256:...",
        "summary": "sha256:...",
        "actions": "sha256:..."
      },
      "transfer_status": "transferred",
      "processing_status": "pending",
      "agent": null,
      "first_seen_utc": "...",
      "last_updated_utc": "..."
    }
  }
}
```

**Статусы переноса:** `pending` / `transferred` / `error` / `restored`
**Статусы обработки:** `pending` / `in_progress` / `done` / `error`

## Содержимое файлов — решения из брифа

- **Формат**: минимальная конвертация JSON → Markdown для читаемости в Obsidian, без обработки смысла
- **Принцип**: брать всё что отдаёт FF API без предобработки содержания
- **YAML-frontmatter**: НЕ добавлять в MoveFromFF — вся разметка/обработка в отдельном инструменте (следующее ТЗ)
- **Транскрипт**: полный текст с таймкодами и спикерами как есть из FF
- **Саммари**: AI-саммари из FF как есть
- **Actions**: action items из FF как есть

## YAML-frontmatter файлов

> ⚠️ Frontmatter НЕ добавляется в MoveFromFF. Разметка для Obsidian (теги, Dataview) — задача отдельного инструмента-разметчика (следующее ТЗ).

Если всё же потребуется в будущем:
```yaml
---
ff_id: "01J..."
date: 2026-05-22T14:30:00+03:00
title: "Встреча по проекту X"
participants: ["a@x.ru", "b@x.ru"]
duration_min: 47
kind: transcript        # transcript | summary | actions
source: fireflies
processing_status: pending
---
```

## Лог `_log.md` (формат)

```markdown
## 2026-05-22 09:00 (cron) — Синхронизация
- FF: ✅ доступен (ping 142 ms)
- Целостность: проверено 6, восстановлено 0
- Новых встреч: 2, файлов записано: 6
- Pending в FF: 1 (id=01J…)
- Ошибок: 0
- Длительность: 8.3 s
```

## Именование файлов

Формат: `YYYY-MM-DD HH-MM-SS <Title> - <kind>.md` — с секундами если FF отдаёт, всё что отдаёт API без предобработки. Время обязательно — возможны 2+ встречи в день.
- Sanitize: `\ / : * ? " < > |` → `-`, trim пробелов
- Ограничение длины: max 180 символов (запас до MAX_PATH=260 на Windows)
- Дубликаты `date+title` → суффикс ` (ff_id_last6)` перед ` - kind.md`
- Пустое название → `YYYY-MM-DD HH-MM Встреча [ID]`

## Технический стек

- Python 3.11+
- `requests` — HTTP/GraphQL
- `tenacity` — retry с backoff
- `portalocker` — file-lock на реестр
- `python-dotenv` — `.env`
- `jinja2` — рендер `_registry.md`
- `pydantic` v2 — валидация реестра
- `hashlib` SHA-256 — чексуммы

## .env конфигурация

```
FIREFLIES_API_KEY=<Bearer Token из Settings → Developer>
WORKVAULT_PATH=C:\Users\tkachenkoav\WorkVault
TG_ALERT_CHAT_ID=400307920
```

## Обработка ошибок API

| Код | Действие |
|---|---|
| 200 + GraphQL `errors[]` | Лог как ошибка, retry если transient |
| 401/403 | Стоп + TG-алерт «проверь токен» |
| 404 на конкретной встрече | Лог, `transfer_status = error`, продолжить остальные |
| 429 | Backoff 60→120→240с, max 3 попытки |
| 5xx / timeout | Retry 3 раза (5, 15, 45с), затем лог + выход |

## Решение: что качать из Fireflies и зачем

**Итог диалога (май 2026) — принято решение:**

| Файл | Ценность | Решение |
|---|---|---|
| `summary.md` | Структурирован FF AI, компактный (~3KB/22мин), ФИО полные, таски атрибутированы | ✅ **Основной рабочий материал конвейера** |
| `transcript.md` | Полный текст с таймкодами и спикерами, ~31KB/22мин | ✅ **Архив** — хранить, использовать точечно ("что именно было сказано про X") |
| `actions.md` | Дословная копия раздела Action Items из summary | ❌ **Дубликат** — **ФИНАЛЬНОЕ РЕШЕНИЕ: не скачивать, не генерировать** (зафиксировано май 2026). Нужно убрать из ТЗ v2.0: алгоритм, схема `files` реестра, шаблон `actions.md.j2`. |

**Код MoveFromFF v2.0 написан и работает** (май 2026). Проект: `C:/Users/tkachenkoav/Documents/Cursor_projects/MoveFromFF/`. 42/42 тестов проходят. `--mode test --dry-run` — exit 0.

**Почему actions.md избыточен:** FF дублирует action items в summary. Отдельный файл не несёт добавленной ценности. Таски из FF в любом случае сырые и привязаны к неправильным сущностям — это не проблема файла, а проблема отсутствия контекста (Exchange GAL).

**Почему не обрабатывать транскрипт напрямую:** часовая встреча = 15-20K токенов. При 24/7 записи (целевой режим) — неприемлемые расходы на Opus. Fireflies уже выполнил STT — это его ценность. Качественный анализ смысла — задача Opus поверх summary + Exchange contacts.

**Решение (зафиксировано 22 мая 2026):** actions.md — дубликат раздела Action Items из summary. Отдельный файл не несёт добавленной ценности. Рассмотреть отказ от скачивания (задача в бэклоге, код заморожен до финализации ТЗ).

**Роль Fireflies — только STT.** Саммари и таски от FF — черновик, не финал. Обработка смысла — задача Opus поверх summary + Exchange GAL. Не просить FF делать "умный" анализ — это неэффективно без знания оргструктуры.

**Целевая модель работы FF:**
```
Fireflies 24/7 → STT + черновой summary (дёшево, в объёме)
     ↓ MoveFromFF
summary.md + transcript.md (actions.md — под вопросом, см. бэклог)
     ↓ Entity Resolver (Exchange GAL)
Правильная атрибуция людей и проектов
     ↓ Opus (по запросу или для важных встреч)
Качественный анализ конкретной встречи
```

## Исправленные баги в v2.0 (код)

**Баг 1 — Speaker N хардкод** (`transcript.md.j2` + `renderer.py`):
- Было: `Speaker 1` жёстко прописан в шаблоне
- Стало: `renderer.py` вычисляет `speaker_map = build_speaker_map(meeting.sentences)`, передаёт в Jinja2 контекст; шаблон использует `{{ speaker_label(sentence, speaker_map) }}`
- Функции `build_speaker_map()` и `speaker_label()` уже были в `ff_schema.py` — просто не подключались

**Баг 2 — lowercase нормализация participants** (`ff_schema.py`):
- Было: метод `_participants_clean` делал `.lower()` на все email
- Стало: `.strip()` без `.lower()` — email хранится как отдаёт FF
- Причина: ТЗ §2 требует "participants (как есть)", данные из FF не редактируются
- Важно для резолва через MoveFromExchange: ключ contacts.enc — email как есть

## Интеграция с MoveFromExchange (contacts)

MoveFromFF хранит в `_registry.json` поле `participants` — список email участников встречи (как отдаёт FF, без нормализации).

**MoveFromFF НЕ делает резолв** email → ФИО — это задача MarkObjectsFromSummary.

Контракт: если `contacts.enc` (MoveFromExchange) доступен, downstream-инструменты читают его через `crypto.py` для обогащения данных встреч.

- Читает файлы из `NewMeetings/`
- Берёт file-lock на `_registry.json` перед изменением
- Меняет только: `processing_status`, `agent`, `last_updated_utc`
- Сам перемещает файлы из `NewMeetings/` после обработки
- Не удаляет записи из реестра — только меняет статус

## Режимы загрузки (решения из брифа)

| Режим | Описание |
|---|---|
| Тестовый (`--mode test`) | Последние 5 дней |
| Штатный (`--mode cron`) | Новые встречи новее `_last_sync - 24h` каждые 4ч |
| Ручной по интервалу (`--mode manual --from-date ... --to-date ...`) | Первоначальная полная загрузка блоками |
| По команде TG | `обнови fireflies` / `обнови ff` — запускает `--mode manual` |
| Только реконсиляция (`--reconcile-only`) | Сверка диск ↔ реестр без обращения к FF |

Удаление файлов из папки — **вручную через проводник Windows**, скрипт не удаляет.

## Финальные решения из брифа (Q1-Q7)

- **Q1. Таймзона:** брать из данных FF как есть, без преобразований
- **Q2. Следующий агент:** `MarkObjectsFromSummary` — заполняет `moved_by.agent` в реестре
- **Q3. Запуск по расписанию:** Hermes cron (для будущего переноса на VM Ubuntu)
- **Q4. TG-команды:** через Hermes Agent (единый чат), не отдельный бот
- **Q5. Ошибка одной встречи:** лог `transfer_status=failed`, продолжить остальные; при следующем запуске повторить попытку
- **Q6. deleted_in_ff:** проверять за последние 90 дней раз в месяц отдельным Hermes cron; локальные файлы не трогать
- **Q7. Реальная схема FF API:** `participants` = `[String]` (НЕ объект), `date` = Unix ms, `audio_url` = null на Pro, `summary.action_items` = строка; см. `references/fireflies-api.md`

## CLI (v2.0)

```bash
# Стандартные режимы
python -m movefromff --mode test                              # последние 5 дней, без TG
python -m movefromff --mode cron                             # последние 4ч 30мин, без TG
python -m movefromff --mode manual --from-date 2026-01-01 --to-date 2026-01-31
python -m movefromff --mode manual --from-date 2026-01-01 --to-date 2026-01-31 --dry-run

# Скачать одну конкретную встречу по ID (только с --mode manual)
python -m movefromff --mode manual --meeting-id <meeting_id>
# Пример: когда MoveFromConfluence хочет опубликовать summary встречи которой нет в NewMeetings/

# Флаги
--dry-run    # план без записи
--no-tg      # отключить TG-алерт (ручной режим без TG, для отладки)
--verbose    # DEBUG лог
```

**`--meeting-id`:** работает только с `--mode manual`. При использовании с `--mode cron` или `--mode test` → exit 2. `from-date`/`to-date` при наличии `--meeting-id` игнорируются.

## Сканирование папки при старте

При каждой проверке доступности FF — сканировать `NewMeetings/` и обновлять реестр:
- Файл в папке, но нет в реестре: если похож на файл FF по содержанию → добавить с `source=manual`
- Файл в реестре, нет в папке, `processing_status=pending` → восстановить из FF
- Файл в реестре, нет в папке, `processing_status ∈ {in_progress, done}` → агент унёс, не восстанавливать

## TG-алерты (правила)

| Триггер | Действие |
|---|---|
| Ручной запуск (`обнови ff`) | Прислать итог + ошибки в TG |
| Автозапуск Windows | Только лог, без TG |
| Cron каждые 4ч | Только лог, без TG |
| Ошибка при автозапуске/cron | Алерт в TG (ошибки всегда алертить) |

## Реестр — дополнительные поля (из брифа)

- `source`: `fireflies` / `manual` (файл добавлен вручную)
- `deleted_in_ff`: `true` / `null` — встреча удалена в FF, локальный файл не трогать
- `moved_by`: имя агента, который унёс файл из NewMeetings
- `moved_at`: ISO 8601 UTC
- `moved_to`: путь куда агент переложил файл (если известен)
- История статусов — **не хранится**, только текущий статус

## MoveFromFF v2.0 — минимальная архитектура

ТЗ v2.0: `WorkVault/Hermes-Backlog/MoveFromFF_TZ_v2.0_minimal.md`

**Что исключено из v1.0:**
- SHA-256 чексуммы и `hashing.py`
- `reconciler.py` — сверка диск ↔ реестр
- Поля постобработки: `processing_status`, `moved_by`, `moved_at`, `moved_to`
- `--mode deleted-check`, `--reconcile-only`
- YAML-frontmatter в файлах встреч

**Что осталось:**
- 3 файла на встречу: `transcript.md / summary.md / actions.md`
- `_registry.json` — 7 полей, статусная машина: `pending / completed / error`
- `_registry.md` — генерируется из JSON через `renderer.py` + Jinja2, без запросов к FF
- 3 режима CLI: `test` / `cron` / `manual --from-date --to-date`
- TG-алерт **только при `--mode manual`**, cron/test — только `_log.md`

## Правило использования

**Любая загрузка встреч из Fireflies — только через инструмент MoveFromFF.** Не писать ad-hoc скрипты, не делать прямые запросы к FF API вне инструмента. Если MoveFromFF не поддерживает нужный сценарий — сначала доработать инструмент, потом использовать.

## Команды в TG и справка

Все команды MoveFromFF включены в `/help` Hermes в отдельном блоке **инструмента MoveFromFF**:
- `обнови fireflies` — запустить синхронизацию
- `обнови ff` — алиас

Правило: **каждый инструмент регистрирует свои команды в общей справке Hermes** отдельным подразделом.

## Шифрование (решение на рассмотрении)

**Статус:** пока без шифрования, вернуться после запуска MoveFromFF.

**Рекомендован Cryptomator (не VeraCrypt)** для `NewMeetings/` — причины:
- Шифрует файлы по отдельности → облако синхронизирует только изменённые (не весь контейнер)
- Официальные клиенты: Windows, Linux, Android, iOS
- Интеграция с Яндекс.Диском через WebDAV
- Obsidian читает прозрачно через виртуальный диск

**Почему не VeraCrypt для мобильных/облака:**
- Контейнер = один большой бинарный файл: при любом изменении внутри — весь контейнер перезаливается
- Яндекс.Диск блокирует смонтированный контейнер (Windows lock)
- На Android нет официального клиента (только EDS Lite — сторонний)
- Cryptomator решает все эти проблемы

**VeraCrypt остаётся вариантом** для локального использования без синхронизации и без мобильного доступа.

**Схема с Cryptomator:**
```
NewMeetings/ → Cryptomator vault → Яндекс.Диск (синхронизация)
Android: Cryptomator app → Obsidian Mobile
Ubuntu VM: Cryptomator Linux → Obsidian
Windows: Cryptomator десктоп → виртуальный диск → Obsidian
```
1. Создать контейнер `C:\Users\tkachenkoav\Secure\meetings.hc`
2. Монтировать как `M:\`
3. Junction: `mklink /J WorkVault\NewMeetings M:\`
4. Python пишет / Obsidian читает прозрачно
5. При запуске по расписанию — скрипт монтирует контейнер через `VeraCrypt.exe /q /v ... /p ...` (пароль из Windows Credential Manager)

Решение принимается отдельно.

## Бэклог и ТЗ

ТЗ хранятся в: `C:/Users/tkachenkoav/Documents/Cursor_projects/hermes-workspace/docs/tz/`
- `MoveFromFF_TZ_v2.0_minimal.md` — актуальное ТЗ (v2.0, на согласовании)
- `MoveFromFF_TZ_v1.md`, `MoveFromFF_TZ_v1.1_addendum.md` — история

Бэклог задач: `C:/Users/tkachenkoav/WorkVault/Hermes-Backlog/backlog.md`

**⚠️ Код заархивирован:** старая версия — `MoveFromFF.archived`. **Актуальный код:** `C:/Users/tkachenkoav/Documents/Cursor_projects/MoveFromFF/` (v2.0, 2 файла на встречу, 42 теста ✅).

## Корпоративные источники данных (бэклог инструментов)

Запланированные инструменты по образцу MoveFromFF:
- **MoveFromJira** — задачи/тикеты из Jira → WorkVault
- **MoveFromConfluence** — страницы из Confluence → WorkVault (`dom.tutu.ru`, тестовая страница pageId=422705401)
- **MoveFromExchange** — почта и календарь из Exchange → WorkVault
- **MoveFromZulip** — сообщения из корпоративного Zulip → WorkVault

Корпоративная учётка ТУТУ (`tkachenkoav@tutu.ru`) работает для всех четырёх сервисов. Хранить как Personal Access Token (не пароль) в `.env`. `redact_secrets: true` уже включён.

## GitHub репозитории

- `workvault-tools`: https://github.com/ialextkachenko-byte/workvault-tools (код инструментов, приватный)
- `hermes-config`: https://github.com/ialextkachenko-byte/hermes-config (конфиг Hermes, скиллы, бэклог, приватный)
- Автосинк: cron каждую ночь в 02:00 МСК (job_id: bc1b0ae442f0)
- Планируется слияние в один репо

## Корпоративные источники данных (credentials)

Все credentials хранятся в `.env` проекта MoveFromFF: `C:/Users/tkachenkoav/Documents/Cursor_projects/MoveFromFF/.env`

| Сервис | Переменная | Как получить |
|---|---|---|
| Confluence/Jira | `TUTU_ATLASSIAN_TOKEN` | dom.tutu.ru → Настройки → Личные маркеры доступа |
| Exchange EWS | `TUTU_EXCHANGE_URL` + `TUTU_PASSWORD` | EWS: `https://cas.tutu.ru/EWS/Exchange.asmx`, NTLM auth |
| Zulip | `TUTU_ZULIP_URL` + `TUTU_ZULIP_API_KEY` | zulip.tutu.ru → Настройки → Учётная запись → API-ключ |
| GitHub | `GITHUB_TOKEN` | github.com → Settings → Fine-grained tokens (нужны: Contents R/W + Administration R/W) |

**Exchange:** самоподписанный сертификат → использовать `verify=False` + `requests_ntlm.HttpNtlmAuth`. При переносе на Ubuntu — заменить `TUTU_PASSWORD` в `.env` с правами 600.

**Zulip:** API недоступен напрямую из терминала (только через браузер/VPN). Для получения API key — зайти через браузер на `zulip.tutu.ru/#settings/account-and-privacy` → «Управление API-ключом».

## ⚠️ ПРАВИЛО РАЗРАБОТКИ (строгое)

Разработку любого изменения MoveFromFF запускать **ТОЛЬКО по согласованному ТЗ** и **ТОЛЬКО после явного "ок, берём в работу"** от Саши в TG. Никакой реализации "по ходу обсуждения". Opus-задачи на реализацию запускать только после этого сигнала.

## Реестр: соглашение по именованию файлов

Реестры сущностей называются с суффиксом сущности — не просто `_registry.json`:

| Сущность | Файлы |
|---|---|
| Meetings | `_registry_meet.json`, `_registry_meet.md`, `_log_meet.md` |
| Contacts | `_registry_cont.json`, `_registry_cont.md` |
| Projects | `_registry_proj.json`, `_registry_proj.md` |
| Tasks | `_registry_task.json`, `_registry_task.md` |

Текущий файл `_registry.json` в `NewMeetings/` → переименовать в `_registry_meet.json` при миграции (Стадия 1).

## Целевая файловая структура WorkVault + USERTOOLS

После миграции (чеклист согласован, май 2026):

```
WorkVault/
├── Contacts/
│   ├── contacts.enc          ← единый для всех инструментов
│   ├── _registry_cont.json
│   └── _registry_cont.md
├── Meetings/
│   └── NewMeetings/
│       ├── _registry_meet.json   ← сейчас: _registry.json
│       ├── _registry_meet.md     ← сейчас: _registry.md
│       └── _log_meet.md          ← сейчас: _log.md
├── Projects/
├── Tasks/
└── _meta/
    ├── MoveFromFF/           ← логи и jsonl
    ├── MoveFromExchange/
    └── MoveFromConfluence/

hermes-agent/USERTOOLS/
├── MoveFromFF/               ← исходники (из CursorProjects/MoveFromFF)
├── MoveFromExchange/
├── MoveFromConfluence/
└── MarkObjectsFromSummary/
```

**Принцип:** WorkVault = данные, CursorProjects = исходники, USERTOOLS = все пользовательские инструменты под одной крышей.

**contacts.enc:** единый файл для всех инструментов (Zulip + Exchange merge). Источник истины — MoveFromFF/contacts.enc (1167 записей, май 2026). contacts.enc MoveFromExchange — только 2 тестовые записи, удалить.

**Логи:** все в `WorkVault/_meta/<ИнструментName>/` — не внутри исходников.

## Оптимизация API-вызовов: паттерн pending+stale (v2.1, согласовано май 2026)

**Проблема без оптимизации:** встреча без summary → пропускается, но НЕ записывается в реестр. Следующий крон (через 2ч) снова делает `fetch_meeting(id)` → снова видит пустой summary → снова пропускает. Лишний API-вызов каждые 2ч на каждую незавершённую встречу.

**Решение (v2.1):** pending-запись в реестре + `last_synced_at`. Backoff **не используется** — встреча просто ждёт следующего синка (каждые 2ч).

**Статусы (4 шт.):** `pending` / `completed` / `error` / `stale`

- `pending` — встреча найдена, но summary/транскрипт ещё не готовы. Ждём следующего синка.
- `completed` — файлы записаны успешно.
- `error` — ошибка fetch или записи.
- `stale` — **терминальный статус**: встреча не обработана FF за 48ч (2 рабочих дня). Больше не пытаемся синкать, алерт в TG.

**Критерии качества встречи (принимается к записи):**
- `summary.overview` не пустой **И**
- суммарная длина всех sentences.text ≥ **500 символов** (порог настраивается через `.env`: `MIN_TRANSCRIPT_CHARS=500`)

Если транскрипт < 500 символов при следующем синке снова < 500 → сразу `stale` (не ждём 48ч).

**Алгоритм Шаг 3 (v2.1):**
```
# Порядок: сначала pending из реестра, потом новые из fetch_range

# 1. Обработать все pending из реестра:
для каждой pending-встречи в реестре:
    если first_seen_at > 48ч → stale, алерт TG, стоп
    fetch_meeting(id) → проверить качество

# 2. Новые встречи:
fetch_range(from_dt, to_dt) → список ID (лёгкие поля)
для каждого ID:
    completed / stale / error → skip (0 API вызовов)
    pending → уже обработан выше → skip
    новый → fetch_meeting(id) → проверить качество:
        summary есть И транскрипт ≥ 500 симв → write_meeting_files() → completed
        нет summary ИЛИ транскрипт < 500 → pending (attempts++, ждём следующего синка)
        pending при прошлом синке И снова < 500 → stale (не ждём 48ч)
```

**Умное окно (v2.1):**
```python
# cron-режим: вместо фиксированных -4.5ч
if registry.last_synced_at:
    from_dt = max(last_synced_at, now - timedelta(hours=24))
else:
    from_dt = now - timedelta(hours=4, minutes=30)  # первый запуск
# После успешного запуска (errors==0): registry.last_synced_at = to_dt
```

**Почему отказались от backoff и 1ч фильтра:** крон каждые 2ч — промежуточные интервалы (5/10/30 мин) бессмысленны. Pending-запись в реестре обеспечивает идемпотентность без лишней сложности. Проверка `summary.overview + len(transcript) >= 500` — достаточный safety net.

**Коды событий лога (v2.1):**
- `meeting_skipped` — уже в реестре со статусом completed/stale/error
- `meeting_pending` — fetch выполнен, качество не прошло, записан pending
- `meeting_stale` — помечен stale (48ч или повторный низкокачественный), TG алерт
- `download_ok` — успешно записан
- `download_error` — ошибка fetch или записи файлов

## Исследование полей FF summary (в процессе, май 2026)

Встреча Trisigma (ID: `01KSFNBC3X0C120ZD501YG0TNX`) показала: в FF веб-интерфейсе видны блоки **тезисов** и **Notes** которые не переносятся в summary.md. Текущий GraphQL-запрос берёт только `overview / action_items / keywords / outline`. Потерянные блоки могут жить в полях `shorthand_bullet`, `bullet_gist`, `gist`, `meeting_info` или в `ai_filters`. Исследование запущено через Opus-cronjob (май 2026) — результат ожидается. После исследования обновить `_MEETING_FIELDS_FULL` в `ff_client.py` и схему `FFSummary` в `ff_schema.py`.

## GraphQL баг: silent empty response (FF cost-limit)

**Симптом:** `--mode manual` возвращает `fetched 0 meeting(s)` хотя встречи есть. Прямой `ff.fetch_range()` работает нормально.

**Причина:** list-запрос с тяжёлыми полями (`sentences`, полный `summary`) превышает cost-лимит FF API. FF молча возвращает `transcripts: []` без `errors` в GraphQL-ответе.

**Фикс (v2.0):** разделить запросы:
- `fetch_range()` — только лёгкие поля (`id, title, date, duration, participants`)
- `fetch_meeting(id)` — полные данные, вызывается только для новых встреч

**Следствие:** rate budget расходуется на N+1 запросов только для новых встреч, не для уже скачанных.

## Питоновское окружение

- Python 3.12.10 (`C:\Users\tkachenkoav\AppData\Local\Programs\Python\Python312\`)
- Создать изолированный venv: `python -m venv .venv` в папке проекта
- Не использовать системный Python и не вмешиваться в venv Hermes (Python 3.11)

## Реальные показатели производительности (май 2026)

Замерено на аккаунте tkachenkoav (тариф Pro, рабочие встречи ТУТУ):

- **16 встреч за 5 дней** → 4.3 сек, ~1.3 MB, 48 файлов (3 на встречу)
- Время почти полностью занимает GraphQL-запрос к FF API (1 запрос)
- Локальная запись файлов — мгновенная (все 16 встреч записаны за <0.1 сек)

Ожидаемые масштабы при полной загрузке:
- ~100 встреч → ~25-30 сек, ~8-9 MB (линейный рост объёма)
- Лимит пагинации FF API: `limit=50` → при >50 встреч нужен второй запрос

## Известный баг: `_log.md` не пишется после --mode test

После запуска `--mode test` файл `_log.md` содержит только заголовок `# Log` без записей о прогоне. Лог фактически не работает. Проверено: май 2026, версия проекта после финального QA.

**Симптом:** `_log.md` = 6 байт (`# Log\n`), несмотря на успешный прогон (downloaded=16).
**Вероятная причина:** logger пишет в stdout, но не вызывает `append` в `_log.md`.
**Приоритет:** высокий — без лога нельзя диагностировать проблемы в cron-режиме.

## Rate Limit Fireflies API

Fireflies Pro тариф имеет дневной лимит на GraphQL запросы. При превышении:
```
FF GraphQL error: Too many requests. Please retry after Sat, 23 May 2026 00:00:00 GMT (UTC)
```
- Лимит сбрасывается в **00:00 UTC** каждый день
- При ручной загрузке большого периода (например, весь май) — можно исчерпать лимит за один прогон
- `fetch_range` через прямой Python (не через `--mode manual`) тоже тратит квоту
- **Workaround:** загружать большие периоды блоками по нескольку дней, не делать несколько прогонов подряд в один день

## MoveFromFF v2.0 — что изменилось vs v1.0

**Убрано:** SHA-256 / hashing.py, reconciler.py (сверка диск↔реестр), processing_status / moved_by / moved_at / moved_to, --mode deleted-check, --reconcile-only, _pending_ff.json, YAML-frontmatter в файлах.

**Осталось:** 2 файла на встречу (transcript/summary), `_registry.json` (идемпотентность), `_registry.md` (рендер из JSON через Jinja2 без доп. запросов к FF), минимальная статусная машина (pending/completed/error), 3 режима CLI (test/cron/manual), retry/атомарная запись/_log.md.

**TG-алерты:** только при `--mode manual` с ошибкой. Cron/test — тишина, всё в `_log.md`.

**Реестр v2.0 — 7 полей:** title, meeting_date, duration_minutes, participants, files, status, fetched_at.

**Баг FF API (решён в v2.0):** list-запрос с тяжёлыми полями (sentences, summary) превышал cost-limit FF и молча возвращал пустой массив. Решение: list-запрос берёт только лёгкие поля, для каждой новой встречи делается отдельный fetch_meeting(id) с полными полями.

**Разработка и ТЗ — только через Opus** (delegate_task model=claude-opus-4-7, provider=anthropic).

## Баг: list-запрос возвращает 0 встреч (cost-limit FF)

GraphQL list-запрос с тяжёлыми полями (`sentences`, полный `summary`) превышает cost-лимит Fireflies и **молча возвращает `transcripts: []`** без `errors` в ответе. Симптом: `fetched 0 meeting(s)` при непустом диапазоне.

**Фикс (v2.0):** разделить запросы — list тянет только лёгкие поля (`id, title, date, duration, participants`), затем для каждой новой встречи отдельный `fetch_meeting(id)` с полными полями. Уже загруженные (status=completed) — не перезапрашиваются.

## Pitfalls

- **API — GraphQL, не REST**: эндпоинт `/graphql`, не `/v1/meetings`
- **Rate limit после нескольких запросов**: FF возвращает `Too many requests. Please retry after <date>`. Суточный бюджет. Тяжёлые list-запросы сжигают его быстрее.
- **SHA-256, не MD5**: MD5 коллизионно небезопасен — оба в `hashlib`, стоят одинаково
- **Атомарная запись обязательна**: `tmp + os.replace`, иначе битый файл + уже записанная чексумма
- **Late-arriving meetings**: встречи `Processing` могут появиться позже — `_pending_ff.json` + overlap -24ч
- **MAX_PATH=260 на Windows**: имена файлов обрезать до 180 символов
- **Идемпотентность по `ff_id`**: не по имени файла — FF может переименовать встречу
- **TG-алерты из cron спамят**: алерты только при `source ∈ {tg, auto}`, cron — только лог
- **Гонки за реестром**: `portalocker` обязателен при параллельном доступе агента-обработчика

- **Windows sleep убивает cron**: блокировка экрана (Win+L) безопасна, но если компьютер уходит в сон — VPN и все задачи падают. Перед ночными cron-задачами проверить и отключить sleep: `powercfg -change standby-timeout-ac 0`. Утром вернуть: `powercfg -change standby-timeout-ac 120`. Текущее значение: `powercfg -query SCHEME_CURRENT SUB_SLEEP`.
- **GraphQL list-запрос молча возвращает `[]` при превышении cost-лимита** — не ошибка, просто пустой массив. Симптом: `fetched 0 meeting(s)` при непустом диапазоне дат. Фикс: убрать тяжёлые поля (`sentences`, полный `summary`) из list-запроса; тянуть их отдельным `fetch_meeting(id)` только для новых встреч.
- **`_registry.md` генерируется из JSON** — не требует запросов к FF. `renderer.py` + Jinja2.
- **TG-алерты только при ручном запуске** — cron (`--mode cron`, `--mode test`) пишет только в `_log.md`, никакого TG.

### Дополнительные pitfalls (из Opus QA финальной проверки ТЗ)

- **Таймзона — противоречие**: ТЗ говорит «брать как есть из FF», но FF отдаёт Unix timestamp UTC. Чётко фиксировать: `meeting_date` в реестре хранить в UTC (`...Z`), имена файлов — из UTC-даты (или с явным смещением). Не смешивать в разных местах ТЗ.
- **`summary.keywords` не отражён**: FF отдаёт `keywords: [String]` — добавить в `summary.md` как секцию `## Ключевые слова` или строку в шапке. Поля `bullet_gist`/`shorthand_bullet` из старой документации **отсутствуют** на Pro тарифе — не использовать.
- **Windows-скрипты при переносе на Ubuntu**: `.bat`-файлы и жёсткие пути `C:\Users\...` в v1.0 — Windows only. При переносе на VM Ubuntu создавать `.sh`-обёртки и параметризовать пути через `.env`/`WORKVAULT_ROOT`. Явно зафиксировать в v1.0: «только Windows, миграция — отдельная задача».
- **`transfer_status=pending` при ошибке скачивания**: если встреча упала → создать/обновить запись в реестре с `transfer_status=pending`, `errors[]+=...`. При следующем запуске — пробовать снова, если встреча ещё есть в FF. **Этот сценарий должен быть явным пунктом в алгоритме** — иначе ошибочные встречи исчезнут из поля зрения.
- **deleted_in_ff — отдельный режим CLI**: проверка за 90 дней — **не часть штатного `--mode cron`**. Выделить в `--mode deleted-check`, запускать отдельным Hermes cron раз в месяц. Иначе каждый cron-запуск будет тянуть данные за 90 дней.
- **`speaker_name` fallback**: если `speaker_name` пустой/null — писать `Speaker {index}` (не `Speaker {speaker_id}` — поля `speaker_id` в реальной схеме нет, только `index`).
- **`duration` float → int**: FF отдаёт `55.18` (float, минуты). В реестре хранить как `duration_minutes: 55` (целое, `round()`). Зафиксировать явно чтобы не было расхождений между документами.

## Конвейер инструментов (pipeline)

```
Fireflies.ai
    ↓ GraphQL API
[MoveFromFF]  →  WorkVault/Meetings/NewMeetings/  →  _registry.json (transfer_status=completed, moved_by=null)
    ↓
[MarkObjectsFromSummary]  →  добавляет YAML-frontmatter, матчит контакты, перекладывает в Processed/YYYY-MM/
    ↓
WorkVault/Contacts/ (новые заготовки контактов с source=fireflies)
WorkVault/Meetings/Processed/YYYY-MM/ (готовые файлы с frontmatter)
```

**MarkObjectsFromSummary** — второй инструмент конвейера:
- ТЗ: `WorkVault/Meetings/MarkObjectsFromSummary_TZ_v0.1.md`
- Читает `participants` (email) из `_registry.json`
- Сопоставляет с Contacts (`@tutu.ru`/`@tutu.tech` = внутренние, остальные = внешние)
- Создаёт заготовки-контакты с `source=fireflies, status=draft` для неизвестных email
- Добавляет YAML-frontmatter в файлы встреч
- Заполняет `moved_by.agent = "MarkObjectsFromSummary"` в реестре
- Бриф MarkObjectsFromSummary не завершён (вопросы A-D открыты)

**Связь через `_registry.json`:**
- MoveFromFF пишет: `transfer_status=completed`, `moved_by=null`
- MarkObjectsFromSummary читает записи с `transfer_status=completed AND moved_by=null`
- После обработки пишет: `moved_by={agent, destination, moved_at}`
- Оба используют `portalocker` при записи в реестр

## References

- `references/fireflies-api.md` — GraphQL API: эндпоинты, поля, примеры Python-кода, тарифы
- `references/performance-benchmarks.md` — реальные замеры скорости/объёма, известные баги
