# ТЗ: Инструмент MarkObjectsFromSummary v1.0 — разметка встреч
# Встречи MoveFromFF → обогащение контактов и проектов → Meetings_Enriched/
# Версия: 1.0 | Дата: 2026-05-23 | Статус: На согласовании

---

## 0. Философия (главное)

**MarkObjectsFromSummary делает ОДНО:** читает встречи из `NewMeetings/` (выгруженные MoveFromFF), обогащает их резолвом **контактов** (email → ФИО + доп. данные из contacts.enc) и **проектов/тем/инициатив** (через LLM-матчинг по projects.md), кладёт обогащённые копии в `Meetings_Enriched/` с чёткими вики-ссылками. Ведёт собственный реестр обработанных встреч.

Всё остальное — задача следующих инструментов конвейера. В первую очередь — **FFContextAggregation** (агрегация, построение графов, контекстуализация).

**Принцип не-делания:**
- Не создаёт карточки контактов (это задача FFContextAggregation + пользователя).
- Не генерирует списки задач / решений / договорённостей (нужно отдельное брифование).
- Не добавляет психологический контекст, настроения (это FFContextAggregation).
- Не публикует в Confluence (это FFContextAggregation).
- Не редактирует исходные файлы MoveFromFF.
- Не требует projects.md (если его нет — матчит проекты как может, низкая точность).

**Один источник истины — `_mark_objects_registry.json`:** «эти встречи уже обработаны, вот статусы и результаты». Точка.

---

## 1. Что делает

- ✅ Читает встречи из `NewMeetings/` (summary.md) + реестр MoveFromFF (`_registry.json`).
- ✅ Резолвит email участников → `contacts.enc` (зашифрованный справочник MoveFromExchange) → fio_short (формат "Иван Иванов").
- ✅ Неизвестные email → создаёт заготовку в `contacts.enc` (поле `is_internal` по домену, остальное пусто).
- ✅ Игнорирует служебные ящики (noreply@, vendor@, support@ и подобные) — не заводит их в справочник.
- ✅ Игнорирует контакты с `ignore: true` в contacts.enc.
- ✅ Матчит упоминания проектов/тем через `projects.md` (LLM-fuzzy, какая LLM — определится тестами).
- ✅ Вставляет вики-ссылки `[[Название проекта]]` в обогащённый файл.
- ✅ Сохраняет встречи с обогащёнными метаданными в `Meetings_Enriched/` (копия summary_enriched.md).
- ✅ Ведёт реестр `_mark_objects_registry.json` (статусы обработки, матчинги контактов и проектов).
- ✅ Логирует все операции в `_log.md` (одна строка) и `logs/markobjects.jsonl` (события).
- ✅ TG-уведомления **только при ручном запуске** и ошибках.
- ✅ Режим `--rematch` для перематчивания уже обработанных встреч.

---

## 2. Чего НЕ делает

- ❌ Не создаёт `.md`-карточки для контактов (файлы типа `Contacts/Иван Иванов.md`).
- ❌ Не генерирует списки Action Items / решений / договорённостей (нужно отдельное брифование).
- ❌ Не добавляет психологический контекст и настроения встреч (это FFContextAggregation).
- ❌ Не публикует встречи в Confluence (это FFContextAggregation).
- ❌ Не редактирует исходные файлы из `NewMeetings/`.
- ❌ Не требует обязательно projects.md (if not exists → матчит как может, точность низкая, логирует warning).
- ❌ Не удаляет скачанные встречи из `NewMeetings/` (они там остаются).
- ❌ Не требует TG для работы (TG — опционально, только уведомления).

---

## 3. Алгоритм обработки (три этапа)

### Этап 1. Preflight

1. Взять `portalocker`-лок `.locks/markobjects.lock`. Занят → exit 2.
2. Проверить `.env`: `WORKVAULT_PATH`, `CONTACTS_ENCRYPTION_KEY` (опционально). Отсутствуют → exit 2 (+ TG только если `--mode manual`).
3. Создать недостающие папки: `Meetings_Enriched/`, `logs/`, `.locks/`.
4. Проверить наличие `_registry.json` (MoveFromFF). Не найден → exit 3 (FF не скачал встречи).

### Этап 2. Скан и фильтр

