---
tool: MoveFromFF
version: 2.4.1
date: 2026-08-29
status: active
last-section-added: 2026-08-29 — добавлен раздел ## Контракты экосистемы (ретрофит §2c)
---

# MoveFromFF ТЗ

Дата редакции: 2026-05-25 (v2.1)
Автор: Opus (на основе обсуждения с А. Ткаченко)
Актуализация формата: 2026-07-03 (миграция в единую TZ-схему).
v2.2 (2026-07-05): доработка apps_preview custom-skill реализована и подтверждена владельцем — см. секцию ниже и §9 «Результаты реализации».

## Изменения относительно v2.0

- Двухэтапная загрузка (fetch_range → fetch_meeting) сохранена.
- Вместо временного «фильтра готовности» (READY_THRESHOLD_H = 1ч) теперь
  используется **pending backoff**: запись с `status=pending` хранит
  `attempts` и `next_retry_at`, и повторно опрашивается с экспоненциальным
  расписанием.
- Появилось **умное окно для cron**: from_dt = max(last_synced_at, now-24ч),
  что устраняет потерю встреч между cron-запусками и убирает повторное
  чтение одного и того же окна.
- Реестр получил поле `last_synced_at` и три новых поля на запись
  (`attempts`, `next_retry_at`, `first_seen_at`).
- Введён TG-алерт `notify_meeting_stale` после `MAX_PENDING_ATTEMPTS = 12`
  безуспешных попыток (переход pending → error).
- SCHEMA_VERSION = "2.1". Миграция v2.0 → v2.1 автоматическая и
  обратно совместимая (новые поля получают дефолты, `extra="ignore"`).

---

## §1 Назначение (без изменений)

См. ТЗ v2.0. Утилита раз в N минут (cron) или вручную вытаскивает
расшифровки и summary встреч из Fireflies и кладёт markdown-файлы в папку
`new_meetings/`, поддерживая реестр `_registry.json`.

## §2 Источники данных (без изменений)

- Fireflies GraphQL API: `transcripts(fromDate, toDate, …)` для листинга и
  `transcript(id) { … sentences summary … }` для полной выгрузки.
- На тарифе Pro `audio_url` всегда null и не используется.

## §3 Алгоритм синхронизации — ОБНОВЛЁН

### Шаг 1. Ping (без изм.)

`ff.ping()` → GraphQL `user { user_id email }`.

### Шаг 2. Умное окно

- `mode=test`   → `from = now - 5 дней`, `to = now`.
- `mode=manual` → `from/to` от пользователя.
- `mode=cron`   → новое поведение:
  - если `registry.last_synced_at` задан:
    `from = max(last_synced_at, now - 24ч)`,
  - иначе (первый запуск или после ручной чистки):
    `from = now - 4ч30мин`.
  - `to = now`.

Этим окном вызывается `ff.fetch_range(from, to)`.

### Шаг 3. Двухэтапная загрузка + pending backoff

Для каждой встречи `m` из `fetch_range`:

1. `rec = registry.meetings.get(m.id)`.
2. Если `rec.status == "completed"` → `meeting_skipped`, продолжить.
3. Если `rec.status == "pending"`:
   - если `now < rec.next_retry_at` → `meeting_backoff` (skip);
   - если `rec.attempts >= MAX_PENDING_ATTEMPTS`:
     - `rec.status = "error"`,
     - `meeting_stale` в лог,
     - TG-алерт `notify_meeting_stale`,
     - skip.
4. Иначе (новая встреча, либо pending после backoff): вызвать
   `full = ff.fetch_meeting(m.id)`. Ошибка/None → `download_error`.
5. Если `full.summary.overview` пуст:
   - upsert pending-записи: `attempts += 1`,
     `next_retry_at = now + PENDING_BACKOFF_MINUTES[attempts-1]`,
     заполнить title/duration/participants/first_seen_at,
   - `meeting_pending` в лог; продолжить.
6. Иначе summary есть → `write_meeting_files`, статус `completed`,
   `meeting_skipped`/`download_ok` в лог.

### Шаг 4. Финализация

- Если `not dry_run and errors == 0 and not meeting_id`:
  `registry.last_synced_at = to.isoformat()`.
- `save_registry` (атомарно).
- Сгенерировать `_registry.md`.
- Лог `run_summary`, TG-уведомления для manual mode.

## §3A cron mode: no-LLM execution (added 2026-08-06)

**Контекст.** Крон `vm_movefromff` исторически был настроен как
LLM-агент (модель `openai/gpt-oss-20b:free`), который лишь запускал
скрипт синхронизации. Синхронизация MoveFromFF (Шаги 1–4 из §3) —
чисто механическая операция: HTTP-запрос списка встреч к Fireflies
GraphQL API, скачивание transcript + summary для новых встреч, запись
файлов на диск, обновление реестра. Никакого рассуждения, генерации
текста или принятия решений естественным языком в этом цикле нет —
всё детерминировано кодом Python (§3, §4–§10). LLM-обёртка вокруг
такой задачи не добавляет ценности, а лишь создаёт лишнюю точку
отказа: вызовы `openai/gpt-oss-20b:free` подвержены rate-limit
провайдера, из-за чего cron-прогоны стали падать без связи с самим
скриптом синхронизации.

**Решение.** Cron-режим запускается **без LLM-обёртки**:

- Параметр планировщика: `no_agent=true`.
- Прямой вызов скрипта/модуля Python, без промежуточного LLM-агента:
  `movefromff_sync.sh` (обёртка) → `python -m movefromff --mode cron`.
- LLM **не используется** ни на одном шаге пайплайна синхронизации
  (§3 Шаг 1–4): запрос окна, fetch_range, fetch_meeting, запись
  файлов, обновление `_registry.json` — всё выполняется прямым кодом.
- Единственный AI-компонент во всей цепочке — пользовательский
  **Fireflies Custom AI Skill** (`apps_preview.outputs`, см. раздел
  «Доработка: вывод самари из apps_preview custom-скилла», v2.2),
  который работает **на стороне Fireflies** (генерирует саммари до
  того, как MoveFromFF о нём вообще запрашивает данные) и никак не
  связан с LLM-агентом крона. MoveFromFF лишь читает готовый
  `response` через GraphQL — это не вызов LLM из нашего кода.

**Что это меняет.** Устраняется зависимость cron-прогона от
доступности/лимитов стороннего LLM-провайдера. Логика §3–§10
(алгоритм, реестр, retry, дедупликация, TG-алерты) не меняется —
меняется только способ запуска (без LLM-обёртки вместо LLM-агента).

**Что НЕ меняется:** сам код `movefromff` (§3–§10), реестр, TG-канал,
конфигурация Fireflies Custom AI Skill.

## §4 Схема реестра v2.1

`MeetingRecord` — новые поля:

| Поле             | Тип            | Назначение |
|------------------|----------------|------------|
| `attempts`       | `int = 0`      | Сколько раз пытались `fetch_meeting`. |
| `next_retry_at`  | `Optional[str]`| ISO-8601 UTC, когда разрешена следующая попытка. |
| `first_seen_at`  | `Optional[str]`| ISO-8601 UTC, когда встреча впервые попала в окно. |

`Registry` — новое поле:

| Поле             | Тип            | Назначение |
|------------------|----------------|------------|
| `last_synced_at` | `Optional[str]`| Конец последнего успешного окна (для умного окна cron). |

Переходы статусов:

```
new → pending → completed
        ↓
       error  (attempts >= MAX_PENDING_ATTEMPTS)
```

## §5 Константы

| Имя | Значение |
|---|---|
| `MAX_PENDING_ATTEMPTS` | `12` |
| `PENDING_BACKOFF_MINUTES` | `[5, 10, 20, 30, 60, 60, 120, 120, 120, 120, 120, 120]` |

Индекс = `attempts - 1` (0-based). После последнего — 120 мин.

Сумма ≈ 5+10+20+30+60+60+120·6 = 905 минут ≈ 15 ч — гарантированно
покрывает обычные задержки FF-сборки summary (5–30 мин) и даёт запас на
сутки до stale-алерта.

## §6 Коды событий лога

- `meeting_skipped` — статус уже completed.
- `meeting_backoff` — pending, next_retry_at в будущем.
- `meeting_pending` — fetch_meeting вернул пустой summary; обновлены
  `attempts` и `next_retry_at`.
- `meeting_stale` — `attempts >= MAX`, переход → error.
- `download_ok` — записан полный комплект файлов.
- `download_error` — `fetch_meeting` упал или вернул None, либо
  `write_meeting_files` бросило исключение.

## §7 TG уведомления

- `notify_meeting_stale(token, chat_id, meeting_id, title)` — отправляется
  один раз в момент перехода pending → error (если `not no_tg`).
- Прочие уведомления (`notify_manual_success`, `notify_manual_error`) —
  без изменений.

## §8 Миграция реестра v2.0 → v2.1

- `load_registry` принимает `schema_version ∈ {"2.0", "2.1"}` без миграции
  записей: pydantic-модель с `extra="ignore"` подставляет дефолты для
  новых полей (`attempts=0`, `next_retry_at=None`, `first_seen_at=None`,
  `last_synced_at=None`).
- При следующем `save_registry` файл перезаписывается уже как v2.1.
- Старые записи v1.x по-прежнему мигрируются через `_migrate_record`.

## §9 Экономия API-вызовов

Старая схема (v2.1-«первая редакция»): фильтр готовности 1 ч; если
встреча моложе 1 ч, в каждом cron-запуске (раз в 30 мин) мы вызывали
только `fetch_range`, но как только встрече > 1 ч — `fetch_meeting` шёл
**каждый запуск** до тех пор, пока summary не появится.

