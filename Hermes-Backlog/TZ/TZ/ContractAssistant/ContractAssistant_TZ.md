---
tool: ContractAssistant
version: 0.3.0
date: 2026-09-08
status: draft
author: architect (cursor-grok-4.6-high)
last-section-added: 2026-09-08 — v0.3.0 решение Саши вариант 2: два своих крона, запрет встраивания в mfl_*
depends_on:
  - MoveFromLoop
  - ExchangeMonitor
  - OKRTool
  - tutu-jira-contract-approval
  - MofsIndex
  - workvault-rag
  - EntityRegistry
  - EntityRegistryCLI
  - ConfluenceSync
  - ErrorBus
  - AnywhereContacts
  - LoopChannelDigest
  - EntitiesMigration
---

# ContractAssistant — ТЗ

Автоматизация знаний и ответов по договорам ТУТУ. Реализация кода **запрещена** до явного «берём в работу». Кроны **не создавать** до «ставь кроны».

## Приложения к ТЗ

Пока нет. Справочные таблицы брифа (если появятся) — `TZ/ContractAssistant/appendix_<тема>_YYYYMMDD.md`.

---

## 1. Цель

Хранить канонические факты по договорам ТУТУ в `WorkVault/Entities/Contracts/` и готовить ответы на вопросы из комментариев JIRA, Loop и почты **только из этих фактов**; если факта нет или источники противоречат — эскалировать Саше, ничего не выдумывая. **Никакой ответ наружу (JIRA, Loop, другие мессенджеры, почта) — без прямого явного OK Саши** (проект ответа + обоснование → Messages → OK → пост в место вопроса; см. §8).

---

## 2. Контекст и проблема

Саша ведёт договорную деятельность ТУТУ: заявки АДД → MIX/TOMAKE (`hq.tutu.ru`), переписка в Loop (`loop.tutu.ru`), почта Exchange (`cas.tutu.ru`), регламенты и выбор поставщика в Confluence, учёт закупок в Excel/Confluence.

Факты сейчас размазаны по комментариям JIRA, DM Loop, КП PDF и страницам Confluence. Типичный сбой (живой прецедент ADD-630106 / MIX-2162, Qlever): в заявке ошибочно указана «закупочная комиссия», хотя сумма 1 411 200 ₽ попадает в коридор 500к–5млн, где комиссии нет — достаточно владельца бюджета + ГД юрлица. Ответ есть в регламенте и в правке Зарубиной, но его приходится каждый раз собирать руками.

Черновик `Entities/Contracts/` **легитимен**: создан по явной постановке Саши 08.09.2026 (R3 соблюдён). Это **не стандарт**, а прототип (карточка, Rules, один агрегат `dwh-agent-qlever`): нет журнала Q&A, нет watch-списка JIRA/Loop, `kind: contract` не входит в enum EntityRegistry, PDF КП в рабочем дереве на момент ТЗ не найден (в агрегате указан `kp-qlever-2606-11.pdf`, источник истины — вложение ADD-630106). Приведение прототипа к H2 §6.4 — только после «берём в работу» (§12 шаг 1).

Нужен инструмент, который: (1) фиксирует стандарт агрегата; (2) следит за вопросами по уже известным договорам; (3) готовит ответ цитатой из агрегата/регламента либо эскалирует — пост наружу только после OK Саши.

---

## 3. Что делаем (Scope) vs Что НЕ трогаем (Non-goals)

### Scope (v0.1)

- Канон структуры `Entities/Contracts/` и шаблон файла-агрегата (см. §6).
- USERTOOL `~/USERTOOLS/ContractAssistant/` + тонкий скилл `productivity/contract-assistant` (в v0.1 обе сущности, Q7; **скилл — отдельная согласуемая сущность** перед `HF:impl`).
- Мониторинг вопросов: комментарии JIRA по watch-ключам из агрегатов; Loop — **только** DM-allowlist + @упоминания с матчем slug/ключ (Q4). Keyword-без-mention «догон» в digest — в том же множестве каналов/DM, не по произвольным каналам.
- Почта Exchange — **триггер идентификации** «вопрос или изменение» (Q5): вопрос → схема ответов §8; не вопрос → уведомление без отправки.
- Пост наружу (JIRA comment / Loop / почта / мессенджеры) **только после явного OK Саши**. `auto_post: false` глобально, `auto_post_slugs: []` — даже `true` не обходит второй рубеж (OK Саши). См. §8.
- Эскалация неизвестного/спорного в Telegram (топик Messages `-1004300127777:6556`).
- Append-only журнал Q&A в агрегате.
- On-demand CLI/скилл: «какой ИНН у Qlever?», «нужна ли комиссия при 1.4 млн?».
- Обновление `Rules/*.md` через существующий `confluencesync pull` известных pageId (не новый коннектор Confluence).
- Ошибки — в ErrorBus (`report_error.sh --tool ContractAssistant`).

### Non-goals

- Создание заявок АДД/TOMAKE — зона скилла `tutu-jira-contract-approval`. Не дублировать бриф полей requestType 232.
- Снимки Jira-проектов — зона `MoveFromJira` (комментарии он **не** тянет; расширять его этим ТЗ нельзя).
- Срочный/дайджест Loop и Exchange в Telegram — зона `MoveFromLoop` / `ExchangeMonitor`. **Запрет встраивания CA в `mfl_urgent_check.py` / `mfl_digest.py`** (паттерн ExchangeMonitor сюда **не** копировать). **Запрет общего** `watermark.json` / `loop_rules.yaml` с MFL. Job `f61b26cbbdf5` / `2865cc674493` и их скрипты **не трогать**. Почему — §4.1 и §7: другой жизненный цикл (лишний источник JIRA, свой `jira_last_ts`, окно пн–пт 8–20, classify, пост только по OK); аналогия LoopChannelDigest Q1 (похожий источник ≠ общий процесс). Hermes отдаёт stdout после exit — любой CA-вызов внутри `mfl_*` задержит срочные Loop (SLO MFL «<30с»). CA — **два своих крона** (urgent со сдвигом + digest), спека §7; в `jobs.json` — только после «ставь кроны».
- On-demand дайджест произвольного канала Loop — зона `LoopChannelDigest` (можно **вызывать** CLI, не форкать клиент).
- Синхронизация Excel-базы закупок и полный реестр портала закупок.
- Автоответ внешнему поставщику; оглашение бюджета закупки поставщику (запрет регламента).
- Правка полей JIRA (комиссия, суммы, КБК) — комментарий только после OK Саши; смена полей — руками Саши или отдельная доработка.
- Подписание/ЭДО/Диадок/СБИС как интеграции.
- Новый `kind: contract` в `entities.schema.json` в v0.1 (enum сейчас: `project|one_on_one|multisync|sync_aid|unknown|tool|person_1on1|person|misc`). Детей договоров в `entities.json` **не заносим** — только файлы под зонтиком; зонтик `Contracts` (`kind: project`) остаётся (Q2).
- Новый `doc_type` в MofsIndex в v0.1 (индекс ТЗ = `tz`/`impl_plan`/`protocol`). Поиск по договорам — чтение файлов агрегата; расширение MofsIndex — отдельный CHANGE.
- Перенос `Entities/trisigma/contract_vendor.md` (договор Авито/Trisigma) в `Contracts/` без отдельной команды.
- Кроны в `jobs.json` — только перечень в §7; постановка после «ставь кроны».
- Запись в `EcosystemManifest.json` на этапе реализации — только фаза `ORCH:shared-state`, не исполнитель. Детей договоров в `entities.json` не писать (Q2).
- Сканирование произвольных каналов Loop по ключу договора — не в v0.1 (контур Q4).

