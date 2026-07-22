# MoveFromFF — карта полей Fireflies GraphQL API

Полное исследование API Fireflies.ai, консолидировано 27.05.2026 + 03.07.2026 (ревью Cursor).

## GraphQL-запрос для полного summary

```graphql
query {
  transcripts(limit: N) {
    id title date
    summary {
      overview short_summary gist bullet_gist shorthand_bullet
      outline action_items keywords notes
      extended_sections { title content }
    }
    apps_preview {
      outputs { app_id title response created_at }
    }
  }
}
```

## Стабильно заполненные поля summary

- `overview` — 5 буллетов, executive summary (~570–750 символов)
- `short_summary` — один связный абзац (~650 символов), удобен для уведомлений
- `gist` — одна фраза, цель встречи (~100 символов). Уникальный источник
- `bullet_gist` — те же 5 пунктов что overview, но с эмодзи. Уникальный источник
- `shorthand_bullet` — таймлайн встречи по фазам с таймкодами (MM:SS-MM:SS) + эмодзи-заголовки (~1500–1800 символов). Уникальный взгляд «как шла встреча по времени»
- `action_items` — plain-text строка, задачи сгруппированы по ФИО исполнителя с таймкодами. Единственный нативный источник «задача → человек»
- `keywords` — list[str], ~6 тегов. Для тегирования/поиска
- `extended_sections` — стабильно 4 секции: `Blockers`, `Questions`, `Meeting Outline`, `Topics`. Единственный источник блокеров и открытых вопросов с таймкодами
- `notes` — тематический нарратив ~6KB с подзаголовками (обнаружено 27.05.2026). В FF UI — блок «Notes» сразу после Bullet points. Отдельное поле типа String, не путать с `extended_sections`.
- `apps_preview.outputs` — массив переменной длины: все AI Skills, встроенные (`1:1`, `Meeting Summary Generator`) и любые пользовательские Custom Skills

## Маппинг FF UI → API (проверено 27.05.2026, встреча 01KSJ49AGHYFJTRARWAD088Q7N)

| Блок в FF UI | API поле | Примечание |
|---|---|---|
| Bullet points вверху | `summary.overview` | 5 буллетов с жирным заголовком |
| **Notes** | `summary.extended_sections` | FF так называет: Blockers / Questions / Meeting Outline / Topics |
| **1:1** (голубая Custom Skill) | `apps_preview.outputs[title="1:1"]` | Gist + Key Topics + Takeaways + Action Items + Decisions |
| **Meeting Summary Generator** (жёлтая Custom Skill) | `apps_preview.outputs[title="Meeting Summary Generator"]` | Самый полный протокол на русском: участники, обсудили, блокеры, задачи по людям |

Все три блока — отдельные визуальные блоки в FF UI, не один.

## Отклонения от документации

- `outline` — **ВСЕГДА null.** Не использовать. Структуру даёт `extended_sections[title="Meeting Outline"]`.
- Реальная форма `extended_sections`: поле называется `content` (не `items`). Структура: `{ title: String, content: String }`.
- `participants` = `[String]` (массив email-строк, НЕ объектов)
- `date` = Unix timestamp в миллисекундах, не ISO-строка
- `audio_url` = `null` на тарифе Pro
- `summary.action_items` = одна plain-text строка, не массив items
- Возможен полностью пустой summary (короткая/прерванная запись) — все поля null, `apps_preview.outputs = []`. Код обязан обрабатывать корректно.

## Custom AI Skills в apps_preview (консолидировано 03.07.2026)

Поля output: `app_id`, `title`, `response` (markdown as-is), `created_at`.

**Идентификация — по `app_id` с fallback на `title`** (решение 03.07.2026 после ревью Cursor): `app_id` стабилен и не меняется при переименовании скилла в FF UI, `title` — запасной вариант. При нескольких outputs с одинаковым app_id/title — брать первый непустой по порядку в списке (не сортировать по `created_at`: формат сырой, без гарантий).

Лёгкая проверка «есть ли вывод скилла» (без тяжёлого `response`):
```graphql
query Transcript($id: String!) {
  transcript(id: $id) { apps_preview { outputs { app_id title } } }
}
```

**Custom Skill работает только на новых встречах, НЕ ретроактивно.** `created_at` вывода совпадает по времени со встречей — скилл срабатывает автоматически при обработке транскрипта. Для встреч до даты подключения скилла вывода нет и не появится через API.

**В GraphQL API Fireflies НЕТ мутации для запуска AI Skill на существующей встрече.** Подтверждено интроспекцией схемы (03.07.2026): 18 мутаций (`updateMeetingTitle/Privacy/Channel`, `deleteTranscript`, `shareMeeting`, `createBite`, `createAskFredThread` и т.п.); ни `runApp`/`triggerSkill`/аналога. Backfill старых встреч кастомным скиллом — только вручную через FF UI, тратит AI credits, по одной встрече за раз, без bulk-API.

**Альтернативный bulk-запрос** (для аудита): `apps(app_id: String, transcript_id: String)` — outputs конкретного AI App по всем встречам, макс. 10/запрос, нужна пагинация.

**Паттерн доработки MoveFromFF:** если найден output нужного скилла → использовать его `response` как summary; если нет → fallback на стандартный формат (`overview`/`action_items`/`extended_sections`/`notes`). Идентификатор скилла — конфигурируемое поле в pydantic `Settings`, не хардкод.

## Питфолл `config.py` (03.07.2026)

Модульная константа `X = os.getenv(...)` на верхнем уровне выполняется ДО `_ensure_env_loaded()`/`load_dotenv()` — значение из `.env` тихо игнорируется, всегда берётся дефолт. Новые конфигурируемые поля — только в pydantic `Settings`, читать в `load_settings()`. До ревью Cursor 03.07.2026 в ТЗ фиксировалась ошибочная версия с модульной константой.

## Техника интроспекции GraphQL-схемы

Полезна для любого GraphQL-сервиса, не только FF:
```graphql
query { __schema { mutationType { fields { name } } queryType { fields { name } } } }
```

Быстрая проверка реальных возможностей API вместо гадания по документации. Документация `docs.fireflies.ai` недоступна через `web_extract` (блокируется как internal network address) — интроспекция + `web_search` по `guide.fireflies.ai` надёжнее.

## Рекомендации по использованию полей

- Компактный превью → `short_summary` или `overview`
- Визуальная шпаргалка → `bullet_gist` или `shorthand_bullet`
- Задачи по людям → `action_items` (нативно) или `apps_preview[Meeting Summary Generator]` (детальнее)
- Блокеры/вопросы с таймкодами → `extended_sections`
- Полный архивный протокол → `apps_preview.outputs[Meeting Summary Generator].response`

Тестовый скрипт: `USERTOOLS/MoveFromFF/test_ff_full_summary.py`