Новая схема: первый пустой ответ ставит `next_retry_at = now + 5 мин`,
следующий — `+10`, `+20`, `+30`, `+60`. То есть для типичного «summary
готов через 20 мин» один fetch_meeting на встречу против ~3–4 ранее в
тот же промежуток. На «зависших» встречах: 12 попыток за 15 ч против
~30 попыток в старой схеме.

Дополнительно: «умное окно» исключает повторные `fetch_range`
одинакового интервала — между cron-запусками реально новое окно
≈ (now − last_synced_at), обычно 30 мин.

## §10 Дедупликация встреч (добавлено 2026-05-27)

Fireflies иногда фиксирует одну и ту же встречу 2+ раз. После
`reconcile_registry` и ДО основного цикла скачивания вызывается
`detect_and_mark_duplicates(reg, new_meetings_dir, logger)`.

### Правило дубля

Две записи считаются дублями, если ВСЕ условия выполнены:

1. Одинаковый `title` (после `strip()`, точное совпадение).
2. Разница `meeting_date` ≤ **10 минут**
   (`DEDUP_TIME_THRESHOLD_MIN`).
3. Пересекаются `participants` (хотя бы один общий email). Если у одной
   из встреч `participants` пусто — пересечение считается. Строки
   «email1,email2,…» из реальных дампов разворачиваются через `split(',')`.

### Выбор winner-а

При сравнении двух записей `_pick_winner` использует приоритеты:

1. **Размер transcript-файла на диске** (если у обеих есть). Кто больше — winner.
2. **Has transcript** — если файл есть только у одной → она winner.
3. **`duration_minutes`** — у кого больше.
4. **`meeting_date`** — более поздняя.
5. Tiebreaker — оставляем первую по порядку.

### Что происходит с проигравшим

- Все файлы из `rec.files` физически удаляются с диска.
- `rec.files = {}`.
- `rec.status = "duplicate"`.
- Лог-событие `meeting_duplicate` с полями `meeting_id`, `winner_id`,
  `title`, `reason ∈ {transcript_size, has_transcript, duration,
  later_date, tiebreaker}`.

### Состояние `duplicate`

- `Status = Literal["pending", "completed", "error", "duplicate"]`.
- Основной цикл скачивания обрабатывает `duplicate` так же, как
  `completed`: запись скипается, никогда не перекачивается, лог
  `meeting_skipped`.
- `reconcile_registry` НЕ сбрасывает `duplicate` в `pending` (даже если
  файлов на диске нет — это нормально).
- Кандидаты для дедупликации: только записи в статусах `completed` /
  `pending`. Записи `error` / `duplicate` не пере-анализируются.

### Группировка >2 дублей

Используется union-find; для каждой связной компоненты из N≥2 записей
выбирается один winner, остальные (N-1) помечаются `duplicate`
последовательным сравнением.

---

## §11 Санитизация имён файлов (добавлено 2026-06-22)

При создании файлов transcript/summary имя проходит через `sanitize_title()`.

### Проблема

Заголовки встреч в Fireflies могут содержать эмодзи (например,
`🔺 ML-платформа Kolmogorov...`). ownCloud/WebDAV не поддерживает
4-байтные Unicode символы (codepoint > U+FFFF) в именах файлов →
ошибки при `rclone sync`.

### Решение

Функция `sanitize_title()` в `filename.py` расширена (v2.1.1):

1. **Удаляет символы вне BMP** (codepoint > U+FFFF) — эмодзи, специальные символы
2. **Удаляет управляющие символы** (Unicode categories Cc, Cf)
3. Заменяет Windows-invalid символы (`\ / : * ? " < > |`) на `_`
4. Коллапсирует множественные пробелы → один пробел
5. Убирает trailing dots/spaces

### Пример

```
Вход:  "🔺 ML-платформа Kolmogorov. Работаем с планом"
Выход: "ML-платформа Kolmogorov. Работаем с планом"
```

### Совместимость

- WebDAV (owncloud) ✓
- Linux ✓  
- Windows ✓
- Кириллица и другие BMP-символы сохраняются

---

## Планируемая доработка: timezone в именах файлов (draft 2026-06-03)

**Статус:** проектируется, ждёт подтверждения Саши.
**Полное ТЗ:** `~/WorkVault/Hermes-Backlog/ТЗ-MoveFromFF-Timezone.md`

### Проблема

`filename.py::filename_date_part` сейчас принудительно конвертирует
`datetime` в **UTC** перед формированием `YYYY-MM-DD HH-MM-SS`. Реальные
встречи проходят по МСК (UTC+3), и человек ожидает увидеть в имени
файла московское время, а видит UTC (смещение −3 часа).

### Решение (кратко)

1. Ввести `LOCAL_TZ = ZoneInfo("Europe/Moscow")` в `config.py` с
   возможностью override через `MOVEFROMFF_LOCAL_TZ`.
2. В `filename_date_part` заменить `astimezone(timezone.utc)` →
   `astimezone(LOCAL_TZ)`.
3. **Реестр НЕ менять** — `meeting_date` остаётся UTC ISO с `+00:00`.
   Дедупликация и `_compute_age_hours` продолжают работать в UTC.
4. Миграция существующих ~475 файлов: одноразовый скрипт
   `scripts/migrate_filenames_to_msk.py` с dry-run, бэкапом реестра,
   pre/post-reconcile проверкой; ownCloud-клиент на время миграции
   останавливается во избежание конфликт-копий.

### Инварианты, которые сохраняются

- Ключ реестра = `meeting_id` (ULID Fireflies), не имя файла →
  переименование не плодит дублей.
- Формат имени `YYYY-MM-DD HH-MM-SS Title — kind.md` и регэксп
  `FF_FILENAME_RE` не меняются.
- Дедупликация (см. раздел «Дедупликация встреч») продолжает работать
  по `meeting_id` без изменений.


---

## Доработка: вывод самари из apps_preview custom-скилла — РЕАЛИЗОВАНО (запланировано 2026-07-03, реализовано 2026-07-03, подтверждено 2026-07-05, v2.2)

> Влито в master-ТЗ 2026-07-03 из точечного файла `ТЗ-MoveFromFF-apps-preview-summary.md` (правило "не распыляться по документам одного инструмента, доработки существующего инструмента = секция в master-ТЗ"). Реализовано по `cursor-implementation-prompt.md` с учётом находок ревью (`cursor-review-findings.md`); результаты подтверждены владельцем 2026-07-05 (см. §9 ниже).

# ТЗ: MoveFromFF — вывод в `summary.md` результата пользовательского Custom AI Skill из Fireflies (`apps_preview.outputs`)

**Статус:** ✅ реализовано и подтверждено (v2.2)
**Дата постановки:** 2026-07-03 · **Дата реализации:** 2026-07-03 · **Дата подтверждения:** 2026-07-05
**Проект:** `/home/tkachenkoav/USERTOOLS/MoveFromFF/`
**Master-ТЗ:** этот файл, `MoveFromFF_TZ.md` (v2.2)
**Связанные файлы:** `movefromff/ff_client.py`, `movefromff/ff_schema.py`, `movefromff/renderer.py`, `movefromff/templates/summary_custom.md.j2` (новый), `movefromff/writer.py`, `movefromff/__main__.py`, `movefromff/config.py`, `.env.example`, `tests/`

---

## 1. Цель

Начиная с 02.07.2026 у пользователя `tkachenkoav` в Fireflies подключён личный Custom AI Skill **«tkachenkoav ff summary prompt 01072026»** (`app_id=6a44d3b85f38b61f42f21cf2`), который автоматически прогоняется на каждой новой встрече и генерирует структурированное саммари (Участники / Решения / Блокеры / Задачи / Риски).

**Что меняем:** если для встречи есть результат этого скилла — используем его как основной контент `summary.md`. Если результата нет (устаревшая встреча / скилл не отработал / отключён) — оставляем текущий стандартный формат саммари (см. ТЗ-MoveFromFF-summary-fields-20260527.md) без изменений.

**Зачем:** пользовательский скилл содержит более релевантную и структурированную сводку (в т.ч. по-русски и в фиксированном формате «Решения / Задачи / Риски»), чем стандартные FF-блоки. Стандартный формат сохраняем как надёжный fallback.

**Маппинг:**

| Условие                                                                                                        | Контент `summary.md`                                                              |
|-----------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------|
| В `apps_preview.outputs[]` есть элемент с `title == <FF_CUSTOM_SKILL_TITLE>` и непустым `response`             | Тело файла = `response` этого элемента (markdown as-is, только заголовок сверху) |
| Иначе                                                                                                          | Текущий стандартный шаблон `summary.md.j2` (Bullet points / Notes / Action items / Blockers / Questions / Meeting Outline / Topics / Keywords) |

---

## 2. Контекст (кратко)

- GraphQL-поле `apps_preview.outputs[]` уже проверено вживую (тест-скрипт `test_custom_summary.py`, файл `test_custom_summary_results.json`). Для встречи `01KWKPM0J86H0227T0PGHBF8WE` возвращается массив из одного элемента с полями `app_id`, `title`, `response`, `created_at`.
- В продовом `_MEETING_FIELDS_FULL` (`ff_client.py`) поле `apps_preview` **не запрашивается** — нужно завести.
- В `FFMeeting` / `FFSummary` (`ff_schema.py`) модели под `apps_preview.outputs[]` **нет** — нужно добавить.
- В `renderer.py` / `templates/summary.md.j2` логика ветвления «кастомный скилл vs стандарт» **не реализована** — нужно добавить.
- Название скилла может меняться (переименование / новый скилл) → выносим в конфиг.

---

## 3. Что НЕ трогать