1. Прочитать `_registry.json` (MoveFromFF) — получить список встреч с полем `participants` (список email).
2. Для каждой встречи в реестре:
   - **Если запись в `_mark_objects_registry.json` уже есть** → пропустить (лог `skipped`), **если не задан режим `--rematch`**.
   - **Иначе** → перейти на этап 3 (обогащение).
3. Если встреча отмечена как `--rematch` → переобработать (обновить запись в реестре).

### Этап 3. Обогащение и запись (для каждой встречи)

**3.1. Резолв контактов:**
1. Прочитать `participants` из `_registry.json` (список email).
2. Для каждого email:
   - **Если `ignore: true` в contacts.enc** → пропустить (не добавлять в обогащённые данные).
   - **Если email в contacts.enc** → взять `fio_short` (формат "Иван Иванов").
   - **Если email не в contacts.enc**:
     - Проверить домен email:
       - Служебный (noreply@, vendor@, support@, no-reply@, notification@, alert@) → пропустить, не заводить заготовку.
       - Внутренний домен (@tutu.ru, @tutu.tech) → `is_internal: true`.
       - Внешний домен → `is_internal: false`.
     - **Если не служебный** → создать заготовку в contacts.enc: `{email, fio: "", login: "", is_internal: bool, active: false, synced_at: null, status: "undefined", ...}`.
     - Добавить в `contacts_unmatched` реестра.
3. Сохранить `contacts_matched` и `contacts_unmatched` в метаданные обработки.

**3.2. Матчинг проектов:**
1. Прочитать `summary.md` встречи.
2. Если `projects.md` существует → LLM-fuzzy матчинг упоминаний проектов (какая LLM — определится тестами).
   - На входе: текст summary.md + список проектов/алиасов из projects.md.
   - На выходе: список matched проектов `["[[Тризигма]]", "[[Проект X]]"]` (вики-ссылки).
   - Если матч не уверен (confidence < 0.7) → не добавлять.
3. Если `projects.md` не существует → логировать warning (⚠️ projects.md не найден), `projects_matched: []`.

**3.3. Обработка спикеров без email:**
1. Если в встрече есть Speaker 1/2/3 (без email в participants) → добавить в `unmatched_speakers` реестра.

**3.4. Создание обогащённого файла:**
1. Читаем `NewMeetings/<meeting_id>/summary.md`.
2. Добавляем в начало YAML-frontmatter (минимум):
   ```yaml
   ---
   meeting_id: <meeting_id>
   processed_at: 2026-05-23T14:00:00+03:00
   participants_resolved: ["Иван Иванов", "Петр Петров"]
   participants_unresolved: ["speaker_1@example.com"]
   projects: ["[[Тризигма]]", "[[Проект X]]"]
   ---
   ```
3. В тексте summary.md заменяем упоминания людей на `fio_short`, проектов — на вики-ссылки `[[...]]`.
4. **Пример замены в тексте:**
   - До: `Иван (ivan@tutu.ru) обсудил проект Тризигма`
   - После: `Иван Иванов обсудил проект [[Тризигма]]`
5. Сохраняем в `Meetings_Enriched/<meeting_id>/summary_enriched.md` (атомарно).

**3.5. Обновление реестра:**
1. Добавить запись в `_mark_objects_registry.json`:
   ```json
   "<meeting_id>": {
     "processed_at": "2026-05-23T14:00:00+03:00",
     "status": "ok",
     "contacts_matched": 3,
     "contacts_unmatched": 1,
     "projects_matched": ["[[Тризигма]]"],
     "unmatched_speakers": ["Speaker 1"],
     "files": {
       "summary_enriched": "Meetings_Enriched/<meeting_id>/summary_enriched.md"
     }
   }
   ```
2. Возможные статусы:
   - `ok` — успешно обработана.
   - `empty` — встреча в summary.md пустая или только заголовок.
   - `no_participants` — нет участников в `participants`.
   - `error` — ошибка при обработке (подробность в jsonl-логе).
3. Записать атомарно (tmp + replace).

### Этап 4. Финализация

1. Дописать одну строку в `_log.md` (см. §8).
2. Записать события в `logs/markobjects.jsonl`.
3. Снять лок.
4. Если `--mode manual` → отправить TG-алерт по правилам §9. Для `--mode cron` / `--mode test` TG не дёргать.
5. Exit 0 (успех) / 1 (часть встреч упала) / 2 (лок) / 3 (FF реестр не найден) / 4 (фатально).

