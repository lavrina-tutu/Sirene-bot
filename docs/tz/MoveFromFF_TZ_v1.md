# ТЗ: Инструмент MoveFromFF v1.0
# Перенос встреч из Fireflies.ai → Obsidian WorkVault
# Версия: 1.0 | Дата: 2026-05-22 | Статус: На согласовании

---

## 1. Назначение и область

**Цель:** Надёжный, идемпотентный перенос встреч из Fireflies.ai в локальную папку `C:\Users\tkachenkoav\WorkVault\Meetings\NewMeetings\` с ведением машиночитаемого реестра, контролем целостности (SHA-256) и структурированным логированием.

**Границы ответственности:**

| Делает | НЕ делает |
|---|---|
| Тянет встречи из FF GraphQL API | Не редактирует содержимое (никакой LLM-обработки) |
| Конвертирует JSON → Markdown (минимально) | Не добавляет YAML-frontmatter (это следующий агент) |
| Пишет 3 файла на встречу: transcript / summary / actions | Не удаляет файлы (удаление — вручную через Проводник) |
| Ведёт `_registry.json` и `_registry.md` | Не хранит историю статусов (только текущий) |
| Шлёт TG-алерты по правилам (§8) | Не перемещает файлы в архив / следующие папки |

---

## 2. Технический стек и окружение

- **Python:** 3.12.10 (`C:\Users\tkachenkoav\AppData\Local\Programs\Python\Python312\python.exe`)
- **Корень проекта:** `C:\Users\tkachenkoav\Documents\Cursor_projects\MoveFromFF\` (читается из `PROJECT_PATH` в `.env`)
- **venv:** `C:\Users\tkachenkoav\Documents\Cursor_projects\MoveFromFF\.venv\`
- **Целевая папка:** `C:\Users\tkachenkoav\WorkVault\Meetings\NewMeetings\` (выводится из `WORKVAULT_PATH` в `.env`)
- **Зависимости:** `requests`, `tenacity`, `portalocker`, `pydantic>=2`, `jinja2`, `loguru`, `python-dotenv`
- **Шифрование секретов:** нет (v1.0). API-ключ FF и TG-токены — в `.env` (gitignored).
- **Таймзона:** **UTC** для всех дат — в именах файлов, в реестре, в логах. Локальное представление — задача downstream-инструментов.

> **ОС-платформа:** v1.0 — **Windows 10**. Миграция на Ubuntu VM — отдельная задача вне данного ТЗ. Все пути (включая `WORKVAULT_PATH`, `PROJECT_PATH`) задаются через `.env` и **не хардкодятся в коде** — это обеспечит безболезненный переезд.

**Обязательные переменные `.env` (пути):**
```
WORKVAULT_PATH=C:\Users\tkachenkoav\WorkVault
PROJECT_PATH=C:\Users\tkachenkoav\Documents\Cursor_projects\MoveFromFF
FIREFLIES_API_KEY=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

---

## 3. Полный алгоритм

