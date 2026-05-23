# ТЗ: Инструмент MarkObjectsFromSummary v0.1
# Разметка объектов и подготовка встреч к архивированию
# Версия: 0.1 (черновик) | Дата: 2026-05-22 | Статус: На согласовании

---

## 1. Назначение и область

**Цель:** Второе звено конвейера обработки встреч. Берёт «сырые» файлы, положенные MoveFromFF в `WorkVault/Meetings/NewMeetings/`, размечает их связями с сущностями WorkVault (на v0.1 — только `Contacts`), добавляет YAML-frontmatter и переносит в архивную структуру `Meetings/Processed/YYYY-MM/`.

**Границы ответственности:**

| Делает | НЕ делает |
|---|---|
| Читает файлы и `_registry.json` после MoveFromFF | Не ходит в Fireflies API |
| Сопоставляет email-участников с `Contacts/*.md` | Не редактирует тело transcript/summary/actions |
| **Обрабатывает `keywords` из `_registry.json` / `summary.md`** (разметка, связь с тегами Obsidian) | Не дозаполняет контакты по внешним источникам (LLM, LinkedIn и т.п.) |
| Создаёт заготовки контактов (stubs) для неизвестных email | Не извлекает задачи/проекты/темы (это будущие инструменты) |
| Добавляет YAML-frontmatter в файлы встреч | Не правит схему реестра |
| Обновляет `_registry.json` (`moved_by.*`) | Не удаляет файлы без подтверждения |
| Перемещает файлы `NewMeetings/` → `Processed/YYYY-MM/` | Не запускается параллельно сам с собой |
| Шлёт TG-алерты по правилам (§9) | |

---

## 2. Технический стек и окружение

