---
name: hermes-memory-hygiene
description: "почисти память/дефрагментация MEMORY"
version: 2.1.1
author: Sirene+Opus
license: MIT
platforms: [linux, macos, windows]
tags: [hermes, memory, user-profile, skills, decluttering, context-hygiene, dev-reset]
metadata:
  hermes:
    tags: [hermes, memory, decluttering, dev-reset]
    related_skills: [all-skills-hygiene, skill-authoring-principles]
---

# Hermes Memory Hygiene — дефрагментация памяти

## Режим

Один агрессивный режим — одним батчем, без блочных подтверждений. Исключение: если Саша сказал «разберём блок за блоком» — интерактивно. После чистки — обязательная сводка (Шаг 5).

Родственный скилл по SKILLS-слою: `all-skills-hygiene` (там другая механика — dedup/dead-skills, не char-budget).

---

## Процедура

### Шаг 1 — Прочитать

```bash
cat ~/.hermes/profiles/<active_profile>/memories/MEMORY.md
cat ~/.hermes/profiles/<active_profile>/memories/USER.md
```

Активный профиль — из системного промпта (`Active Hermes profile: <name>`).

### Шаг 2 — Классифицировать каждую запись

| Категория | Действие |
|---|---|
| Chat IDs, thread IDs | ✅ Оставить — без них кроны падают |
| Токены, ключи шифрования | ✅ Оставить |
| Пути к venv, contacts.enc, ТЗ | ✅ Оставить как pointer |
| Safety-директивы (dry-run, --yes) | ✅ Оставить |
| Статусы (v1✅, 24.07✅), версии, счётчики | ❌ Удалить — лог/устаревает |
| Питфоллы и процедуры | → Перенести в профильный скилл, потом удалить |
| Дубли скиллов | ❌ Удалить, оставить pointer «→ skill X» |
| Активный проект (устаревший) | ❌ Удалить или обновить |

**USER.md не трогать** — там identity/preferences, они не мусорятся.

### Шаг 3 — Перенести питфоллы в скиллы (до удаления из MEMORY)

Оценить актуальность:

| Критерий | Действие |
|---|---|
| Инструмент использовался ≤2 недель | ✅ Перенести в профильный скилл |
| Не использовался >2 недель / тривиальный / без повторений | ❌ Удалить |

Для переноса:
1. Определить профильный скилл (тот, что загружается при следующем использовании инструмента, не «где нашли»).
2. `skill_manage(action='patch', name=<skill>, ...)` — в раздел Pitfalls.
3. Только после подтверждения записи — включить в батч на удаление.

### Шаг 4 — Выполнить чистку одним батчем

```python
memory(action='...', operations=[
    {'action': 'remove', 'old_text': '...'},
    {'action': 'replace', 'old_text': '...', 'content': '→ skill X'},
], target='memory')
```

Если store переполнен (>2200 chars) и `memory` tool отказывает — писать напрямую через `write_file` на `~/.hermes/profiles/<profile>/memories/MEMORY.md`, затем `wc -c` проверить <2200.

### Шаг 5 — Сводка (обязательно)

```
✅ Память очищена: было X → стало Y симв (Z%).
Перенесено: <питфолл> → skill <name> (по строке на элемент).
Удалено: статусы/версии/счётчики (коротко).
Оставлено: chat IDs, токены, safety, пути.
[если dev-reset] Передавай контекст новой задачи — что делаем, путь к ТЗ, что out-of-scope.
```

---

## Что НИКОГДА не удалять

- Telegram `chat_id` / `thread_id` — кроны падают
- Токены (Loop TOKEN, CONTACTS_ENCRYPTION_KEY и др.)
- Safety-директивы (dry-run, --all требует --yes)
- USER.md целиком

---

## Write-time gate — перед каждым `memory(action='add')`

1. Процедура/питфолл/how-to? → профильный скилл, не MEMORY
2. Факт о Саше (preference, identity)? → USER PROFILE
3. Уникальный env-quirk (платформа, интеграция)? → `~/.hermes/HERMES.md` (не char-budgeted)
4. Иначе → MEMORY, коротко, pointer-форма

**Scope-тег для профиля `tz-dev`.** При добавлении нового факта в `~/.hermes/profiles/tz-dev/memories/MEMORY.md` — определить scope и добавить тег в конце строки:

- `[impl]` — нужен субагенту-реализатору (пути, venv, entities, safety)
- `[tz]` — нужен Opus при написании ТЗ (принципы проектирования, инвентарь)
- `[coord]` — только координатору Сирень (TG-топики, кроны, триггеры скиллов)
- `[all]` — нужен всем

Теги не ломают другие профили и скиллы — воспринимаются как часть текста. См. `tz-workflow/references/subagent-context.md` — фильтр промпта субагента по scope.