### Шаг 0. Lock + preflight
- Файловый лок: `.locks/movefromff.lock` через `portalocker`. Если занят → exit code 2, лог `lock_busy`.
- Проверить `WorkVault\Meetings\NewMeetings\` — существует и доступен на запись.
- Проверить `.env`: `FIREFLIES_API_KEY` обязателен; TG-параметры — обязательны при ручном запуске.
- Создать недостающие подпапки: `logs/`, `.locks/`.

### Шаг 1. Проверка доступности Fireflies API
- Тестовый GraphQL-запрос.
- Retry: 3 попытки, экспоненциальная задержка 2/4/8 сек.
- При недоступности → exit code 3, лог, TG-алерт по правилам §8.

### Шаг 2. Реконсиляция (диск ↔ реестр)
1. Прочитать `_registry.json` (если нет — создать пустой).
2. Просканировать `NewMeetings/`.
3. Для каждого файла на диске:
   - Если в реестре → пересчитать SHA-256. Совпал → OK. Не совпал → `integrity=modified_locally`.
   - Если нет на диске, но есть в реестре с `transfer_status=completed` → `transfer_status=missing_locally` (если `moved_by=null`) или оставить (если `moved_by` заполнен).
   - Если на диске, но нет в реестре (формат соответствует regex) → добавить с `source=manual`.

### Шаг 3. Определение окна выгрузки
- `--mode=test` → последние 5 дней
- `--mode=cron` → последние 4 часа + 30 мин нахлёста
- `--mode=manual --from-date --to-date` → произвольный интервал

### Шаг 4. Загрузка новых встреч
1. Если `meeting_id` в реестре с `transfer_status=completed` + файлы есть + хеши совпадают → **пропустить**.
2. Если в реестре но `integrity=modified_locally` → **молча перезаписать**, лог `overwritten_from_ff`.
3. Если не в реестре → скачать, записать 3 файла, добавить в реестр.
4. Если FF отдаёт `audio_url` — вставить ссылку в начало `transcript.md`.
5. **При ошибке скачивания одной встречи:** создать/обновить запись в реестре с `transfer_status=pending`, дописать `errors[] += [{"timestamp": "<UTC ISO>", "error_message": "<str>"}]`. Файлы НЕ создавать (частично записанные — удалить). При следующем запуске инструмент повторит попытку, **если встреча ещё доступна в FF API**. Обработка остальных встреч из пачки **не прерывается**.

### Шаг 5. Обработка удалённых в FF (режим `--mode deleted-check`)
- **Выполняется ТОЛЬКО** при явном вызове `--mode deleted-check`. В режимах `--mode cron`, `--mode test`, `--mode manual` этот шаг **пропускается** — cron не должен случайно помечать встречи как удалённые из-за частичной выдачи FF API.
- Окно проверки: **последние 90 дней** (от текущего UTC-времени). Параметр захардкожен в коде, при необходимости вынести в `.env` (`DELETED_CHECK_WINDOW_DAYS=90`).
- Алгоритм: для каждой записи реестра с `transfer_status=completed` и `meeting_date` в окне 90 дней → запросить FF API по `meeting_id`. Если FF вернул 404/not found → `transfer_status=deleted_in_ff`, `last_checked_at=<UTC ISO>`. **Файлы на диске НЕ трогать.**
- Запуск: отдельный Hermes cronjob, **раз в месяц**.

### Шаг 6. Обновление реестра и логов
- `_registry.json` — атомарная запись (temp + os.replace).
- `_registry.md` — генерация из jinja2-шаблона.
- `_log.md` и `logs/movefromff.jsonl` — дополнить.

### Шаг 7. TG-алерт + освобождение лока.

**Коды выхода:**
- `0` — успех
- `1` — частичный успех (часть встреч упала)
- `2` — лок занят / preflight провален
- `3` — FF недоступен / auth-ошибка
- `4` — фатальная ошибка

---

## 4. Содержимое файлов (JSON → Markdown)

**Принцип:** брать как есть, форматировать для читаемости. Никакой LLM-обработки, никаких сокращений.

### `transcript.md`
```
# {{ title }}

**Дата:** YYYY-MM-DD HH:MM:SS
**Длительность:** {{ duration }} мин
**Участники:** {{ participants | join(", ") }}
**Аудио:** {{ audio_url }}  ← если есть
**Meeting ID:** {{ meeting_id }}

---

## Транскрипт

[00:00:12] **Имя Спикера:** текст реплики...
[00:00:34] **Другой Спикер:** текст реплики...
```

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
- Секции соответствуют **реальной схеме FF Pro** (`summary.overview`, `summary.action_items`, `summary.keywords`).
- Пустые/`null` секции — пропускать (не выводить заголовок).
- Поле `keywords` пишется **как есть** из FF (строка или массив, см. §13 аддендума). Дальнейшая разметка (связь с тегами Obsidian) — задача инструмента **MarkObjectsFromSummary** (см. `WorkVault/Meetings/MarkObjectsFromSummary_TZ_v0.1.md`).

### `actions.md`
```
# Action items: {{ title }}