- **Встречи до 02.07.2026** — этим ТЗ **не бэкафилятся**. У них в `apps_preview.outputs[]` нет элемента с нужным title → сработает стандартный fallback. Ретроактивный запуск скилла в FF UI на старых встречах — отдельная будущая задача, вне scope.
- `transcript.md.j2`, `render_transcript()` — формат транскрипта не меняется.
- `registry.py`, `registry.md.j2`, `render_registry_md()` — реестр не меняется (поле «есть кастомный саммари да/нет» **не добавляем** в этой итерации).
- `_MEETING_FIELDS_LIST`, `fetch_range()` — лёгкий запрос для листинга не трогаем.
- Существующие поля `overview`, `notes`, `action_items`, `keywords`, `extended_sections` — поведение и модель не меняются. Они по-прежнему запрашиваются и десериализуются; просто в случае «кастомный скилл есть» они **не рендерятся** в `summary.md`.
- CLI-флаги, дедупликация, перенос файлов в WorkVault, обработка ошибок / retry.
- `QUERY_PING`, аудио, платные поля.

---

## 4. Алгоритм доработки (по файлам)

### 4.1 `movefromff/config.py` (+ `.env` / `.env.example`)

Добавить конфигурируемое поле в существующий pydantic `Settings` (НЕ модульную константу — верхнеуровневый `os.getenv()` выполнится до `_ensure_env_loaded()`/`load_dotenv()`, значение из `.env` будет проигнорировано, всегда возьмётся дефолт):

```python
class Settings(BaseModel):
    # ... существующие поля ...
    custom_skill_app_id: str = ""    # NEW. Основной идентификатор скилла — стабилен при переименовании в FF UI.
    custom_skill_title: str = ""     # NEW. Fallback, если app_id не задан. Пустая строка у обоих = фича off.
```

В `load_settings()`:

```python
custom_skill_app_id=os.environ.get("FF_CUSTOM_SKILL_APP_ID", "6a44d3b85f38b61f42f21cf2").strip(),
custom_skill_title=os.environ.get("FF_CUSTOM_SKILL_TITLE", "tkachenkoav ff summary prompt 01072026").strip(),
```

В `.env.example` добавить обе строки с комментарием: `app_id` — основной идентификатор (стабилен, не меняется при переименовании скилла в FF UI), `title` — fallback на случай, если `app_id` не задан. В `.env` пользователя — фактические значения (уже совпадают с дефолтами).

`render_summary()` получает оба значения как аргументы (или через `settings`-объект), НЕ через top-level `from movefromff.config import FF_CUSTOM_SKILL_TITLE` — иначе monkeypatch в тестах (§7.2) не подействует (связывание имени происходит при импорте, до патча).

### 4.2 `movefromff/ff_schema.py`

Добавить новую модель и поле в `FFMeeting`:

```python
class FFAppOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    app_id: Optional[str] = None
    title: Optional[str] = None
    response: Optional[str] = None
    created_at: Optional[Any] = None  # FF возвращает ISO-строку или timestamp; храним сырым


class FFAppsPreview(BaseModel):
    model_config = ConfigDict(extra="ignore")

    outputs: List[FFAppOutput] = Field(default_factory=list)


class FFMeeting(BaseModel):
    # ... существующие поля ...
    apps_preview: Optional[FFAppsPreview] = None  # NEW
```

**Хелпер (в конце файла):**

```python
def find_custom_skill_output(
    meeting: "FFMeeting", skill_app_id: str, skill_title: str = ""
) -> Optional[FFAppOutput]:
    """Возвращает output пользовательского скилла, либо None.

    Поиск: сначала по точному app_id (стабилен, не меняется при переименовании
    скилла в FF UI), затем — если app_id не задан или не нашёл совпадений —
    fallback на точное совпадение title (case-sensitive, trim по краям).
    Пустой response трактуем как «нет результата».
    При нескольких подходящих outputs берём ПЕРВЫЙ непустой по порядку в списке
    (created_at — сырое поле без гарантированного формата, сортировка по нему
    ненадёжна; на практике дублей на одну встречу не встречается).
    """
    ap = meeting.apps_preview
    if ap is None or not ap.outputs:
        return None

    if skill_app_id:
        needle_id = skill_app_id.strip()
        for out in ap.outputs:
            if (out.app_id or "").strip() == needle_id and (out.response or "").strip():
                return out

    if skill_title:
        needle_title = skill_title.strip()
        for out in ap.outputs:
            if (out.title or "").strip() == needle_title and (out.response or "").strip():
                return out

    return None
```

> Приоритет: `app_id` → `title` (fallback). Если ни один параметр не задан (обе строки пустые) — фича выключена, функция вернёт `None` для любой встречи.

### 4.3 `movefromff/ff_client.py`

Обновить только `_MEETING_FIELDS_FULL` — добавить блок `apps_preview`, **НЕ трогая `extended_sections`** (реальная прод-схема FF — `{ title content }`, не `{ title items text }`; правка `extended_sections` сломает GraphQL-запрос и существующий тест `test_query_full_includes_notes_and_extended_sections`):

```python
_MEETING_FIELDS_FULL = """
id
title
date
duration
participants
sentences {
  index
  speaker_id
  speaker_name
  text
  start_time
  end_time
}
summary {
  overview
  action_items
  keywords
  outline
  notes
  extended_sections {
    title
    content
  }
}
apps_preview {
  outputs {
    app_id
    title
    response
    created_at
  }
}
""".strip()
```

`_MEETING_FIELDS_LIST` — без изменений.

**Замечания:**
- Если FF на нашем тарифе временно вернёт ошибку типа `Cannot query field "apps_preview"` — поле убрать из запроса, зафиксировать в README TODO и оставить fallback работать (в схеме `apps_preview: Optional`, десериализация не упадёт). По исследованию — поле доступно.

### 4.4 `movefromff/renderer.py`

В `render_summary(meeting: FFMeeting) -> str` добавить ветвление в самом начале:

```python
from movefromff.ff_schema import find_custom_skill_output

def render_summary(meeting: FFMeeting, custom_skill_app_id: str = "", custom_skill_title: str = "") -> str:
    custom = find_custom_skill_output(meeting, custom_skill_app_id, custom_skill_title)
    if custom is not None:
        tmpl = _env.get_template("summary_custom.md.j2")
        return tmpl.render(
            title=meeting.display_title,
            body=custom.response.strip(),
            skill_title=custom.title,
        )

    # --- fallback: текущий стандартный рендер (без изменений) ---
    tmpl = _env.get_template("summary.md.j2")
    summary = meeting.summary
    sections = (summary.extended_sections if summary else []) or []
    return tmpl.render(
        title=meeting.display_title,
        overview=(summary.overview if summary else None),
        notes=(summary.notes if summary else None),
        action_items=(summary.action_items if summary else None),
        keywords=keywords_as_text(summary.keywords if summary else None),
        blockers=section_as_text(find_extended_section(sections, "Blockers")),
        questions=section_as_text(find_extended_section(sections, "Questions")),
        meeting_outline=section_as_text(find_extended_section(sections, "Meeting Outline")),
        topics=section_as_text(find_extended_section(sections, "Topics")),
    )
```

### 4.5 Новый шаблон `movefromff/templates/summary_custom.md.j2`

```jinja
{% if title -%}
# Саммари: {{ title }}
{% else -%}
# Саммари встречи
{% endif %}

{{ body }}
```

**Замечания по шаблону:**
- `body` рендерим as-is (`response` уже приходит в markdown). Никакого пост-процессинга, экранирования или добавления заголовков секций поверх — они уже внутри `response` (Участники / Решения / Блокеры / Задачи / Риски).
- Заголовок H1 — единственная добавка, чтобы файл был визуально консистентен со стандартным `summary.md`.
- Финальный `\n` в конце файла — как в существующем `summary.md.j2` (проверить визуально; в тестах — `.endswith("\n")`).

Существующий `summary.md.j2` — **не трогаем**, он используется в fallback-ветке как есть.

---

## 5. Схема данных

### 5.1 Что добавляется в `FFMeeting`

```
FFMeeting
├── ... (существующее)
└── apps_preview: Optional[FFAppsPreview]
    └── outputs: List[FFAppOutput]
        ├── app_id: Optional[str]
        ├── title: Optional[str]
        ├── response: Optional[str]
        └── created_at: Optional[Any]
```

### 5.2 Registry (`registry.py`, `registry.md.j2`)

**Не меняется в этой итерации.** Флаг «использован кастомный скилл» в реестр не добавляем. Если позже понадобится колонка «Source: custom/standard» — отдельная микро-задача.

### 5.3 Config

| Ключ (env / config)         | Тип   | Дефолт                                       | Назначение |
|------------------------------|-------|----------------------------------------------|------------|
| `FF_CUSTOM_SKILL_APP_ID`     | str   | `6a44d3b85f38b61f42f21cf2`                   | Основной идентификатор Custom AI Skill в `apps_preview.outputs[].app_id`. Стабилен при переименовании скилла в FF UI. |
| `FF_CUSTOM_SKILL_TITLE`      | str   | `tkachenkoav ff summary prompt 01072026`     | Fallback-поиск по `apps_preview.outputs[].title`, используется только если `app_id` не задан или не даёт совпадений. |

Обе строки пустые → фича полностью выключена, всегда стандартный шаблон.

---

## 6. Критерии успеха

