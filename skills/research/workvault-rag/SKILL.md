---
name: workvault-rag
description: "RAG и семантический поиск по WorkVault (Obsidian MD) — установка, обновление индекса, интеграция с USERTOOLS кронами. Инструменты: enzyme (Hermes plugin) и qmd (optional-skill)."
version: 1.2.0
author: Sirene
tags:
  - RAG
  - Obsidian
  - WorkVault
  - enzyme
  - qmd
  - knowledge-base
related_skills:
  - obsidian
  - llm-wiki
platforms:
  - linux
---

# WorkVault RAG — семантический поиск по MD-заметкам

## Когда использовать

- Пользователь спрашивает что-то по митингам, проектам, контактам без указания конкретного файла
- PM Briefing в начале сессии — «что важного по проектам?»
- Поиск по 1000+ файлам NewMeetings без явных ключевых слов
- Нужно найти связи между заметками (кто участвовал, какой проект упоминался)

## Два инструмента: enzyme vs qmd

### enzyme — Hermes plugin (compile-time граф)

**Установка:**
```bash
hermes plugin install jshph/enzyme-skill
```

**Первая индексация** (из ~/WorkVault):
```bash
cd ~/WorkVault && enzyme refresh
```

**Начало сессии:**
```bash
enzyme petri   # briefing: trending topics, thematic tensions
```

**Характеристики:**
- 8ms поиск (compile-time, не per-query)
- 23MB модель
- Лучший для: «агент знает vault до первого сообщения», граф связей тегов/ссылок/папок
- Находит связи без совпадения ключевых слов (через catalysts)

### qmd — official optional-skill Hermes

**Установка:**
```bash
hermes skills install qmd
```

**Добавление коллекций:**
```bash
qmd collection add ~/WorkVault/Meetings/NewMeetings --name meetings
qmd collection add ~/WorkVault/Projects --name projects
qmd collection add ~/WorkVault/Confluence --name confluence
qmd context add ~/WorkVault/Meetings/NewMeetings "Meeting summaries and transcripts from Fireflies"
```

**Генерация эмбеддингов (первый раз и при новых файлах):**
```bash
qmd embed
```

**Поиск:**
```bash
qmd search "запрос"     # BM25 ~0.2s
qmd vsearch "запрос"    # semantic ~3s
qmd query "запрос"      # hybrid + reranking, лучшее качество
```

**Характеристики:**
- ~2GB моделей (gemma-300M, qwen3-0.6B, 1.7B)
- Node.js >= 22 required
- MCP интеграция: `qmd mcp --http --daemon`
- Лучший для: точечный поиск, программная интеграция в Python-скрипты

## Выбор по задаче

| Задача | enzyme | qmd |
|---|---|---|
| PM Briefing, session start | лучше | — |
| Поиск по митингам с именем/датой | — | лучше |
| Связи между темами/проектами | лучше | — |
| Интеграция в Python-скрипт | — | лучше |
| Частый refresh | ~20с на весь vault | медленнее |
| MCP-сервер | — | есть |

**Оптимально:** enzyme для session context + qmd для точечного поиска в инструментах.

## USERTOOLS — карта интеграции

Python-инструменты пишут файлы → RAG читает файлы. **Переделывать инструменты не нужно.**

| Инструмент | Что пишет | Формат | RAG видит | Cron в Hermes |
|---|---|---|---|---|
| MoveFromFF | Meetings/NewMeetings/*.md | MD | да | `vm_movefromff` каждые 2ч |
| MoveFromZulip | Contacts/ | MD | да | paused |
| MoveFromJira | Projects/*/jira_snapshot.json | JSON | нет | нет |
| ConfluenceSync | Confluence/*.md | MD | да | нет |
| AnywhereContacts | Contacts/contacts.enc | зашифрован | нет | нет |

## Необходимые доработки

### 1. MoveFromFF (активен) — добавить refresh в cron, инструмент не трогать

В cron `vm_movefromff` дописать после основной команды:
```bash
cd ~/WorkVault && enzyme refresh
# и/или:
qmd embed
```

### 2. ConfluenceSync — нет cron, создать + refresh внутри

Инструмент не трогать. Только новый Hermes cron с `enzyme refresh` в конце.

### 3. MoveFromJira — JSON не индексируется, нужна доработка инструмента

Пишет `jira_snapshot.json`, не MD. Варианты:
- **Быстро:** настроить qmd включать JSON-файлы в Projects/
- **Правильно:** добавить в `sync.py` (~20 строк) генерацию `card.md` из snapshot рядом с JSON. Тогда Projects/*/card.md = актуальный Jira-статус, виден и RAG, и AfM.

### 4. AnywhereContacts и MoveFromZulip — пропустить

Зашифрованный store и paused соответственно. Вернуться при активации.

## Решение для текущего внедрения (08.07.2026)

Для реального сценария Саши (точечные факт-запросы через Telegram по встречам/ТЗ — «что обещал Х», «какое ТЗ описывает Y») выбран **qmd, не enzyme** — детерминированный BM25+vector с явными коллекциями надёжнее для этого класса запросов, чем ассоциативный граф enzyme. Enzyme не разворачивается (экономия ресурсов/сложности) до появления реальной потребности в широком тематическом брифинге.

