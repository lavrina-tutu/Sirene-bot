# Дополнение к ТЗ MoveFromFF — v1.1

> Этот файл — приращение к `MoveFromFF_TZ_v1.md`. После согласования влить разделы в основной документ (§13 — новый, §14 — новый, §9 — замена).

---

## 13. Нормализация данных FF API (уточнения v1.1)

По итогам анализа реальных ответов Fireflies GraphQL API на тарифе **Pro** зафиксированы расхождения с первоначальной схемой §4 / §9. Все они применяются на стороне `ff_schema.py` и `renderer.py`.

| Поле FF | Тип в API | Нормализация в MoveFromFF |
|---|---|---|
| `participants` | `string[]` — массив **email** (без имён) | Сохранять как есть: `["a@tutu.ru", "b@gmail.com"]`. В `transcript.md` шапка → `**Участники:** a@tutu.ru, b@gmail.com`. Связь с ФИО — задача следующего агента. |
| `audio_url` | `null` на тарифе Pro | Если `null` → строку «Аудио:» **не выводить** в `transcript.md`. В `_registry.json` хранить `audio_url: null`. |
| `date` / `dateString` | Unix timestamp **миллисекунды** (int) | Конвертировать в `datetime` в **UTC** (без локальной TZ). В именах файлов — `YYYY-MM-DD HH-MM-SS` (UTC), в реестре — ISO-8601 с суффиксом `Z` (например `2026-05-20T11:30:00Z`). |
| `duration` | `float` (минуты) | **Хранить как есть, без округления.** В реестре поле `duration_minutes: float`. В шапке `transcript.md` показывать с одной значащей дробной частью (`47.3 мин`). |
| `sentences[].start_time` | `float` секунды от начала встречи | Конвертировать в `[MM:SS]` (если ≥ 60 мин — `[HH:MM:SS]`). Используется в `transcript.md` перед каждой репликой. |
| `sentences[].speaker_name` | `string` (может быть пустым/`null`) | Если пустой или `null` → подставить `Speaker {index}`, где `index` — порядковый номер уникального спикера во встрече (1-based, считается по `speaker_id` или по порядку появления). **Не использовать** `speaker_id` напрямую и **не писать** «Unknown Speaker». |
| `summary.overview` | `string` или `null` | В `summary.md` блоком `## Overview`. Если пусто/`null` — секцию пропускать. |
| `summary.action_items` | `string` (markdown-блок), **не массив** | В `actions.md` вставлять как есть, без попытки разобрать в чек-лист. Также дублируется в `summary.md` блоком `## Action Items`. Если строка пустая/`null` → `actions.md` с шапкой и текстом `_Нет action items._`. |
| `summary.keywords` | `string` или `string[]` (зависит от плана / ответа FF) | В `summary.md` блоком `## Keywords` **как есть** (если массив — через запятую). В `_registry.json` сохранять в поле `keywords` (тип `string \| string[] \| null`). |

**Принцип неизменности:** нормализация — это только смена *формата представления* (timestamp → UTC ISO, float → `[MM:SS]`). Содержимое (текст реплик, action_items как строка, keywords) НЕ редактируется и НЕ переписывается LLM.

> **Дальнейшая обработка `keywords`** (разметка тегов, связь с тегами Obsidian, нормализация регистра/синонимов) — задача инструмента **MarkObjectsFromSummary**. См. ТЗ: `WorkVault/Meetings/MarkObjectsFromSummary_TZ_v0.1.md`. MoveFromFF только переносит keywords из FF в `summary.md` и в `_registry.json` без модификации.

> **Удалены из v1.0:** поля `summary.bullet_gist` и `summary.shorthand_bullet` — в реальной схеме FF Pro их **нет**, упоминание в ранних драфтах было ошибкой. Шаблон `summary.md` опирается только на `overview` / `action_items` / `keywords`.

---

## 14. Связи с другими инструментами

MoveFromFF — **первое звено** конвейера обработки встреч. Все downstream-инструменты читают результат через `_registry.json` (единственный источник правды) и файлы в `NewMeetings/`.

### 14.1 Карта конвейера

```
┌──────────────┐   files + registry    ┌──────────────────────────┐
│  Fireflies   │ ────────────────────► │  MoveFromFF              │
│  GraphQL API │                       │  (этот инструмент)       │
└──────────────┘                       └────────────┬─────────────┘
                                                    │ NewMeetings/*.md
                                                    │ _registry.json
                                                    ▼
                                        ┌──────────────────────────┐
                                        │ MarkObjectsFromSummary   │
                                        │ • match participants     │
                                        │ • create contact stubs   │
                                        │ • add YAML frontmatter   │
                                        │ • move → Processed/      │
                                        └────────────┬─────────────┘
                                                     │ Processed/YYYY-MM/
                                                     │ Contacts/<new>.md
                                                     ▼
                                        ┌──────────────────────────┐
                                        │ (future: SemanticEnrich, │
                                        │  TaskExtractor, ...)     │
                                        └──────────────────────────┘
```