1. **GraphQL:** ручной `_post(QUERY_TRANSCRIPT_BY_ID, {"id": <id>})` возвращает `data.transcript.apps_preview.outputs[]` для встречи с прогнанным скиллом (например `01KWKPM0J86H0227T0PGHBF8WE`) и `apps_preview: null` (или пустой outputs) для старой встречи.
2. **Кастомный путь:** для встречи, где есть output с нужным title, сгенерированный `summary.md`:
   - начинается с `# Саммари: <title>`;
   - далее содержит `response` из скилла без изменений (посекционно совпадает с исходным markdown);
   - **не содержит** стандартных заголовков `## Bullet points`, `## Notes`, `## Action items`, `## Blockers`, `## Questions`, `## Meeting Outline`, `## Topics`, `## Keywords` (кроме случая, когда эти строки органически присутствуют внутри `response` — что маловероятно, т.к. скилл выдаёт по-русски).
3. **Fallback:** для встречи без нужного output (в т.ч. любая встреча до 02.07.2026) `summary.md` идентичен тому, что генерируется сейчас — все существующие тесты рендера проходят без изменений.
4. **Пустой response:** если элемент с нужным title есть, но `response` пустой / whitespace → сработает fallback (стандартный шаблон), а не пустой файл.
5. **Config off:** при `FF_CUSTOM_SKILL_TITLE=""` рендер всегда идёт стандартным путём (регрессия off-состояния).
6. **Схема:** `apps_preview: None`, `apps_preview.outputs=[]`, отсутствие ключа `apps_preview` в JSON — все три сценария корректно десериализуются в `FFMeeting` без исключений.
7. **Smoke на реальных встречах:** прогнать fetch на 3 встречах — (a) свежая с отработавшим скиллом, (b) свежая без скилла / со стандартным AI Summary, (c) старая до 02.07.2026. Все три `summary.md` сгенерированы корректно; (a) — кастомный формат, (b) и (c) — стандартный.
8. **Регрессии:** весь существующий сьют `tests/` зелёный без правок ожиданий.
9. **Lint/type:** `mypy` / `ruff` (если используются) без новых ошибок.

---

## 7. Тестовый план

### 7.1 `tests/test_ff_schema.py` (новые)

- `test_ff_meeting_parses_apps_preview_outputs` — десериализация полного JSON с одним output.
- `test_ff_meeting_missing_apps_preview_defaults_none` — старый JSON без `apps_preview` → `meeting.apps_preview is None`.
- `test_ff_meeting_apps_preview_empty_outputs` — `{"apps_preview": {"outputs": []}}` → `meeting.apps_preview.outputs == []`.
- `test_find_custom_skill_output_returns_match` — title совпадает, response непустой → возвращает FFAppOutput.
- `test_find_custom_skill_output_title_mismatch_returns_none`.
- `test_find_custom_skill_output_empty_response_returns_none` — title совпадает, но `response` пустой / whitespace.
- `test_find_custom_skill_output_empty_skill_title_returns_none` — фича выключена (`skill_title == ""`).
- `test_find_custom_skill_output_no_apps_preview_returns_none`.

### 7.2 `tests/test_renderer.py` (новые + без правок существующих)

- `test_render_summary_uses_custom_skill_when_present` — meeting с валидным output и стандартным `summary` (overview, notes, ...): в результате есть `# Саммари: <title>` и содержимое `response`; отсутствуют строки `## Bullet points`, `## Action items` и т.п.
- `test_render_summary_falls_back_when_custom_skill_absent` — `apps_preview=None`: рендер идентичен текущему стандартному (сравнение с существующей golden-строкой или проверка ключевых заголовков).
- `test_render_summary_falls_back_when_custom_skill_title_mismatch` — есть output, но с другим title → стандартный шаблон.
- `test_render_summary_falls_back_when_custom_response_empty` — output с нужным title, но `response=""` → стандартный шаблон.
- `test_render_summary_falls_back_when_config_disabled` — `FF_CUSTOM_SKILL_TITLE=""` (monkeypatch) → стандартный шаблон, даже если output есть. **Важно:** проверить, что ветвление реагирует на актуальное значение конфига (импорт внутри функции или чтение через `settings.` объект — на усмотрение исполнителя, но testable).

### 7.3 `tests/test_ff_client.py` (новые/обновление)

- `test_query_full_includes_apps_preview` — `_MEETING_FIELDS_FULL` содержит подстроки `apps_preview`, `outputs`, `response`, `app_id`, `title`, `created_at`.
- `test_fetch_meeting_parses_apps_preview` — мок HTTP-ответа с `apps_preview.outputs[<1 элемент>]` → `meeting.apps_preview.outputs[0].response` заполнен.
- `test_fetch_meeting_tolerates_missing_apps_preview` — мок ответа без `apps_preview` → `fetch_meeting` возвращает `FFMeeting`, `apps_preview is None`.

### 7.4 Данные для тестов

**Инлайн, без файлов-фикстур** — в этом репозитории тесты строят данные через dict/pydantic-объекты + `MockSession` прямо в теле теста (проверено по `tests/test_ff_schema.py`, `tests/test_renderer.py`, `tests/test_ff_client.py`), каталога `tests/fixtures/` нет и практики так делать тоже нет. Собрать `apps_preview`-моки тем же способом, не заводить новую практику ради одной фичи.

**Ожидаемое покрытие:** ~13–15 новых тестов, итог по сьюту ≈ 83–85 тестов, все зелёные.

---

## 8. План работы (для исполнителя)

1. Добавить `FF_CUSTOM_SKILL_TITLE` в `config.py` и `.env.example`. Проверить чтение из `.env`.
2. Обновить `ff_schema.py` (модели `FFAppOutput`, `FFAppsPreview`, поле в `FFMeeting`, хелпер `find_custom_skill_output`) + юнит-тесты.
3. Обновить `_MEETING_FIELDS_FULL` в `ff_client.py` + тесты на строку query и парсинг мока.
4. Добавить шаблон `templates/summary_custom.md.j2`.
5. Обновить `render_summary()` в `renderer.py` (ветвление в начале) + тесты рендера (позитив, 4 варианта fallback, config-off).
6. Прогнать `pytest tests/ -v`. Все зелёные.
7. Smoke на 3 реальных встречах (см. §6.7). Приложить примеры `summary.md` (custom + fallback) к PR.
8. После мержа — обновить master-ТЗ до v2.2 отдельным коммитом (не в этом ТЗ).

---

## 9. Результаты реализации (2026-07-05)

Реализация выполнена по плану §8, с одним непредусмотренным в ТЗ, но необходимым дополнением и одной мелкой находкой, устранённой на месте:

- **Проброс конфига до вызова рендера.** ТЗ описывало сигнатуру `render_summary(meeting, custom_skill_app_id, custom_skill_title)`, но не описывало, как эти значения попадают туда из `settings` в реальном пайплайне. Добавлен проброс через `write_meeting_files()` (`writer.py`) и оба места вызова в `__main__.py` — иначе фича осталась бы недостижимой в проде (всегда дефолтные пустые строки → fallback). `writer.py`/`__main__.py` не входят в раздел «Что НЕ трогать» ТЗ.
- **Финальный `\n` в `summary_custom.md.j2`.** Из-за `keep_trailing_newline=False` у общего Jinja `_env` кастомный шаблон изначально не заканчивался переводом строки (стандартный `summary.md` — `\n\n`). Добавлен запасной перевод строки в конце исходника шаблона; `_env` не менялся (риск регрессии в других шаблонах). Добавлен тест `test_render_summary_custom_ends_with_newline`.

**Тесты:** `pytest tests/ -v` → 147 passed (было 117 до доработки; план ожидал ~83–85 итого — фактическое покрытие шире плана §7, включая доп. кейсы приоритета app_id над title и дублей outputs). Регрессий нет, ожидания существующих тестов не менялись. `ruff check` по изменённым файлам — новых ошибок нет (3 предсуществующих F401 в `renderer.py`, не связаны с доработкой, не исправлялись — вне scope).

**Smoke на реальных встречах FF** (критерий §6.7):

| Сценарий | Встреча | Путь рендера | Результат |
|---|---|---|---|
| (a) свежая со скиллом | `01KWKPM0J86H0227T0PGHBF8WE`, 2026-07-03, «Trisigma. Обсуждаем вопросы от Авиа» | CUSTOM | `# Саммари: <title>` + response скилла (Участники/Решения/Блокеры/Задачи/Риски), без стандартных заголовков, файл заканчивается `\n\n` |
| (b) свежая без скилла | не найдена в окне 21 день — на дату проверки все встречи после 02.07.2026 имели отработавший скилл | — | подтверждено косвенно: 8 renderer-тестов на fallback (нет output / промах app_id и title / пустой response / фича выключена) |
| (c) старая до 02.07.2026 | `01KWCHT4GKSZ733TMC8R1HZWNX`, 2026-07-01, «Подведение результатов АБ по снижению СС» | FALLBACK | стандартный `summary.md` (`## Bullet points`, `## Action items`, …) без изменений |

Примеры файлов сохранены на ВМ во время сессии в `/tmp/mff_smoke/` (не персистентно; при необходимости smoke можно перезапустить в любой момент — скрипт не сохранён в репозитории, только результат в этом отчёте).

**Артефакты:**
- Снапшот кода до правок: `~/USERTOOLS/MoveFromFF/.backups/pre-apps-preview-20260703-193404.tgz`
- Снапшот этого ТЗ до бампа версии: `~/WorkVault_backup/Hermes-Backlog/TZ/MoveFromFF/MoveFromFF_TZ_snapshots-20260705-1617.tgz`

**Открытые вопросы ревью** (`cursor-review-findings.md`) — закрыты по решению «рекомендация Cursor принята полностью»: поиск по `app_id` с fallback на `title`, при дублях — первый непустой по порядку (не по `created_at`), `created_at` оставлен `Optional[Any]`, конфигурация — только через pydantic `Settings`.

---

## Планируемая доработка: обрезка имени файла по байтам UTF-8 (XFS Namelen=255) (2026-07-05)

### Контекст / проблема

