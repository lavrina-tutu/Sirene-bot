---
name: upstream-dependency-monitor
description: "отслеживай upstream: итоги и решения из стенограммы"
version: 1.0.1
author: agent
tags: [monitoring, upstream, git, no-agent, watchdog]
platforms: [linux, macos]
---

# Upstream Dependency Monitor

Мониторинг внешних репозиториев без токенов. Уведомляет только при изменениях.

## Паттерн

**no_agent watchdog скрипт** (`upstream_monitor.sh`):
- `git fetch origin --quiet` (только fetch, не merge/pull)
- Сравнить SHA с `~/.hermes/upstream-monitor.json` (`last_sha`)
- Пусто (exit 0, no stdout) → тихо, TG не получает сообщение
- Есть новые коммиты → вывести log + grep breaking changes → доставить в TG
- Обновить `last_sha` в state-файле

**Расписание:** понедельник 08:00 (`0 8 * * 1`) — после выходных максимум изменений.

## State-файл

`~/.hermes/upstream-monitor.json`:
```json
{"last_sha": "abc1234...", "checked_at": "2026-06-04T08:00:00"}
```
Создаётся при первом запуске. Если отсутствует — инициализировать текущим HEAD.

## Что выводить при изменениях

```
🔔 Upstream hermes-agent: N новых коммит(ов)

<git log --oneline last_sha..upstream_sha | head -10>

⚠️ Возможные breaking changes:
<строки с: break|breaking|config|schema|migration|rename|remove|deprecat>

Для обновления: git -C ~/hermes-agent pull --ff-only
Обновлён last_sha → abcd1234
```

## Grep-паттерн breaking changes

```bash
git log --oneline "$LAST..$NEW" | \
  grep -iE "break|breaking|config|schema|migration|rename|remove|deprecat|incompatible" | head -5
```

## Процедура применения обновления ядра

1. `git -C ~/hermes-agent status -s` → должен быть чистым (0 файлов)
2. Если грязный: `git -C ~/hermes-agent checkout -- . && git -C ~/hermes-agent config core.autocrlf input`
3. Бэкап: `bash ~/.hermes/scripts/backup_hermes.sh`
4. `git -C ~/hermes-agent pull --ff-only`
5. Читать `RELEASE_v*.md` или `CHANGELOG.md`
6. `pip install -e ~/hermes-agent` если изменился `pyproject.toml`
7. `systemctl --user restart hermes-gateway.service`
8. Smoke-test: одно сообщение в TG + одна cron-задача вручную

## Анализ категорий и затронутых компонентов

После обнаружения изменений — полезно сразу категоризировать:

```bash
# Подсчёт по типу
FEAT=$(git log --oneline "$LAST..$NEW" | grep -c "^[a-f0-9]* feat" || echo 0)
FIX=$(git log --oneline "$LAST..$NEW" | grep -c "^[a-f0-9]* fix" || echo 0)

# Затронутые top-level директории
COMPONENTS=$(git diff --name-only "$LAST" "$NEW" | sed 's|/.*||' | sort -u | tr '\n' ' ')

# Пересечение с компонентами которые мы используем (VM-конфиг)
OURS=$(git diff --name-only "$LAST" "$NEW" | \
    grep -E "^(cron/|gateway/|hermes_constants|agent/prompt_builder|tools/|skills/)" | head -10 || true)

# Schema changes
CONFIG_CHANGE=$(git diff --name-only "$LAST" "$NEW" | \
    grep -E "DEFAULT_CONFIG|hermes_constants|pyproject.toml" || true)

# Итоговая рекомендация
if [ -n "$BREAKING" ]; then
    echo "🔴 Рекомендация: ОТЛОЖИТЬ — изучить breaking changes вручную"
elif [ -n "$OURS" ] || [ -n "$CONFIG_CHANGE" ]; then
    echo "🟡 Рекомендация: ПРОВЕРИТЬ — затронуты используемые компоненты, QA после pull"
else
    echo "🟢 Рекомендация: БЕЗОПАСНО применить git pull --ff-only"
fi
```