---

## 4. Схемы данных

### 4.1. Структура `_mark_objects_registry.json`

```json
{
  "schema_version": "1.0",
  "updated_at": "2026-05-23T14:00:00+03:00",
  "meetings": {
    "<meeting_id>": {
      "processed_at": "2026-05-23T14:00:00+03:00",
      "status": "ok",
      "contacts_matched": 3,
      "contacts_unmatched": 1,
      "projects_matched": ["[[Тризигма]]", "[[Проект X]]"],
      "unmatched_speakers": ["Speaker 1"],
      "files": {
        "summary_enriched": "Meetings_Enriched/<meeting_id>/summary_enriched.md"
      }
    },
    "<meeting_id_2>": {
      "processed_at": "2026-05-23T14:15:00+03:00",
      "status": "empty",
      "contacts_matched": 0,
      "contacts_unmatched": 0,
      "projects_matched": [],
      "unmatched_speakers": [],
      "files": {
        "summary_enriched": "Meetings_Enriched/<meeting_id_2>/summary_enriched.md"
      }
    }
  }
}
```

**Правила:**
- Все даты — UTC+03:00 (МСК) ISO-8601 с `+03:00`.
- `files.summary_enriched` — только имя пути относительно `WORKVAULT_PATH`.
- `status` ∈ {`ok`, `empty`, `no_participants`, `error`}:
  - `ok` — встреча успешно обогащена, файл создан.
  - `empty` — встреча в summary.md не содержит текста (только заголовок).
  - `no_participants` — в `participants` нет email (встреча без участников).
  - `error` — ошибка обработки (подробность в jsonl).
- `contacts_matched` — количество успешно резолвленных email.
- `contacts_unmatched` — количество email, которые не найдены в contacts.enc (заготовки созданы).
- `projects_matched` — массив вики-ссылок `[["[[Проект 1]]", "[[Проект 2]]"]]`.
- `unmatched_speakers` — массив имён спикеров без email (Speaker 1/2/3).

### 4.2. Структура `summary_enriched.md`

```markdown
---
meeting_id: 01H9J7XYZ
processed_at: 2026-05-23T14:00:00+03:00
participants_resolved: ["Иван Иванов", "Петр Петров"]
participants_unresolved: ["Speaker 1"]
projects: ["[[Тризигма]]", "[[Проект X]]"]
---

# Саммари: Встреча с клиентом

## Overview
Иван Иванов и Петр Петров обсудили статус проекта [[Тризигма]]. Согласованы следующие шаги...

## Action Items
- Иван Иванов — подготовить финальный отчёт к 25-му
- Петр Петров — согласовать с stakeholders проекта [[Проект X]]

## Keywords
облако, архитектура, масштабирование
```

**Правила:**
- YAML-frontmatter в начале: `meeting_id`, `processed_at`, `participants_resolved`, `participants_unresolved`, `projects`.
- Текст summary.md копируется с заменами:
  - Email и имена людей → `fio_short` (без email в тексте).
  - Упоминания проектов → вики-ссылки `[[Название]]`.
- Пустые / null секции (Overview, Action Items, Keywords) — переносятся как есть (если пусты в исходном файле).
- Никакого дополнительного редактирования текста (только замены).

---

## 5. Интеграции и контракты

### 5.1. Контракт с MoveFromFF

**MoveFromFF гарантирует:**
- Файлы встреч в `NewMeetings/<meeting_id>/summary.md` + `transcript.md`.
- Реестр `_registry.json` с полями: `meeting_id`, `title`, `participants` (список email), `fetched_at`.
- Имена файлов — стабильные (детерминированное именование по дате+title).

**MarkObjectsFromSummary читает:**
- `_registry.json` (особенно поле `participants`).
- `NewMeetings/<meeting_id>/summary.md`.

**MarkObjectsFromSummary НЕ редактирует:**
- Файлы в `NewMeetings/` — они остаются нетронутыми.
- Реестр `_registry.json` MoveFromFF.

---

### 5.2. Контракт с MoveFromExchange