---

## 4. Архитектура / место в экосистеме

Два слоя, как у `LoopChannelDigest`: детерминированный CLI (опрос, матчинг, цитаты, пост) + тонкий скилл (триггеры, формат ответа, запрет выдумывать).

```
JIRA comments / Loop posts / Exchange mail
        │  poll (own watermark; empty tick → всё равно двигать)
        ▼
ca_watch.py (no_agent, один процесс)
  watch → inbox.jsonl → match/retrieve/classify → проект в stdout
  БЕЗ --apply / БЕЗ --sasha-ok
        │
        ├── крон deliver → Messages :6556 (проект + обоснование)
        └── пост наружу ТОЛЬКО интерактивно:
            скилл `ca post --apply --sasha-ok` после явной фразы Саши
            (auto_post=false + auto_post_slugs=[] в v0.1;
             даже true не обходит гейт OK)
        │
        ▼
append Q&A в агрегат   +   ErrorBus при сбое (fail-quiet, exit 0)
```

Интерактивный путь (сессия Сирени): скилл вызывает `ca ask "..."` (здесь агент/LLM допустим) по тем же retrieve/classify, ответ в чат Саше; пост в JIRA/Loop/почту — только `ca post --apply --sasha-ok` после явного «отправь» / OK. Отдельный agent-job `ca_answer` — **не в v0.1**.

Код: `~/USERTOOLS/ContractAssistant/`. Скилл: `~/hermes-workspace/skills/productivity/contract-assistant/` (после согласования). Данные: только vault `Entities/Contracts/` + `~/USERTOOLS/ContractAssistant/state/` и `contract_rules.yaml`.

### 4.1 Связи с существующими инструментами

| Инструмент / скилл | Связь | Что reuse | Чего не делать |
|---|---|---|---|
| `tutu-jira-contract-approval` | знания полей ADD→MIX, КБК, ЭДО, ЮЛ | справочник fieldId, путь АДД 232 | не создавать задачи |
| `tutu-confluence-jira` | JIRA Bearer, curl к `hq.tutu.ru` | паттерн auth из `anthropic/.env` | не патчить Confluence storage |
| OKRTool `okrtool/jira.py` | `comment_issue`, GET issue | **паттерн** POST `/rest/api/2/issue/{key}/comment` | не импортировать пакет OKRTool (связность) |
| MoveFromJira | JIRA API | ничего по комментариям (их нет в scope MFJ) | не расширять `jira_snapshot.json` |
| MoveFromLoop `loop_api.py` | Loop v4, curl+subprocess, `since` в мс | **паттерн** клиента; `mention_count>0` | **не** встраивать CA в `mfl_urgent_check.py` / `mfl_digest.py`; не общий `watermark.json` / `loop_rules.yaml`; не `requests`; не сканировать произвольные каналы по ключу; job `f61b26cbbdf5` / `2865cc674493` не трогать |
| LoopChannelDigest | дайджест канала | CLI on-demand для ingest переписки в агрегат | не крон LCD. **Прецедент Q1 LCD:** похожий источник Loop ≠ общий процесс с MFL — тот же аргумент для CA vs MFL/Exchange |
| ExchangeMonitor | Inbox EWS | `exchangemonitor.fetcher` + `person_checker` **импортом пакета** (чтение писем). Встраивание EM в `mfl_*` — **не образец для CA** | не `loop_rules.yaml`; не хук в mfl-скрипты; не общий watermark |
| workvault-rag / MofsIndex | поиск | `search_docs` для вопросов «что в ТЗ/протоколе»; договоры v0.1 — файлы `Entities/Contracts/**/*.md` | не новый `doc_type` без CHANGE MofsIndex |
| ConfluenceSync | Rules | `confluencesync pull <pageId> --to-file` для 338627217 и 331126580 | не писать в Confluence |
| EntityRegistry / CLI | реестр | зонтик `Contracts` (`kind: project`) остаётся; детей договоров в `entities.json` **не заносим** (Q2) — только файлы под зонтиком | не `kind: contract`; не записи детей |
| AnywhereContacts | люди | резолв zarubina/sivets/agababyan/aralov по `login` | не новый коннектор контактов |
| ErrorBus | ошибки | `report_error.sh --tool ContractAssistant` Mode A | не слать бизнес-эскалации в Errors `:11112` |
| EntitiesMigration / workvault-entities | layout | slug латиница; исключение зонтика — §6 | не плоские `Entities/<slug>/` для каждого договора в v0.1 |

**Почему CA не встраивается в `mfl_*` (вариант 2, решение Саши 08.09.2026).** ContractAssistant — другой жизненный цикл, чем MFL/ExchangeMonitor: (1) лишний источник JIRA-комментариев, которого у MFL нет; (2) свой watermark с ключом `jira_last_ts` (и `loop_last_ts` / `exchange_last_ts` в своём файле); (3) окно только пн–пт 8–20, тогда как MFL urgent круглосуточный `*/3`; (4) classify (эвристика; LLM опционален) и проект ответа; (5) пост наружу только после OK Саши. Аналогия — LoopChannelDigest Q1: похожий источник (Loop) ≠ общий процесс. **Причина таймаута:** Hermes отдаёт stdout в `deliver` только после exit процесса; любой вызов CA внутри `mfl_urgent_check.py` / `mfl_digest.py` удлинит тик срочных Loop и сорвёт SLO MFL «<30с». Поэтому CA имеет **два своих крона** (urgent со сдвигом `1-59/3` + digest со сдвигом `:05`), а не хук в `mfl_*`.

### 4.2 Связи с инфраструктурой Hermes

