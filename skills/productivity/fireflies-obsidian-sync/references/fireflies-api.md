# Fireflies.ai API — справочник

## ⚠️ Важно: GraphQL, не REST

Fireflies использует **GraphQL API**, не REST v1.

- **Эндпоинт:** `https://api.fireflies.ai/graphql` (POST)
- **Аутентификация:** `Authorization: Bearer <API_KEY>`
- **Формат:** JSON body с полем `query`
- **Получение токена:** Settings → Developer → API Key (показывается один раз)

## Реальная схема ответа (верифицировано на Pro тарифе, 2026-05-22)

Результат живого теста на реальном аккаунте tkachenkoav@tutu.ru:

```json
{
  "id": "01KS7EXTEB5AGMX6NYCM8GY298",
  "title": "Внедрение платформы MLOps и обучение",
  "date": 1779440700000,
  "duration": 55.18000030517578,
  "audio_url": null,
  "participants": ["tkachenkoav@tutu.ru"],
  "sentences": [
    {
      "index": 0,
      "speaker_name": "Speaker 1",
      "text": "А мы собирались...",
      "start_time": 1.91,
      "end_time": 47.21
    }
  ],
  "summary": {
    "overview": "- **Цель внедрения:** ...",
    "action_items": "\n**Спикер 1 (email)**\nПодготовить план... (49:44)\n",
    "keywords": ["Feature Store", "MLOps", "CI/CD"],
    "outline": null
  }
}
```

### Критические отличия от документации

| Поле | Ожидалось | Реально (Pro тариф) |
|---|---|---|
| `audio_url` | string / URL | `null` — не отдаётся на Pro |
| `participants` | `[{name, email}]` | `["email@domain.com"]` — просто массив строк, **НЕ объект** |
| `summary.action_items` | `[string]` | **строка** с маркдаун-разметкой и группировкой по спикерам |
| `summary.outline` | структура | `null` на Pro |
| `speaker_name` | имя человека | `"Speaker 1"`, `"Speaker 2"` — FF не всегда идентифицирует |
| `date` | ISO 8601 | Unix timestamp в **миллисекундах** — делить на 1000 для datetime |
| `duration` | int (секунды) | float, **в минутах** (55.18 = 55 мин 11 сек) |

### Что НЕ работает с participants

```python
# ❌ НЕПРАВИЛЬНО — participants не объект
for p in transcript["participants"]:
    print(p["name"])  # KeyError

# ✅ ПРАВИЛЬНО — participants это список email-строк
for email in transcript["participants"]:
    print(email)  # "tkachenkoav@tutu.ru"
```

### Конвертация даты

```python
from datetime import datetime, timezone

# date — Unix timestamp в миллисекундах
ts_ms = 1779440700000
dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
# → 2026-05-22 00:45:00+00:00

# Для имени файла с локальным временем — брать как есть из FF
# (согласно решению из брифа: таймзону из FF без преобразований)
```

### Конвертация таймкодов транскрипта

```python
# start_time/end_time — секунды (float)
def format_time(seconds: float) -> str:
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"
# 1.91 → "00:01", 47.21 → "00:47"
```

## Проверка доступности

```graphql
query {
  user {
    user_id
    email
  }
}
```

## Получение встреч

```graphql
query Transcripts($fromDate: String, $limit: Int, $skip: Int) {
  transcripts(fromDate: $fromDate, limit: $limit, skip: $skip) {
    id
    title
    date
    duration
    audio_url
    participants
    summary {
      overview
      action_items
      keywords
      outline
    }
    sentences {
      index
      speaker_name
      text
      start_time
      end_time
    }
  }
}
```

Переменные:
- `fromDate`: ISO 8601 строка (`"2026-05-01T00:00:00.000Z"`)
- `limit`: max 50 на запрос
- `skip`: для пагинации

⚠️ `participants` НЕ принимает subfields — это `[String]`, не объект:
```graphql
# ❌ ОШИБКА — вернёт GRAPHQL_VALIDATION_FAILED
participants { name email }

# ✅ ПРАВИЛЬНО
participants
```

## Статусы встреч и задержка обработки

- `processing` — ещё обрабатывается (пропустить, добавить в `_pending_ff.json`)
- `completed` — готово, `transcript_ready = true`