**MoveFromExchange гарантирует:**
- Зашифрованный справочник `contacts.enc` со схемой v1.0 (ключ в `.env` как `CONTACTS_ENCRYPTION_KEY`).
- Поля: `email` (ключ), `fio_short`, `fio`, `is_internal`, `active`, `ignore`, `status`.

**MarkObjectsFromSummary:**
- Читает `contacts.enc` (расшифровывает с помощью ключа из `.env`).
- При необходимости **добавляет новые контакты** в `contacts.enc` (если email не найден и не служебный).
- **Не обновляет** существующие контакты (только добавляет новые).

**Если `contacts.enc` недоступен:**
- MarkObjectsFromSummary работает в режиме graceful degradation: используется email как есть, статус `ok` → создаёт заготовку в памяти (не записывает в contacts.enc).

---

### 5.3. Контракт с projects.md

**Источник:** файл `projects.md` в WORKVAULT_PATH (готовится вручную пользователем).

**Формат (примерно):**
```markdown
# Проекты и инициативы

## Тризигма
- Описание: платформа X
- Алиасы: Тризигма, TZ, Platform TZ

## Проект X
- Описание: инициатива Y
- Алиасы: Проект X, ProjectX

## CORE Initiative
- Описание: комплексная переработка
- Алиасы: CORE, Core Initiative, ядро
```

**Алгоритм матчинга:**
1. Если projects.md не существует → статус `projects_matched: []`, warning в лог.
2. Если существует → LLM-fuzzy матчинг упоминаний текста summary.md против списка проектов/алиасов.
3. На выходе: массив вики-ссылок `[[Тризигма]]`, `[[Проект X]]` (если confidence >= 0.7).

**MarkObjectsFromSummary НЕ создаёт:**
- Сами файлы проектов (это пользователь или FFContextAggregation).

---

### 5.4. Запись новых контактов в contacts.enc

**Когда:** если email из `participants` не найден в contacts.enc и не служебный → заготовка добавляется.

**Заготовка:**
```json
{
  "email": "new@example.com",
  "fio": "",
  "fio_short": "",
  "login": "",
  "display_name": "",
  "department": "",
  "team": null,
  "position": "",
  "is_room": false,
  "is_internal": false,  // если @example.com (внешний домен)
  "active": false,
  "synced_at": null,
  "status": "undefined",
  "aliases": [],
  "messenger_ids": {},
  "notes": "Автоматически добавлен из встречи 01H9J7XYZ",
  "custom_updated_at": null
}
```

**Алгоритм:**
1. Проверить домен email — определить `is_internal`.
2. Перед записью в contacts.enc → проверить служебные ящики (noreply@, vendor@, и т. д.) — **НЕ заводить их**.
3. Файл contacts.enc перезаписать атомарно (tmp + replace).

---

## 6. CLI

```bash
# Обработка новых встреч
python -m markobjects --mode test                    # последние встречи из test-набора, без TG
python -m markobjects --mode cron                    # встречи, не обработанные ещё, без TG
python -m markobjects --mode manual                  # обработать всё, с TG-уведомлением

# Переобработка (rematch)
python -m markobjects --rematch --meeting-id <id>    # перематчить одну встречу
python -m markobjects --rematch --from-date 2026-01-01 --to-date 2026-01-31  # период
python -m markobjects --rematch --all                # перематчить всё

# Утилиты
python -m markobjects --mode test --dry-run          # план без записи
python -m markobjects --mode manual --no-tg          # ручной запуск без TG
python -m markobjects --mode cron --verbose          # DEBUG лог
```

**Коды выхода:**
- `0` — успех (обработана 1+ встреча).
- `1` — частичный успех (часть встреч упала).
- `2` — ошибка конфигурации (лок занят, `.env` неполный).
- `3` — FF реестр не найден (MoveFromFF ещё не запущен).
- `4` — фатальная ошибка (крах внутри обработки).

---

## 7. TG-команды

**Главный принцип:** TG-уведомления отправляются **только при ручном запуске** и **ошибках**. Cron работает молча — все статусы в лог.

```
/mark_objects status               — текущий статус (сколько обработано, ошибок)
/mark_objects rematch <id>         — перематчить встречу по ID
/mark_objects rematch all          — перематчить все встречи
/mark_objects export               — экспортировать реестр в JSON (отправить в TG)
```

