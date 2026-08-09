---
name: hermes-skills-discovery
description: "Find and evaluate new Hermes skills by topic and popularity."
version: 1.1.0
author: agent
tags: [hermes, skills, discovery, skills.sh, cron, monitoring]
platforms: [linux]
---

# Hermes Skills Discovery

Класс задачи: находить новые/популярные скиллы во внешней экосистеме Hermes/OpenClaw по интересующим Сашу темам, с объективной метрикой популярности (число установок), не только по описанию.

## Когда использовать

- Саша просит найти скиллы по конкретной теме ("есть скилл для X?")
- Нужно оценить, насколько популярен/проверен конкретный скилл перед установкой
- Обслуживание ежемесячного дайджеста скиллов (крон + `skills_digest.py`)
- Расширение списка отслеживаемых тем в существующем дайджесте
- Промежуточная ad-hoc проверка новых скиллов между дайджестами

## Два независимых канала данных — используй оба

| Канал | Команда | Даёт | Не даёт |
|---|---|---|---|
| Hermes встроенный хаб | `hermes skills search "<query>"` | Мультиисточниковый поиск, готовые identifier для `hermes skills install` | Число установок/популярность — этого поля НЕТ ни в табличном, ни в `--json` выводе |
| skills.sh публичный legacy API | `curl -s "https://skills.sh/api/search?q=<query>"` | Поле `installs` — реальное число установок, без ключа | Не покрывает источники вне skills.sh |

**Правило: если нужно решить "стоит ли смотреть этот скилл подробнее" — сортируй по `installs`, не по формулировке описания.** Installs — единственный объективный сигнал без ручного чтения кода.

```bash
curl -s "https://skills.sh/api/search?q=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "context compression")" | python3 -m json.tool
```

**Официальный `skills.sh/api/v1/...` требует API-ключ.** Легаси `/api/search` работает стабильно без ключа — предпочитай его.

## Питфолл: `hermes skills search --json` работает, `hermes skills inspect --json` — нет

`hermes skills search "<query>" --json` возвращает валидный JSON-массив. `hermes skills inspect <id> --json` падает с `unrecognized arguments: --json` — для inspect используй табличный вывод.

## Готовая автоматизация: ежемесячный дайджест по темам (v2, 16.07.2026)

`~/.hermes/scripts/skills_digest.py` — крон **ежемесячно** (1 число, 09:00). Полный отчёт в `WorkVault/News/NewSkills+<дата>.md`. Доставка в топик Backlog.

- Темы: управление проектами, контекст/токены, RAG, ТЗ/скиллы, гигиена памяти, админ, склад, бухгалтерия, Hermes+Obsidian
- Порог `MIN_INSTALLS = 500`, `TOP_N = 10` на тему
- Перевод через Haiku одним батчем (прямой Anthropic API, не агентный цикл)
- Ключи: `HERMES_SKILLS_DIGEST_ANTHROPIC_KEY` и `HERMES_SKILLS_DIGEST_GH_TOKEN` (НЕ стандартные имена — Hermes вырезает ANTHROPIC_API_KEY/GITHUB_TOKEN из subprocess)
- Перевод: жёсткий промпт, retry с backoff (3×5/10/15s)
- После записи → `systemctl --user start owncloud-sync.service`

**Добавление новой темы:** отредактировать `TOPICS` в скрипте.

## Промежуточные проверки (ad-hoc / еженедельные)

Когда скилл загружается вне месячного дайджеста — **не генерировать полный дайджест**. Вместо этого:

1. **Запросить skills.sh** по всем темам (через `execute_code`, без описаний/перевода — только id/name/installs/source)
2. **Найти последний дайджест:** `ls -t ~/WorkVault/News/NewSkills+*.md | head -1`
3. **Сравнить:** исключить все `id`, уже присутствующие в дайджесте
4. **Вывести только новинки** — компактно: тема, название, source, installs
5. **Порог:** новых нет → `[SILENT]`. 1-3 пограничных → короткий отчёт. 4+ → подробнее

Цель: сигнальная проверка, не дублировать `skills_digest.py`.

## Питфолл: GitHub git-trees API для description скилла

`skills.sh/api/search` не отдаёт description. Для получения текста:

```python
# 1. Дерево репо:
url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/main?recursive=1"
# ищем SKILL.md по пути, содержащему /{skill_id}/

# 2. Raw-содержимое:
url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/{path}"
# regex: r"^description:\s*(.+)$"
```

Rate limit: 60/час без токена → 5000/час с `HERMES_SKILLS_DIGEST_GH_TOKEN`. Кэш деревьев внутри прогона по `owner/repo`.

## Отличие от hermes-upstream-check

`hermes-upstream-check` — апдейты ЯДРА `NousResearch/hermes-agent`. Этот скилл — СКИЛЛЫ сторонних авторов в экосистеме. Не путать.

## Возможное расширение

`official/devops/watchers` — мониторинг за пределами skills.sh. Решение отложено.