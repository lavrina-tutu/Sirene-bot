# ТЗ: Инструмент MoveFromFF v2.0 — минимальная версия
# Перенос встреч из Fireflies.ai → Obsidian WorkVault
# Версия: 2.0 (minimal) | Дата: 2026-05-22 | Статус: На согласовании
# Замещает: v1.0 + v1.1_addendum

---

## 0. Философия (главное)

**MoveFromFF делает ОДНО:** забирает из Fireflies три файла на встречу (transcript / summary / actions) и кладёт их в `NewMeetings/`. Один раз. Идемпотентно.

Всё остальное — задача следующих инструментов конвейера. В первую очередь — **MarkObjectsFromSummary** (разметка, frontmatter, перемещение в Processed/).

**Принцип не-делания:**
- Не редактируем содержимое (никакой LLM, никакой нормализации текста).
- Не добавляем YAML-frontmatter.
- Не сверяем целостность файлов SHA-256 (если пользователь руками изменил файл — это его дело).
- Не отслеживаем «удалено в FF», «изменено локально», «пропало с диска».
- Не перемещаем, не архивируем, не удаляем.
- Не делаем reconcile диск ↔ реестр.
- Не отслеживаем постобработку (что downstream сделал с файлами — нас не касается).

**Один источник истины — `_registry.json`:** «эти `meeting_id` уже скачаны». Точка.

---

## 1. Что остаётся (из v1.0 / v1.1)

| Блок v1.0/v1.1 | Судьба в v2.0 | Комментарий |
|---|---|---|
| 3 файла на встречу (transcript / summary / actions) | ✅ Остаётся | Ядро инструмента |
| GraphQL-клиент к FF + retry (tenacity) | ✅ Остаётся | Без изменений |
| Pydantic-модели FF-ответа (`ff_schema.py`) | ✅ Остаётся | Упрощённая схема (§5) |
| Идемпотентность по `meeting_id` | ✅ Остаётся | Главный механизм «не качать повторно» |
| Режимы `--mode test / cron / manual` | ✅ Остаётся | Без `deleted-check` и `--reconcile-only` |
| UTC везде (даты, имена файлов, реестр) | ✅ Остаётся | Подтверждено |
| Именование файлов `YYYY-MM-DD HH-MM-SS Title - {kind}.md` | ✅ Остаётся | Sanitize и обрезка по длине |
| Portalocker-лок процесса | ✅ Остаётся | Защита от двойного запуска |
| Атомарная запись JSON (`tmp + os.replace`) | ✅ Остаётся | Базовая надёжность |
| `.env` для секретов и путей | ✅ Остаётся | Без хардкода путей |
| Templates jinja2 для 3 markdown-файлов | ✅ Остаётся | Рендер через `writer.py` |
| **`_registry.md`** (markdown-вид реестра) | ✅ Остаётся | Генерируется из `_registry.json` через `renderer.py` + Jinja2. Без доп. запросов к FF — чистая конвертация JSON → Markdown для удобства чтения человеком. |
| **Минимальная статусная машина загрузки** (`status` ∈ {`pending`, `completed`, `error`}) | ✅ Остаётся | Только результат загрузки. Никакой постобработки. |
| TG-уведомления **только при ручном запуске** (`--mode manual` или TG-команда `обнови ff`) | ✅ Остаётся | Cron/test — без TG, всё в `_log.md`. См. §7 |
| `_log.md` + `logs/movefromff.jsonl` | ✅ Остаётся | Минимальный формат, см. §8 |
| Коды выхода 0/1/2/3/4 | ✅ Остаётся | Те же |

---

## 2. Что исключается (минус из v1.0 / v1.1)