Полный пофайловый план реализации (установка, симлинк-ферма для исключения transcript, systemd daemon, MCP-интеграция, крон-автообновление) — `WorkVault/Hermes-Backlog/TZ/QMD-Search/QMD-Search_TZ.md` (hранится по правилам `tz-workflow`, статус `draft` до «берём в работу»). Этот файл — источник актуальных команд, не дублировать его содержимое здесь.

**VM-специфичный гочтка при установке npm-пакетов (обнаружено 08.07.2026):** на VM Сирени существуют **два независимых Node.js** — `~/.local/bin/node` (реальный активный `npm prefix`, туда ставится `npm install -g`) и `~/.hermes/profiles/anthropic/node/bin/node` (изолированный, используется только для внутренних Hermes npm-модулей вроде `agent-browser`). Перед тем как хардкодить путь к бинарнику в systemd unit или крон-скрипте — обязательно проверить фактически: `which node`, `which npm`, `npm config get prefix`. Не полагаться на путь, который "кажется логичным" (например Hermes-профильный, раз работаешь внутри Hermes) — легко ошибиться и получить unit, который не находит бинарник.

## Ссылки

- enzyme: https://github.com/jshph/enzyme-skill
- qmd: optional-skills/research/qmd/SKILL.md в NousResearch/hermes-agent
- Подробный аудит: references/usertools-rag-audit.md

## Scoping к конкретным папкам (не индексировать весь vault)

**enzyme:** конфиг `~/.enzyme/config.toml` (генерируется `enzyme scan --write-config`, дальше правится вручную). Ключевые механизмы:
- `folder:<path>` entries — явно помечают папку как важный узел графа (например `folder:Hermes-Backlog/TZ`, `folder:Meetings`). Выбор родительской папки обычно достаточен — дочерние wikilink-страницы подхватываются автоматически.
- `targets = [...]` — отдельный механизм для точечного поиска по внешним/специфичным директориям вне обычного индекса (`enzyme catalyze "query" --target ./some-dir`), пути указываются как raw filesystem path, БЕЗ префикса `folder:`.
- Служебные папки (`.hermes`, `.git`, `.obsidian`, `node_modules` и т.п.) исключаются автоматически.
- Нет явного строгого allowlist-режима ("индексировать ТОЛЬКО эти папки, ничего больше") в документации — механизм работает через приоритизацию нужных folder-узлов + автоисключение мусора, не через hard include-list. Если критично не касаться других папок (например `Contacts/` с зашифрованными данными) — проверять на практике при установке, не полагаться только на конфиг.

**qmd:** явные именованные коллекции — `qmd collection add ~/WorkVault/Hermes-Backlog/TZ --name tz` и отдельно `qmd collection add ~/WorkVault/Meetings/NewMeetings --name meetings`. Это настоящий allowlist — qmd видит только явно добавленные коллекции, ничего лишнего в индекс не попадает. Более предсказуемо для точечного scoping, чем enzyme.

## Требования на VM (обе не требуют Obsidian запущенным)

Obsidian — просто GUI поверх той же папки `.md`-файлов; ни enzyme, ни qmd не используют Obsidian API — оба читают файловую систему напрямую. Держать Obsidian включённым на VM для их работы не нужно.

- **enzyme**: 11MB бинарник + 23MB embedding-модель (ONNX, локально). LLM для генерации catalysts — либо hosted bootstrap enzyme (без логина для первого init), либо свой ключ через `--use-env-llm`. Компилирует 1000+ документов <20с, дальше поиск ~8мс, $0/запрос.
- **qmd**: требует Node.js ≥22. ~2GB локальных GGUF-моделей (embedding + reranker + query-expansion), полностью локальный инференс, $0/запрос всегда. В daemon-режиме (`qmd mcp --http --daemon`, systemd unit) держит ~2GB RAM постоянно, но снимает холодный старт (~19с → ~2-3с).

Проверено на VM Сирени (AlmaLinux 9.7, 4 vCPU Xeon Gold 6150, 11GiB RAM, 199GB диск) 06.07.2026 — оба варианта укладываются с большим запасом (8.9GB своб. RAM, 181GB своб. диска, Node v22.23.1 уже установлен). Ресурсы VM не являются ограничивающим фактором выбора между enzyme/qmd — выбор определяется функциональными критериями (см. таблицу "Выбор по задаче").

## Риск: summary.md vs transcript.md в одной коллекции/индексе

MoveFromFF пишет и `summary.md` (плотный, ~3KB), и `transcript.md` (полный, ~31KB) на одну встречу. Индексирование обоих без разбора создаёт проблему:

- **qmd**: transcript даёт ~30+ чанков (31KB / ~900 токенов на чанк) против 1-2 чанков от summary. При RRF-слиянии transcript-чанки численно доминируют топ-30 кандидатов для реранкинга просто по объёму, даже если менее релевантны конкретному запросу.
- **enzyme**: менее критично (catalyst работает на уровне сущности/темы, не чанка), но всё равно может подтягивать дублирующие excerpts из обоих файлов на одну тему.