- Креды JIRA: `JIRA_TOKEN`, `JIRA_BASE_URL=https://hq.tutu.ru` — `~/.hermes/profiles/anthropic/.env` (не `source ~/.config/hermes/.env` — спецсимволы пароля ломают bash).
- Loop: `LOOP_TOKEN` (PAT Bearer), тот же anthropic `.env`. HTTP только `curl` через subprocess (`requests` на `loop.tutu.ru` зависает).
- Exchange: `TUTU_DOMAIN_PASSWORD` в `~/.config/hermes/.env`, читать grep/cut, не `source`. Пакет `exchangemonitor` (system Python 3.11 / тот же интерпретатор, что MFL).
- Confluence: `CONFLUENCE_TOKEN` из `~/USERTOOLS/ConfluenceSync/.env`, точечная загрузка переменных (не `source` всего файла).
- Telegram эскалации: `deliver` в Messages `:6556`. Техсбои: ErrorBus `:11112`.
- Entry-скрипты кронов копировать в `~/.hermes/scripts/` с хардкодом `_ROOT=/home/tkachenkoav/USERTOOLS/ContractAssistant` (урок MFL: `Path(__file__).parent` из scripts/ указывает на `~/.hermes/`). Копии: `ca_watch.py` (оба режима). MFL-скрипты `mfl_urgent_check.py` / `mfl_digest.py` **не** править и не копировать CA внутрь них.
- Кроны CA — **спека в §7**, не записи в `jobs.json` до «ставь кроны». Сдвиг urgent `1-59/3` — чтобы не бить Loop/EWS в ту же секунду, что `f61b26cbbdf5`; digest `:05` — чтобы не совпасть с `2865cc674493` в `:00`.
- Манифест экосистемы — после реализации, фаза `ORCH:shared-state`. До «берём в работу» манифест не трогать.
- Gateway не рестартовать.

---

## 5. Функциональные блоки

Раскладка (план, не код):

```
USERTOOLS/ContractAssistant/
  contractassistant/
    config.py          # пути vault, creds, auto_post + auto_post_slugs
    rules.py           # contract_rules.yaml
    registry.py        # сканер Entities/Contracts → watch keys/slugs
    state.py           # watermark + seen_ids TTL 48ч + inbox.jsonl (flock, os.replace)
    jira_client.py     # curl/urllib: GET comments, POST comment; Bearer
    loop_client.py     # curl subprocess, паттерн MFL, НЕ requests; контур Q4
    exchange_watch.py  # import exchangemonitor.fetcher
    match.py           # event → slug (JIRA key, ИНН, имя контрагента, slug)
    retrieve.py        # чтение агрегата + Rules, нарезка секций
    classify.py        # known/partial/unknown + обязательная цитата
    answer.py          # текст ответа (без эмодзи)
    post_jira.py / post_loop.py
    escalate.py        # stdout карточки для TG
    journal.py         # append Q&A; flock или атомарный os.replace/temp-file (как state.py) — urgent/digest не гоняются на одном slug
    watch.py           # независимый poll JIRA/Loop/Exchange; свой watermark ВСЕГДА (пустой тик — тоже двигать)
    ask.py             # CLI вопрос (интерактив; агент/LLM допустим)
  scripts/ca_watch.py  # оркестрация watch→answer; БЕЗ --apply/--sasha-ok; окно 8–20 как защита
  scripts/ca_post.py   # только интерактив / скилл `ca post --apply --sasha-ok` (не крон)
  tests/
  contract_rules.yaml
  state/
  pyproject.toml
```

| Блок | Вход | Выход | LLM? |
|---|---|---|---|
| Registry | `Entities/Contracts/**/*.md` frontmatter | список `{slug, jira_keys[], loop_users[], keywords[]}` | нет |
| Watch JIRA | ключи + watermark | события `source=jira` | нет |
| Watch Loop | mention_count + DM allowlist; digest keyword-без-mention только в том же контуре (Q4) | события `source=loop` | нет |
| Watch Exchange | письма since watermark, фильтр людей/ключей | события `source=exchange` | нет |
| Match | событие + registry | `slug` или `unmatched` | нет (ключи/slug); LLM только fallback, результат `unmatched` если не уверен |
| Retrieve | slug | секции агрегата + Rules | нет |
| Classify | вопрос + секции | `known` + quote_path / `partial` / `unknown` | **v0.1 крон: эвристика** (keyword/H2/`?`); LLM **опционален**, из крона `no_agent` **не** вызывается. Интерактивный `ca ask` может использовать LLM сессии. **Запрет ответа без quote_path** для `known` |
| Post / Escalate | classify | карточка Messages (проект+обоснование); POST только `ca post --apply --sasha-ok` после OK Саши; крон **никогда** не ставит `--sasha-ok` | нет |
| Journal | Q + A + source | секция «Журнал Q&A» | нет |
| Ask CLI | текст вопроса | тот же classify в stdout | да (интерактив), с цитатой |

Инвариант classify: нет пути вида «модель вспомнила сумму без заголовка секции файла» → всегда `unknown`.

---

## 6. Схема данных

### 6.1 Разбор черновика (AS-IS 2026-09-08)

Что оставить:

- Зонтик `Entities/Contracts/` + карточка `Contracts.md`.
- `Rules/` для нормативных выжимок (не сырой дамп Confluence).
- Один файл-агрегат на договор: все факты в одном `.md` (прецедент `dwh-agent-qlever.md` — удачный).
- Wikilink на Rules из агрегата; таблица сравнения поставщиков; блок «открытые вопросы»; список URL источников.
- Люди зонтика: Зарубина (закупки), Сивец (владелец процесса), комиссия ср 11:00.

Что доработать в стандарт:

- Журнал Q&A как **обязательная** секция (в черновике только обещание в конце файла).
- Явный watch: JIRA keys, Loop username, keywords — в frontmatter, не только в прозе.
- Статус договора (`selection|approval|signed|active|closed`).
- `schema_version` агрегата.
- Артефакты (PDF/DOCX) в `artifacts/`, не вперемешку с md.
- Frontmatter `kind: contract` **не писать в entities.json** в v0.1 — сломает схему. В агрегате поле `record_type: contract` (локальный дискриминатор).
- Вложенность `Entities/Contracts/<slug>/` — исключение из «одна сущность = `Entities/<slug>/`» (`workvault-entities`). Осознанно: зонтик каталога, дети не маршрутизируются PFS. Детей в `entities.json` **не заносим** — только файлы под зонтиком; зонтик `Contracts` (`kind: project`) остаётся (Q2/Q3).
- ПДн: `Entities/*` в whitelist PIIScan → агрегаты вне скана. **Решение:** минимизация полей. Храним: ИНН, юрлицо, суммы. **Не** храним в агрегатах: телефоны, паспорта, иные удостоверения. В ответ наружу — только поля по вопросу и только после OK Саши.
- PDF КП: если файла нет на диске — качать из JIRA attachment при ingest, класть в `artifacts/`.

Не смешивать с `Entities/trisigma/contract_vendor.md` (другой жизненный цикл, уже внутри проекта).

### 6.2 Целевой layout

```
WorkVault/Entities/Contracts/
  Contracts.md                 # зонтик: люди, индекс активных, ссылка на Rules
  Rules/
    purchase-rules.md          # pageId 338627217
    purchase-portal.md         # pageId 331126580
    _sources.yaml              # pageId → filename для pull
  <slug>/                      # латиница, без дефисов в новых slug
    <slug>.md                  # КАНОН фактов
    artifacts/                 # КП PDF, BIF xlsx, уставные
```

