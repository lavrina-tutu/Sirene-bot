---
name: workvault-rag
description: "RAG и семантический поиск по WorkVault (Obsidian MD) — установка, обновление индекса, интеграция с USERTOOLS кронами. Инструменты: enzyme (Hermes plugin) и qmd (optional-skill)."
version: 1.0.0
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

## Ссылки

- enzyme: https://github.com/jshph/enzyme-skill
- qmd: optional-skills/research/qmd/SKILL.md в NousResearch/hermes-agent
- Подробный аудит: references/usertools-rag-audit.md
