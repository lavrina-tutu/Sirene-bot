---
name: about_usr_skills
description: "Use when: (1) Саша спрашивает «что ты умеешь / расскажи о се"
version: 3.0.1
author: agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [workvault, movefrom, sync, pipeline, contacts, fireflies, exchange, zulip, confluence, jira, loop]
    related_skills: [hermes-feature, tz-workflow, hermes-agent-skill-authoring]
---

# USERTOOLS — экосистема инструментов Саши

Мастер-скилл по всем пользовательским инструментам: выгрузка, разметка, публикация, поиск, индексация, реестры. Единственная точка входа на вопрос «что ты умеешь».

## Точка входа: «что ты умеешь»

Когда Саша спрашивает про возможности — НЕ пересказывать по памяти. Выполнить алгоритм:

### Шаг 1 — реестр инструментов
`read_file("~/WorkVault/Hermes-Backlog/TZ/MAIN_TZ_INVENTORY.md")` → таблица «Активные ТЗ» — актуальный список с версиями/статусами.

### Шаг 2 — детали конкретного инструмента
Прочитать `TZ/<Инструмент>/<Инструмент>_TZ.md` по пути из инвентаря.

### Шаг 3 — наши скиллы
`skills_list()` → отфильтровать по признаку: описание про Jira/Confluence/WorkVault/АИД/OKR/SR/протоколы — наш. Generic (spotify, minecraft, ascii) — упоминать по остаточному принципу.

### Шаг 4 — живые примеры
`session_search(query="<тема>")` — реальный диалог. Секции ТЗ «Бриф-сессия», «Открытые вопросы», «Решения».

### Формат ответа
1. 2-3 предложения общего резюме
2. Список активных инструментов с одной строкой каждый, сгруппировать: сбор (MoveFrom*) → структурирование (MOFS, AnywhereContacts, EntityRegistry) → публикация (ProtocolFromSummary) → задачи (TaskRefresh, DialogBacklog) → поиск (MofsIndex, workvault-rag) → служебные
3. 1-2 живых примера если вопрос про область
4. Generic-возможности — только если явно спросили

### Питфоллы точки входа
- Не пересказывать версии/статусы по памяти (устареют за день)
- Критерий «наш»: привязка к ТУТУ/Сашиной работе
- На вопрос «а можешь X?» — конкретный ответ через шаги 1-4

---

## Принципы (обязательны для всех инструментов)

1. **Минимум файлов на единицу данных** — количество файлов определяется ценностью, не полнотой.
2. **Идемпотентность через `_registry.json`** — не качать повторно уже загруженное.
3. **Никакой постобработки** — зона следующих инструментов конвейера.
4. **Минимальная статусная машина:** `pending` / `completed` / `error`.
5. **`_registry.md`** — рендерится из JSON через Jinja2, без доп. запросов к API.
6. **TG-алерты только при ручном запуске** с ошибкой. Cron — тишина, всё в `_log.md`.
7. **Атомарная запись:** `tmp + os.replace` для файлов и реестра.
8. **Разработка и ТЗ — только через Opus** (`delegate_task model=claude-opus-4-7` или cronjob).

## Структура инструмента

```
MoveFrom<Service>/
├── movefrom<service>/
│   ├── __main__.py      ← CLI: preflight → ping → skip-or-download → finalize
│   ├── config.py        ← pydantic Settings (НЕ модульные os.getenv!)
│   ├── client.py        ← API клиент (requests + tenacity retry)
│   ├── schema.py        ← Pydantic модели
│   ├── writer.py        ← атомарная запись
│   ├── renderer.py      ← _registry.md из JSON через Jinja2
│   ├── registry.py      ← _registry.json: load/save, portalocker
│   ├── lock.py          ← portalocker single-instance guard
│   ├── logger.py        ← _log.md + jsonl events
│   ├── tg.py            ← TG-алерты (только manual)
│   └── templates/
├── tests/
├── .env
└── .venv/
```

**Коды выхода CLI:** `0` успех / `1` частичный / `2` lock/preflight / `3` сервис/auth / `4` фатально.