Встреча `01KVZK8BQ8790CBM2K9TQZ9D9B` (Trisigma, 2026-06-26) зависла в статусе `pending` в реестре и валилась при каждой попытке записи с ошибкой `OSError: [Errno 36] File name too long` от XFS.

Заголовок:
> «Trisigma. Смотрим статус развертывания и тестов, что можно проверить заранее, и разбираем риски SDK и худший сценарий по ошибкам в AA-тестах»

Итоговое имя `<дата> <время> <title> - transcript.md` содержало ~163 символа, что укладывалось в исторический лимит `MAX_FILENAME_LEN = 200` — но в UTF-8 это 281 байт, потому что почти все символы кириллические (по 2 байта). XFS/ext4/btrfs накладывают лимит **255 байт** на один компонент пути (`stat -f -c '%l'` → `Namelen: 255`), поэтому `write` падал ещё до атомарного `rename`.

Симптом на уровне registry: `status=pending`, `attempts` инкрементится, `next_retry_at` двигается по экспоненте, но каждая повторная попытка воспроизводит ту же ошибку — имя детерминировано из `meeting_dt` и `title`, backoff проблему не лечит. После `MAX_PENDING_ATTEMPTS=12` встреча уходит в `error` и триггерит TG-алерт — но исправление на этом уровне уже поздно.

### Решение

В `movefromff/filename.py` добавляем второй, байтовый слой обрезки в `build_filename()` — поверх существующего символьного (`MAX_FILENAME_LEN=200`):

1. Константа `MAX_FILENAME_BYTES = 255` — жёсткий FS-лимит.
2. Хелпер `_truncate_to_bytes(text, max_bytes)` — обрезает строку так, чтобы её UTF-8 представление ≤ `max_bytes`, не разрывая многобайтовый символ (walk back по continuation-байтам `0b10xxxxxx`).
3. В `build_filename()` после символьной обрезки — если `len(name.encode('utf-8')) > 255`, режем **только title**, префикс `YYYY-MM-DD HH-MM-SS ` (20 байт ASCII) и суффикс ` - transcript.md` / ` - summary.md` (16/13 байт ASCII) не трогаем. Резервируем 3 байта под ellipsis `…`.

### Инварианты (сохраняются)

- **Ключ реестра — `meeting_id`**, не имя файла (§6, §2). Обрезка не создаёт коллизий: две встречи с одинаковым префиксом заголовка и датой всё равно различаются по `meeting_id` в `registry.json`; на диске возможна дубляжная запись имени только если совпадёт `date + time + первые ~230 байт title`, что при секундной точности времени и разной семантике встреч не встречается на практике. При гипотетическом столкновении сработает существующий `_unique_path()` в `writer.py`.
- **Обратная совместимость**: короткие ASCII-заголовки проходят оба слоя без изменений (тест `test_short_ascii_name_unchanged`), все существующие тесты `tests/test_filename.py` остаются зелёными.
- **Границы UTF-8**: обрезка всегда на lead-байте, `decode('utf-8')` результата никогда не бросает (тест `test_utf8_no_split_mid_character`).
- **Суффикс не портится**: `parse_filename()` по-прежнему матчит имя через `FF_FILENAME_RE`, поле `kind` восстанавливается корректно.

### Тесты

Добавлены в `tests/test_filename.py::TestBuildFilename`:
- `test_utf8_byte_length_limit_cyrillic` — регрессия по реальному кейсу встречи `01KVZK8BQ8790CBM2K9TQZ9D9B`: проверяет ≤255 байт и сохранность prefix/suffix.
- `test_utf8_no_split_mid_character` — 200 кириллических символов (400 байт), проверяет round-trip encode/decode.
- `test_short_ascii_name_unchanged` — backward compat для коротких ASCII имён.

Все 150 тестов зелёные.

### Что НЕ трогаем в этой доработке

- Логика реестра, backoff, `MAX_PENDING_ATTEMPTS`, TG-алерты — без изменений.
- Существующее правило символьной обрезки (`MAX_FILENAME_LEN=200`) — оставлено как первый слой (для «пусть коротко визуально» кейсов).
- WebDAV/owncloud sanitization (эмодзи, non-BMP, control chars) — работает как раньше, до байтовой обрезки.

### Ручной допуск зависшей встречи — ВЫПОЛНЕНО 2026-07-13

Встреча `01KVZK8BQ8790CBM2K9TQZ9D9B` (26.06.2026) была перекачана вручную после деплоя фикса (детали — см. секцию «Ручной допуск ранее битой встречи» ниже). Больше не в pending.

## Доработка: ужесточение byte-limit имени файла под ownCloud — РЕАЛИЗОВАНО И ПРОВЕРЕНО (2026-07-13)

**Статус:** ✅ реализовано, протестировано (151/151 тестов), проверено живым синком на ownCloud (лог чист после фикса, ручной `owncloud-sync.service` прошёл `status=0/SUCCESS`).

### Контекст

Фикс от 2026-07-05 (см. секцию «UTF-8 byte-length safeguard») выставил
`MAX_FILENAME_BYTES = 255` — это лимит локальной ФС на ВМ (XFS `Namelen=255`,
подтверждено `stat -f`). После деплоя фикса длинные кириллические имена
легально ложились на диск, но systemd-timer `owncloud-sync.timer` (rclone,
каждые 10 мин, лог `~/.local/share/hermes/logs/owncloud-sync.log`) начал
стабильно падать с ошибкой:

```
Failed to copy: unchunked simple update failed: File name is too long.:
OCA\DAV\Connector\Sabre\Exception\FileNameTooLong: 400 Bad Request
```

на файлах встречи `01KVZK8BQ8790CBM2K9TQZ9D9B` (Trisigma, 26.06.2026):
transcript — 255 байт, summary — 254 байта. То есть XFS 255 — не тот
лимит, который действительно ограничивает синк: реальная граница — WebDAV
сервер ownCloud, и она заметно ниже.

### Эмпирические измерения (2026-07-13)

Бинарный поиск через `rclone copyto` в `owncloud:WorkVault/_test*/` тестовых
файлов с кириллическими именами разной длины:

| Байт | Результат |
|------|-----------|
| 220 | OK |
| 224-228 | OK, но нестабильно (пограничная зона) |
| 229-230+ | стабильно `FileNameTooLong` (400 Bad Request) |

Тестовые папки удалены после измерений.

Гипотеза о нестабильной границе 228-230: сервер вероятно считает не чистый
basename, а что-то дополнительное (полный путь / нормализованное имя в БД
/ URL-encoded вариант). Отсюда — впритык к границе подбирать нельзя.

### Решение

`MAX_FILENAME_BYTES_OWNCLOUD = 180`, `MAX_FILENAME_BYTES` (публичное имя
константы для обратной совместимости) теперь ссылается на него. Запас
~50 байт ниже нестабильной границы 228-230 — страховка от:

- промежуточных прокси/redirect, которые могут добавлять байты в путь,
- возможного будущего ужесточения серверного лимита,
- URL-encoding кириллицы (в некоторых сценариях `%D0%B0` вместо `а`
  раздувает передаваемое имя, хотя стандартный WebDAV принимает UTF-8).

Логика двухслойной обрезки (`_truncate_to_bytes`, обрезка на границе
UTF-8-символа) уже была — переиспользована как есть, изменена только
константа + комментарии в `filename.py`.

### Что сделано в коде

- `movefromff/filename.py`: константа `MAX_FILENAME_BYTES` = 180
  (+ псевдоним `MAX_FILENAME_BYTES_OWNCLOUD`), развёрнутый комментарий с
  историей лимита и обоснованием.
- `tests/test_filename.py`: существующие тесты `test_utf8_byte_length_limit_cyrillic`
  и `test_utf8_no_split_mid_character` скорректированы с `≤255` на `≤180`;
  добавлен новый тест `test_owncloud_byte_limit_various_cyrillic_titles` —
  прогоняет несколько длинных кириллических заголовков, все укладываются
  в 180 байт, границы UTF-8 не бьются.
- Полный тест-сьют зелёный: **151 passed** (по сравнению со 150 в v2.2 —
  +1 новый тест).

### Ручной допуск ранее битой встречи

Встреча `01KVZK8BQ8790CBM2K9TQZ9D9B` перекачана вручную:
- запись в реестре сброшена в `status=pending`, `files={}`, `attempts=0`;
- старые файлы (255/254 байт) удалены с диска;
- `python -m movefromff --mode manual --meeting-id 01KVZK8BQ8790CBM2K9TQZ9D9B --no-tg --verbose` создал новые:
  - `... и р… - transcript.md` — 179 байт;
  - `... и раз… - summary.md` — 180 байт;
- ручной `rclone copyto` обоих файлов на ownCloud прошёл без ошибок,
  файлы видны в `rclone lsf owncloud:WorkVault/Meetings/NewMeetings/`.

Дальше обычный `owncloud-sync.timer` подхватит всё сам, доп. рестартов
не нужно.

### Что НЕ трогаем

- Символьный лимит `MAX_FILENAME_LEN = 200` — оставлен как первый слой.
- WebDAV-sanitization (эмодзи, non-BMP, control chars) — работает как раньше.
- `owncloud-sync.timer`/`.service` — конфиг не менялся.
- Реестр, backoff, TG-алерты, миграции — не тронуты.

## Штатный паттерн «тихого исключения» встречи из обработки (2026-07-13)

### Контекст и корневая причина инцидента

У MoveFromFF **нет** штатного механизма исключить конкретную встречу из
дальнейшей обработки: в `movefromff/registry.py` не существует полей/флагов
`exclude`/`ignore`/`skip`/`blacklist`, и enum `MeetingRecord.status`
допускает только четыре значения: `pending`, `completed`, `error`,
`duplicate`.