Новый договор: папка + агрегат по шаблону + строка в `Contracts.md`. Запись ребёнка в `entities.json` — **не делаем** (Q2). Зонтик `Contracts` уже в реестре. На `ORCH:shared-state` — манифест/digest, не дети реестра.

### 6.3 Frontmatter агрегата (`schema_version: "1.0"`)

Обязательные:

| Поле | Смысл | Пример |
|---|---|---|
| `title` | отображаемое имя | DWH + агентный контур (Qlever) |
| `slug` | = имя папки | `dwh-agent-qlever` |
| `record_type` | всегда `contract` | `contract` |
| `parent` | зонтик | `Contracts` |
| `status` | жизненный цикл | `approval` |
| `schema_version` | формат агрегата | `"1.0"` |
| `jira_keys` | watch JIRA | `[ADD-630106, MIX-2162]` |
| `legal_entity` | ЮЛ наше | `НТТ` |
| `counterparty` | имя | `Qlever` |
| `amount_ex_vat` | число, ₽ | `1411200` |
| `currency` | | `RUB` |

Рекомендуемые: `inn`, `jira_add`, `jira_mix`, `source_kp`, `loop_users` (username), `watch_keywords`, `kbk`, `edo`, `roles` ( holdee / payer / customer / owner / procurement ) логинами AnywhereContacts. Телефоны, паспорта, удостоверения — **не** поля агрегата (§6.1 ПДн).

`kind` в смысле EntityRegistry в этом файле не дублировать. Карточка зонтика `Contracts.md` сохраняет `kind: project` как сейчас в `entities.json`.

### 6.4 Обязательные H2 агрегата

1. Задачи JIRA (ключи, URL, вложения)
2. Контрагент
3. Суммы и сроки
4. ЮЛ и роли
5. Закупочная процедура (комиссия / выбор партнёра / ед. поставщик + ссылка на Rules)
6. Выбор поставщика (таблица)
7. Предмет / состав работ
8. Открытые вопросы (не закрыты источниками)
9. Журнал Q&A (append-only, см. ниже)
10. Переписка (хронология, сжато)
11. Источники (URL/pageId/JIRA/PDF)

Журнал Q&A — фиксированный формат записи:

```
### YYYY-MM-DD HH:MM MSK · source=jira|loop|exchange|ask · id=<external_id>
- Q: …
- A: … | unknown
- cite: `Entities/Contracts/<slug>/<slug>.md` §<H2>
- action: posted|escalated|dry-run|notify
```

### 6.5 `contract_rules.yaml` (инструмент, не vault)

```yaml
schema_version: "1.0"
auto_post: false          # глобальный дефолт; в v0.1 не включать
auto_post_slugs: []       # allowlist slug; пуст в v0.1 — ни один slug не постится по флагу
# Второй рубеж: даже при auto_post true пост наружу только после явного OK Саши (§8)
my_jira_user: tkachenkoav
my_loop_username: tkachenkoav
contract_urgent_users:    # Loop username + email для Exchange
  - zarubina
  - sivets
escalation_telegram: "telegram:-1004300127777:6556"
poll_lookback_minutes: 15
```

Watch-ключи **не** дублировать здесь, если они уже в frontmatter агрегатов; rules — политика, registry — факты.

### 6.6 State

`~/USERTOOLS/ContractAssistant/state/watermark.json`: `jira_last_ts`, `loop_last_ts`, `exchange_last_ts` — **int миллисекунды**, как MFL. `seen_ids: [{id, ts}]` TTL 48ч. Первые значения: now−10 мин (urgent-тик), не 0.

Свой файл. Ключи MFL не трогать. **Пустой успешный тик (нет новых событий) — watermark всё равно двигать**, иначе вечный lookback. При полном отказе источника (JIRA/Loop/EWS) — этот ключ **не** двигать, fail-quiet + ErrorBus; остальные источники того же тика отрабатывают независимо.

---

## 7. Триггеры мониторинга

Решение Саши 08.09.2026 — **вариант 2:** ContractAssistant имеет **два своих крона** (urgent со сдвигом + digest) с тем же рисунком расписания, что MFL. Job MFL `f61b26cbbdf5` / `2865cc674493` и скрипты `mfl_urgent_check.py` / `mfl_digest.py` **не трогать**. Встраивание в `mfl_*` как ExchangeMonitor — **запрещено** (почему — §3 Non-goals, §4.1).

Ночью и в выходные проекты ответов **не** генерируются: это **expr крона**, не runtime-gate как основной механизм. Окно 8–20 пн–пт **продублировать** в `ca_watch.py` как защиту (если job когда-нибудь поставят 24/7): вне окна — `exit 0` без poll, без сдвига watermark, без проекта. Вне окна **не** опрашивать источники: иначе ночной тик мог бы пометить события seen без карточки.

Оба job — `no_agent`, один скрипт `ca_watch.py` (watch→answer склеены). `ca_answer` как отдельный agent-job — **не в v0.1**. Крон **никогда** не ставит `--apply` / `--sasha-ok`. Classify в кроне — эвристика.

**Спека job (НЕ создавать в `jobs.json` до «ставь кроны»):**

| Job (спека) | expr | Сдвиг vs MFL | script | no_agent | deliver |
|---|---|---|---|---|---|
| CA urgent | `1-59/3 8-20 * * 1-5` | минуты `1,4,7,…` vs `f61b26cbbdf5` (`*/3` = `0,3,6,…` 24/7) — не бить Loop/EWS в ту же секунду | `ca_watch.py` (режим urgent, без `--apply`/`--sasha-ok`) | true | `telegram:-1004300127777:6556` |
| CA digest | `5 8-20 * * 1-5` | рисунок как MFL `0 8-20 * * 1-5`, минута `:05` — не совпасть с `2865cc674493` в `:00` | `ca_watch.py --mode digest` (без `--apply`/`--sasha-ok`) | true | `telegram:-1004300127777:6556` |
| ask / post | on-demand | — | скилл: `ca ask`; пост — `ca post --apply --sasha-ok` после явной фразы Саши | агент только у интерактивного `ca ask` | чат сессии / Messages |

Имена job при постановке (после «ставь кроны»): `ContractAssistant — urgent`, `ContractAssistant — digest`. Копии entry в `~/.hermes/scripts/` с `_ROOT=/home/tkachenkoav/USERTOOLS/ContractAssistant`.

| Режим | Источники | Поведение |
|---|---|---|
| urgent | JIRA comments по `jira_keys`; Loop: DM-allowlist + @упоминания с матчем slug/ключ (Q4); Exchange от тех же людей или body содержит `jira_keys` | один процесс `ca_watch.py`: watch→inbox→classify (эвристика)→проект в stdout для deliver. **Не** пост |
| digest | те же источники. Keyword-без-mention «догон» (прочитано с телефона, `mention_count=0`) — **только в том же множестве каналов/DM**, что mention-контур. Сканирование произвольных каналов команды по ключу — **не в v0.1** | то же, `--mode digest` |
| ask | нет poll | CLI/скилл, интерактив |
| post | после OK | только скилл `ca post --apply --sasha-ok`, не крон |