**Поведение:**
- Успех при ручном запуске: `✅ Обработано N встреч, ошибок K`.
- Ошибка (любая): `⚠️ Ошибка: [описание]`, список ID если применимо.

---

## 8. Логирование

**`_log.md`** — одна строка на запуск (append-only):
```
2026-05-23 14:00:00 MSK [cron] processed=5 skipped=2 empty=1 errors=0 duration=12.4s
2026-05-23 16:00:00 MSK [manual] processed=10 skipped=0 empty=0 errors=1 duration=8.7s
```

**`logs/markobjects.jsonl`** — одна строка JSON на событие:
```json
{"ts":"2026-05-23T14:00:05+03:00","event":"process_ok","meeting_id":"01H9J7XYZ","contacts_matched":3,"projects_matched":1}
{"ts":"2026-05-23T14:00:07+03:00","event":"contact_created","email":"new@example.com"}
{"ts":"2026-05-23T14:00:08+03:00","event":"process_error","meeting_id":"01J...","error":"summary.md not found"}
{"ts":"2026-05-23T14:00:15+03:00","event":"run_summary","mode":"cron","processed":5,"skipped":2,"empty":1,"errors":0}
```

---

## 9. Крон и расписание

- **Запуск:** сразу после MoveFromFF (если тот завершился успешно).
- **Частота:** каждые 2 часа (пн-пт 10:00-20:00 МСК).
- **Примерный cron (Linux):** `0 */2 * * 1-5 10-20 python -m markobjects --mode cron` (уточнить для Windows).
- **На Windows:** `run_cron.bat` → PowerShell или bash script.
- **TG-уведомления:** НЕ отправляются из cron (только из `--mode manual`).
- **Молчание при успехе:** инструмент молчит, всё в логе.

---

## 10. Структура проекта

```
MarkObjectsFromSummary/
├── .venv/
├── .env                       # WORKVAULT_PATH, CONTACTS_ENCRYPTION_KEY, TELEGRAM_*
├── .env.example
├── pyproject.toml
├── README.md
├── markobjects/
│   ├── __main__.py            # CLI + оркестрация (Этапы 1-4)
│   ├── config.py              # pydantic Settings из .env
│   ├── ff_registry.py         # read MoveFromFF/_registry.json
│   ├── contacts.py            # read/write contacts.enc (расшифровка, добавление новых)
│   ├── projects.py            # read projects.md, LLM-матчинг проектов
│   ├── enricher.py            # main logic: резолв контактов, матчинг проектов, обогащение
│   ├── writer.py              # запись summary_enriched.md + frontmatter
│   ├── registry.py            # read/write _mark_objects_registry.json (атомарно)
│   ├── lock.py                # portalocker
│   ├── logger.py              # _log.md + jsonl
│   ├── tg.py                  # TG-уведомления (только ручной запуск)
│   └── templates/
│       └── frontmatter.j2     # YAML-frontmatter для summary_enriched.md
├── tests/
│   ├── test_enricher.py
│   ├── test_contacts.py
│   ├── test_projects.py
│   ├── test_registry.py
│   └── fixtures/
└── scripts/
    └── run_cron.bat
```

---

## 11. Backlog (v1.1+, FFContextAggregation)

**Будущие версии:**

- **Карточки контактов** `Contacts/Иван Иванов.md` — когда contacts.enc будет иметь отдельные .md файлы (сейчас не планируется для v1.0).
- **Action Items / решения / договорённости** — после отдельного брифования (нужна LLM-разметка текста).
- **Психологический контекст, настроения** — агрегируется в FFContextAggregation.
- **Публикация в Confluence** — агрегируется в FFContextAggregation.
- **Граф связей между людьми/проектами** — построение в FFContextAggregation.
- **История изменений обогащённых данных** — версионирование (не в MVP).

---

## 12. Открытые вопросы

- **Q1:** Какая LLM для матчинга проектов? → Определится тестами. Возможны: GPT-4, Claude, локальная модель (SentenceTransformers).
- **Q2:** Если projects.md не существует → молчать или warning? → **Warning в лог и jsonl** (проекты не матчены, точность 0%).
- **Q3:** Что делать если contacts.enc недоступен (криптография упала)? → Graceful degradation: используем email как есть, не добавляем в contacts.enc.
- **Q4:** Нужна ли история контактов в contacts.enc? → Не в v1.0. Версионирование — позже.
- **Q5:** Может ли MarkObjectsFromSummary создавать `Contacts/Иван Иванов.md`? → Нет в v1.0. Это FFContextAggregation или пользователь.
- **Q6:** Как часто переобрабатывать встречи (--rematch)? → Вручную по команде или по расписанию (не в MVP, только по требованию).