12.07.2026 возникла разовая задача: исключить личную встречу
`01KXAGX7CE86QHBSBMD2PVYPZ9` (заголовок `Jul 12, 09:40 AM`, единственный
участник — сам Саша). Первая попытка (Sirene/Sonnet) — вписать в JSON
реестра `status: "excluded_personal"` — сломала pydantic-валидацию всей
модели реестра: `load_registry()` падал на `ValidationError`, и **весь
инструмент переставал видеть любые встречи**. Крон `vm_movefromff`
несколько часов (10:00–14:00 13.07.2026) молча ничего не обрабатывал —
его промпт трактовал ненулевой exit code как «нет новых встреч», а это
был реальный traceback.

Мораль: любое произвольное значение в поле `status` — не «безобидная
метка», а фатальная поломка всего цикла синхронизации.

### Официальный паттерн (решение Саши: «давай и далее исключать записи подобным образом»)

Пока в коде не появится настоящий механизм exclusion (см. «Открытый
пункт» ниже), встречу исключают **редактированием записи в
`_registry_meet.json` вручную**, приводя её к виду:

```json
{
  "title": "<оригинальный title>",
  "meeting_date": "<оригинальный ISO datetime>",
  "duration_minutes": <оригинальное число>,
  "participants": [<оригинальный список>],
  "files": {"transcript": "", "summary": ""},
  "status": "completed",
  "fetched_at": "<текущий UTC ISO Z>",
  "attempts": 0,
  "next_retry_at": null,
  "first_seen_at": "<оригинальный first_seen_at или текущее время>"
}
```

Ключ meeting_id в `meetings` остаётся исходный (`01K…`).

### Почему именно так — обоснование каждого поля

- **`status: "completed"`** — единственный валидный enum-статус, который
  говорит «эту встречу больше не трогаем». `pending`/`error` вернут её в
  очередь ретраев, `duplicate` семантически неверен (это не дубль).
- **`files: {"transcript": "", "summary": ""}`, а НЕ `{}`.**
  В `reconcile_registry()` (см. `movefromff/registry.py`, ~строки
  237–254) для записей со `status=completed` выполняется проверка:
  ```python
  missing = [fn for fn in rec.files.values()
             if fn and not (new_meetings_dir / fn).exists()]
  ```
  - Если `files={}` — срабатывает отдельная ветка «completed без
    файлов = аномалия» и запись сбрасывается обратно в `pending`
    (встреча снова попадает в цикл, всё зря).
  - Если `files={"transcript":"","summary":""}` — итератор проходит по
    значениям, но `if fn` на пустой строке даёт False, и missing
    остаётся пустым. Проверка «все файлы на месте» проходит **без
    реальных файлов на диске**. Запись остаётся `completed` навсегда.
- **`attempts: 0`, `next_retry_at: null`** — на всякий случай, чтобы
  никакой будущий проход не подумал, что запись «в процессе».
- **`fetched_at`** — обновить на момент правки, для аудита.

Физическое удаление файлов транскрипта/саммари с диска (и из
ownCloud-зеркала) — **осознанная часть паттерна**, если содержимое не
должно попасть в дальнейшие пайплайны (RAG, aggregate). Оставлять их не
нужно.

### Чеклист применения (для будущих случаев)

1. Найти meeting_id встречи в `~/WorkVault/Meetings/NewMeetings/_registry_meet.json`
   (ключ в объекте `meetings`).
2. **Сначала сделать бэкап реестра**:
   `cp ~/WorkVault/Meetings/NewMeetings/_registry_meet.json{,.bak-YYYYMMDD-HHMM}`.
3. Отредактировать запись строго по шаблону выше. Проверить, что:
   - `status` = ровно `"completed"` (никаких `excluded_*`, `skipped`,
     `ignored` — pydantic упадёт, инструмент ослепнет).
   - `files` = `{"transcript": "", "summary": ""}` (обе строки пустые,
     но словарь НЕ пустой).
4. Если файлы `<title> - transcript.md` / `<title> - summary.md`
   существуют в `~/WorkVault/Meetings/NewMeetings/` — удалить их (и
   дождаться, пока `owncloud-sync.timer` уберёт их с ownCloud), либо
   удалить и на ownCloud напрямую через `rclone deletefile`.
5. Прогнать `python -m movefromff --mode cron --no-tg --verbose` один
   раз и убедиться:
   - в stdout нет traceback / `ValidationError`;
   - в stdout нет упоминания этого meeting_id как pending/error;
   - в реестре запись после прогона по-прежнему `status=completed`, не
     сбросилась обратно.
6. Записать в `~/WorkVault_backup/_moved-YYYY-MM-DD.log` строку вида
   `EXCLUDED meeting <id> (<title>) via completed+empty-files pattern`.

### Жёсткие предупреждения

- **НИКОГДА** не вписывать произвольные строки в поле `status` реестра.
  Допустимо только одно из `pending` / `completed` / `error` /
  `duplicate`. Любое другое значение — мгновенная поломка всего цикла
  синхронизации через `ValidationError` в `load_registry()`.
- **НИКОГДА** не оставлять `files: {}` при `status=completed` — запись
  сбросится обратно в pending на первом же `reconcile_registry()`, и
  встреча снова попадёт в обработку.
- Не пытаться «на всякий случай» добавлять новые поля в JSON записи —
  `MeetingRecord` использует `extra="ignore"`, лишние поля молча
  игнорируются, а значит смысла от них нет; но полагаться на это как на
  «канал сигнала» нельзя.

### Открытый пункт (на будущее, НЕ реализовывать сейчас)

Текущий паттерн — **обходной путь**, который держится на двух
имплементационных деталях (`if fn` фильтрует пустые строки в
`reconcile_registry()` + `extra="ignore"` в pydantic-модели). Если
случаи ручного исключения встреч начнут повторяться регулярно (условно
>1 раза в месяц) — стоит добавить в код настоящий механизм:

- Новое enum-значение `MeetingRecord.status = "excluded"` (+ бамп
  `SCHEMA_VERSION` с обратно-совместимой миграцией).
- Отдельная короткая ветка в `reconcile_registry()` и в основном цикле
  `process_pending()` — «`excluded` пропускаем, аномалиями не считаем,
  ретраи не назначаем».
- CLI-команда `movefromff exclude <meeting_id> [--reason "..."]`,
  которая делает всё атомарно: правит запись, удаляет файлы с диска,
  логирует в `_moved-*.log`.
- Опционально — поле `excluded_reason: Optional[str]` для аудита.

Пока таких случаев мало (первый прецедент — 12.07.2026), заводить
отдельный механизм преждевременно. Зафиксировано как рекомендация,
триггер к реализации — повторяемость.

### Что НЕ трогаем (в рамках этой доработки-документирования)

- Код `movefromff/registry.py` и любые другие модули — не менялись.
- Enum `status`, схема `MeetingRecord`, `SCHEMA_VERSION` — не менялись.
- `reconcile_registry()`, `process_pending()`, миграции — не тронуты.
- Cron `vm_movefromff`, gateway, TG-алерты — не тронуты.


---

# §10 Доработка: детект и retry Custom AI Skill (v2.3)

Дата: 2026-07-28
Автор: Opus (по постановке А. Ткаченко)
Версия ТЗ: 2.3 (аддитивно к v2.2, обратно совместимо)
Статус: draft, ждёт реализации.

## §10.1 Цель

Сделать так, чтобы MoveFromFF **никогда не публиковал bullet-points-саммари
молча**, если для встречи должен был отработать пользовательский Custom AI
Skill в Fireflies. На практике Custom Skill иногда возвращает пустой
output — тогда `find_custom_skill_output()` → `None`, и `render_summary()`
падает на fallback-шаблон `summary.md.j2` (Bullet points). В итоге MOFS/PFS
получает не тот формат протокола, чем задумано.

Инструмент должен:

1. **Детектировать** факт fallback-а на bullet_points при записи summary.
2. **Ретраить** такие встречи 2 раза (через 5 и 10 минут), не считая их
   финально завершёнными.
3. **Уведомлять в TG**, если после 2 ретраев Custom Skill всё ещё пуст —
   с явной рекомендацией переимпортировать руками.

Backoff-механика pending из v2.1 остаётся нетронутой (она про отсутствие
overview целиком, а не про отсутствие custom-skill вывода). Новый механизм
живёт **параллельно** и триггерится только на успешно скачанных встречах
с непустым summary.overview, но пустым custom-skill output.

## §10.2 Текущее состояние (факт по коду, 2026-07-28)

- `movefromff/renderer.py::render_summary()` строки 48–82:
  - вызывает `find_custom_skill_output(meeting, custom_skill_app_id, custom_skill_title)`,
  - если `custom is not None` → рендер через `summary_custom.md.j2`,
  - иначе → fallback на `summary.md.j2` (bullet points).
  - Факт fallback никуда не пробрасывается: вызывающая сторона
    (`writer.py::write_meeting_files()`) получает только строку с markdown
    и записывает её на диск. Информации о формате нет.
- `movefromff/registry.py::MeetingRecord`: полей про формат summary нет.
  `status` ∈ {pending, completed, error, duplicate}. `SCHEMA_VERSION = "2.1"`.
- `movefromff/__main__.py` строки 444–492 (ветка «summary есть → записать
  файлы»): после `write_meeting_files()` запись сразу переводится в
  `status="completed"`. Дальше её никто не трогает.
- `movefromff/tg.py`: есть `send_message()`, `notify_manual_success()`,
  `notify_meeting_stale()`, `notify_manual_error()`. Канал для алертов —
  `settings.telegram_chat_id`.