**Задержка обработки (важно для синка):**
Fireflies-бот пишет встречу в реальном времени (online), но transcript и summary через API доступны только **после окончания встречи** — обычно через 5–30 минут. За это время:
- `transcript(id)` вернёт пустой `sentences: []` или `summary: null`
- Никакой ошибки не будет — просто пустые данные

**Надёжный способ проверить готовность:**
```python
meeting = ff.fetch_meeting(meeting_id)
if meeting.summary and meeting.summary.overview:
    # готово, можно записывать
else:
    # ещё не обработано
```

**Pre-filter по времени (оптимизация API):**
Чтобы не тратить `fetch_meeting(id)` на явно незрелые встречи:
```python
meeting_end_ms = meeting.date + (meeting.duration or 0) * 60 * 1000
age_hours = (now_ms - meeting_end_ms) / 3_600_000
if age_hours < 1:
    # пропустить без вызова fetch_meeting — не готово с высокой вероятностью
```
Это экономия, не гарантия — итоговая проверка summary.overview обязательна.

## Двухэтапная загрузка (обязательный паттерн)

FF API имеет **cost-limit** на GraphQL-запросы. При запросе тяжёлых полей (`sentences`, `summary`) в list-запросе FF **молча возвращает пустой массив** без ошибки.

**Правильный паттерн:**
```
Шаг A: fetch_range() — только лёгкие поля
         → id, title, date, duration, participants

Шаг B: для каждой новой встречи → fetch_meeting(id) — полные поля
         → sentences, summary (+ проверка готовности)
```

**Неправильно (приводит к пустым файлам):**
```graphql
# ❌ — FF вернёт transcripts: [] или sentences: [] без ошибки
transcripts(fromDate: ...) {
  id title date sentences { text } summary { overview }
}
```

## Rate Limits (Pro тариф)

~60–100 запросов/минуту. При превышении: `429 Too Many Requests`.  
Стратегия: backoff 60→120→240с, max 3 попытки.

## Тарифы и доступ к API

| Тариф | Цена | API | Саммари | Action Items | Webhooks |
|---|---|---|---|---|---|
| Basic | бесплатно | ✅ | ❌ | ❌ | ❌ |
| Pro | ~$10/мес | ✅ | ✅ | ✅ | ❌ |
| Business | ~$20-40/мес | ✅ | ✅ | ✅ | ✅ |

**Текущий тариф: Pro** → webhooks недоступны, используем polling.
`audio_url` = null на Pro.

## Webhooks (только Business+)

События:
- `meeting.completed` — встреча завершена (транскрипт может быть сырым)
- `meeting.transcription.completed` — ИИ-обработка готова ← **ключевое**

## Пример запроса (Python)

```python
import requests
from datetime import datetime, timezone

GRAPHQL_URL = "https://api.fireflies.ai/graphql"
API_KEY = "your_key_here"

def get_transcripts(from_date: str, limit: int = 50, skip: int = 0):
    query = """
    query Transcripts($fromDate: String, $limit: Int, $skip: Int) {
      transcripts(fromDate: $fromDate, limit: $limit, skip: $skip) {
        id title date duration audio_url participants
        summary { overview action_items keywords }
        sentences { index speaker_name text start_time end_time }
      }
    }
    """
    response = requests.post(
        GRAPHQL_URL,
        json={"query": query, "variables": {"fromDate": from_date, "limit": limit, "skip": skip}},
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        timeout=30
    )
    response.raise_for_status()
    data = response.json()
    if "errors" in data:
        raise ValueError(f"GraphQL errors: {data['errors']}")
    return data["data"]["transcripts"]

def parse_meeting_date(ts_ms: int) -> datetime:
    """date из FF — Unix timestamp в миллисекундах"""
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)

def format_timecode(seconds: float) -> str:
    """Для отображения в транскрипте: 1.91 → '[00:01]'"""
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"[{m:02d}:{s:02d}]"
```

## Готовые интеграции

- Notion: прямая интеграция
- Obsidian: только через Zapier/Make (нативного плагина нет)
- Slack: уведомления + чат-бот Ask Flo
- Zoom, Google Meet, Teams, Webex: нативный бот