| Что было | Почему убрано |
|---|---|
| **SHA-256 контроль целостности** (`hashing.py`, поле `sha256` в реестре) | Если пользователь руками изменил файл — это его право, не моё дело. Восстановление из FF не нужно: downstream-инструмент уже мог унести файл, и «возвращать» его опасно. |
| **Реконсиляция диск ↔ реестр** (`reconciler.py`, статус `missing_locally`, `modified_locally`) | Усложнение без задачи. «Реестр говорит — скачано» — этого достаточно. |
| **Статус `source = manual`** (файлы, положенные руками) | MoveFromFF не должен ничего знать о ручных файлах. Это область ответственности пользователя. |
| **Режим `--mode deleted-check`** (проверка удалённых в FF за 90 дней) | Отдельный инструмент / отдельный cron-джоб. В MVP не нужен. Если потребуется — отдельное ТЗ. |
| **Режим `--reconcile-only`** | Нечего реконсилировать. |
| **Сложная схема статусов** (`transfer_status` ∈ {pending, completed, failed, deleted_in_ff, missing_locally}, `integrity` ∈ {ok, modified_locally, unknown}) | Заменена на минимальную: только `status` ∈ {`pending`, `completed`, `error`} — результат загрузки и ничего больше. |
| **Поля постобработки** (`processing_status`, `moved_by`, `moved_at`, `moved_to`, статусы `in_progress` / `done`) | Это область ответственности downstream (MarkObjectsFromSummary). MoveFromFF не должен знать, что произошло после загрузки. |
| **`errors[]` в записи реестра** | При ошибке загрузки — запись в реестр **не создаётся** (попробует в следующий cron). Ошибка — в jsonl-лог и TG. |
| **`_pending_ff.json`** (встречи в статусе Processing) | Просто пропускаем, попадут в следующее окно (overlap 30 мин или 24 ч). |
| **Поле `audio_url`** в реестре и в transcript | На тарифе Pro всегда `null`. Не выводить. |
| **Шифрование (Cryptomator)** | Отдельная инфраструктурная задача, к коду MoveFromFF не относится. |
| **Подробная нормализация полей FF** (вся таблица §13 v1.1) | Минимум: `date` (UTC), `duration` (как есть), `participants` (как есть), `speaker_name` (если пусто — `Speaker N`). Остальное — слово в слово как отдаёт FF. |
| **Длинная матрица TG-алертов** (7 строк) | 2 правила, см. §7. Cron/test вообще не шлёт в TG. |
| **DoD с 16 пунктами** | Сжимается до 7 пунктов, см. §10. |

---

## 3. Полный алгоритм (v2.0)

### Шаг 0. Preflight
1. Взять `portalocker`-лок `.locks/movefromff.lock`. Занят → exit 2.
2. Проверить `.env`: `FIREFLIES_API_KEY`, `WORKVAULT_PATH`. Нет → exit 2 (+ TG только если `--mode manual`; для `cron`/`test` — только в `_log.md`).
3. Создать недостающие папки: `NewMeetings/`, `logs/`, `.locks/`.

### Шаг 1. Ping Fireflies
- `query { user { user_id } }`, таймаут 15 с, 3 retry с backoff 2/4/8 с.
- Недоступен → exit 3 (+ TG только если `--mode manual`; для `cron`/`test` — только в `_log.md` и `logs/movefromff.jsonl`).

### Шаг 2. Запрос окна
- `--mode test` → `from = now_utc - 5 дней`
- `--mode cron` → `from = now_utc - 4ч 30мин` (overlap)
- `--mode manual --from-date --to-date` → произвольный интервал (UTC)
- GraphQL: `transcripts(fromDate, toDate, limit=50)` с пагинацией.

### Шаг 3. Фильтр и скачивание
Для каждой встречи из ответа FF:
1. **Если `meeting_id` уже есть в `_registry.json`** → пропустить (лог `skipped`).
2. **Иначе** скачать полный объект (`transcript`, `summary`, `sentences`), отрендерить 3 markdown-файла, записать на диск (атомарно: tmp + replace).
3. **При успехе** — добавить запись в реестр (атомарно: tmp + replace всего файла).
4. **При ошибке** на конкретной встрече:
   - Файлы (если частично записаны) — удалить.
   - В реестр **ничего не писать**.
   - Записать строку в `logs/movefromff.jsonl` с `event=download_error`, `meeting_id`, `error`.
   - **Продолжить** с остальными встречами.
   - При следующем запуске эта встреча попадёт в окно снова и будет повторно скачана (если ещё есть в FF).

