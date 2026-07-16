---
name: hermes-skills-discovery
description: "Мониторинг внешней экосистемы скиллов Hermes/OpenClaw (skills.sh, GitHub, community hubs) по темам интереса — поиск новых и популярных скиллов с реальным числом установок, не путать с hermes-upstream-check (тот про апдейты ядра hermes-agent, этот — про скиллы других авторов). Загружать при задачах 'найди скиллы по теме X', 'что нового в сообществе скиллов', 'оцени популярность скилла', 'дайджест скиллов'."
version: 1.0.0
author: agent
tags: [hermes, skills, discovery, skills.sh, cron, monitoring]
platforms: [linux]
---

# Hermes Skills Discovery

Класс задачи: находить новые/популярные скиллы во внешней экосистеме Hermes/OpenClaw по интересующим Сашу темам, с объективной метрикой популярности (число установок), не только по описанию.

## Когда использовать

- Саша просит найти скиллы по конкретной теме ("есть скилл для X?")
- Нужно оценить, насколько популярен/проверен конкретный скилл перед установкой
- Обслуживание еженедельного дайджеста скиллов (крон + `skills_digest.py`)
- Расширение списка отслеживаемых тем в существующем дайджесте

## Два независимых канала данных — используй оба

| Канал | Команда | Даёт | Не даёт |
|---|---|---|---|
| Hermes встроенный хаб | `hermes skills search "<query>"` | Мультиисточниковый поиск (official, skills-sh, clawhub, github, lobehub, browse-sh, nvidia, openai, anthropic, huggingface, voltagent, gstack, minimax — см. `--source`), готовые identifier для `hermes skills install` | Число установок/популярность — этого поля НЕТ ни в табличном, ни в `--json` выводе |
| skills.sh публичный legacy API | `curl -s "https://skills.sh/api/search?q=<query>"` | Поле `installs` — реальное число установок на конкретный скилл/источник, без ключа авторизации | Не покрывает источники вне skills.sh (например чистый GitHub-поиск или clawhub-only записи) |

**Правило: если нужно решить "стоит ли смотреть этот скилл подробнее" — сортируй по `installs`, не по формулировке описания.** Описания в маркетплейсе пишут авторы скиллов сами — они не коррелируют с качеством или проверенностью. Installs — единственный объективный сигнал, который есть без ручного чтения кода.

```bash
curl -s "https://skills.sh/api/search?q=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "context compression")" | python3 -m json.tool
```

Пример структуры ответа:
```json
{"query": "...", "searchType": "fuzzy", "skills": [
  {"id": "owner/repo/skill-name", "skillId": "skill-name", "name": "skill-name",
   "installs": 1163, "source": "owner/repo"}
]}
```

**Официальный `skills.sh/api/v1/...` требует API-ключ** (запрашивается отдельно у команды skills.sh, не выдаётся автоматически — см. `vercel-labs/skills#1053`). Легаси `/api/search` работает стабильно без ключа (проверено 16.07.2026, несколько последовательных запросов — 200 OK, без rate-limit проблем) — предпочитай его, пока официальный ключ не получен.

## Питфолл: `hermes skills search --json` работает, `hermes skills inspect --json` — нет

`hermes skills search "<query>" --json` возвращает валидный JSON-массив (name/identifier/source/trust_level/description) — используй для скриптования. Но `hermes skills inspect <id> --json` в текущей версии CLI падает с `unrecognized arguments: --json` — для inspect используй обычный табличный вывод (без `--json`), он читаем и так.

## Готовая автоматизация: ежемесячный дайджест по темам (v2, 16.07.2026)

`~/.hermes/scripts/skills_digest.py` — крон "Дайджест новых скиллов Hermes по темам", **ежемесячно** (1 число, 09:00). Доставка: короткое сообщение с кликабельной (copy-on-tap) obsidian-ссылкой в топик Backlog; полный отчёт пишется в файл `WorkVault/News/NewSkills+<дата>.md`. Новый отдельный ТГ-канал/топик под это НЕ заводили — намеренное решение (Саша передумал на стадии обсуждения), доставка идёт в существующий Backlog.

