---
date: 2026-06-02
author: Сирень (Opus)
type: daily-self-check
---

# Daily Self-Check — 2026-06-02

## ✅ Что в порядке

- **Распределение моделей по cron корректное:**
  - `GitHub autosync` (терминальный sync) → Haiku ✓
  - `MoveFromFF — синхронизация каждые 2ч` → Haiku ✓
  - `MoveFromZulip` → Haiku ✓ (хоть и paused)
  - `Сирень — daily self-check` → Opus ✓ (анализ)
  - `Dialog Backlog — понедельничная сводка` → Opus ✓ (анализ + планирование)
  - `P5 routing analysis` → Haiku ✓ (короткая проверка логов)
- **config.yaml консистентен:** sirene-персона задана, fallback → Haiku, delegation → Opus с reasoning=high, routing-секция явно отключена с комментарием (без сюрпризов).
- **System prompt в config.yaml** содержит чёткие правила выбора модели (Opus/Sonnet/Haiku) — это та же логика, что в моём промпте.
- **Git hermes-agent:** последние 7 дней коммитов не было; за 14 дней — фичи (импорт usertools, миграция layout, наблюдение unmentioned TG-сообщений, skills-hub дедуп, TUI clipboard на Linux).

## ⚠️ Что нашла

### 1. Дублирующиеся скиллы про один и тот же MoveFromFF
В `skills/productivity/` лежат **два скилла про один инструмент**:
- `movefromff/SKILL.md` (v1.0.0, краткий, путь `Documents/Cursor_projects/MoveFromFF` — **такого пути нет**)
- `fireflies-obsidian-sync/SKILL.md` (v2.0.0, развёрнутый, путь `hermes-agent/USERTOOLS/MoveFromFF/`)

**Рекомендация:** удалить `movefromff/SKILL.md` (устарел и врёт про путь), оставить `fireflies-obsidian-sync` как канонический.

### 2. Рассогласование путей после "migration v1" (коммит bea78675b)
В крон-задачах фигурируют **три разных места** для MoveFromFF:
- `hermes-agent/USERTOOLS/MoveFromFF/` — основной cron (job `1e62e18ae399`)
- `hermes-workspace/tools/movefromff` — тестовый cron (job `ea18f323a671`, paused)
- `Documents/Cursor_projects/MoveFromFF` — скилл `movefromff/SKILL.md` (несуществует)

Реально на диске сейчас есть оба: `hermes-agent/USERTOOLS/` (старый) и `hermes-workspace/tools/` (после миграции). После завершения миграции одно из них — мусор; нужно решить и выровнять.

### 3. Мёртвые/зависшие cron-задачи
- `ea18f323a671` (MoveFromFF тест с реальным FF API) — **paused с 25.05.2026** (8 дней). Если миграция завершена — удалить или включить с новым путём.
- `50a30903f503` (MoveFromZulip еженедельная синхронизация) — **paused с 29.05.2026**, ни одного успешного запуска. Решить: чинить или удалять.

### 4. Скилл `movefrom-instruments`
Лежит в `productivity/movefrom-instruments/` с 7 reference-файлами (Confluence, Exchange, Zulip, contacts и т.д.) — это монолитный архив «всё про movefrom». При наличии отдельных скиллов `movefrom-confluence/`, `movefromff/`, `fireflies-obsidian-sync/` он создаёт информационный шум при skill discovery. Рассмотреть удаление или конвертацию в чистый references-каталог без SKILL.md.

### 5. Модели в cron — всё ок
Никаких неправильных назначений не нашла. Принцип «Haiku — терминальные, Opus — анализ» соблюдён.

## 💡 Топ-3 улучшения для Саши

### 1. Прибраться в скиллах movefrom-* (15 минут, экономит токены каждого старта агента)
- Удалить `skills/productivity/movefromff/SKILL.md` (дубль + устаревший путь).
- Перевести `skills/productivity/movefrom-instruments/SKILL.md` в `references/` (без фронт-маттера skill), либо удалить если содержимое уже распределено.
- Это уменьшит шум при autoload и устранит риск того, что агент пойдёт по фейковому пути.

### 2. Завершить миграцию `hermes-workspace` и зачистить cron
- Решить: `hermes-agent/USERTOOLS/` или `hermes-workspace/tools/` — единственный source of truth.
- Удалить paused cron `ea18f323a671` и `50a30903f503` (либо переключить на новый путь и снять с паузы).
- Выровнять путь в `fireflies-obsidian-sync/SKILL.md` со стартовым путём текущего рабочего cron.

### 3. Подключить новую фичу "наблюдение unmentioned TG group messages"
Коммит `a9db0e2c7` в hermes-agent добавил возможность видеть сообщения в группе без явного @упоминания. Если планируешь использовать Сирень в групповых чатах (не только в личке) — стоит обновиться до этой версии Hermes и сконфигурировать `telegram.thread_require_mention=false` для нужных групп. Сейчас стоит `allowed_chats: 400307920` (только личка), поэтому фича пока «спит», но удобно иметь возможность подключать рабочие чаты.

---

*Self-check выполнен Opus-воплощением Сирени. Отчёт доставлен через cron-delivery в Telegram.*