Компоненты которые мы используем на VM:
`cron/`, `gateway/`, `hermes_constants.py`, `agent/prompt_builder.py`, `tools/`, `skills/`

## Двухступенчатый пайплайн (рабочая схема)

**Правило:** `no_agent` скрипт сам в TG НЕ доставляется (`deliver: local`). Его вывод читает Opus через `context_from`. Это единственный способ гарантировать русскоязычный отчёт — у bash-скрипта нет языковой модели, и коммиты он выводит как есть (на английском).

```
08:00 пн  vm_upstream_monitor  (no_agent, deliver: local)  — тихо собирает данные
08:30 пн  vm_upstream_report   (Opus, context_from: [vm_upstream_monitor])  — анализирует и пишет в TG
```

При создании крон-задачи мониторинга:
- `deliver: local` на скрипте (не в TG напрямую!)
- Отдельный Opus-крон с `context_from: [<id скрипта>]`, модель `claude-opus-4-7`
- В промпте Opus: явно указать «Отвечай ТОЛЬКО на русском языке» и контекст конфигурации пользователя

## Анализ коммитов через Opus (шаблон промпта)

Когда watchdog обнаружил изменения и вывод краткий — для детального анализа запустить Opus-крон:

```
Изучи N новых коммитов upstream hermes-agent (SHA: LAST..NEW).
Для каждого коммита:
- Что меняет (1-2 строки)
- Касается ли нашей конфигурации: проверь ~/.hermes/profiles/anthropic/config.yaml на prefill/supermemory/затронутые секции
- Риск при применении
- Рекомендация: применять / отложить / не нужно

Проверить:
- git show <sha> --stat
- grep -r "<changed_key>" ~/.hermes/profiles/anthropic/config.yaml

Итог: 🟢/🟡/🔴 + команда git -C ~/hermes-agent pull --ff-only если безопасно.
```

**Практика (04.06.2026):** обновление supermemory (session-level ingest) + prefill key fix + dashboard register — все 4 коммита оказались безопасными (🟢). supermemory не используется (`memory.provider: ''`), prefill пустой, dashboard register — аддитивная фича.

## Pitfalls

- **Не делать `git pull` в скрипте** — только `fetch`. Pull меняет рабочую копию и может сломать запущенный gateway.
- **CRLF-загрязнение:** если `git status -s | wc -l > 5` после fetch — это CRLF, не правки. Исправить: `git checkout -- . && git config core.autocrlf input`.
- **SSH-ключ недоступен ночью:** если fetch падает с auth error — скрипт должен выводить warn и exit 0 (не 1), иначе false alarm в TG.
- **Первый запуск инициализирует state** с текущим HEAD — не с upstream. Следующий понедельник покажет реальные изменения.
- **no_agent скрипт всегда на английском** — коммиты из git log выводятся как есть. НИКОГДА не ставить `deliver: telegram` на no_agent мониторинг репозиториев. Только `deliver: local` + отдельный Opus-крон с `context_from`.
- **Большой накопленный долг (>500 коммитов):** скрипт покажет только `head -10`. При реальном обновлении нужно передавать Opus полный список через отдельную разовую задачу с явным списком коммитов в промпте.
- **`HEAD~N` в pip-проверке:** при накоплении 1000+ коммитов `git diff HEAD~1200 HEAD -- pyproject.toml` выполняется долго. Лучше: `git diff <OLD_SHA> HEAD -- pyproject.toml` — взять SHA из state-файла `~/.hermes/upstream-monitor.json` (поле `last_sha`) до pull.

## Файлы

- `scripts/upstream_monitor.sh` — основной watchdog скрипт
- `templates/opus_update_and_qa.md` — готовый промпт для разового Opus-крона «обновление + Weekly QA» (копировать как есть, подставить N коммитов и запускать через `cronjob run` немедленно)

## Применение для других репозиториев

Паттерн универсален: любой внешний git-репо (плагины, USERTOOLS, зависимости). Менять только `REPO` и `STATE` переменные.