- [ ] {{ item.text }} — {{ item.assignee }} ({{ item.due }})
```
Если нет action items → файл с шапкой и текстом `_Нет action items._`

**БЕЗ YAML-frontmatter** — задача следующего инструмента.

---

## 5. Именование файлов

```
YYYY-MM-DD HH-MM-SS Название встречи - transcript.md
YYYY-MM-DD HH-MM-SS Название встречи - summary.md
YYYY-MM-DD HH-MM-SS Название встречи - actions.md
```

- **Дата/время — в UTC** (из FF Unix timestamp → UTC, без конвертации в локальную TZ).
- Время с секундами если FF отдаёт, иначе `HH-MM-00`
- Запрещённые символы Windows (`\ / : * ? " < > |`) → заменяются на `_`
- Длина имени файла > 200 символов → название обрезается с `…`

**Regex распознавания FF-формата:**
```
^(\d{4}-\d{2}-\d{2}) (\d{2}-\d{2}-\d{2}) .+ - (transcript|summary|actions)\.md$
```

---

## 6. CLI интерфейс

```bash
python -m movefromff --mode test                              # последние 5 дней
python -m movefromff --mode cron                              # последние 4 часа
python -m movefromff --mode manual --from-date 2026-01-01 --to-date 2026-01-31
python -m movefromff --mode deleted-check                     # проверка удалённых в FF за 90 дней (раз в месяц через Hermes cron)
python -m movefromff --reconcile-only                         # только сверка диск ↔ реестр
python -m movefromff --mode test --dry-run                    # показать план без записи
python -m movefromff --mode cron --verbose                    # DEBUG лог
python -m movefromff --mode cron --no-tg                      # без TG-алертов
```

**`--mode deleted-check`** — отдельный режим, **не пересекается с cron**. Проходит по реестру и для каждой записи с `transfer_status=completed` и `meeting_date` за последние 90 дней проверяет в FF API. Не найденные → `transfer_status=deleted_in_ff`. Файлы не трогает. Запускается отдельным Hermes cronjob раз в месяц.

---

## 7. Структура проекта

```
MoveFromFF\
├── .venv\
├── .env                     # FIREFLIES_API_KEY, TELEGRAM_* (gitignored)
├── .env.example
├── .gitignore
├── pyproject.toml
├── README.md
├── movefromff\
│   ├── __main__.py          # entrypoint, argparse, оркестрация
│   ├── config.py            # pydantic Settings
│   ├── ff_client.py         # GraphQL клиент + tenacity
│   ├── ff_schema.py         # pydantic-модели FF
│   ├── registry.py          # _registry.json (атомарно)
│   ├── reconciler.py        # шаг 2
│   ├── writer.py            # запись файлов
│   ├── renderer.py          # jinja2 шаблоны
│   ├── hashing.py           # SHA-256
│   ├── filename.py          # генерация/парсинг имён
│   ├── lock.py              # portalocker wrapper
│   ├── tg_notifier.py       # TG-алерты
│   ├── logger.py            # loguru + jsonl
│   └── templates\
│       ├── transcript.md.j2
│       ├── summary.md.j2
│       ├── actions.md.j2
│       └── registry.md.j2
├── tests\
│   ├── test_filename.py
│   ├── test_registry.py
│   ├── test_reconciler.py
│   ├── test_ff_client.py
│   └── fixtures\
└── scripts\
    ├── run_cron.bat
    └── run_manual.bat
```

---

## 8. TG-алерты — матрица правил

| Сценарий | TG-алерт? | Содержание |
|---|---|---|
| Ручной запуск, успех | ✅ | Итог: «Скачано N, пропущено M, ошибок 0» |
| Ручной запуск, частичная ошибка | ✅ | Итог + список ID с ошибками |
| Ручной запуск, фатальная ошибка | ✅ | Текст ошибки + traceback |
| Cron, успех | ❌ | Только в лог |
| Cron, есть ошибки | ✅ | Текст ошибки + ID встреч |
| Лок занят | ❌ | — |
| Флаг `--no-tg` | ❌ | — |

**Команды TG:** `обнови fireflies`, `обнови ff`
Регистрируются в Hermes `/help` → подраздел **MoveFromFF**.