⚠️ Exit code 1 НЕ всегда «нет новых» — проверять содержимое вывода на `Traceback`/`Error`/`Exception`.

**Режимы:** `--mode test` (5 дней), `--mode cron` (новые), `--mode manual --from-date --to-date`.

## Приоритеты и цели

**Цели департамента Аналитики и данных (ТУТУ)** — Jira OKRAID, проекты — OKRS.

**Приоритет инструментов:**
1. **MoveFromExchange (contacts/GAL)** — эталонный справочник людей (email = ключ)
2. **MoveFromJira (OKRAID + OKRS)** — цели и проекты
3. **Быстрая постановка задачи через TG** — после п.1 и п.2

## Железное правило публикации

Система **никогда не публикует автономно** в Jira, мессенджеры и публичные каналы. Только: нашла → TG → пользователь подтверждает → публикация.

## Резолвер сущностей

**Три состояния:** `resolved` (точное совпадение), `ambiguous` (суффикс `(?)`), `unknown` (сырой текст).

**Главное: не угадывать.** Лучше пропустить чем соврать.

**Ключи:** контакт → `email` (Exchange GAL); проект → `canonical_name` + `aliases`.

## Корпоративные credentials

Единая учётка `lavrina@tutu.ru` для Confluence, Jira, Exchange, Zulip. **Хранить как PAT, не пароль.**

В `.env` каждого проекта:
```
TUTU_USERNAME=lavrina@tutu.ru
TUTU_TOKEN=<personal_access_token>
TUTU_BASE_URL=https://dom.tutu.ru
```

## Правила разработки

- **ТЗ пишет и правит только Opus** (cronjob). Даже мелкие правки. Haiku — недопустим.
- **После правки ТЗ — Opus проверяет все смежные ТЗ** на непротиворечивость.
- **Код пишет Sonnet** по плану Opus. Финальная проверка — Haiku (читает код и ТЗ).
- **Разработку запускать ТОЛЬКО по ТЗ и ТОЛЬКО после «берём в работу» от Саши.**
- **«Только читать / диагностика» — явно запрещать мутации в промпте субагента.**
- **`--dry-run` — проверять smoke-тестом перед боевым прогоном.**
- **Делегирование Opus длинных задач — через cronjob, не delegate_task.**

## Стиль работы с Сашей

Диалог с уточняющими вопросами — по одному. **Варианты только цифрами 1/2/3**, не A/B/C.

**Рекомендации по двум критериям:** скорость поиска (сколько шагов агенту) и сложность поддержки (устареет ли без сопровождения).

## Связанные файлы

- `references/tools-reference.md` — специфичные секции по каждому инструменту (MoveFromFF, AnywhereContacts, MOFS, PFS, TaskRefresh, EntityRegistry, …)
- `references/tools-status.md` — таблица статусов всех инструментов с версиями и кронами
- `references/pitfalls.md` — общие питфоллы всех инструментов
- `references/movefromff-api-fields.md` — карта Fireflies GraphQL API
- `references/anywhere-contacts-architecture.md` — архитектура AnywhereContacts
- `references/loop-mattermost-api.md` — Loop/Mattermost API
- `references/tutu-corporate-integrations.md` — auth-паттерны сервисов ТУТУ
- `references/qa-verification-checklist.md` — чек-лист QA против ТЗ

## Verification Checklist

- [ ] Инструмент следует всем 8 принципам
- [ ] CLI поддерживает три режима и коды выхода 0–4
- [ ] Конфиги — pydantic Settings, не модульные os.getenv
- [ ] Атомарная запись через tmp + os.replace, portalocker lock
- [ ] Если пишет контакты — AnywhereContacts.store, mask_contact перед выводом
- [ ] Если пишет в WorkVault — триггер owncloud-sync.service после синка
- [ ] TG-алерты только при --mode manual с ошибкой; cron молчит
- [ ] Актуальное ТЗ в TZ/<Tool>/<Tool>_TZ.md и MAIN_TZ_INVENTORY.md
- [ ] Разработка запущена только после «берём в работу» от Саши
- [ ] Перед реализацией — живой запрос к API (схема совпала с ТЗ)
- [ ] Кастомные поля не перезаписываются коннектором