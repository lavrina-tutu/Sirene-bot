---
name: fireflies-transcripts
description: "Fireflies.ai: fetch transcripts via GraphQL API, filter, chronologize, and integrate into narrative writing."
version: "1.0.0"
platforms: [linux, macos, windows]
tools: [terminal]
triggers:
  - "фф / fireflies / транскрипт записи"
  - "MoveFromFF / выгрузи из FF"
  - "обработай запись разговора"
  - "вставь детали из разговора в текст"
  - "отчёт из встречи"
metadata:
  hermes:
    tags: [fireflies, transcripts, meetings, graphql, narrative]
---

# Fireflies Transcripts — Fetch, Filter, Integrate

## Когда использовать
- Пользователь присылает ссылку вида `https://app.fireflies.ai/view/<ID>`
- Просит «выгрузить из фф» / «забери транскрипт»
- Нужно извлечь детали из живого разговора и интегрировать в текст

## Доступ через API

**API ключ:** `FIREFLIES_API_KEY` в `~/.config/hermes/.env`  
**Endpoint:** `https://api.fireflies.ai/graphql`  
**Auth:** Bearer token в заголовке

### Получить список транскриптов
```bash
FF_KEY=$(grep FIREFLIES_API_KEY ~/.config/hermes/.env | cut -d'=' -f2)
curl -s -X POST https://api.fireflies.ai/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $FF_KEY" \
  -d '{"query": "{ transcripts(limit: 10) { id title date duration } }"}' \
  | python3 -m json.tool
```
`date` — Unix timestamp в миллисекундах.

### Получить полный транскрипт по ID
```bash
curl -s -X POST https://api.fireflies.ai/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $FF_KEY" \
  -d '{
    "query": "{ transcript(id: \"<ID>\") { id title date sentences { text speaker_name start_time end_time } } }"
  }' > /tmp/ff_transcript.json
```

### Разобрать через Python
```python
import json
with open('/tmp/ff_transcript.json') as f:
    data = json.load(f)
t = data['data']['transcript']
for s in t['sentences']:
    print(f"[{s['speaker_name']}]: {s['text']}")
```

### Питфолл: web_extract не работает
`web_extract("https://app.fireflies.ai/view/...")` → заблокировано (требует авторизации).  
Всегда использовать GraphQL API напрямую через `execute_code` + `terminal`.

---

## Workflow: транскрипт → нарратив (для Саши Ткаченко)

Когда нужно интегрировать живой разговор в литературный текст (отчёт о походе, дневник и т.п.), строго следовать этому порядку. **Не переходить к следующему шагу без подтверждения.**

### Шаг 1 — Фильтрация
Разделить на два списка:
- ✅ **Оставить** — эмоциональное, образное, путешественное, характерные детали
- ❌ **Выкинуть** — сиюминутное (организационное, бытовое), некрасивое, чужое (истории не про эту поездку)

Показать оба списка пользователю. Ждать подтверждения.

### Шаг 2 — Хронологизация
Разложить отфильтрованные фрагменты по дням/главам согласно плану.  
Где неясно — задавать вопросы в виде **предположений**:  
> «Это про день 6, подъём с дождиком? Или про день 7?»

Один вопрос за раз. Режим брифа.

### Шаг 3 — Подтверждение хронологии
Только после того как пользователь сказал «всё верно» / «.» / «ю» — переходить к интеграции.

### Шаг 4 — Интеграция
Вписать характерные детали и эмоциональный окрас из транскрипта в текст согласно плану, сохраняя хронологию.

---

## Питфолы
- Транскрипты Fireflies — живой разговор: много шума, повторений, обрывков. Не брать всё подряд.
- Speaker names дефолтные (Speaker 1, 2, 3...) — не надеяться на идентификацию по имени.
- Длинные транскрипты (>1000 реплик) читать через `execute_code`, не в контекст напрямую.
- «TUTU» в транскриптах Саши — артефакт Fireflies, скрывает корпоративные имена. Игнорировать.
- **Вечерний разговор ≠ хронология дня.** Участники вспоминают события вразброс, перескакивают между днями. Никогда не привязывать фрагмент к дню без подтверждения автора.
- **Разговор в день X может быть про события дня X-1 или X-2.** В походе записи Fireflies — вечерние посиделки: обсуждают вчерашнее и позавчерашнее.
- **Одна запись может содержать несколько дней.** Длинный транскрипт (1539 реплик) = вечер после дня 7, но упоминаются события дней 1–7.
- **Контекст записи:** у Саши — запись в ресторане в Каспийске в вечер последнего дня (день 7, п.14). Всё что там сказано — взгляд назад на весь поход.