JIRA: `GET /rest/api/2/issue/{key}/comment` + `GET /rest/api/2/issue/{key}?fields=updated,comment`. Watermark по `created` комментария. Пропуск: автор = `my_jira_user`; пустой body. Падение JIRA — свой try/except → ErrorBus `--tool ContractAssistant`, `exit 0`; на MFL **не** влияет (отдельный процесс).

Loop: `GET /api/v4/users/me/teams/{team_id}/channels/members` → `mention_count>0` (team `b1mrmr41dtrhbgk3a9qa7bxhqe`); плюс DM с allowlist. Контур v0.1 (Q4): **только** эти DM и посты с @упоминанием, где матчится slug/`jira_keys`. `GET .../posts?since={ms}`. `since` — 13 цифр мс. Пропуск: `type!=""`, `delete_at!=0`, свои посты. Digest-догон без mention — не шире этого множества каналов/DM.

Exchange: `fetch_inbox_since` из ExchangeMonitor; фильтр: sender login ∈ `contract_urgent_users` **или** keyword = любой `jira_keys` / URL `hq.tutu.ru/browse/...`. Письмо — триггер идентификации «вопрос или изменение» (Q5). Вопрос (кому-либо, по договору) → схема §8 (проект + обоснование + OK Саши → пост в место вопроса). Не вопрос → уведомление в Messages, без отправки. Не менять `is_read`. SMTP/EWS без явного OK Саши — запрещён.

Не-вопрос (ack / изменение без вопроса) — не тишина: уведомление в Messages, без отправки наружу (Q5, схема §8). Эвристика вопроса — там же.

`watch.py`: независимый poll JIRA / Loop / Exchange; свой watermark **всегда** (пустой успешный тик — двигать, иначе вечный lookback). Отказ одного источника не блокирует остальные.

Кроны в отчёте реализации перечислить; в `jobs.json` **не** создавать без «ставь кроны».

---

## 8. Логика ответа (проект → OK Саши → пост)

**Инвариант (глобально, все каналы, v0.1 и далее пока не снято):** никакой ответ наружу — JIRA comment, Loop post, другие мессенджеры, SMTP/EWS — без прямого явного указания Саши. СА всегда: (1) готовит **проект ответа + обоснование** («почему такой ответ», с `cite`); (2) шлёт карточку в топик Messages `:6556` (крон `ca_watch.py` — только этот шаг); (3) ждёт явного OK; (4) только тогда постит в место вопроса. Интерактивный «отправь» в сессии = тот же OK.

**OK только интерактивно.** Крон **никогда** не ставит `--sasha-ok` и `--apply`. POST в JIRA/Loop — только скилл `ca post --apply --sasha-ok` после явной фразы Саши. `ca_answer` как отдельный agent-job — **не в v0.1**. В v0.1 classify в кроне — эвристика (LLM опционален, из `no_agent` не вызывается); watch+answer склеены в один `no_agent` процесс `ca_watch.py`. Агент оставить интерактивному `ca ask`.

Два рубежа, оба обязательны:

1. **Флаг/allowlist:** `auto_post: false` глобально, `auto_post_slugs: []`. В v0.1 прод-пост по флагу **не** осуществляется. Даже если флаг когда-либо станет `true` и slug попадёт в allowlist — это **не** снимает рубеж 2.
2. **OK Саши:** явное согласование проекта. Без него POST/SMTP не вызываются. Крон не является каналом OK.

Порядок для каждого события из inbox (идемпотентность по `seen_ids`):

1. Дедуп `source+external_id`.
2. Match → slug; нет slug → эскалация `unmatched` (возможен новый договор — не создавать папку без команды Саши).
3. Классификация события:
   - **вопрос** (кому-либо, по договору) → дальше retrieve/classify и схема проекта.
   - **не вопрос** (ack «ок», «принял»; изменение без вопроса) → mark seen, **уведомление** в Messages без проекта отправки наружу (Q5). Эвристика вопроса: есть `?` или глаголы запроса (нужно/уточни/какая сумма/кто заказчик); спорные — как вопрос (эскалация проекта), не skip-тишина.
4. Retrieve секций агрегата + `Rules/purchase-rules.md` (+ portal, если вопрос про процесс/портал).
5. Classify:
   - **known** — ответ целиком следует из одной или нескольких секций, `cite` указывает H2 (и якорь таблицы, если сумма/ИНН).
   - **partial** — часть есть, часть в «Открытые вопросы» агрегата. **Эталон partial:** КБК Qlever (и смежно ЭДО, держатель бюджета) — в открытых вопросах агрегата, смежные факты (сумма, комиссия) есть; не выдумывать число КБК.
   - **unknown** — в файлах нет; **или** два источника противоречат.
6. Сборка **проекта** (ещё не пост): без эмодзи; коротко; не дублировать поля, которые спрашивающий уже видит в форме JIRA, если вопрос не про их ошибочность; при коррекции ошибки (комиссия) — порог из Rules + сумма из агрегата. Плюс **обоснование**: почему `known`/`partial`/`unknown`, на каких секциях стоит ответ, чего не хватает.
7. Доставка **до OK** — только эскалация (все classify, все source включая exchange-вопрос):
   - Карточка в Messages с проектом + обоснованием. Никакого POST/SMTP.
   - `auto_post` / `auto_post_slugs` в v0.1 не открывают пост.
8. **После явного OK Саши** — пост в место вопроса **только** через скилл/CLI `ca post --apply --sasha-ok` (не крон): source=jira → POST comment в **тот же** issue; source=loop → `POST /api/v4/posts` в тот же `channel_id`, `root_id` треда; source=exchange → только если OK явно указывает канал (JIRA/Loop/письмо); иначе остаётся уведомление. Без обоих флагов — POST не вызывается.
9. Journal всегда (включая dry-run, unknown, notify).
10. Эскалация: карточка в Messages:

```
📋 ContractAssistant · <slug> · known|partial|unknown|unmatched|notify
Q: …
Проект: … | — (notify: без проекта отправки)
Обоснование: … (почему такой ответ / почему только уведомление)
cite: …
🔗 JIRA|Loop|OWA
```

Запреты ответа (и проекта `known` без cite):

- Нет `cite` → нельзя `known`.
- Не оглашать бюджет/потолок закупки, если вопрос не от внутренней роли заказчика/закупок (при сомнении — эскалация без проекта оглашения).
- Не обещать сроки подписания, если их нет в агрегате.
- Не отвечать на юр. оценку «можно ли без комиссии обойти регламент» сверх цитаты порогов — эскалация.
- Не постить наружу без явного OK Саши — ни по флагу, ни «для экономии».