### Шаг 4. Финализация
- Дописать строку в `_log.md` (одна строка-итог: см. §8).
- Сгенерировать `_registry.md` из `_registry.json` (`renderer.py` + Jinja2; никаких запросов к FF) и записать атомарно (tmp + replace).
- Снять лок.
- Если `--mode manual` — отправить TG-алерт по правилам §7. Для `--mode cron` / `--mode test` TG не дёргать вообще.
- Exit 0 (всё ок) / 1 (часть встреч упала) / 3 (FF недоступен) / 4 (фатально).

**Никакой реконсиляции, никакой проверки целостности, никакого scan диска.**

---

## 4. Схема `_registry.json` (минимальная)

```json
{
  "schema_version": "2.0",
  "updated_at": "2026-05-22T14:30:00Z",
  "meetings": {
    "<meeting_id>": {
      "title": "Встреча с клиентом",
      "meeting_date": "2026-05-20T11:30:00Z",
      "duration_minutes": 47.3,
      "participants": ["a@tutu.ru", "b@example.com"],
      "files": {
        "transcript": "2026-05-20 11-30-00 Встреча с клиентом - transcript.md",
        "summary":    "2026-05-20 11-30-00 Встреча с клиентом - summary.md",
        "actions":    "2026-05-20 11-30-00 Встреча с клиентом - actions.md"
      },
      "status": "completed",
      "fetched_at": "2026-05-22T14:30:05Z"
    }
  }
}
```

**Правила:**
- Все даты — UTC ISO-8601 с `Z`.
- `files.*` — только имена файлов (без путей), относительно `NewMeetings/`.
- `status` ∈ {`pending`, `completed`, `error`} — **минимальная статусная машина результата загрузки**:
  - `pending` — встреча обнаружена в FF, загрузка ещё не завершена (промежуточное состояние внутри одного запуска).
  - `completed` — все 3 файла успешно записаны на диск.
  - `error` — последняя попытка загрузки упала; запись остаётся, чтобы downstream/человек видели проблему. В следующий cron MoveFromFF может попробовать снова.
- Других состояний нет. Никакой постобработки в этом поле не отражается.
- Поле `meeting_id` хранится как ключ объекта `meetings` — дублировать его внутрь не нужно.

**Никаких полей:** `transfer_status`, `integrity`, `source`, `processing_status`, `moved_by`, `moved_at`, `moved_to`, `errors`, `sha256`, `audio_url`, `last_checked_at`, `keywords` (keywords попадают в `summary.md` — этого достаточно).

---

## 5. Содержимое 3 файлов

### `transcript.md`
```
# {{ title }}

**Дата (UTC):** {{ meeting_date_iso }}
**Длительность:** {{ duration }} мин
**Участники:** {{ participants | join(", ") }}
**Meeting ID:** {{ meeting_id }}

---

## Транскрипт

[MM:SS] **{{ speaker_name }}:** {{ text }}
...
```
- Если `speaker_name` пустой/null → `Speaker N` (N — индекс уникального спикера в этой встрече, 1-based).
- Если `start_time ≥ 3600` сек → формат `[HH:MM:SS]`.

### `summary.md`
```
# Саммари: {{ title }}

## Overview
{{ summary.overview }}

## Action Items
{{ summary.action_items }}

## Keywords
{{ summary.keywords }}
```
- Пустые / `null` секции — заголовок и тело не выводим.
- `keywords` (string или array) — выводим как есть (если array — через запятую).
- Никакой LLM-обработки.

### `actions.md`
```
# Action items: {{ title }}

{{ summary.action_items }}
```
- Если `action_items` пусто → `_Нет action items._`
- Содержимое — как отдал FF (markdown-строка), не парсим в чек-лист.

**Никакого YAML-frontmatter.** Его добавляет MarkObjectsFromSummary.

---

## 6. Именование файлов

Формат:
```
YYYY-MM-DD HH-MM-SS <Title> - <kind>.md
```
где `<kind> ∈ {transcript, summary, actions}`.

- Дата/время — UTC.
- Sanitize Windows: `\ / : * ? " < > |` → `_`.
- Длина имени > 200 символов → обрезать `<Title>` с многоточием.
- Пустой `Title` → `Meeting [{meeting_id[-6:]}]`.