- `movefromff/config.py::Settings`: есть `custom_skill_app_id`,
  `custom_skill_title`, `telegram_bot_token`, `telegram_chat_id`. Полей
  для управления новыми ретраями нет.

Вывод: точечная доработка — writer/renderer возвращает признак формата,
`__main__` использует этот признак для новой ветки ретрая, TG-алерт и
конфиг добавляются рядом с существующими.

## §10.3 §A — Детектирование формата саммари

**Изменения в renderer.py.**

- `render_summary()` **дополнительно** возвращает признак формата.
  Реализация: сменить сигнатуру на возврат кортежа
  `(text: str, format: Literal["custom", "bullet_points"])`.
  Логика:
  - `format = "custom"`, если `find_custom_skill_output(...) is not None`
    **и** `custom.response` после `.strip()` непусто;
  - `format = "bullet_points"` во всех остальных случаях (в т.ч. когда
    custom-skill объект есть, но `response` пуст/whitespace — трактуем как
    «не сработал»).
- Обратная совместимость: у вызывающей стороны один вызов
  (`writer.py::write_meeting_files`); менять оба места одним коммитом.
  Никаких публичных API вне пакета `render_summary` не отдаёт.

**Изменения в writer.py.**

- `write_meeting_files()` **дополнительно** возвращает `summary_format`
  (Literal["custom","bullet_points"]) вместе с текущим `files: Dict[str,str]`.
  Проще всего — возвращать кортеж `(files, summary_format)` либо
  `TypedDict`/dataclass `WriteResult(files=..., summary_format=...)`.
  Выбор — на реализатора; предпочтителен dataclass ради читаемости.

**Изменения в registry.py.**

- В `MeetingRecord` добавить поле:
  ```python
  summary_format: Optional[Literal["custom", "bullet_points"]] = None
  # None — старые записи (до v2.3) и pending-записи, где файл не писался.
  custom_skill_retries: int = 0  # сколько ретраев именно по причине bullet_points уже было
  ```
- `SCHEMA_VERSION` бампаем до `"2.3"`. Миграция: старые записи получают
  дефолты `summary_format=None`, `custom_skill_retries=0`. `extra="ignore"`
  и текущая логика `_migrate_record()` продолжают работать без правок,
  плюс аккуратно прокидываем новые поля из `raw`.

**Изменения в __main__.py (запись completed).**

- В блоке 460–492: после `write_meeting_files(...)` (который теперь
  возвращает `(files, summary_format)`) писать
  `rec_new.summary_format = summary_format` **до** установки статуса.
- Ниже — ветка §10.4 определяет статус.

## §10.4 §B — Retry-логика по пустому Custom Skill

**Триггер:** после успешной записи файлов на диск, если
`summary_format == "bullet_points"` и в системе включён Custom Skill
(`settings.custom_skill_app_id` или `settings.custom_skill_title` непусты),
запись **не** финализируется как обычная `completed`.

Поведение по статусам:

| Условие                                              | Действие                                                      |
| ---------------------------------------------------- | ------------------------------------------------------------- |
| `summary_format == "custom"`                         | `status = "completed"` (как сейчас, без изменений).            |
| `summary_format == "bullet_points"`, custom не настроен | `status = "completed"` (нам нечего ждать).                  |
| `summary_format == "bullet_points"`, `custom_skill_retries < MFF_CUSTOM_SKILL_RETRY_COUNT` | `status = "pending_custom_skill"`, `next_retry_at = now + delays[retries] минут`, `custom_skill_retries += 1`. |
| `summary_format == "bullet_points"`, `custom_skill_retries >= MFF_CUSTOM_SKILL_RETRY_COUNT` | `status = "completed_no_custom"` (финальный, из цикла выпадает). TG-алерт (см. §10.5). |

**Новые значения enum `Status`:**

```python
Status = Literal[
    "pending", "completed", "error", "duplicate",
    "pending_custom_skill",    # v2.3: ждём ретрая по custom-skill output
    "completed_no_custom",     # v2.3: сдались, live с bullet_points
]
```

Обратная совместимость: `_migrate_record()` не выбрасывает записи с этими
статусами. Все ветки `if rec.status == "completed"` в коде (`meeting_skipped`,
reconcile, backfill) сохраняют своё поведение только для `"completed"`;
`"completed_no_custom"` тоже должен трактоваться **как финальный** — т.е.
эти записи так же пропускаются в основном цикле (`meeting_skipped`) и в
backfill.

**Retry-механика:**

- Записи с `status == "pending_custom_skill"` обрабатываются в **отдельной
  ветке** в конце основного цикла `__main__`, до `write_registry()` (по
  аналогии с backfill из §3, но проще: нам не нужен fetch_range, только
  прямой `ff.fetch_meeting(mid)`).
- Условие взятия в работу: `now >= rec.next_retry_at`.
- Действия при ретрае:
  1. `full = ff.fetch_meeting(mid)`. Ошибка/None → сохранить `next_retry_at`
     как есть, лог `custom_skill_retry_fetch_error`, продолжить (не считать
     попытку израсходованной — это ошибка сети, а не пустой skill).
  2. Проверить `find_custom_skill_output(full, app_id, title)`:
     - Непустой → **перезаписать** summary-файл через
       `write_meeting_files()`, обновить `rec.files`, `rec.summary_format="custom"`,
       `rec.status="completed"`, `rec.next_retry_at=None`. Лог
       `custom_skill_retry_success`.
     - Пустой → `custom_skill_retries += 1`.
       - Если `custom_skill_retries < MFF_CUSTOM_SKILL_RETRY_COUNT`:
         `next_retry_at = now + delays[custom_skill_retries] минут`, лог
         `custom_skill_retry_still_empty`.
       - Иначе: `status = "completed_no_custom"`, `next_retry_at = None`,
         лог `custom_skill_retry_exhausted`, отправить TG (§10.5).

**Важно:** ретрай **не удаляет** уже записанный bullet-points файл. Пока
Custom Skill не отдал результат — на диске лежит fallback-саммари, MOFS/PFS
может его подхватить. Если ретрай успешен — файл перезаписывается
custom-версией; MOFS/PFS при следующем проходе увидит новый контент.

**Лимиты и защита:**

- В одном прогоне cron обрабатывать не более `MFF_CUSTOM_SKILL_RETRY_MAX_PER_RUN`
  записей (по умолчанию 5) — чтобы не выесть rate-limit FF, если внезапно
  30 встреч разом попали в `pending_custom_skill`. Константа рядом с
  `BACKFILL_MAX_PER_RUN`.
- `FFRateLimit` / `FFAuthError` / `FFTransientError` в ретрае → прекратить
  ветку, оставить всё как есть на следующий прогон (по аналогии с backfill).

## §10.5 §C — TG-уведомление

Новая функция в `movefromff/tg.py`:

```python
def notify_custom_skill_exhausted(
    bot_token: Optional[str],
    chat_id: Optional[str],
    meeting_id: str,
    title: str,
    meeting_date: Optional[str],
    retry_count: int,
) -> None:
    ...
```

Формат сообщения (Markdown, TG-канал `settings.telegram_chat_id`):

```
⚠️ MoveFromFF: нестандартный формат саммари
📌 <title>
🕐 <meeting_date в человеческом формате, YYYY-MM-DD HH:MM UTC или '—' если None>
❗ Custom AI Skill не вернул результат после <retry_count> попыток
🔧 Для переимпорта: python -m movefromff --mode manual --meeting-id <meeting_id>
```

Триггер: единственная точка вызова — момент перехода `status →
"completed_no_custom"` в §10.4. Дублей не будет: после этого перехода
запись становится финальной и больше в ветку ретрая не попадает.

Использовать существующий `send_message()`; экранирование Markdown — как
в `notify_meeting_stale()` (заголовок и meeting_id прогонять через
эскейпер, если он есть; если нет — обернуть в backticks).

При `bot_token`/`chat_id == None` (например, `--no-tg`) — тихий no-op,
как и все остальные `notify_*`.

## §10.6 §D — Конфигурация

Добавить в `movefromff/config.py::Settings`:

```python
custom_skill_retry_count: int = 2           # MFF_CUSTOM_SKILL_RETRY_COUNT
custom_skill_retry_delays: List[int] = [5, 10]  # MFF_CUSTOM_SKILL_RETRY_DELAYS, минуты
custom_skill_retry_max_per_run: int = 5     # MFF_CUSTOM_SKILL_RETRY_MAX_PER_RUN
```

Парсинг из env:
- `MFF_CUSTOM_SKILL_RETRY_COUNT` → `int(os.environ.get(..., "2"))`.
- `MFF_CUSTOM_SKILL_RETRY_DELAYS` → CSV `"5,10"` → `[5, 10]`. Валидация:
  длина списка должна быть `>= retry_count`; иначе — `RuntimeError` при
  старте (в `load_settings()`), не молчаливый фолбэк.
- `MFF_CUSTOM_SKILL_RETRY_MAX_PER_RUN` → `int(os.environ.get(..., "5"))`.

Обновить `.env.example` в корне репо (`~/USERTOOLS/MoveFromFF/.env.example`)
секцией с комментариями:

```
# --- Custom AI Skill retry (v2.3) ---
# Сколько раз перевыгружать встречу, если Custom AI Skill не вернул output.
MFF_CUSTOM_SKILL_RETRY_COUNT=2
# Задержки между попытками (минуты, CSV). Длина списка >= RETRY_COUNT.
MFF_CUSTOM_SKILL_RETRY_DELAYS=5,10
# Лимит ретраев за один cron-прогон (защита от rate-limit FF).
MFF_CUSTOM_SKILL_RETRY_MAX_PER_RUN=5
```

## §10.7 Тест-кейсы (минимум 5)