Эталон known (Qlever): «Проводилась ли комиссия?» → нет; 1 411 200 ₽ ∈ [500к; 5млн]; достаточно владельца бюджета + ГД; поле в ADD — ошибка (Зарубина). Cite: агрегат §процедура + Rules §пороги. Проект + обоснование → Messages → ждать OK.

Эталон partial (Qlever): «Какой КБК?» → `partial`; КБК в «Открытых вопросах»; не подставлять число.

---

## 9. Поиск/RAG по фактам

Порядок (reuse-first, без нового эмбеддингового индекса):

1. Match slug (ключи JIRA в тексте, slug, ИНН, `counterparty`, aliases из `Contracts.md`).
2. Прочитать `<slug>.md` целиком (агрегаты целево короткие; Qlever ~120 строк).
3. Если вопрос регламентный (порог, RACI, комиссия, ед. поставщик, портал) — обязательно `Rules/purchase-rules.md` и при необходимости portal.
4. Если вопрос «что обсуждали на встрече по этому договору» — `workvault-rag` / `search_meetings` + `search_protocols` с пометкой слоя (черновик FF vs протокол Confluence). Это **дополнение**, не замена агрегата. В проект ответа наружу из встреч **не** класть без появления того же факта в агрегате (встречи = черновик) и без OK Саши.
5. Fallback grep только по `Entities/Contracts/`, не по всему vault.
6. PDF КП: в v0.1 не парсить бинарник в проекте ответа; факты из PDF заносятся в агрегат руками или командой ingest (текст из JIRA/Confluence). OCR — non-goal.

Подпись в интерактивном `ca ask`: «Из агрегата `<slug>` §…» / «Из регламента закупок (pageId 338627217)» / «Во встречах (FF, черновик) — в ответ наружу не идёт». Проект из встреч в JIRA/Loop/почту **не** класть без того же факта в агрегате и без OK Саши.

Расширение MofsIndex `doc_type=contract` — не в этом ТЗ; при росте числа договоров >20 — отдельный CHANGE.

---

## 10. Интеграции

### JIRA (`https://hq.tutu.ru`, REST v2)

- Auth: `Authorization: Bearer $JIRA_TOKEN`.
- Чтение: `GET /rest/api/2/issue/{key}/comment`, `GET /rest/api/2/issue/{key}?fields=summary,comment,attachment,updated`.
- Запись: `POST /rest/api/2/issue/{key}/comment` body `{"body": "..."}` (как OKRTool `comment_issue`) — **только после явного OK Саши** (§8).
- Не использовать `/user/search?query=` (400); picker — не нужен в v0.1.
- Не вызывать Service Desk create request.
- Вложения: download КП при ingest в `artifacts/` (`X-Atlassian-Token: no-check` на attach; для GET attachment content — штатный API).

### Loop (`https://loop.tutu.ru`, API v4)

- Auth: Bearer PAT. Логин/пароль запрещены.
- Чтение: `users/me`, `channels/members`, `posts?since=`, `channels/{id}`, `POST /users/ids`.
- Запись: `POST /api/v4/posts` `{channel_id, message, root_id?}` — **только после явного OK Саши** (§8).
- Клиент: curl subprocess, `--max-time 10`, retry 1/3/9с на 5xx/429 как MFL.
- Ссылка на пост: `https://loop.tutu.ru/tutu/pl/{post_id}`.
- `per_page=200` у members игнорируется (все каналы одним ответом) — цикл пагинации всё равно оставить.

### Exchange (`cas.tutu.ru`, EWS)

- Только чтение Inbox через существующий `exchangemonitor`.
- Три варианта username как в ExchangeMonitor.
- Watermark в мс, свои ключи.
- Автоответ SMTP/EWS без явного OK Саши — запрещён. После OK — только если Саша явно указал письмо как место ответа.

### Confluence

- `confluencesync pull 338627217` / `331126580` → обновление выжимок Rules (ручной или отдельный редкий крон — не ставить без «ставь кроны»). Оригинал остаётся в Confluence.

### Telegram

- Эскалации: Messages `:6556`.
- Ошибки: ErrorBus, не Messages.

---

## Контракты экосистемы

### Источник истины

- Владелец фактов по договору: файл-агрегат `Entities/Contracts/<slug>/<slug>.md` (`schema_version` внутри frontmatter).
- Владелец регламента: Confluence pageId 338627217 / 331126580; локальная выжимка `Entities/Contracts/Rules/` — кэш для ответов, при расхождении побеждает Confluence после pull.
- Владелец watch-политики: `contract_rules.yaml` инструмента.

### Входные контракты

| Поле | Тип | Обязательность | Источник (кто отдаёт) | Формат/enum |
|---|---|---|---|---|
| slug | str | required | файл-агрегат / registry.py | латиница, как имя папки |
| jira_keys | str | required | файл-агрегат frontmatter | ключи ADD-/MIX-/TOMAKE- через запятую в YAML-списке |
| comment.id | str | required | api_jira | id комментария |
| comment.body | str | required | api_jira | текст комментария |
| post.id | str | required | api_loop | post_id Mattermost |
| post.message | str | required | api_loop | текст поста |
| post.channel_id | str | required | api_loop | channel_id |
| item.id | str | optional | api_exchange | EwsId письма |
| login | str | optional | AnywhereContacts | login = email до "@" |
| auto_post | bool | required | contract_rules.yaml | true/false, дефолт false |
| auto_post_slugs | str | required | contract_rules.yaml | YAML-список slug; в v0.1 пуст `[]` |

### Выходные контракты

| Поле | Тип | Потребитель (кто получает) | Формат/enum |
|---|---|---|---|
| classify | enum[known,partial,unknown,unmatched,notify,skip] | post_jira / post_loop / escalate | одно значение на событие; skip = self/пусто; notify = не-вопрос без отправки |
| cite | str | журнал Q&A, эскалация | путь vault + заголовок H2 |
| jira_comment_id | str | журнал Q&A | id созданного комментария, пусто если dry-run |
| loop_post_id | str | журнал Q&A | id ответа в Loop, пусто если dry-run |
| tool | str | ErrorBus | "ContractAssistant" |
| message | str | ErrorBus | текст ошибки |

### Зависимости

- Получает от: [api_jira, api_loop, api_exchange, AnywhereContacts, ConfluenceSync, ExchangeMonitor (fetcher), EntityRegistry (umbrella Contracts)]
- Отдаёт: [api_jira (comment, только после OK Саши), api_loop (post, только после OK Саши), api_telegram (эскалация проекта), ErrorBus, WorkVault (агрегат journal)]

### Breaking changes policy

- Версионирование формата: `schema_version` в frontmatter агрегата и в `contract_rules.yaml` (не версия этого ТЗ).
- При breaking change: `migrate_vN_to_vN+1()` для агрегатов, уведомить потребителей из «Отдаёт».

### Границы («что НЕ трогать»)