---

## 7. TG-алерты (2 правила)

**Главный принцип:** TG-алерты шлёт **только ручной запуск**. Cron и test работают молча — все статусы и ошибки пишутся только в `_log.md` (и в `logs/movefromff.jsonl`).

| Сценарий | TG? | Текст |
|---|---|---|
| **Ручной запуск** (`--mode manual` или TG-команда `обнови ff`) — успех | ✅ | Итог: «Скачано N, пропущено M, ошибок K» + список ID с ошибками если есть |
| **Ручной запуск** (`--mode manual` / `обнови ff`) — любая ошибка (preflight, FF недоступен, часть встреч упала, фатально) | ✅ | Текст ошибки + список ID (если применимо) |
| **Cron** (`--mode cron`) — успех или ошибки | ❌ | Только в `_log.md` + `logs/movefromff.jsonl` |
| **Test** (`--mode test`) — успех или ошибки | ❌ | Только в `_log.md` + `logs/movefromff.jsonl` |

Флаг `--no-tg` отключает TG-алерт и в ручном режиме (на случай отладки).

---

## 8. Логирование

**`_log.md`** — одна строка на запуск (append-only):
```
2026-05-22 14:30:00Z [cron] downloaded=3 skipped=12 errors=0 duration=8.2s
2026-05-22 18:30:00Z [cron] downloaded=0 skipped=15 errors=0 duration=1.4s
```

**`logs/movefromff.jsonl`** — одна строка JSON на событие:
```json
{"ts":"2026-05-22T14:30:05Z","event":"download_ok","meeting_id":"01H...","title":"..."}
{"ts":"2026-05-22T14:30:07Z","event":"download_error","meeting_id":"01J...","error":"timeout"}
{"ts":"2026-05-22T14:30:08Z","event":"run_summary","mode":"cron","downloaded":3,"skipped":12,"errors":0}
```

---

## 9. CLI

```bash
python -m movefromff --mode test                                    # последние 5 дней, без TG
python -m movefromff --mode cron                                    # последние 4ч 30мин, без TG
python -m movefromff --mode manual --from-date 2026-01-01 --to-date 2026-01-31
python -m movefromff --mode test --dry-run                          # план без записи
python -m movefromff --mode manual --no-tg                          # ручной запуск без TG (отладка)
python -m movefromff --mode cron --verbose                          # DEBUG лог
```

**Удалено из v1.0:** `--mode deleted-check`, `--reconcile-only`.

**Коды выхода:** `0` успех / `1` частичный успех / `2` лок занят или preflight / `3` FF недоступен / `4` фатально.

---

## 10. Структура проекта (минимальная)

```
MoveFromFF/
├── .venv/
├── .env                       # FIREFLIES_API_KEY, WORKVAULT_PATH, TELEGRAM_*
├── .env.example
├── pyproject.toml
├── README.md
├── movefromff/
│   ├── __main__.py            # CLI + оркестрация (Шаги 0-4)
│   ├── config.py              # pydantic Settings из .env
│   ├── ff_client.py           # GraphQL + tenacity retry
│   ├── ff_schema.py           # pydantic-модели ответа FF (минимум полей)
│   ├── registry.py            # read/write _registry.json (атомарно)
│   ├── writer.py              # рендер jinja2 + запись 3 файлов
│   ├── renderer.py            # генерация _registry.md из _registry.json (Jinja2, без запросов к FF)
│   ├── filename.py            # генерация имени файла
│   ├── lock.py                # portalocker
│   ├── tg.py                  # TG-уведомления (только для --mode manual; cron/test молчат)
│   ├── logger.py              # _log.md + jsonl
│   └── templates/
│       ├── transcript.md.j2
│       ├── summary.md.j2
│       ├── actions.md.j2
│       └── registry.md.j2     # шаблон для _registry.md (конвертация JSON → MD)
├── tests/
│   ├── test_filename.py
│   ├── test_registry.py
│   ├── test_ff_client.py
│   └── fixtures/
└── scripts/
    └── run_cron.bat
```

**Удалено из v1.0:** `reconciler.py`, `hashing.py`, `tests/test_reconciler.py`.