### 14.2 Контракт «MoveFromFF → MarkObjectsFromSummary»

| Сторона | Обязательство |
|---|---|
| **MoveFromFF (producer)** | Пишет 3 файла **без YAML-frontmatter**, кладёт запись в `_registry.json` с `transfer_status=completed`, `integrity=ok`, `moved_by=null`. Поле `participants` — массив email-строк. |
| **MarkObjectsFromSummary (consumer)** | Берёт записи с `transfer_status=completed AND moved_by=null`, обрабатывает, заполняет `moved_by.agent="MarkObjectsFromSummary"`, `moved_by.destination`, `moved_by.moved_at`, опционально `contacts_matched` / `contacts_new`. |
| **Совместный лок** | Оба инструмента берут `portalocker` на `_registry.json` **только на время записи**. Чтение — без лока. |

### 14.3 Семантика поля `participants` для связи с WorkVault/Contacts

- В реестре и в файлах MoveFromFF поле `participants` — это **массив email-строк** в нижнем регистре, без дубликатов, без пробелов.
- Email — стабильный ключ для join с сущностью `Contacts` в WorkVault (см. ТЗ MarkObjectsFromSummary §3).
- MoveFromFF **не разрешает** email → ФИО и **не создаёт** заготовки контактов. Это ответственность MarkObjectsFromSummary.

### 14.4 Что MoveFromFF гарантирует / не гарантирует

✅ Гарантирует:
- Email в `participants` — валидные по RFC (если FF отдал мусор — отбрасывается с записью в `errors[]`).
- Дата встречи в реестре — в **UTC** (ISO-8601 с суффиксом `Z`).
- Идемпотентность: повторный запуск не меняет `moved_by` и не «откатывает» работу downstream-агентов.

❌ Не гарантирует:
- Соответствия email реальному человеку.
- Уникальности участников между встречами (один email может встречаться в N записях реестра — это норма).
- Заполнения `moved_by` (это делает downstream).

---

## 9. Схема `_registry.json` (v1.1, замена раздела)

Изменения относительно v1.0: `participants` — email-массив, `audio_url` допускает `null`, добавлен блок `moved_by` с расширенной структурой.

```json
{
  "schema_version": "1.1",
  "updated_at": "2026-05-22T14:30:00Z",
  "meetings": {
    "<meeting_id>": {
      "meeting_id": "01HXYZ...",
      "title": "Встреча с клиентом",
      "meeting_date": "2026-05-20T11:30:00Z",
      "duration_minutes": 47.3,
      "participants": [
        "tkachenkoav@tutu.ru",
        "ivan.petrov@example.com"
      ],
      "keywords": ["onboarding", "Q2-planning"],
      "source": "fireflies",
      "transfer_status": "completed",
      "integrity": "ok",
      "files": {
        "transcript": {
          "filename": "2026-05-20 11-30-00 Встреча - transcript.md",
          "sha256": "abc123...",
          "size_bytes": 18432,
          "written_at": "2026-05-22T14:30:05Z"
        },
        "summary":  { "filename": "...", "sha256": "...", "size_bytes": 0, "written_at": "..." },
        "actions":  { "filename": "...", "sha256": "...", "size_bytes": 0, "written_at": "..." }
      },
      "audio_url": null,
      "fetched_at": "2026-05-22T14:30:05Z",
      "last_checked_at": "2026-05-22T14:30:05Z",
      "moved_by": null,
      "errors": []
    }
  }
}
```

**Расширенный `moved_by` (заполняется downstream-агентом, MoveFromFF только читает):**
```json
"moved_by": {
  "agent": "MarkObjectsFromSummary",
  "agent_version": "0.1",
  "destination": "Meetings/Processed/2026-05/",
  "moved_at": "2026-05-22T14:35:12Z",
  "contacts_matched": ["tkachenkoav@tutu.ru"],
  "contacts_new":     ["ivan.petrov@example.com"]
}
```

**Перечисления:**
- `source` ∈ `{ fireflies, manual }`
- `transfer_status` ∈ `{ pending, completed, failed, deleted_in_ff, missing_locally }` — статус `restored` **не используется**, исключён намеренно (восстановление файла = перезапись из FF при следующем cron-проходе).
- `integrity` ∈ `{ ok, modified_locally, unknown }`

**Типы и формат:**
- Все даты — **UTC**, ISO-8601 с суффиксом `Z`.
- `duration_minutes` — `float` (хранится как есть из FF, без округления).
- `keywords` — `string | string[] | null` (как отдал FF; см. §13).

**Совместимость:** при чтении файла со `schema_version=1.0` инструмент автоматически апгрейдит структуру (participants — оставляет как есть, добавляет недостающие поля) и пишет обратно с `schema_version=1.1`.