- Не встраивать ContractAssistant в `mfl_urgent_check.py` / `mfl_digest.py` (паттерн ExchangeMonitor **запрещён**). Job `f61b26cbbdf5` / `2865cc674493` и их скрипты не менять. Почему: другой жизненный цикл (JIRA + свой `jira_last_ts` + окно 8–20 + classify + пост только по OK); аналогия LoopChannelDigest Q1; Hermes отдаёт stdout после exit — CA внутри `mfl_*` сорвёт SLO MFL «<30с».
- Не менять `MoveFromLoop/state/watermark.json` и `loop_rules.yaml`. Не общий watermark с MFL.
- Не менять поля issue JIRA, только comment (и только после OK Саши через `ca post --apply --sasha-ok`).
- Не писать письма в Exchange без явного OK Саши.
- Не добавлять `kind: contract` в `entities.schema.json` в рамках v0.1.
- Не заносить детей договоров в `entities.json`.
- Не двигать `Entities/trisigma/contract_vendor.md`.
- Не постить в JIRA/Loop/мессенджеры/почту без прямого явного OK Саши — даже при `auto_post: true`. Крон **никогда** не передаёт `--sasha-ok`.
- Не сканировать произвольные каналы Loop по ключу договора (v0.1).
- Не создавать job в `jobs.json` до «ставь кроны». Не ставить `ca_answer` как agent-job в v0.1.

---

## 11. Риски

| Риск | Почему | Митигация |
|---|---|---|
| Галлюцинация сумм/ИНН/комиссии в прод JIRA | LLM без цитаты | `known` только с `cite`; `auto_post: false` + пустой allowlist; **пост только после OK Саши**; тесты на эталоне Qlever |
| Двойной ответ (человек + бот) | Саша уже ответил с телефона | skip своих комментариев; `seen_ids`; не постить, если после вопроса уже есть комментарий Саши; гейт OK |
| Схлопывание с MFL seen_ids | общий watermark | свой `state/`; **не** встраивать в `mfl_*` |
| Встраивание CA в `mfl_*` (паттерн EM) | Hermes stdout после exit; SLO MFL «<30с»; другой ЖЦ (JIRA, `jira_last_ts`, 8–20, classify, OK) | два своих крона со сдвигом; job MFL не трогать (Q8) |
| Loop `requests` hang | известный питфолл | только curl subprocess |
| `mention_count=0` после прочтения в мобилке | окно ≤3 мин | digest-тик keyword-без-mention **только** в контуре Q4 (DM-allowlist + каналы mention), не по всем каналам |
| Гонка urgent↔digest на одном slug | параллельный append журнала | `journal.py`: flock или атомарный `os.replace`/temp-file, как `state.py` |
| PAT Loop/JIRA постит от имени Саши | ожидаемо, но ошибка = его имя | без OK поста нет; dry-run; короткий текст; журнал |
| Оглашение коммерции не той аудитории | регламент: бюджет не оглашать | эскалация при сомнении; контур Loop = DM/упоминание; пост только после OK |
| ПДн в агрегате vs whitelist PIIScan | `Entities/*` вне скана; ИНН/телефоны не ловятся | **Решение:** минимизация. Храним ИНН, юрлицо, суммы. **Не** храним телефоны, паспорта, удостоверения. В ответ — поля по вопросу, после OK |
| Рассинхрон Rules vs Confluence | выжимка устарела | cite + source_url; периодический pull |
| Вложенность vs EntityRegistry | дети не в корне Entities | исключение зонтика; детей в `entities.json` не заносим (Q2/Q3 закрыты) |
| Basic-auth Exchange выключат | SPOF с ExchangeMonitor | тот же риск, не чинить здесь |
| Новый договор как unmatched flood | вопросы до заведения агрегата | эскалация `unmatched`, папку не создавать; параллельный эталон (Q6) — заводить по шаблону, не ждать конца Qlever |

---

## 12. Шаги реализации (атомарные)

Каждый шаг — отдельный проверяемый кусок. Код — только после «берём в работу» и плана `HF:plan`. Кроны — только после «ставь кроны».

1. Зафиксировать шаблон агрегата и `_sources.yaml`; привести `dwh-agent-qlever.md` к H2 §6.4 **без** выдумывания новых фактов (журнал пустой). **Входит в гейт «берём в работу»:** приведение существующего агрегата и правки vault-прототипа **не** выполняются до явного «берём в работу» (не отдельно разрешённое до гейта).
2. Каркас `USERTOOLS/ContractAssistant/` + venv + `contract_rules.yaml` (`auto_post: false`, `auto_post_slugs: []`) + `state/` gitignore.
3. `registry.py`: сканер frontmatter → список watch; тест на Qlever keys ADD-630106/MIX-2162.
4. `state.py`: watermark мс, seen_ids TTL 48ч, flock, первый запуск lookback 10 мин.
5. `jira_client.py`: GET comments (мок), фильтр своих; интеграционный smoke за VPN — по флагу.
6. `loop_client.py`: curl, mentions+DM allowlist (контур Q4), фильтр type/delete/self; digest keyword не шире этого контура.
7. `exchange_watch.py`: import fetcher ExchangeMonitor, фильтр людей/ключей, без записи в MFL state; классификация вопрос vs изменение.
8. `watch.py`: независимый poll JIRA/Loop/Exchange → inbox.jsonl; свой watermark **всегда** (пустой успешный тик — двигать). Отказ источника — не двигать его ключ. `ca_watch.py --dry-run`.
9. `retrieve.py` + нарезка H2; тест: вопрос «комиссия Qlever» видит Rules+агрегат.
10. `classify.py`: **эвристика** в v0.1 (крон); эталон known комиссия Qlever; эталон **partial** КБК Qlever; запрет known без cite. LLM — опциональный модуль, из крона не вызывать.
11. `answer.py`: формат проекта без эмодзи + обоснование «почему»; лимит длины (JIRA comment ≤ 4000 символов в v0.1).
12. `post_jira.py` / `post_loop.py` + `scripts/ca_post.py`: вызываются **только** интерактивно `ca post --apply --sasha-ok` после явного OK Саши. `auto_post` + непустой allowlist **недостаточны**. Крон **не** вызывает post. Без OK — только stdout проекта.
13. `escalate.py`: карточка с проектом + обоснованием; stdout для cron deliver.
14. `journal.py`: append идемпотентный по `source+id`; **flock или атомарный os.replace/temp-file** (как `state.py`), чтобы urgent и digest не гонялись на одном slug.
15. `ca_watch.py`: оркестрация watch→answer **без** `--apply`/`--sasha-ok`; окно часов пн–пт 8–20 как защита в скрипте (вне окна — exit 0 без poll). Fail-quiet: свой try/except → `report_error.sh --tool ContractAssistant`, `exit 0`. Падение JIRA не влияет на MFL. Копия entry в `~/.hermes/scripts/` с хардкодом `_ROOT`. `ca ask` — интерактив, агент допустим. `ca_answer` как agent-job — **не делать** в v0.1.
16. Скилл `contract-assistant` (триггеры, запрет выдумки, вызов CLI; **пост только** `ca post --apply --sasha-ok` после явной фразы) — **в v0.1 вместе с CLI** (Q7); скилл — отдельная согласуемая сущность, не внедрять до согласования.
17. Тесты: ≥ эталоны Qlever known + **partial (КБК)** + unknown-без-cite, match keys, skip self, journal format, нет POST без OK; крон-путь не передаёт `--sasha-ok`; пустой тик двигает watermark; вне окна 8–20 — нет проекта; без живых POST в CI. Параллельно — тот же набор на любом новом договоре, заведённом по шаблону (Q6; не ждать окончания Qlever).
18. ErrorBus Mode A в `ca_watch.py` (и ask/post); fail-quiet крона.
19. Спека кронов §7 в README инструмента (`1-59/3 8-20 * * 1-5` и `5 8-20 * * 1-5`, `no_agent`, `ca_watch.py`). Job в `jobs.json` **не** создавать. MFL-кроны не трогать.
20. `ORCH:shared-state`: манифест, digest; зонтик `Contracts` уже в реестре — **детей не регистрировать** (Q2).
21. `mofs index docs` для этого ТЗ — **после финализации ТЗ** (шаг `tz-workflow`, не вход в импл-гейт `HF:impl`).