---

## 13. Сравнение объёма и сложности

| Метрика | MarkObjectsFromSummary v1.0 | Сложность |
|---|---|---|
| Python-модулей | 11 | средняя |
| Полей в записи реестра | 7 | стандартная |
| Режимов CLI | 5 (`test`/`cron`/`manual` + `--rematch`) | стандартная |
| Статусов обработки | 4 (`ok` / `empty` / `no_participants` / `error`) | минимум |
| TG-интеграция | Уведомления (+ запросы) | стандартная |
| Зависимостей | MoveFromFF, MoveFromExchange, projects.md (опционально) | сложная интеграция |
| LLM-компонент | Матчинг проектов (fuzzy) | высокая сложность |

---

## 14. Контрольные точки совместимости

**С MoveFromFF v2.0:**
- ✅ Читает `_registry.json` (schema_version: 2.0).
- ✅ Поле `participants` — список email.
- ✅ Не редактирует исходные файлы MoveFromFF.

**С MoveFromExchange v1.0:**
- ✅ Расшифровывает `contacts.enc` (AES-256-GCM, ключ из `.env`).
- ✅ Добавляет новые контакты заготовками.
- ✅ Использует поле `fio_short` для резолва.

**С projects.md:**
- ✅ Опциональный файл (warning если не найден).
- ✅ LLM-матчинг со списком проектов и алиасов.

**С FFContextAggregation (next):**
- ✅ Создаёт `Meetings_Enriched/<meeting_id>/summary_enriched.md` (обогащённые встречи).
- ✅ Ведёт реестр `_mark_objects_registry.json` (статусы, матчинги).
- ✅ FFContextAggregation читает оба и агрегирует данные по проектам/контактам.

---

## 15. Критерии приёмки (DoD, 7 пунктов)

1. ✅ `--mode test` обрабатывает встречи, создаёт обогащённые копии в `Meetings_Enriched/`.
2. ✅ Контакты с `ignore: true` — пропускаются (не добавляются в обогащённый файл).
3. ✅ Неизвестные (не служебные) email → заготовка в `contacts.enc`, `status: "undefined"`.
4. ✅ Служебные ящики (noreply@, vendor@) — игнорируются, не заводятся в справочник.
5. ✅ projects.md существует → LLM-матчинг работает, вики-ссылки вставлены. Не существует → warning, `projects_matched: []`.
6. ✅ Повторный запуск без `--rematch` → встречи пропускаются (lог `skipped`).
7. ✅ `_mark_objects_registry.json` валиден по pydantic-схеме (schema_version=1.0), все встречи учтены.

---

## 16. Статус документа

**Дата:** 2026-05-23  
**Версия:** 1.0 (первая версия на согласовании)  
**Статус:** На согласовании

**Связанные документы:**
- MoveFromFF_TZ_v2.0_minimal.md (входные данные)
- MoveFromExchange_TZ_contacts_v1.0.md (справочник контактов)
- FFContextAggregation_TZ_v1.0.md (следующий инструмент, в разработке)

---

## 17. Примечания для разработчиков

1. **Критичность интеграций:**
   - MoveFromFF (обязателен): реестр и файлы встреч.
   - MoveFromExchange (обязателен при наличии `contacts.enc`): зашифрованный справочник.
   - projects.md (опционален): если нет → предупреждение, работаем без проектов.

2. **Безопасность:**
   - Ключ `CONTACTS_ENCRYPTION_KEY` хранится только в `.env` (не в коде).
   - При распаковке contacts.enc используется контекстный менеджер (автоматическое удаление расшифрованных данных из памяти).

3. **Надёжность:**
   - Все записи в файлы — атомарные (tmp + os.replace()).
   - Лок-файл предотвращает параллельные запуски.
   - При ошибке на одной встрече — продолжаем со следующих.

4. **Мониторинг:**
   - Все ошибки логируются в jsonl.
   - TG-алерты только для ручного запуска.
   - Cron работает молча (лог в `_log.md`).