**Запрещено в MEMORY:** события с датой, версии инструментов, открытые TODO, процедуры, how-to.

---

## Что куда

| Store | Назначение |
|---|---|
| SOUL.md | Идентичность агента |
| agent.system_prompt | Операционные правила сессии |
| USER PROFILE | Кто Саша — preferences, style |
| MEMORY | Env-факты, указатели, решения без TTL |
| SKILLS | Процедуры, эндпоинты, скрипты, питфоллы |
| HERMES.md | Env-quirks (не char-budgeted, byte-stable) |

---

## Питфоллы

- **Удалить питфолл до переноса в скилл** → потеря знания. Сначала `skill_manage(patch)`, потом `memory(remove)`.
- **Перенести в «где нашли», а не «где предотвращает»** → скилл не загрузится при следующем использовании инструмента.
- **Удалить chat_id** → кроны падают с ошибкой доставки.
- **`memory(action='add')` когда store полный** → использовать `operations=[remove+add]` одним вызовом.
- **`old_text` в replace не совпадает байт-в-байт** → batch отклоняется. Копировать точный текст из `current_entries` в ответе об ошибке.
- **MEMORY >2200 chars** → `memory` tool не поможет. Писать напрямую через `write_file`.
- **`~/.hermes/HERMES.md` — только UPPERCASE**. Строчный `hermes.md` gateway не загружает.
- **При чистке >40% объёма — `write_file` эффективнее батча.** Прецедент 26.07.2026: MEMORY 86% (2685 байт), много мелких удалений — один `write_file` с только нужными записями чище и надёжнее, чем 8+ `memory(remove)` вызовов. Писать только что принадлежит MEMORY (без статусов/счётчиков), проверить `wc -c < 2200`.
- **Скиллы субагента созданы в профиле `default`, а не в активном** — Opus/Haiku по умолчанию пишет в `~/.hermes/profiles/default/skills/`, даже если сессия работает под `tz-dev`. Симптом: крон запускается, но видит `⚠️ Skill not found and skipped: <name>`. Фикс: `cp -r ~/.hermes/profiles/default/skills/devops/<skill> ~/.hermes/profiles/tz-dev/skills/devops/`. Предотвращение: явно указывать в промпте субагента полный путь: `~/.hermes/profiles/tz-dev/skills/devops/<name>/`. Прецедент 27.07.2026: backlog-collector и backlog-analyst.
- **Отвечать о статусе задачи/крона/инструмента без реальной проверки — нарушение Integrity (SOUL.md).** Даже если кажется что «ещё идёт» — всегда сначала `cronjob(action='list')` + `cat output/*.md`. «Ещё N минут» без инструмента = ложь. Прецедент 27.07.2026: правило зафиксировано в USER PROFILE и SOUL.md, но должно быть и здесь как напоминание перед началом dev-сессии.
- **Dead pointers** — при удалении скилла сразу grep MEMORY.md, USER.md и скиллы на его имя.
- **`\uXXXX` escape-sequences вместо кириллицы** — двойной JSON-encode. Fix: `re.sub(r'\\\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), raw)` → `write_file`.

---

## Разделение триггеров между dev-скиллами (25.07.2026)

Чтобы не загружать несколько скиллов одновременно при одной фразе:

| Фраза | Скилл |
|---|---|
| «почисти память», «dev reset», «сброс памяти» | `hermes-memory-hygiene` |
| «исследуй», «проанализируй», «новое ТЗ», «доработка инструмента» | `tz-workflow` |
| «разработай», «новый инструмент», «баг», «не работает» | `hermes-feature` |

**Правило:** слова «инструмент», «разработка», «исследование» не должны быть в description `hermes-memory-hygiene` — они вызовут конкурирующие загрузки. Триггеры memory-hygiene должны быть уникальными (только про память/контекст).

---

## Cross-profile скилл (паттерн shared-skills)

Если скилл нужен во всех профилях — `~/.hermes/shared-skills/` + симлинки (не копии):

```bash
mkdir -p ~/.hermes/shared-skills/devops/<skill-name>
for p in default tz-dev anthropic openai; do
  mkdir -p ~/.hermes/profiles/$p/skills/devops/
  ln -sf ~/.hermes/shared-skills/devops/<skill-name> \
         ~/.hermes/profiles/$p/skills/devops/<skill-name>
done
```

Почему не `~/.hermes/skills/`: апдейтер Hermes перезаписывает. Почему не копии: рассинхрон при правках.

---

## vm_selfcheck (cron, без пользователя)

Только детект, не чистить. Если MEMORY ≥75% → в отчёт: `⚠️ MEMORY X% — скажи «почисти память»`. Иначе — молчать.