Новые сущности на согласование (reuse-first): скилл `contract-assistant` (в поставке v0.1, отдельное согласование); USERTOOL ContractAssistant (это ТЗ); **не** запись детей в EntityRegistry; **не** новый kind и **не** новый doc_type MofsIndex в v0.1.

---

## 13. Критерии успеха (проверяемые)

1. Файл этого ТЗ: `TZ/ContractAssistant/ContractAssistant_TZ.md`, строка в `MAIN_TZ_INVENTORY.md`.
2. После реализации (не сейчас): `ca ask "Проводилась ли закупочная комиссия по Qlever?"` → `known`, cite на агрегат+Rules, текст содержит «не проводилась» и коридор 500к–5млн; не содержит выдуманного КБК; карточка эскалации содержит **проект + обоснование**; POST нет до OK.
3. `ca ask "Какой КБК у Qlever?"` → **`partial`** (эталон partial: КБК в «Открытых вопросах» агрегата, смежные факты есть) + эскалация проекта с пробелом, **не** число КБК.
4. Watch по ADD-630106 видит новый чужой комментарий-вопрос в dry-run inbox; свой комментарий — skip.
5. При `auto_post: false` и `auto_post_slugs: []` ни один POST в JIRA/Loop/SMTP не выполняется без явного OK Саши; карточка эскалации содержит проект + обоснование для known. Даже если тестово выставить `auto_post: true` — POST без OK не выполняется (второй рубеж).
6. `watermark.json` MFL после прогона CA не меняется (тест mtime/хеш).
7. Loop-клиент в дереве CA не импортирует `requests`/`httpx`. Digest keyword-без-mention не читает каналы вне контура Q4.
8. Юнит-тесты шага 17 зелёные без VPN; живой smoke — отдельно, за флагом.
9. Ошибка API → `report_error.sh --tool ContractAssistant`, watch fail-quiet `exit 0`; падение JIRA не меняет процесс MFL (отдельный крон).
10. Журнал Q&A после ask/watch содержит запись с `cite` или `unknown`/`partial`; concurrent append urgent+digest на одном slug не рвёт файл (flock/atomic).
11. Эталон приёмки (Q6): Qlever **и** любой новый договор, приходящий параллельно — тот же контур classify/escalate; не ждать окончания Qlever, параллельный контур запускается и тестируется тоже.
12. Агрегат не содержит телефонов/паспортов; ИНН/юрлицо/суммы допустимы.
13. Спека кронов: urgent `1-59/3 8-20 * * 1-5`, digest `5 8-20 * * 1-5`; оба `no_agent` + `ca_watch.py` без `--sasha-ok`; в `jobs.json` нет записей до «ставь кроны». `mfl_*` и job `f61b26cbbdf5`/`2865cc674493` без diff.
14. Пустой успешный тик двигает свой watermark; полный отказ источника — ключ не двигается, ErrorBus, `exit 0`.
15. Вне пн–пт 8–20 скрипт (защита) не генерирует проект ответа.

---

## 14. Открытые вопросы

Статус ТЗ: `draft`. Q1–Q8 **закрыты** 08.09.2026 решениями Саши. Финализация — по фразе «финализируй». Реализация — отдельное «берём в работу». Кроны — отдельное «ставь кроны».

**Q1. Автопост.** **Закрыт:** прод-пост автоматически **не** осуществляется. СА готовит проект ответа + обоснование → Messages → явное OK Саши → только тогда пост в место вопроса (JIRA comment / Loop). `auto_post: false`, `auto_post_slugs: []`. Даже `true` не обходит гейт OK.

**Q2. Дети в `entities.json`.** **Закрыт:** детей договоров в реестр **не** заносим (только файлы под зонтиком). Зонтик `Contracts` (`kind: project`) остаётся.

**Q3. Вложенность.** **Закрыт:** оставляем `Entities/Contracts/<slug>/`.

**Q4. Контур Loop.** **Закрыт:** только DM-allowlist + @упоминания с матчем slug/ключ. Digest keyword-без-mention — в том же множестве каналов/DM. Сканирование произвольных каналов по ключу — не в v0.1.

**Q5. Exchange.** **Закрыт:** почта — триггер идентификации «вопрос или изменение». Вопрос (кому-либо, по договору) → схема ответов §8 (проект + OK Саши). Не вопрос → уведомление, без отправки.

**Q6. Эталон приёмки.** **Закрыт:** Qlever + любой новый договор, приходящий параллельно (не ждать окончания Qlever; запускать параллельный контур и тестировать на нём тоже).

**Q7. Скилл vs CLI.** **Закрыт:** в v0.1 — CLI + скилл `contract-assistant` (обе сущности). Скилл — отдельная согласуемая сущность. Пост наружу — только `ca post --apply --sasha-ok` после явной фразы Саши. Крон `--sasha-ok` не ставит.

**Q8. Кроны vs MFL.** **Закрыт (вариант 2):** два своих крона CA (urgent `1-59/3 8-20 * * 1-5` + digest `5 8-20 * * 1-5`), `no_agent`, `ca_watch.py` (watch→answer без `--apply`/`--sasha-ok`). MFL-кроны `f61b26cbbdf5` / `2865cc674493` и `mfl_*` **не трогать**. Встраивание в `mfl_*` как ExchangeMonitor — **запрещено**. `ca_answer` agent-job — не в v0.1. Ночь/выходные — expr крона (плюс защита 8–20 в скрипте).

---

Согласование этого текста ≠ команда на реализацию.