- **Python:** 3.12.10
- **Корень проекта:** `C:\Users\tkachenkoav\Documents\Cursor_projects\MarkObjectsFromSummary\`
- **venv:** `…\.venv\`
- **WorkVault:** `C:\Users\tkachenkoav\WorkVault\`
- **Источник:** `WorkVault\Meetings\NewMeetings\`
- **Назначение (встречи):** `WorkVault\Meetings\Processed\YYYY-MM\`
- **Контакты:** `WorkVault\Contacts\` (см. §3)
- **Зависимости:** `python-frontmatter`, `pyyaml`, `portalocker`, `pydantic>=2`, `jinja2`, `loguru`, `python-dotenv`, `requests` (только для TG)
- **Секреты:** `.env` (TG-токен; FF-ключ инструмент НЕ читает).

---

## 3. Модель данных WorkVault/Contacts

**Каноническая структура папки (как принято в WorkVault на момент v0.1):**

```
Contacts/
├── tutu-contacts.md          # сводная таблица внутренних (markdown table)
├── external-contacts.md      # сводная таблица внешних (markdown table)
├── README.md                 # Dataview-обзор (не трогаем)
├── templates/
│   └── contact-template.md   # YAML-шаблон для отдельных файлов
└── <login-или-slug>.md       # ← отдельные страницы-контакты (создаёт этот инструмент)
```

**Frontmatter контакта (по шаблону):**
```yaml
---
login: ""           # tutu-логин (если внутренний)
email: ""           # каноничный email
telegram: ""
fio: ""             # ФИО
aliases: []         # массив прозвищ
department: ""
team: ""
position: ""
notes: ""
source: ""          # ← добавляется этим инструментом: fireflies | manual
created_by: ""      # MarkObjectsFromSummary
created_at: ""      # ISO-8601
status: ""          # draft | confirmed   ← заготовки = draft
---
```

> **Открытый вопрос Q1 (брифа):** заготовки кладём отдельными `.md` файлами или дописываем строку в `tutu-contacts.md` / `external-contacts.md`. По умолчанию в v0.1 — **отдельные файлы**, имя = `<local-part-email>.md` (с защитой от коллизий).

### 3.1 Алгоритм матчинга email → контакт

Для каждого email из `participants`:
1. Нормализуем (`lower`, strip).
2. Сканируем `Contacts/*.md`:
   - читаем frontmatter (если есть);
   - сравниваем `email` поле — точное совпадение;
   - если в `email` пусто — сканируем markdown-таблицы в `tutu-contacts.md` и `external-contacts.md` (regex по колонке email).
3. Если найдено ≥1 совпадение → `contacts_matched += [{email, file, login?, fio?}]`.
4. Если не найдено → создаём заготовку (§3.2).

### 3.2 Создание заготовки контакта

- **Классификация внутренний/внешний:** по домену email.
  - `@tutu.ru`, `@tutu.tech` → внутренний;
  - всё остальное → внешний.
  - Список доменов — конфигурируемый (`config.internal_email_domains`, дефолт `["tutu.ru", "tutu.tech"]`).
- **Файл:** `Contacts/<local-part>.md` (Q1: возможно `Contacts/_inbox/` — на согласование).
- **Защита от коллизий:** если файл существует — добавляем суффикс `-2`, `-3`.
- **Содержимое:** копируем шаблон, заполняем `email`, `source=fireflies`, `status=draft`, `created_by=MarkObjectsFromSummary`, `created_at=<iso>`. Остальное — пустое (заполнит человек).
- **TG-алерт:** опционально, по правилам §9 (Q3).

### 3.3 Входные данные из MoveFromFF (keywords, спикеры)

Помимо `participants`, инструмент использует следующие поля как **входные данные для разметки**:

- **`keywords`** (из `_registry.json`, поле `keywords`, тип `string | string[] | null`) — список ключевых слов/фраз, отданный Fireflies. В v0.1 MarkObjectsFromSummary:
  - читает значение «как есть» из реестра (MoveFromFF гарантирует неизменность);
  - нормализует (lowercase, trim, удаление пунктуации в хвосте);
  - сопоставляет с тегами Obsidian (`#tag-name`) по словарю синонимов в `config.keyword_to_tag_map` (на v0.1 — пустой, fallback `slugify(keyword)`);
  - дописывает в YAML-frontmatter поле `tags: [...]` (Obsidian-совместимое) + сохраняет оригинал в `keywords: [...]`;
  - **не** создаёт автоматически новые теги без подтверждения (в v0.1 — только маппинг по словарю, остальные keywords уходят в `keywords_unmapped` для ручного review).

- **`Speaker {index}` в `transcript.md`** — fallback-обозначение спикера без имени (MoveFromFF §13). В v0.1 MarkObjectsFromSummary **не пытается** автоматически связать `Speaker {index}` с реальными контактами — поле уходит в frontmatter как есть. **В v0.2 запланировать механизм связи `Speaker {index}` с реальными контактами из `Contacts/`** (например, через ручной mapping в frontmatter или через анализ часто упоминаемых имён в транскрипте).

---

## 4. Полный алгоритм

### Шаг 0. Lock + preflight
- Лок: `.locks/markobjects.lock` (portalocker). Занят → exit 2.
- Проверить наличие `WorkVault\Meetings\NewMeetings\` и `_registry.json`.
- Проверить запись в `Processed/`, `Contacts/`.

### Шаг 1. Чтение реестра
- Открыть `_registry.json` без лока (read-only).
- Отфильтровать записи: `transfer_status == "completed" AND moved_by IS NULL`.
- Если пусто → exit 0, лог `nothing_to_do`, TG не шлём.

### Шаг 2. Для каждой встречи
1. **Найти 3 файла** на диске (`transcript`, `summary`, `actions`) по именам из `files.*.filename`. Если хоть один отсутствует → запись пропустить, `errors += ["file_missing:<kind>"]`, продолжить.
2. **Сверить SHA-256** с реестром. Если не совпадает → лог `integrity_mismatch`, обработку **не выполнять** (передоверяем MoveFromFF восстановить).
3. **Матчинг участников** (§3.1) → `contacts_matched`, `contacts_new`.
4. **Создать заготовки** для `contacts_new` (§3.2). Перед записью — повторная проверка существования файла (race-safe).
5. **Обработать `keywords`** (§3.3): прочитать из реестра, нормализовать, смаппить на теги Obsidian; получить `tags` и `keywords_unmapped`.
6. **Сформировать frontmatter** (§5) для каждого из 3 файлов с правильным `kind`, включая поля `keywords`, `tags`, `keywords_unmapped`.
7. **Вписать frontmatter** в начало файла (`python-frontmatter.dumps`). Если frontmatter уже есть (повторный запуск) → мерж: новые ключи перезаписывают, неизвестные ключи сохраняются.
8. **Атомарно переместить** файлы в `Meetings/Processed/<YYYY-MM>/` (по `meeting_date`, UTC). `os.replace` поверх `shutil.move` для кросс-диска.
9. **Обновить запись** в реестре (in-memory):
   ```json
   "moved_by": {
     "agent": "MarkObjectsFromSummary",
     "agent_version": "0.1",
     "destination": "Meetings/Processed/2026-05/",
     "moved_at": "<UTC iso>",
     "contacts_matched": ["..."],
     "contacts_new":     ["..."]
   }
   ```
10. Обновить `files.*.filename` → новый относительный путь (от корня WorkVault) для трассируемости.

### Шаг 3. Запись реестра (под локом)
- Взять portalocker на `_registry.json`.
- Перечитать (на случай гонки с MoveFromFF), смержить только изменённые записи (по `meeting_id`).
- Атомарная запись (temp + `os.replace`).
- `_registry.md` — перегенерировать.

### Шаг 4. TG-алерт + лог + освобождение лока.

**Коды выхода:**
- `0` — успех (включая «нечего делать»)
- `1` — частичный успех (часть встреч упала, остальные обработаны)
- `2` — лок занят / preflight провален
- `4` — фатальная ошибка

---

## 5. YAML-frontmatter файлов встреч

Один и тот же блок для всех трёх kind, отличается только `kind`:

```yaml
---
ff_id: "01HXYZ..."                      # = meeting_id из реестра
date: "2026-05-20T11:30:00Z"            # UTC, из реестра MoveFromFF
title: "Встреча с клиентом"
participants:
  - tkachenkoav@tutu.ru
  - ivan.petrov@example.com
duration_min: 47.3                      # float, как в реестре
kind: transcript                        # transcript | summary | actions
contacts_matched:
  - "Contacts/tkachenkoav.md"
contacts_new:
  - "Contacts/ivan.petrov.md"
keywords:                               # оригинал из FF, как есть
  - onboarding
  - Q2-planning
tags:                                   # mapped через config.keyword_to_tag_map (v0.1: slugify fallback)
  - onboarding
  - q2-planning
keywords_unmapped: []                   # keywords, не нашедшие маппинг
processing_status: done
processed_by: MarkObjectsFromSummary
processed_by_version: "0.1"
processed_at: "2026-05-22T14:35:12Z"    # UTC
source: fireflies
---
```

- `contacts_matched` / `contacts_new` — **wiki-link готовые пути** относительно корня WorkVault, чтобы Obsidian Dataview / Graph их видел.
- При повторном запуске значения перезаписываются (источник правды — текущий проход).

---

## 6. Перемещение в Processed/YYYY-MM/

- Папка определяется по `meeting_date.year` и `meeting_date.month`. Реестр хранит дату в **UTC** (см. ТЗ MoveFromFF §13 / §9). При группировке в `Processed/YYYY-MM/` — берётся UTC-год/месяц. Локальная репрезентация даты (если нужна) — задача downstream-инструментов.
- Имя файла — **не меняется** (формат MoveFromFF, UTC).
- Если файл с таким именем в `Processed/YYYY-MM/` уже есть:
  - SHA совпадает → удалить из `NewMeetings/` (это повторный прогон того же).
  - SHA не совпадает → суффикс `-dup-<short_sha>.md`, лог `duplicate_in_archive`.

---

## 7. CLI интерфейс

```bash
python -m markobjects --once                                      # одна пачка, выход
python -m markobjects --dry-run                                   # план без записи
python -m markobjects --verbose                                   # DEBUG лог
python -m markobjects --no-tg                                     # без TG
python -m markobjects --only-meeting-id 01HXYZ...                 # одна встреча для отладки
python -m markobjects --rematch-contacts                          # перематчить ВСЕ Processed/, обновить frontmatter (не двигая файлы)
```

---

## 8. Структура проекта

```
MarkObjectsFromSummary\
├── .venv\
├── .env                     # TELEGRAM_*, никакого FIREFLIES_API_KEY
├── .env.example
├── pyproject.toml
├── README.md
├── markobjects\
│   ├── __main__.py
│   ├── config.py            # pydantic Settings (vault_path, internal_domains, …)
│   ├── registry_io.py       # чтение/мерж/запись _registry.json
│   ├── contact_index.py     # сканер Contacts/*.md, парсер таблиц
│   ├── contact_matcher.py   # email → контакт, классификация internal/external
│   ├── contact_writer.py    # создание заготовок по шаблону
│   ├── frontmatter_writer.py# мерж frontmatter в файлы встреч
│   ├── mover.py             # NewMeetings → Processed/YYYY-MM
│   ├── lock.py
│   ├── tg_notifier.py
│   ├── logger.py
│   └── templates\
│       └── contact-stub.md.j2
├── tests\
│   ├── fixtures\
│   ├── test_contact_matcher.py
│   ├── test_frontmatter_writer.py
│   ├── test_mover.py
│   └── test_registry_io.py
└── scripts\
    └── run_cron.bat
```

---

## 9. TG-алерты — матрица правил

| Сценарий | TG-алерт? | Содержание |
|---|---|---|
| Cron, нечего обрабатывать | ❌ | Только в лог |
| Cron, обработано N встреч без ошибок | ❌ (по умолчанию) | Лог; флаг `--tg-on-success` включит |
| Cron, **созданы новые заготовки контактов** | ✅ (Q3, по умолчанию ON) | Список email + ссылка на файлы |
| Cron, частичная ошибка | ✅ | Текст + список meeting_id |
| Cron, фатальная ошибка | ✅ | traceback |
| Ручной запуск `--once` | ✅ | Всегда итог |
| Лок занят / `--no-tg` | ❌ | — |

**TG-команды:** `размечай встречи`, `обработай новые встречи`. Регистрируются в Hermes `/help` → подраздел **MarkObjectsFromSummary**.

---

## 10. Логирование

- `logs/markobjects.jsonl` — событийный лог (одна строка на встречу).
- `_log.md` (в WorkVault/Meetings/) — общий human-readable, дописываем секцию:
  ```
  ## 2026-05-22 14:35:12 — MarkObjectsFromSummary
  - Обработано: 3 встречи
  - Сматчено контактов: 7
  - Новых заготовок: 2 (ivan.petrov@example.com, anna@external.com)
  - Перемещено в Processed/2026-05/: 9 файлов
  - Ошибок: 0
  ```

---

## 11. Идемпотентность и безопасность

1. **Race с MoveFromFF:** оба инструмента берут лок только на запись реестра, перечитывают перед мержем.
2. **Повторный прогон:** записи с `moved_by != null` пропускаются. Re-frontmatter — только через `--rematch-contacts`.
3. **Откат:** инструмент не удаляет файлы. Если что-то пошло не так — файл лежит либо в `NewMeetings/`, либо в `Processed/`, реестр это видит.
4. **Контакты:** заготовка создаётся **до** перемещения файлов. Если перемещение упало — заготовка остаётся, статус встречи — `errors += ["move_failed"]`, `moved_by` остаётся `null`, на следующем прогоне дообработаем.

---

## 12. Критерии приёмки (DoD)

1. ✅ Папка `NewMeetings/` с N встречами после MoveFromFF → после прогона пуста, всё в `Processed/YYYY-MM/`.
2. ✅ Все 3 файла каждой встречи получили валидный YAML-frontmatter с правильным `kind`.
3. ✅ Email сматчен с существующим контактом → запись в `contacts_matched`, заготовка НЕ создана.
4. ✅ Неизвестный email → создана заготовка с `source=fireflies`, `status=draft`.
5. ✅ Внутренний домен (`@tutu.ru`, `@tutu.tech`) → классифицирован как `internal` (Q1: место хранения).
6. ✅ Повторный запуск — без изменений, `moved_by` не перезаписывается.
7. ✅ `--rematch-contacts` обновляет frontmatter в `Processed/` без перемещения файлов.
8. ✅ SHA-256 не совпал → встреча пропущена, `errors` заполнен, ошибка в логе.
9. ✅ Race с MoveFromFF (параллельный запуск): оба завершаются успешно, реестр консистентен.
10. ✅ `--dry-run` ничего не пишет (ни файлы, ни реестр).
11. ✅ TG-алерт о новых заготовках содержит список email и кликабельные пути.
12. ✅ Unit-тесты, покрытие ≥70%.
13. ✅ Подраздел MarkObjectsFromSummary в `/help` Hermes.
14. ✅ `keywords` из реестра прочитаны, нормализованы, замапены на `tags`; немапящиеся — в `keywords_unmapped`.
15. ✅ `Speaker {index}` в transcript остаётся как есть (v0.1 не пытается резолвить в контакт; v0.2 — отдельная задача).

---

## 13. Открытые вопросы

См. `MarkObjectsFromSummary_Brief_Questions.md`.