**Рекомендация:** индексировать в основной коллекции/индексе **только `summary.md`**. Transcript — НЕ включать в дефолтный поиск: либо отдельная explicit-коллекция, либо доступ точечно через `qmd get`/`read_file` только когда уже известна конкретная встреча и нужна дословная цитата. Тот же принцип из обсуждения версионированных ТЗ (не давать RAG равный доступ к материалам разной надёжности/детализации) применим и здесь: summary — плотный сигнал, transcript — архив для точечного обращения.

## Общий паттерн: symlink-farm для фильтрации разнородного контента (08.07.2026)

Тот же риск, что у summary/transcript, возникает у **любой** папки, где вперемешку лежат финальные материалы и черновой/промежуточный процесс. Пример — `Hermes-Backlog/TZ/`: помимо master-ТЗ там есть `pm/sessions/*` (черновые handoff-логи и промежуточные Q&A по ходу разработки), `_TEMPLATE.md`, `README.md`, `MAIN_TZ_INVENTORY.md`, `cursor-*.md` — если индексировать папку целиком, RAG может выдернуть устаревший промежуточный вариант решения вместо актуального финального.

**Решение — та же симлинк-ферма, что и для summary/transcript:**
```bash
COLL_ROOT="$HOME/.local/share/qmd-collections"
mkdir -p "$COLL_ROOT/<name>"
find <source-dir> \( -name "<final-pattern>" \) -not -path "*/<draft-subdir>/*" -not -name "_TEMPLATE.md" \
  -print0 | xargs -0 -I{} ln -sf {} "$COLL_ROOT/<name>/"
qmd collection add "$COLL_ROOT/<name>" --name <name>
```
Не полагаться на недокументированные `--exclude`/`--include` флаги qmd (не описаны в SKILL.md, поведение не подтверждено) — симлинк-ферма детерминирована и легко проверяется `ls`.

**Проверенный пример** (TZ-коллекция, `QMD-Search_TZ.md` v0.3): индексируются `*_TZ.md` + `TZ_*.md` (master-ТЗ и модули) + `PM_DECISIONS_LOG.md`/`GOLDEN_REFS.md` (зафиксированные решения); исключаются `pm/sessions/*`, `_TEMPLATE.md`, `README.md`, `MAIN_TZ_INVENTORY.md`, `_TZ-WORKFLOW-RULES.md`, `cursor-*.md`.

**Обновление симлинк-фермы у контента без периодического крона** (в отличие от встреч через MoveFromFF, ТЗ правятся вручную/через Opus по `tz-workflow`, не по расписанию) — досоздание симлинков (`ln -sf`, idempotent) + `qmd embed` встраивать в конец соответствующей процедуры правки контента (например `tz-workflow` Блок B/C), а не в отдельный крон.

## Управление коллекциями qmd (добавление/удаление хранилищ)

**Добавление новой коллекции** — только по явному запросу пользователя, не самостоятельная инициатива:
1. Оценить, нужна ли symlink-farm (контент смешанный — черновики+финалы) или можно `qmd collection add` напрямую на реальную папку (контент уже однородный).
2. `qmd collection add <path> --name <name>` + `qmd context add qmd://<name> "<описание>"` + `qmd embed`.
3. Зафиксировать в живом плане проекта (см. `QMD-Search_TZ.md` §5а — таблица активных коллекций: путь, что индексируем/исключаем, дата) — не терять историю решений о scope.

**Удаление коллекции:**
1. `qmd collection remove <name>` — точный синтаксис не описан в `optional-skills/research/qmd/SKILL.md`, проверить при первом использовании.
2. Удалить связанную симлинк-ферму (`rm -rf ~/.local/share/qmd-collections/<name>`), если была.
3. Убрать строку из таблицы коллекций в плане.

## Кейс "запросы через мессенджер к удалённой VM" (ТЗ / встречи)

И enzyme, и qmd только находят релевантные куски текста — финальный ответ пользователю всё равно формирует агент (Sonnet/Opus) поверх найденного контекста. Для этого сценария:
- **qmd** надёжнее для точечных вопросов ("что в ТЗ MoveFromFF", "что обсуждали на встрече с Ивановым X числа") — детерминированный BM25+vector с явными коллекциями, предсказуемый результат по конкретному термину/имени.
- **enzyme** лучше для широких/ассоциативных вопросов ("что сейчас активно по проектам") — семантические связи без совпадения слов, но менее предсказуем для точечного запроса.
- Для латентности через Telegram — qmd в daemon-режиме даёт стабильные 2-3с; enzyme даёт 8мс на уже посчитанный граф (быстрее, но требует состоявшегося `refresh` заранее).
- Учитывая уже принятое решение про версионированные ТЗ (qmd с ручными коллекциями безопаснее для документов, где новая версия отменяет старую) — та же логика распространяется на выбор инструмента для ТЗ-запросов конкретно.