Все тесты — pytest, в `~/USERTOOLS/MoveFromFF/tests/`. Фикстуры FFMeeting
брать из существующих (`tests/fixtures/`), при необходимости добавить
новые с `apps_preview.outputs = []` и с пустым `response`.

**T1. Detect: Custom Skill вернул непустой response.**
- Вход: `FFMeeting` с `apps_preview.outputs[0].response = "## Итоги..."`.
- Ожидание: `render_summary()` → `(text, "custom")`; markdown содержит
  тело из custom-skill.

**T2. Detect: Custom Skill вернул пустой response (whitespace).**
- Вход: `apps_preview.outputs[0].response = "   \n  "`, но overview есть.
- Ожидание: `render_summary()` → `(text, "bullet_points")`; markdown —
  fallback из `summary.md.j2`.

**T3. Retry lifecycle: bullet_points → pending_custom_skill → success.**
- Прогон 1: встреча приходит, `summary_format="bullet_points"`,
  `custom_skill_app_id` настроен → запись становится
  `status="pending_custom_skill"`, `custom_skill_retries=1`,
  `next_retry_at = now + 5m`.
- Прогон 2 (через 5+ минут, мок `ff.fetch_meeting` возвращает встречу
  уже с custom-skill output) → запись становится `status="completed"`,
  `summary_format="custom"`, `next_retry_at=None`, файл summary
  перезаписан custom-версией.

**T4. Retry exhausted: bullet_points → 2 retry → completed_no_custom + TG.**
- Прогон 1: `pending_custom_skill`, `retries=1`, `next=+5m`.
- Прогон 2 (fetch снова без custom): `retries=2`, `next=+10m`.
- Прогон 3 (fetch снова без custom): `status="completed_no_custom"`,
  `next_retry_at=None`. Мок `notify_custom_skill_exhausted` вызван
  ровно 1 раз с правильными аргументами (meeting_id, title,
  meeting_date, retry_count=2).

**T5. Custom skill не настроен → нет ретраев.**
- `settings.custom_skill_app_id == ""` и `custom_skill_title == ""`.
- Даже если `summary_format == "bullet_points"` — статус сразу
  `"completed"`, никаких `pending_custom_skill`.

**T6. Migration: старая запись без summary_format читается корректно.**
- В `_registry_meet.json` запись v2.1 без полей `summary_format` и
  `custom_skill_retries`. После `load_registry()` они = `None` и `0`
  соответственно. Запись со `status="completed"` в основной цикл не
  затягивается (skip как раньше).

**T7. Rate limit в ретрае → не тратит попытку.**
- В ретрай-ветке `ff.fetch_meeting` бросает `FFRateLimit`. Ожидание:
  `custom_skill_retries` не увеличился, `next_retry_at` не сдвинулся,
  ветка ретрая прекращается, лог `custom_skill_retry_fetch_error` (или
  выделенный `custom_skill_retry_rate_limited`) записан.

**T8. TG выключен (`--no-tg` или пустой bot_token) → no-op, статус всё равно
   `completed_no_custom`.**

## §10.8 Что НЕ трогать

- `pending`-backoff из v2.1 (`MAX_PENDING_ATTEMPTS`, `PENDING_BACKOFF_MINUTES`,
  `notify_meeting_stale`) — отдельная механика, работает по overview, не
  по custom-skill. Не сливать в одно.
- `SCHEMA_VERSION`-миграции v1.x → v2.0 → v2.1 — оставить как есть,
  только добавить v2.1 → v2.3 (v2.2 = документная, не меняла схему).
- `reconcile_registry()` — не расширять; новая ветка ретраев живёт в
  своём блоке в `__main__`.
- MOFS/PFS не трогаем: они дальше по конвейеру, они не знают про
  `summary_format`. Их дело — читать файл с диска. Если ретрай успешен,
  файл перезаписан — они увидят новую версию на следующем проходе.
- Шаблоны `summary.md.j2` / `summary_custom.md.j2` — без правок.
- CLI-флаги — без новых обязательных; всё через env.

## §10.9 Критерии успеха

1. При bullet_points-саммари для встречи с настроенным custom-skill —
   инструмент **автоматически** делает до 2 ретраев с задержками 5 и
   10 минут (или значения из env) и перезаписывает файл, как только
   Custom Skill отдал результат.
2. После 2 неудачных ретраев в TG-канал `settings.telegram_chat_id`
   приходит одно (и только одно) сообщение по шаблону из §10.5.
3. Запись в `_registry_meet.json` содержит `summary_format` и
   `custom_skill_retries`, статус финализируется как `completed` (успех)
   или `completed_no_custom` (сдались).
4. Ни одна pending-запись v2.1-типа не путается с
   `pending_custom_skill`: обе живут параллельно, счётчики независимые
   (`attempts` vs `custom_skill_retries`).
5. Все существующие тесты продолжают проходить; новые тесты T1–T8
   зелёные.
6. При `MFF_CUSTOM_SKILL_RETRY_DELAYS`, длина которого меньше
   `RETRY_COUNT`, `load_settings()` падает с внятной ошибкой на старте —
   не молча и не в середине cron-прогона.
7. `.env.example` обновлён и коммит-ready; в `MAIN_TZ_INVENTORY.md`
   запись про MoveFromFF отражает v2.3.

## §10.10 Открытые вопросы (на согласование перед реализацией)

1. **Формат TG-даты встречи.** Взять `rec.meeting_date` как есть
   (ISO-8601 UTC), сконвертировать в Europe/Moscow или оставить UTC?
   По умолчанию в ТЗ — UTC с суффиксом `UTC`; если нужно локальное — уточнить.
2. **Файл на диске в промежутке между retry.** Оставлять fallback
   bullet-points-файл на диске (текущее решение в §10.4) или
   *не* писать summary до финализации? Второй вариант чище, но
   ломает поведение «MOFS/PFS видят что-то сразу». По умолчанию —
   оставить bullet_points на диске, перезаписать при успехе ретрая.
3. **Диагностика частоты.** Стоит ли добавить агрегированный
   ежедневный TG-summary «за сутки X встреч ушли в `completed_no_custom`»?
   Если проблема массовая — это сигнал переключаться на другой skill.
   Пока — вне scope, но пометить как «возможное расширение».

---

## Контракты экосистемы

### Источник истины
- Владелец исходных расшифровок и видеозаписей встреч: Fireflies GraphQL API (`fireflies`) и Zoom API (`api_zoom`).
- Владелец реестра встреч WorkVault: MoveFromFF (`~/WorkVault/Meetings/NewMeetings/_registry_meet.json` и файлы встреч в `vault_meetings_folder`).

### Входные контракты
| Поле | Тип | Обязательность | Источник (кто отдаёт) | Формат/enum |
|---|---|---|---|---|
| id | str | required | Fireflies GraphQL API | ULID встречи Fireflies (`transcript.id`) |
| title | str | required | Fireflies GraphQL API | Название встречи |
| date | datetime(iso8601) | required | Fireflies GraphQL API | Время проведения встречи (ISO-8601 UTC) |
| duration | int | optional | Fireflies GraphQL API | Длительность встречи в минутах |
| participants | str | optional | Fireflies GraphQL API | Список участников/email через запятую |
| sentences | str | optional | Fireflies GraphQL API | Список реплик спикеров транскрипта |
| overview | str | optional | Fireflies GraphQL API | Стандартное краткое описание встречи |
| apps_preview.outputs | str | optional | Fireflies GraphQL API | Результаты Custom AI Skill (`app_id`, `title`, `response`) |

### Выходные контракты
| Поле | Тип | Потребитель (кто получает) | Формат/enum |
|---|---|---|---|
| meeting_id | str | MofsIndex, ProtocolFromSummary, MOFS | ULID встречи в `_registry_meet.json` |
| title | str | MofsIndex, ProtocolFromSummary, MOFS | Очищенное имя встречи в файле и реестре |
| meeting_date | datetime(iso8601) | MofsIndex, ProtocolFromSummary | ISO-8601 UTC дата встречи |
| duration_minutes | int | MofsIndex, ProtocolFromSummary | Длительность в минутах |
| participants | str | AnywhereContacts, ProtocolFromSummary, MOFS | Список email участников встречи |
| status | enum[pending, completed, error, duplicate, pending_custom_skill, completed_no_custom] | MofsIndex, MoveFromFF internal | Статус обработки встречи в реестре |
| summary_format | enum[custom, bullet_points] | ProtocolFromSummary, MOFS | Формат сгенерированного summary |
| files | dict | MofsIndex, ProtocolFromSummary, MOFS | Пути к файлам `transcript` и `summary` |

### Зависимости
- Получает от: [Fireflies GraphQL API, Zoom API]
- Отдаёт: [MofsIndex, ProtocolFromSummary, MarkObjectsFromSummary]

### Breaking changes policy
- Версионирование реестра: поле `schema_version` внутри `_registry_meet.json` (текущая версия "2.3").
- При изменениях структуры реестра или схемы `MeetingRecord` обязательна автомиграция в `load_registry()` с поддержкой `extra="ignore"`.
- Маскирование и санитизация имён файлов (лимит 180 байт UTF-8 для ownCloud WebDAV) сохраняются для защиты от сбоев синхронизации.

### Границы («что НЕ трогать»)
- Встречи в статусе `completed` с `files: {"transcript": "", "summary": ""}` не сбрасывать обратно в `pending` при `reconcile_registry()`.
- Исключение встреч производить только штатным паттерном через `status="completed"` + `files={"transcript":"","summary":""}` или будущий явный механизм exclusion (запрещено вписывать произвольные невалидные enum-значения в `status`).
- Файлы `summary.md` и `transcript.md` генерируются строго в папке `NewMeetings/` (`vault_meetings_folder`).