---

## 9. Схема `_registry.json`

```json
{
  "schema_version": "1.0",
  "updated_at": "2026-05-22T14:30:00Z",
  "meetings": {
    "<meeting_id>": {
      "meeting_id": "...",
      "title": "Встреча с клиентом",
      "meeting_date": "2026-05-20T11:30:00Z",
      "duration_minutes": 47.0,
      "participants": ["Иван Петров"],
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
        "summary": {},
        "actions": {}
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

**Перечисления:**
- `source` ∈ `{ fireflies, manual }`
- `transfer_status` ∈ `{ pending, completed, failed, deleted_in_ff, missing_locally }`
- `integrity` ∈ `{ ok, modified_locally, unknown }`

**Таймзона:** все даты (`updated_at`, `meeting_date`, `written_at`, `fetched_at`, `last_checked_at`, `errors[].timestamp`) — в **UTC**, формат ISO-8601 с суффиксом `Z`.

**Типы:**
- `duration_minutes`: **float** (хранится как есть из FF, без округления).

---

## 10. Контракт с агентом-обработчиком

1. MoveFromFF пишет файлы в `NewMeetings/` со статусом `transfer_status=completed`, `integrity=ok`, `moved_by=null`.
2. Следующий агент:
   - Берёт портало-лок на `_registry.json`
   - Выбирает записи с `transfer_status=completed` и `moved_by=null`
   - После обработки заполняет `moved_by: {agent, destination, moved_at}`
3. MoveFromFF при следующем запуске:
   - `moved_by` заполнен → файл не восстанавливать
   - `moved_by=null` и файла нет → `transfer_status=missing_locally`

---

## 11. Логирование

**`_log.md`** (human-readable):
```
## 2026-05-22 14:30:00 — cron
- Проверка FF: OK
- Реконсиляция: 142 файла, 1 modified_locally (перезаписан)
- Скачано новых: 3
- Удалено в FF: 0
- Ошибок: 0
- Длительность: 8.2 сек
```

**`logs/movefromff.jsonl`** — одна строка на событие (JSON).

---

## 12. Критерии приёмки (DoD)

1. ✅ `--mode test` скачивает встречи за 5 дней в правильном формате
2. ✅ Повторный запуск — без дублей (идемпотентность)
3. ✅ Изменённый вручную файл → молча перезаписан, запись в лог
4. ✅ Удалённый вручную файл → `missing_locally`, не восстанавливается
5. ✅ Встреча удалена в FF → файлы не тронуты, `deleted_in_ff`
6. ✅ Файл положенный вручную → в реестре с `source=manual`
7. ✅ `--mode manual --from-date ... --to-date ...` работает корректно
8. ✅ `--mode cron` без новых встреч → <5 сек, код 0, без TG
9. ✅ `--mode cron` с ошибкой FF → TG-алерт + код 3
10. ✅ `--dry-run` ничего не пишет
11. ✅ Параллельный запуск → exit code 2
12. ✅ `_registry.json` валиден по pydantic-схеме после любого прогона
13. ✅ TG-команды запускают ручной режим и присылают итог
14. ✅ Подраздел MoveFromFF в `/help` Hermes
15. ✅ Unit-тесты, покрытие ≥70%
16. ✅ Все секреты только в `.env`

---

## Открытые вопросы (ответить перед разработкой)

- ✅ Q1: Точная GraphQL-схема FF — закрыт §13 аддендума
- ✅ Q2: Таймзона — **UTC везде**
- ✅ Q3: Имя следующего агента — **MarkObjectsFromSummary**
- ✅ Q4: Cron — **Hermes cronjob**
- ✅ Q5: TG-команды — **через Hermes Agent**
- ✅ Q6: Ошибка скачивания одной встречи — **продолжать пачку**, упавшая → `transfer_status=pending`, retry на след. запуске (см. §3 Шаг 4 п.5)
- ✅ Q7: Окно `deleted_in_ff` — **90 дней**, отдельный режим `--mode deleted-check` (раз в месяц)
