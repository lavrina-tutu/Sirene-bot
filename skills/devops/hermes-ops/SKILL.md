---
name: hermes-ops
description: "Проверять docs.hermes-agent.nousresearch.com как источник истины перед любой настройкой/расширением/диагностикой Hermes: конфиги, скиллы, MCP, память, cron, оптимизация. Triggers: настройка Hermes, MCP, скиллы, оптимизация Hermes, память Hermes, memory, config.yaml, hermes update, hooks, cron, gateway, профили Hermes, plugins."
version: 0.2.0
author: agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [hermes, ops, docs, configuration, skills, mcp, memory, optimization, hooks]
    related_skills: [hermes-agent, hermes-feature, hermes-upstream-check, hermes-multi-profile-skills, skill-authoring-principles]
---

# hermes-ops

## Overview

Операционное правило для любой задачи, где нужно настроить, расширить, продиагностировать или оптимизировать сам Hermes Agent (не пользовательские инструменты — это `hermes-feature`). Дополняет bundled-скилл `hermes-agent` (справочный хаб, перезаписывается апдейтом) активным требованием: **доки на nousresearch.com — источник истины, не память и не содержимое скиллов**, которое может отставать от установленной версии.

## When to Use

- Настройка Hermes: конфигурация, провайдеры, модели, gateway, профили
- Разработка/правка скиллов: создание, аудит, версионирование
- MCP: подключение серверов, конфигурация, отладка, фильтрация тулов
- Оптимизация: токены, контекст, кэш промпта, роутинг моделей, кроны
- Работа с памятью: MEMORY.md/USER.md, memory providers, дефрагментация
- Плагины и hooks: pre/post_tool_call, pre_llm_call, shell-hooks
- Диагностика: «Hermes сломался», «не работает X», «почему Y»

**Не для:** написания пользовательского кода/инструментов на базе Hermes (`hermes-feature`); самого процесса апдейта апстрима (`hermes-upstream-check` — владеет этим процессом; этот скилл дополняет его сверкой конкретных деталей конфигурации с докой во время апдейта, не заменяет план обновления).

## ЖЁСТКОЕ ПРАВИЛО: Docs — источник истины

ПЕРЕД любой настройкой, диагностикой, расширением или оптимизацией Hermes:

1. **Определи тему** по routing table ниже.
2. **Загрузи docs** через `web_extract` релевантного раздела `https://hermes-agent.nousresearch.com/docs/`.
3. **Если тема не покрыта таблицей, или URL вернул 404/redirect** — загрузи `https://hermes-agent.nousresearch.com/docs/llms.txt` (курируемый индекс всех страниц, ~17 КБ, генерируется на каждом деплое) и найди актуальный путь. Не угадывать путь и не полагаться на старую таблицу молча.
4. **Сравни с текущей версией** (`hermes --version`). Если docs описывают функционал, которого нет в установленной версии — отметь это явно.
5. **Работай по docs, не по памяти.** Если docs и установленная версия расходятся — следуй docs, но предупреди пользователя о разнице.

NEVER answer Hermes questions from memory or bundled skills alone — они могут быть написаны для другой версии.

## Routing Table: тема → URL

| Тема | URL |
|---|---|
| Architecture | `/docs/developer-guide/architecture` |
| Tools & Toolsets | `/docs/user-guide/features/tools` |
| Skills System | `/docs/user-guide/features/skills` |
| Creating Skills (авторинг) | `/docs/developer-guide/creating-skills` |
| Curator (staleness/архивация скиллов) | `/docs/user-guide/features/curator` |
| Memory | `/docs/user-guide/features/memory` |
| Memory Providers (Honcho, Mem0, ...) | `/docs/user-guide/features/memory-providers` |
| MCP Integration | `/docs/user-guide/features/mcp` |
| Plugins & Hooks | `/docs/user-guide/features/plugins` , `/docs/user-guide/features/hooks` |
| Configuration | `/docs/user-guide/configuration` |
| Cron Scheduling | `/docs/user-guide/features/cron` |
| Security | `/docs/user-guide/security` |
| CLI Usage | `/docs/user-guide/cli` |
| Messaging Gateway | `/docs/user-guide/messaging/index` |
| Contributing | `/docs/developer-guide/contributing` |
| CLI Reference | `/docs/reference/cli-commands` |
| Environment Variables | `/docs/reference/environment-variables` |
| Bundled/Optional Skills Catalog | `/docs/reference/skills-catalog` , `/docs/reference/optional-skills-catalog` |

Таблица сверена с `/docs/llms.txt` на 07.08.2026. Пути реорганизуются между релизами — при расхождении см. шаг 3 правила выше, а не патчить таблицу вручную по памяти.

## Версия Hermes

```bash
hermes --version
```

Не хранить версию в памяти или скиллах — она меняется при каждом апдейте.

## Skill Development Rules

- Для in-repo скиллов (в `~/hermes-agent/skills/`) — `hermes-agent-skill-authoring` (hardline standards, требует PR/тесты/git).
- Для user-local скиллов — `skill_manage(action='create')`, канонизация в `~/hermes-workspace/skills/` через `sync-to-hermes.sh` (см. `hermes-multi-profile-skills`).
- Один скилл = одна ответственность; триггеры должны однозначно указывать на один скилл.
- Новый скилл, влияющий на работу с Hermes-конфигом/скиллами/памятью, обязан появиться в `related_skills` этого файла и наоборот — односторонние ссылки создают "скилл-сироты" (прецедент: сам `hermes-ops` не был нигде связан до 07.08.2026 и не синкался за пределы default/tz-dev).

## MCP Rules

- Конфигурация через `hermes mcp add` или `config.yaml`.
- Тестировать подключение перед использованием: `hermes mcp list`.
- Референс по фильтрации/утилити-тулам — `/docs/reference/mcp-config-reference`.

## Pitfalls

- **`hermes-agent` SKILL.md — bundled, НЕ редактировать.** Upstream-файл, перезаписывается при `hermes update`. Операционные правила — здесь.
- **Docs > memory.** Если память говорит одно, а docs — другое, следуй docs.
- **Cross-profile writes.** Скиллы в `~/hermes-workspace/skills/` → симлинки во ВСЕ профили (`default`, `tz-dev`, `anthropic`, `openai`) через `sync-to-hermes.sh <profile>`. Прямая правка внутри `~/.hermes/profiles/<name>/skills/` или `~/.hermes/skills/` реальной директорией (не симлинком) создаёт несинканную копию — она не переживёт следующую генерацию скилла и не видна другим профилям.
- **Не путать со скиллом `hermes-upstream-check`** — тот владеет процессом самого апдейта апстрима (git, риск-анализ, план); этот скилл — про то, откуда брать факты о текущем функционале во время любой Hermes-работы, включая, но не ограничиваясь, апдейтом.
- **Gateway НЕ рестартовать** без явного императива пользователя.
- **Hooks — осторожно.** `pre_llm_call` работает на каждом ходу, требует allowlist в config.yaml. Предпочитать скилл хуку, если скилл покрывает задачу.

## Verification Checklist

- [ ] Docs загружены через `web_extract` перед ответом на вопрос про Hermes
- [ ] Если URL из таблицы не сработал — загружен `/docs/llms.txt` для поиска пути
- [ ] Текущая версия Hermes проверена (`hermes --version`)
- [ ] При расхождении docs и версии — пользователь предупреждён
- [ ] Скилл создан по правилам (skill_manage для user-local, write_file + git для in-repo)
- [ ] Файл лежит в `~/hermes-workspace/skills/devops/hermes-ops/` (не `~/.hermes/skills/` или `~/.hermes/profiles/*/skills/`)