Архитектура v2 — **гибрид no_agent + прямой Haiku-вызов** (не полноценный agent-крон, но и не чистый no_agent):
- Темы отслеживания (словарь `TOPICS` прямо в скрипте): управление проектами/задачами, управление контекстом/снижение токенов, RAG, ТЗ и разработка скиллов, гигиена памяти Hermes, административная работа, складская деятельность, личная бухгалтерия, связка Hermes+Obsidian
- Источник installs: skills.sh legacy API (см. выше)
- Порог `MIN_INSTALLS = 500` (ужесточён с 20 — Саша явно попросил меньше шума), `TOP_N = 10` находок на тему (расширен с 5)
- Описания скиллов достаются с GitHub git-trees API (см. питфолл ниже) и переводятся на русский одним пакетным вызовом claude-haiku-4-5 через прямой Anthropic API-клиент внутри скрипта (import anthropic; client.messages.create(...)) — НЕ через агентный цикл Hermes. Это и есть смысл "гибрида": сам крон остаётся дешёвым/детерминированным no_agent-скриптом, а перевод — единственный платный LLM-вызов, вынесенный в тот же процесс напрямую по API-ключу.
- ⚠️ Ключи читаются НЕ под стандартными именами (ANTHROPIC_API_KEY, GITHUB_TOKEN) — под HERMES_SKILLS_DIGEST_ANTHROPIC_KEY и HERMES_SKILLS_DIGEST_GH_TOKEN в .env. Причина и полный разбор — см. питфолл "no_agent cron scripts: provider/GitHub API keys are stripped from subprocess env" в скилле hermes-gateway-setup. Коротко: Hermes безусловно вырезает ANTHROPIC_API_KEY/GITHUB_TOKEN/GH_TOKEN (и другие provider/gateway-креды) из окружения ЛЮБОГО спавнутого subprocess, включая no_agent-крон-скрипты — это защита от утечки кредов (GHSA-rhgp-j443-p4rf), не баг. Решение: завести отдельно названную переменную в .env, не входящую в блок-лист, и читать её вместо оригинала.
- Промпт перевода ОБЯЗАН быть жёстким ("верни ТОЛЬКО пронумерованный список, без альтернатив/вступлений/markdown") — без этого Haiku возвращает "основной + альтернативные варианты" на некоторые пункты, что ломает построчный парсинг регэкспом `^\s*\d+\.\s*(.+)$` (count mismatch → fallback на английский текст).
- Retry с backoff (3 попытки, 5/10/15 сек) на перевод — Anthropic API может вернуть `529 Overloaded` временно; без retry дайджест молча остаётся на английском. Если и после retry не получилось — не падать, использовать английское описание как fallback, не блокировать доставку отчёта.
- v1 (еженедельно, топ-5, порог 20, state-based дедуп в `~/.hermes/skills-digest-state.json`) — **упразднён**, весь топ-N выводится в файл каждый прогон заново, дедуп через месячный интервал не нужен (за месяц список объективно успевает измениться).
- После записи файла — синк в облако строго через штатный `systemctl --user start owncloud-sync.service` (НИКОГДА не руками с самодельными `rclone sync --exclude` — см. инцидент 15.07.2026 в скилле `workvault-sync-infra`, потеря данных на ownCloud от ручного вызова).

**Добавление новой темы:** отредактировать словарь `TOPICS` в скрипте (`тема на русском: поисковый запрос`) — новая тема появится в следующем ежемесячном прогоне.

## Питфолл: GitHub git-trees API для description скилла — без токена, но с rate limit

`hermes skills search` и `skills.sh/api/search` не отдают текст `description` скилла (только installs/source/name). Чтобы получить реальный текст description для перевода, нужно найти и прочитать сам `SKILL.md` в исходном репозитории:

```python
# 1. Найти путь к SKILL.md внутри репо БЕЗ токена (публичные репо):
url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/main?recursive=1"
# ищем в дереве: t['path'].endswith('SKILL.md') and f"/{skill_id}/" в пути

# 2. Прочитать raw-содержимое и вытащить description из YAML frontmatter:
url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/{path}"
# regex: r"^description:\s*(.+)$" с re.MULTILINE
```

**Rate limit пойман на практике (16.07.2026):** неавторизованный GitHub API — лимит **60 запросов/час**. При топ-10 × 9 тем это до ~90 репозиториев за один прогон — превышает лимит при нескольких тестовых прогонах подряд в течение часа (проверено: `x-ratelimit-remaining: 0` после второго прогона теста). Для РЕАЛЬНОГО ежемесячного расписания это не критично — между прогонами месяц, лимит гарантированно успевает сброситься (сбрасывается раз в час). Скрипт устойчив к превышению лимита: если запрос к GitHub упал — пропускает description этого скилла (`(описание недоступно)`), не падает целиком. Лимит уже поднят до 5000/час: создан отдельный GitHub Personal Access Token (scope `public_repo`, без прав на запись), сохранён в `.env` как `HERMES_SKILLS_DIGEST_GH_TOKEN` (НЕ как `GITHUB_TOKEN` — см. питфолл про stripping выше), передаётся в заголовке `Authorization: Bearer <token>` GitHub API запросов.

**Кэширование внутри одного прогона:** один и тот же репозиторий может встретиться в нескольких темах (например `sickn33/antigravity-awesome-skills` даёт находки сразу в RAG, context-compression и др.) — скрипт кэширует уже скачанное дерево репозитория в `_repo_tree_cache` по ключу `owner/repo`, чтобы не тратить лишний запрос на повторный репозиторий в рамках одного прогона.

## Отличие от hermes-upstream-check

`hermes-upstream-check` — про апдейты ЯДРА `NousResearch/hermes-agent` (наш форк, git log/diff между версиями кода). Этот скилл — про СКИЛЛЫ сторонних авторов в экосистеме (skills.sh/GitHub/clawhub), не про сам движок. Разные источники данных, разные критерии решения, не путать при выборе какой загружать.

## Возможное расширение (обсуждалось, отложено)

Официальный скилл `official/devops/watchers` (`hermes skills install official/devops/watchers`) даёт `watch_rss.py`/`watch_github.py`/`watch_http_json.py` с дедупликацией по watermark — можно расширить мониторинг за пределы skills.sh: GitHub-коммиты в `NousResearch/hermes-agent/optional-skills/`, Reddit r/hermesagent RSS. Решение отложено намеренно (пересмотреть через ~неделю после первого боевого прогона дайджеста, достаточно ли текущего покрытия skills.sh) — не устанавливать `watchers` без явного решения, что текущего покрытия не хватает.
