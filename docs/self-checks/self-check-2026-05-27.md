# Сирень — Self-check 2026-05-27

Время: 03:00 (Opus, ежедневный cronjob)

## ✅ Что в порядке
- `config.yaml`: default=`claude-sonnet-4-6`, fallback=`claude-haiku-4-5` — корректно. system_prompt с правилами делегирования (Opus/Sonnet/Haiku) на месте.
- Скиллы `~/AppData/Local/hermes/skills/` (100 SKILL.md) читаются, структура цела. Профильные скиллы `persona/sirene-identity` и `persona/sirene-chat-friends` присутствуют.
- Self-check сам (job `e7a53b2e2cf2`) — корректно на Opus, last_status=ok.
- MoveFromExchange (weekly) и MoveFromFF (каждые 2ч в будни) — no-agent + terminal toolset, last_status=ok. Это правильно: лёгкие скрипт-задачи без LLM.
- Hermes-agent репо `AppData/Local/hermes/hermes-agent` синхронизируется с upstream NousResearch (git fetch показал новые коммиты `2517917de..bb4703c76` — ничего срочного, fix/skills-hub/tui/gateway). Локальный Cursor-checkout у Саши на коммите `bea78675b` (migration v1).

## ⚠️ Что нашла

### 1. 🔴 Сломанный cronjob `bc1b0ae442f0` "GitHub автосинк (hermes-workspace)"
- Каждую ночь 02:00 падает с `Script not found: C:\Users\tkachenkoav\AppData\Local\hermes\scripts\hermes_workspace_autosync.sh`. Last 6 запусков подряд — error.
- В `~/AppData/Local/hermes/scripts/` лежит только `switch_delegation_model.py`. Скрипта `hermes_workspace_autosync.sh` физически нет.
- Сам prompt джобы содержит готовый bash-скрипт — но `no_agent=true` + `script=hermes_workspace_autosync.sh` означает «выполни файл», а файла нет.
- **Решение**: либо положить bash-файл по этому пути (вынуть из prompt), либо переключить джобу в `no_agent=false` с моделью Haiku (терминальная задача — git push) и убрать поле `script`.

### 2. 🟡 Возможный путь-конфликт после migration v1
- Джоб «MoveFromFF — тест с реальным FF API» (`ea18f323a671`, paused) указывает на `hermes-workspace/tools/movefromff`.
- Боевая джоба `1e62e18ae399` синхронизации FF использует `hermes-agent/USERTOOLS/MoveFromFF`.
- Оба пути сейчас существуют — но это два разных чекаута одного инструмента. После `migration v1` канонической версией скорее всего становится `hermes-workspace/tools/`, и `USERTOOLS/` устареет. Стоит выбрать один и поправить пути в обоих джобах, иначе будут расходиться venv'ы и состояние.

### 3. 🟡 Дубли/пересечения в скиллах
- `software-development/plan/` и `software-development/writing-plans/` — два скилла про планирование. Стоит сверить, не пересекаются ли по содержанию (один — про /plan slash, второй — про написание plan-документов; если так, имена надо явно развести в frontmatter).
- `productivity/movefromff/` (скилл) и `productivity/fireflies-obsidian-sync/` — оба про Fireflies. Первый — про инструмент MoveFromFF, второй — про сам пайплайн в Obsidian. Лучше связать перекрёстными ссылками, чтобы Sonnet/Opus не путались.
- `devops/gateway-platform-configuration/` и `devops/hermes-gateway-setup/` — близкие темы (setup vs configuration). Сейчас разделение по уровню (start vs tune) — нормально, но в SKILL.md одного стоит явно указать «для первичной настройки — см. hermes-gateway-setup».

### 4. 🟡 Модель Opus на джобе `ea18f323a671` (MoveFromFF test) — overkill
- Это `dry-run` + повторный запуск без `--dry-run`, плюс анализ ошибок rate-limit. Подойдёт Haiku (терминал + чтение лога), c fallback на Sonnet если нужен глубокий разбор traceback. Сейчас джоба paused — это не горит, но при возобновлении лучше понизить модель.

## 💡 Топ-3 улучшения для Саши

1. **Починить GitHub автосинк (job bc1b0ae442f0)** — самое срочное. Вариант A: создать `~/AppData/Local/hermes/scripts/hermes_workspace_autosync.sh` со скриптом из prompt джобы. Вариант B (лучше, простой git push — это Haiku-задача): отредактировать джобу — поставить `no_agent=false`, `model=claude-haiku-4-5`, `script=null`, оставить prompt как есть. Тогда Haiku выполнит push сам, бесплатно по контексту. Команда: `hermes cron edit bc1b0ae442f0` или прямой patch `cron/jobs.json`.

2. **Унифицировать путь MoveFromFF/MoveFromExchange** — после `migration v1` определить канон (предположительно `hermes-workspace/tools/`) и поправить пути во всех cron-джобах (`1e62e18ae399`, `58ab10e1ee15`, `ea18f323a671`). Заодно удалить устаревший USERTOOLS-чекаут или сделать его симлинком, иначе разойдутся venv'ы.

3. **Подтянуть свежие коммиты Hermes upstream** — есть 31 новый коммит в `AppData/Local/hermes/hermes-agent` (origin/main впереди на `2517917de..bb4703c76`). Релевантное: `fix(gateway): reorder telegram menu priority — everyday commands first`, `Observe unmentioned Telegram group messages`, `fix(security): prevent API key leakage to non-authoritative custom endpoints`. Последний — security-fix, желательно `git pull` на ближайшей неделе. На dev-чекауте в Cursor_projects уже есть локальные коммиты Саши, там pull не делаем — только в `AppData/Local/hermes/hermes-agent`.

---
*Сирень-Opus, отчёт сформирован автономно.*