**Остаётся из v1.0 (без изменений по смыслу):** `renderer.py` + `templates/registry.md.j2` — рендер `_registry.md` из `_registry.json` (только конвертация локального JSON в Markdown, никаких запросов к Fireflies).

---

## 11. Критерии приёмки (DoD, минимум)

1. ✅ `--mode test` скачивает встречи за 5 дней в правильном формате.
2. ✅ Повторный запуск без новых встреч → `downloaded=0 skipped=N`, длительность <5 сек.
3. ✅ Уже скачанная встреча (запись в реестре) — **никогда** не качается повторно.
4. ✅ Ошибка одной встречи → остальные продолжают качаться, упавшая попадёт в следующий cron.
5. ✅ Параллельный запуск → exit 2 (лок).
6. ✅ `_registry.json` валиден по pydantic-схеме (`schema_version=2.0`).
7. ✅ Секреты — только в `.env`, путей нет в коде.

---

## 12. Контракт с MarkObjectsFromSummary (минимальный)

**MoveFromFF гарантирует:**
- Три файла на каждую встречу в `NewMeetings/` без YAML-frontmatter.
- Запись о встрече в `_registry.json` (ключ = `meeting_id`, поля по §4).
- Имена файлов — стабильные (генерируются детерминированно по дате+title).

**MoveFromFF НЕ обязан:**
- Знать, что произошло с файлами после.
- Хранить статусы обработки downstream.
- Восстанавливать унесённые downstream'ом файлы.

**MarkObjectsFromSummary читает `_registry.json`** и сам решает, что с какими файлами делать. Свой прогресс — ведёт в **своём** реестре / своих метаданных, не в нашем.

---

## 13. Миграция с v1.0/v1.1 → v2.0

Если в `_registry.json` встретился `schema_version=1.0` или `1.1`:
1. Прочитать список `meeting_id` → переписать в новой схеме (оставить только нужные поля: `title`, `meeting_date`, `duration_minutes`, `participants`, `files`, `fetched_at`).
2. Проставить `status="completed"` всем записям, у которых на диске реально лежат 3 файла. Если каких-то файлов нет — `status="error"` (downstream увидит проблему).
3. Записать обратно с `schema_version="2.0"`.
4. Старые поля (`sha256`, `transfer_status`, `integrity`, `processing_status`, `moved_by`, `moved_at`, `moved_to`, `errors`, `audio_url`, `last_checked_at`, `keywords`, `source`) — **отбросить**.
5. Сгенерировать свежий `_registry.md` из обновлённого `_registry.json`.

Файлы на диске — не трогать. Имена файлов сохраняются.

---

## Открытые вопросы (под минималку)

- **Q1:** Сохранять ли `keywords` в реестре отдельным полем для будущего использования downstream? → **Нет.** Если потребуется — downstream распарсит `summary.md`. Принцип: не плодить дублирование.
- **Q2:** Что делать, если FF переименовал встречу между запусками (`meeting_id` тот же, `title` другой)? → **Ничего.** Файл уже на диске под старым именем, в реестре. Повторно не качаем. Если пользователь хочет — удалит запись из реестра, и встреча перезальётся.
- **Q3:** Нужен ли `--force-redownload <meeting_id>`? → **Не в MVP.** Можно вручную удалить запись из `_registry.json` — то же самое.

---

## Сравнение объёма

| Метрика | v1.0 + v1.1 | v2.0 minimal |
|---|---|---|
| Python-модулей | 14 | 11 |
| Полей в записи реестра | 13 | 7 |
| Режимов CLI | 5 (`test`/`cron`/`manual`/`deleted-check`/`reconcile-only`) | 3 (`test`/`cron`/`manual`) |
| Статусов | 5 transfer + 3 integrity + 2 source + статусы постобработки | 3 (`pending` / `completed` / `error`) — только результат загрузки |
| TG-правил | 7 | 2 (только ручной запуск; cron/test — без TG) |
| DoD-пунктов | 16 | 7 |
| Шаблонов jinja2 | 4 | 4 (`transcript`, `summary`, `actions`, `registry`) |
