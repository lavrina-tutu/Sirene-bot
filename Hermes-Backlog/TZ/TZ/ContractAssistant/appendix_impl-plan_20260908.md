---
type: appendix
tool: ContractAssistant
theme: impl-plan
date: 2026-09-08
version: 0.1.0
status: HF:plan
author: architect (cursor-grok-4.6-high)
master: TZ/ContractAssistant/ContractAssistant_TZ.md
master_version: 0.2.0
---

# ContractAssistant — пофайловый план реализации (`HF:plan`)

План по master-ТЗ v0.2.0. Код — только после явного «берём в работу» и `GATE:plan-approve`. Кроны в `jobs.json` — только после «ставь кроны». Gateway не рестартовать. Исполнитель **не** пишет в `EcosystemManifest.json` / `entities.json` / `.env` / `jobs.json`.

**Инвариант ответа наружу:** JIRA comment / Loop post / SMTP/EWS / мессенджеры — только после явного OK Саши **и** `--apply`. `auto_post: false` + `auto_post_slugs: []` в v0.1; даже `true` не обходит второй рубеж.

---

## 0. Рекомендация архитектора (reuse-first)

Один новый USERTOOL `~/USERTOOLS/ContractAssistant/` + тонкий скилл `productivity/contract-assistant` (Q7). Не расширять MoveFromLoop / MoveFromJira / ExchangeMonitor. HTTP Loop — **curl subprocess** по образцу `LoopChannelDigest/loop_channel_digest/client.py` (не `MoveFromLoop/loop_api.py`: там `requests`, питфолл hang на `loop.tutu.ru`). JIRA — **паттерн** OKRTool `comment_issue` (Bearer в рантайме), без импорта пакета `okrtool`. Exchange — `import exchangemonitor.fetcher` (+ username-тройка из `exchangemonitor.client`). State/journal — flock + `os.replace` как `movefromloop.state`. Ошибки — ErrorBus Mode A (`report_error.sh --tool ContractAssistant`). Детей договоров в `entities.json` не заносить.

---

## 1. Новые сущности (согласование до `HF:impl`)

| Сущность | Статус | Действие исполнителя |
|---|---|---|
| USERTOOL `ContractAssistant` | это ТЗ | создавать после «берём в работу» |
| скилл `contract-assistant` | **новая, Q7** — отдельное согласование | не внедрять до явного ОК скилла; файлы скилла — отдельный подшаг волны G |
| `kind: contract` в `entities.schema.json` | **не в v0.1** | не трогать |
| дети в `entities.json` | **не заносим (Q2)** | не трогать реестр; зонтик `Contracts` уже есть |
| `doc_type=contract` в MofsIndex | **не в v0.1** | не трогать |
| кроны в `jobs.json` | спека в README | не создавать без «ставь кроны» |
| запись в `EcosystemManifest.json` | только `ORCH:shared-state` | исполнитель не пишет |

> Новая сущность X — требует согласования Саши: **скилл `contract-assistant`**. Без явного ОК реализация скилла не начинается. CLI можно писать раньше.

---

## 2. Reuse-карта (не копировать пакеты целиком)

| Что | Откуда | Как | Чего не делать |
|---|---|---|---|
| Loop HTTP | `USERTOOLS/LoopChannelDigest/loop_channel_digest/client.py` | curl `-sS -m 10` `-w \n%{http_code}`, retry `(1,3,9)` на 5xx/429/timeout | `import requests` / `httpx`; общий `watermark.json` MFL |
| Loop контур | MFL `mentions_fetcher` + ТЗ Q4 | `mention_count>0`, team `b1mrmr41dtrhbgk3a9qa7bxhqe`, DM allowlist, `posts?since=` мс 13 цифр | сканировать произвольные каналы по ключу |
| JIRA comment POST | `OKRTool/okrtool/jira.py` `comment_issue` | `POST /rest/api/2/issue/{key}/comment` `{"body":...}`; `_AUTH_SCHEME + " " + token` в рантайме (маскировщик Hermes) | `import okrtool`; `/user/search`; Service Desk create; requests-пакет OKR |
| JIRA GET comments | тот же REST v2 | `GET .../issue/{key}/comment` + `fields=updated,comment` | расширять `jira_snapshot.json` MoveFromJira |
| Exchange Inbox | `exchangemonitor.fetcher.fetch_inbox_since` | `sys.path` → `~/USERTOOLS/ExchangeMonitor`; username `tkachenkoav@tutu.ru` / `TUTU\tkachenkoav` / `tkachenkoav` | менять `is_read`; SMTP; `loop_rules.yaml`; MFL state |
| Exchange person | `exchangemonitor.person_checker` | фильтр людей; login из `contract_urgent_users` | новый коннектор контактов |
| State flock | `movefromloop/state.py` | `fcntl.flock` + `os.replace` temp-file; TTL 48ч `seen_ids` | ключи `urgent_last_ts` MFL |
| ErrorBus | `~/.hermes/scripts/report_error.sh` | Mode A, `--tool ContractAssistant`; watch fail-quiet (exit 0 после репорта) | бизнес-эскалации в Errors `:11112` |
| Confluence Rules | `confluencesync pull <pageId> --to-file` | pageId 338627217 / 331126580 | писать в Confluence; новый коннектор |
| Креды JIRA/Loop | `~/.hermes/profiles/anthropic/.env` | построчный parse (не `source`) | `source ~/.config/hermes/.env` для JIRA |
| Креды Exchange | `~/.config/hermes/.env` | grep/cut `TUTU_DOMAIN_PASSWORD` | `source` всего файла |
| Креды Confluence | `~/USERTOOLS/ConfluenceSync/.env` | точечные ключи | `source` |
| Entry cron | `~/.hermes/scripts/mfl_urgent_check.py` | хардкод `_ROOT=/home/tkachenkoav/USERTOOLS/ContractAssistant` | `Path(__file__).parent` как корень пакета |
| Роли людей | AnywhereContacts `login` | zarubina / sivets / agababyan / aralov | новый kind |

---

## 3. Волны реализации и точки проверки

Исполнитель проходит точки **молча** (без отчётов Саше). Код — после «берём в работу». Волна 0 (vault) входит в гейт «берём в работу» (ТЗ §12 шаг 1): не раньше.

Каждая точка: команда + критерий. Юнит-тесты без VPN. Живой smoke — за флагом `--integration` / env `CA_LIVE=1`.

### Волна 0 — канон агрегата (vault, шаг 1)

**Точка П0.** `dwh-agent-qlever.md` соответствует H2 §6.4; frontmatter `schema_version: "1.0"`; телефоны/паспорта отсутствуют; журнал пустой (заголовок есть, записей нет); факты не выдуманы.

### Волна A — каркас (шаг 2)

**Точка П1.** `cd ~/USERTOOLS/ContractAssistant && venv_linux/bin/python -c "import contractassistant"` → 0. `contract_rules.yaml`: `auto_post: false`, `auto_post_slugs: []`. `state/` в `.gitignore`.

### Волна B — registry + state (шаги 3–4)

**Точка П2.** `pytest tests/test_registry.py` — Qlever отдаёт `ADD-630106` и `MIX-2162`.
**Точка П3.** `pytest tests/test_state.py tests/test_state_locking.py` — watermark мс, TTL 48ч, первый lookback 10 мин, flock.

### Волна C — клиенты (шаги 5–7)

**Точка П4.** `pytest tests/test_jira_client.py` — GET comments мок; skip `my_jira_user`; нет живого POST.
**Точка П5.** `pytest tests/test_loop_client.py tests/test_loop_no_requests.py` — curl; нет `requests`/`httpx` в `loop_client.py`; digest keyword не шире контура Q4.
**Точка П6.** `pytest tests/test_exchange_watch.py` — фильтр людей/ключей; вопрос vs не-вопрос; MFL `watermark.json` mtime/хеш не меняется (фикстура копии).

### Волна D — watch (шаг 8)

**Точка П7.** `ca_watch --dry-run` пишет inbox-события в stdout/файл; свои комментарии skip; `pytest tests/test_watch.py`.

### Волна E — retrieve / classify / answer (шаги 9–11)

**Точка П8.** Вопрос «комиссия Qlever» → секции агрегата §процедура + Rules §пороги.
**Точка П9.** Эталон known (комиссия) + partial (КБК) + unknown-без-cite; `known` без `cite` невозможен.
**Точка П10.** Проект без эмодзи; длина ≤ 4000; обоснование «почему»; нет выдуманного КБК.

### Волна F — post-gate / escalate / journal / CLI (шаги 12–15, 18)

**Точка П11.** POST не вызывается без `--apply` **и** `--sasha-ok`. `auto_post=true` + slug в allowlist без `--sasha-ok` → POST нет.
**Точка П12.** Карточка escalate: проект + обоснование + cite; stdout.
**Точка П13.** Journal идемпотентен по `source+id`; concurrent append не рвёт файл.
**Точка П14.** `ca ask` эталоны Qlever; ErrorBus при искусственной ошибке API (мок `report_error.sh`).

### Волна G — скилл (шаг 16, после ОК скилла)

**Точка П15.** Скилл: триггеры, запрет выдумки, вызов CLI, **пост только по OK Саши**.

### Волна H — тесты + README (шаги 17, 19)

**Точка П16.** Весь набор шага 17 зелёный без VPN. Фикстура второго договора (Q6) проходит тот же контур. README: спека кронов, job не созданы.

### После `HF:docs-handoff` — `ORCH:shared-state` (шаг 20)

**Точка П17.** Манифест + digest; скилл в дереве workspace; `restore-all-skills.sh`; детей в `entities.json` нет. Исполнитель эту точку **не** закрывает.

---

## 4. Дерево файлов (создать)

```
~/USERTOOLS/ContractAssistant/
  pyproject.toml
  README.md
  .gitignore
  contract_rules.yaml
  contractassistant/
    __init__.py
    __main__.py          # python -m contractassistant ask|watch|answer|post
    config.py
    rules.py
    registry.py
    state.py
    jira_client.py
    loop_client.py
    exchange_watch.py
    match.py
    retrieve.py
    classify.py
    answer.py
    post_gate.py         # общая проверка двух рубежей (импорт post_jira/post_loop)
    post_jira.py
    post_loop.py
    escalate.py
    journal.py
    watch.py
    ask.py
    errorbus.py          # обёртка Mode A
  scripts/
    ca_watch.py
    ca_answer.py
  state/                 # gitignore contents; .gitkeep опционально
  tests/
    conftest.py
    fixtures/
      dwh-agent-qlever.md    # санитизированная копия (без телефонов)
      acme-parallel.md       # Q6: второй договор по шаблону
      purchase-rules.md
      mfl_watermark.json     # копия для теста «не трогаем MFL»
    test_registry.py
    test_state.py
    test_state_locking.py
    test_jira_client.py
    test_loop_client.py
    test_loop_no_requests.py
    test_exchange_watch.py
    test_watch.py
    test_match.py
    test_retrieve.py
    test_classify.py
    test_answer.py
    test_post_gate.py
    test_escalate.py
    test_journal.py
    test_ask.py
    test_pii_aggregate.py
    test_errorbus.py
    test_mfl_untouched.py

~/WorkVault/Entities/Contracts/
  _templates/contract-aggregate.md
  Rules/_sources.yaml
  dwh-agent-qlever/dwh-agent-qlever.md   # изменить
  dwh-agent-qlever/artifacts/            # создать; PDF не парсить

~/hermes-workspace/skills/productivity/contract-assistant/
  SKILL.md
```

`post_gate.py` — тонкий общий модуль (не в списке ТЗ §5, но без него два POST-файла дублируют рубеж). Если исполнитель хочет строго 1:1 со списком ТЗ — держать `assert_may_post()` в каждом из `post_*.py` идентично; предпочтение: один модуль, оба импортируют.

---

## 5. Пофайлово: USERTOOL

### 5.1 `pyproject.toml`

**Назначение.** Пакет `contractassistant`, Python ≥3.10, pytest.

**Ключевые поля.** `name = "contractassistant"`. Dependencies: `pyyaml`, `python-dotenv`. **Не** `requests`/`httpx`. Dev: `pytest`. Scripts: `ca = "contractassistant.__main__:main"`. pytest `testpaths = ["tests"]`.

**Тесты.** Импорт пакета из venv; `pip show` не тянет requests как прямую зависимость.

### 5.2 `.gitignore`

Игнорировать `state/*.json`, `state/*.jsonl`, `state/*.lock`, `venv_linux/`, `__pycache__`, `.pytest_cache`. Не игнорировать `contract_rules.yaml`.

### 5.3 `README.md`

Спека кронов (не job): urgent `*/3 * * * *` пн–пт 8–20; digest `0 8–20 * * 1-5`. `ca_watch` = no_agent; `ca_answer` = agent → эскалация проекта, не пост. Креды, `_ROOT` для копий в `~/.hermes/scripts/`. Запрет поста без OK. ПДн: ИНН/ЮЛ/суммы да; телефоны/паспорта нет.

**Тесты.** Нет (документ). Критерий: расписание совпадает с ТЗ §7.

### 5.4 `contract_rules.yaml`

Как ТЗ §6.5: `schema_version: "1.0"`, `auto_post: false`, `auto_post_slugs: []`, `my_jira_user`, `my_loop_username`, `contract_urgent_users: [zarubina, sivets]`, `escalation_telegram: "telegram:-1004300127777:6556"`, `poll_lookback_minutes: 15`. Watch-ключи **не** дублировать.

**Тесты.** `test_rules.py` (можно внутри `test_registry`/`conftest`): загрузка; дефолт auto_post false; пустой allowlist.

### 5.5 `contractassistant/config.py`

**Назначение.** Пути vault, корня инструмента, файлов state, загрузка кредов.

**Классы/функции.**

- `TOOL_ROOT`, `VAULT_CONTRACTS = ~/WorkVault/Entities/Contracts`
- `STATE_DIR`, `WATERMARK_PATH`, `INBOX_PATH`
- `load_env_keys(path, keys) -> dict` — построчно, не `source`
- `jira_creds()`, `loop_creds()`, `exchange_password()`, `confluence_token()` — точечно из путей ТЗ §4.2
- `EXCHANGE_MONITOR_ROOT` для `sys.path`

**Тесты.** Парсер `.env` на temp-файле со спецсимволами в значении; не подхватывает лишние ключи.

### 5.6 `contractassistant/rules.py`

**Назначение.** Загрузка `contract_rules.yaml` → dataclass.

**Классы.** `ContractRules(auto_post: bool, auto_post_slugs: list[str], my_jira_user, my_loop_username, contract_urgent_users, escalation_telegram, poll_lookback_minutes, schema_version)`. `load_rules(path) -> ContractRules`.

**Тесты.** Отсутствие файла → безопасные дефолты с `auto_post=False`, `auto_post_slugs=[]`.

### 5.7 `contractassistant/registry.py`

**Назначение.** Сканер `Entities/Contracts/**/*.md` (не `Rules/`, не `_templates/`, не `Contracts.md`).

**Классы/функции.**

- `ContractRecord` dataclass: `slug`, `path`, `jira_keys: list[str]`, `loop_users`, `keywords`, `inn`, `counterparty`, `status`, `title`
- `scan_contracts(root) -> list[ContractRecord]`
- Парс YAML-frontmatter; `jira_keys` + fallback `jira_add`/`jira_mix`
- Aliases из `Contracts.md` wikilink-строк — опционально в v0.1 (match.py может читать индекс)

**Тесты.** Фикстура Qlever → keys `{ADD-630106, MIX-2162}`; игнор Rules; битый frontmatter не роняет сканер (skip + лог).

### 5.8 `contractassistant/state.py`

**Назначение.** Свой `watermark.json` + `seen_ids` TTL 48ч + append `inbox.jsonl`. flock + atomic `os.replace`.

**Формат watermark.**

```json
{
  "jira_last_ts": <ms>,
  "loop_last_ts": <ms>,
  "exchange_last_ts": <ms>,
  "seen_ids": [{"id": "jira:123", "ts": <ms>}]
}
```

Ключи **не** как у MFL (`urgent_last_ts`). Первый запуск: `now_ms() - 10*60*1000`, не 0.

**Классы.** `State` по образцу MFL: `load/save`, `_acquire_lock`, `mark_seen`, `prune_seen(ttl_ms=48h)`, `is_seen(source, external_id)`, `append_inbox(event)` (отдельный flock на `inbox.jsonl`).

**Тесты.** Lookback 10 мин; prune старше 48ч; concurrent save (как `test_state_locking` MFL); id формат `source+id`.

### 5.9 `contractassistant/jira_client.py`

**Назначение.** GET comments / issue fields; POST comment **только** через `post_jira.py`. urllib или curl; не requests.

**Функции.**

- `_headers()` — Bearer в рантайме (`_AUTH_SCHEME + " " + token`), как OKRTool
- `get_comments(key) -> list[dict]` (`id`, `created`, `author.name`, `body`)
- `get_issue(key, fields=...)`
- `download_attachment(...)` — только ingest, не ответ; `X-Atlassian-Token: no-check`
- Не вызывать POST из этого модуля без явного вызова `post_comment` из `post_jira` (либо `post_comment` живёт только в `post_jira.py`)

**Пропуск.** `author == my_jira_user`; пустой body.

**Тесты.** Мок HTTP; skip self; пустой body skip. Интеграционный smoke за VPN — `@pytest.mark.integration`, по флагу. **Никакого POST в CI.**

### 5.10 `contractassistant/loop_client.py`

**Назначение.** Loop v4 curl subprocess. Канон транспорта: LCD `LoopClient` (не MFL `requests`). `--max-time 10`, retry 1/3/9 с на 5xx/429.

**Функции.**

- `_curl(method, path, params, json_body)` — без import requests
- `me()`, `channel_members(team_id)`, `posts_since(channel_id, since_ms)`, `users_ids`, `get_channel`
- `iter_mention_channels(team_id)` — `mention_count>0`
- `iter_dm_allowlist(usernames)` — DM только с allowlist
- `filter_post(post)` — skip `type!=""`, `delete_at!=0`, `user_id==me`
- `q4_channel_ids(state)` — множество: DM allowlist ∪ каналы, где были @упоминания с матчем slug/jira_keys
- Digest keyword-без-mention: **только** внутри `q4_channel_ids`

**Константы.** `TEAM_ID = "b1mrmr41dtrhbgk3a9qa7bxhqe"`, `PER_PAGE=200` (пагинацию всё равно оставить), `since` — int 13 цифр.

**Тесты.** Мок `subprocess.run`; сборка curl-команды; retry; `test_loop_no_requests.py` — `ast`/`grep` по файлу: нет `import requests`/`httpx`. Keyword вне Q4 не запрашивает `posts`.

### 5.11 `contractassistant/exchange_watch.py`

**Назначение.** Чтение Inbox через ExchangeMonitor; классификация вопрос vs изменение (Q5). Не менять `is_read`. Не писать MFL state.

**Функции.**

- `_ensure_exchangemonitor_path()`
- `fetch_events(since_ms, rules, registry) -> list[Event]`
- Фильтр: sender login ∈ `contract_urgent_users` **или** body/subject содержит любой `jira_keys` / URL `hq.tutu.ru/browse/...`
- `is_question(text) -> bool` — `?` или глаголы (нужно/уточни/какая сумма/кто заказчик); спорное → вопрос
- Не-вопрос → событие `kind=notify`, не тишина

**Тесты.** Фикстуры писем; keyword JIRA; чужой отправитель без ключа → drop; `is_question`; патч fetcher не вызывает save MFL.

### 5.12 `contractassistant/match.py`

**Назначение.** Event → slug или `unmatched`. Без LLM в v0.1 основном пути; LLM-fallback только если не уверен → всё равно `unmatched`.

**Функции.** `match_event(event, records) -> MatchResult(slug|None, method)`. Порядок: jira_keys в тексте/полях → slug папки → ИНН → counterparty (регистронезависимо) → aliases `Contracts.md`.

**Тесты.** ADD-630106 → `dwh-agent-qlever`; неизвестный ключ → unmatched; не создавать папку.

### 5.13 `contractassistant/retrieve.py`

**Назначение.** Чтение агрегата + нарезка H2; Rules при регламентном вопросе.

**Функции.**

- `split_h2(md) -> dict[str, str]` (ключ — текст H2)
- `load_aggregate(slug) -> AggregateDoc`
- `retrieve(slug, question) -> Retrieved(sections, paths)`
- Регламентные маркеры (порог, RACI, комиссия, ед. поставщик, портал) → обязательно `Rules/purchase-rules.md`, portal при «портал»
- Fallback grep **только** `Entities/Contracts/`
- Встречи/RAG: не класть в проект наружу (опц. пометка слоя; v0.1 можно заглушка + комментарий «дополнение, не замена»)

**Тесты.** «комиссия Qlever» видит H2 процедуры + Rules пороги 500к–5млн; PDF не читается как бинарник.

### 5.14 `contractassistant/classify.py`

**Назначение.** `known | partial | unknown` (+ вызывающий добавит `unmatched`/`notify`/`skip`). **Запрет `known` без `cite`.**

**Классы.** `ClassifyResult(label, cite: str | None, missing: list[str], rationale: str)`.

**Функции.**

- `is_question(text)` — общая эвристика (можно re-export из exchange_watch / общий `heuristics.py`; не плодить расхождение)
- `validate_known(result, retrieved) -> ClassifyResult` — нет `cite` или cite не из retrieved → `unknown`
- `build_prompt(question, sections)` — в промпт **только** переданные секции, не «вспомни сумму»
- `classify(question, retrieved, llm_complete: Callable | None)` — LLM опционален; без LLM: эвристика по якорям (комиссия+сумма+порог → known на фикстуре Qlever; КБК в «Открытых вопросах» → partial). Инвариант валидатора всегда
- Эталон partial: КБК Qlever — не подставлять число

**Тесты.** Known комиссия + cite на агрегат и Rules. Partial КБК — нет цифры КБК. FakeLLM `known` без cite → unknown. FakeLLM выдуманная сумма → unknown.

### 5.15 `contractassistant/answer.py`

**Назначение.** Текст **проекта** ответа + обоснование. Без эмодзи. Не пост.

**Функции.** `build_project(classify, retrieved, event) -> Project(text, rationale, cite)`. Лимит 4000 символов (JIRA). Не дублировать поля формы, если вопрос не про ошибку. Коррекция комиссии: порог Rules + сумма агрегата. Не оглашать бюджет поставщику; не обещать сроки подписания вне агрегата.

**Тесты.** Нет эмодзи в `text`; есть «не проводилась» и «500»/«5» для эталона; нет КБК-числа; rationale непустой; truncate 4000.

### 5.16 `contractassistant/post_gate.py`

**Назначение.** Единый второй рубеж.

**Функции.** `assert_may_post(*, sasha_ok: bool, apply: bool) -> None`. `auto_post` и allowlist **не** входят в условие. Без обоих флагов — `PermissionError` / `PostGateError`.

**Тесты.** Матрица 2×2 флагов + матрица auto_post true/false × slug in/out allowlist — POST разрешён **только** sasha_ok∧apply.

### 5.17 `contractassistant/post_jira.py`

**Назначение.** `POST /rest/api/2/issue/{key}/comment` после гейта. Тот же issue, что в событии.

**Функции.** `post_jira_comment(key, body, *, sasha_ok, apply) -> str` (comment id или `""` на dry-run). Вызов HTTP только после `assert_may_post`.

**Тесты.** Без флагов HTTP-мок не вызван; с флагами — вызван, id вернулся. CI без сети.

### 5.18 `contractassistant/post_loop.py`

**Назначение.** `POST /api/v4/posts` `{channel_id, message, root_id?}` после гейта. Тот же `channel_id` / тред.

**Функции.** `post_loop_reply(...)`. SMTP/EWS здесь нет (запрет). Exchange-ответ — только если OK явно указал канал; иначе notify.

**Тесты.** Аналогично post_jira; curl-мок.

### 5.19 `contractassistant/escalate.py`

**Назначение.** Карточка Messages (stdout для cron `deliver`). Все classify, все source. POST нет.

**Формат (ТЗ §8; эмодзи карточки — исключение, не в теле проекта):**

```
📋 ContractAssistant · <slug> · known|partial|unknown|unmatched|notify
Q: …
Проект: … | — (notify: без проекта отправки)
Обоснование: …
cite: …
🔗 JIRA|Loop|OWA
```

**Функции.** `format_card(...) -> str`. Не звать ErrorBus (это не техсбой).

**Тесты.** Поля на месте; notify без проекта отправки; unmatched без создания папки.

### 5.20 `contractassistant/journal.py`

**Назначение.** Append-only секция «Журнал Q&A». flock или atomic `os.replace` (urgent∥digest). Идемпотентность `source+id`.

**Формат записи (ТЗ §6.4):**

```
### YYYY-MM-DD HH:MM MSK · source=jira|loop|exchange|ask · id=<external_id>
- Q: …
- A: … | unknown
- cite: `Entities/Contracts/<slug>/<slug>.md` §<H2>
- action: posted|escalated|dry-run|notify
```

**Функции.** `append_qa(slug, entry)`; `has_entry(slug, source, id)`; lock на файл агрегата (не только state).

**Тесты.** Повторный append того же id — 1 запись. Два процесса параллельно — файл валидный markdown, обе записи или идемпотентный skip. Journal всегда, включая dry-run/unknown/notify.

### 5.21 `contractassistant/watch.py`

**Назначение.** Склейка JIRA+Loop+Exchange → inbox.jsonl. `run_watch(dry_run=False)`.

**Поведение.** Обновить watermark по прочитанным ts. Дедуп seen_ids. Skip self. Не вызывать classify/post. `--dry-run`: не писать watermark (или писать копию), события в stdout.

**Тесты.** Чужой комментарий ADD-630106 → inbox; свой → skip; Loop вне Q4 не попадает.

### 5.22 `contractassistant/ask.py`

**Назначение.** On-demand вопрос. Тот же retrieve/classify. Ответ в stdout. Поста нет.

**Функции.** `ask(question, slug_hint=None) -> AskResult`. Подпись: «Из агрегата `<slug>` §…» / «Из регламента закупок (pageId 338627217)».

**Тесты.** Эталоны критерия успеха ТЗ §13 п.2–3.

### 5.23 `contractassistant/errorbus.py`

**Назначение.** Mode A.

**Функции.** `report_error(message, *, stage, detail, exit_code)`. Вызов `~/.hermes/scripts/report_error.sh --tool ContractAssistant`. Fail-soft: скрипт exit 0; watch ловит API-ошибку, репортит, сам выходит 0 (как ExchangeMonitor/MFL).

**Тесты.** Мок скрипта; `--tool ContractAssistant` в argv. Не слать эскалацию Q&A в Errors.

### 5.24 `contractassistant/__main__.py`

CLI: `watch`, `answer`, `ask`, `post`.

- `watch [--dry-run] [--mode urgent|digest]`
- `answer [--apply] [--sasha-ok]` — оркестрация inbox → match → question-gate → retrieve → classify → project → escalate → journal. **POST только если оба флага.** В v0.1 крон `ca_answer` флаги не передаёт.
- `ask "вопрос"`
- `post --source jira|loop --id ... --apply --sasha-ok` — явный пост после OK Саши

**Тесты.** CLI `--help`; `post` без флагов не дергает HTTP.

### 5.25 `scripts/ca_watch.py`

Entry no_agent. Хардкод `_ROOT=/home/tkachenkoav/USERTOOLS/ContractAssistant` (урок MFL). `sys.path.insert(0, str(_ROOT))`. try/except → `errorbus.report_error`, exit 0. stdout: тишина или путь inbox (крон agent смотрит nonempty).

**Тесты.** Косвенно через `watch.py`. Копия в `~/.hermes/scripts/` — **не** в `HF:impl`; спека README; физическая копия при «ставь кроны» или `ORCH:shared-state`.

### 5.26 `scripts/ca_answer.py`

Entry agent-cron. Хардкод `_ROOT`. Читает inbox, оркестрирует без `--apply`/`--sasha-ok`. stdout = карточки escalate (deliver в `:6556`). ErrorBus на сбое.

**Тесты.** Мок inbox → stdout содержит «Проект» и «Обоснование»; HTTP post не вызван.

---

## 6. Пофайлово: vault

### 6.1 `Entities/Contracts/_templates/contract-aggregate.md`

Шаблон frontmatter §6.3 + 11 H2 §6.4 + пустой журнал. `record_type: contract`, **не** `kind: contract`. ПДн-комментарий в шаблоне: телефоны/паспорта не заполнять.

**Тесты.** `test_registry` может сканировать копию шаблона как `acme-parallel`.

### 6.2 `Entities/Contracts/Rules/_sources.yaml`

```yaml
338627217: purchase-rules.md
331126580: purchase-portal.md
```

Для `confluencesync pull`. Не новый коннектор.

### 6.3 `Entities/Contracts/dwh-agent-qlever/dwh-agent-qlever.md` (изменить)

**Назначение.** Привести прототип к канону **без новых фактов**.

**Frontmatter (обязательные):** `title`, `slug: dwh-agent-qlever`, `record_type: contract`, `parent: Contracts`, `status: approval`, `schema_version: "1.0"`, `jira_keys: [ADD-630106, MIX-2162]`, `legal_entity: НТТ`, `counterparty: Qlever`, `amount_ex_vat: 1411200`, `currency: RUB`. Рекомендуемые из уже известных: `inn: "7810898586"`, `jira_add`, `jira_mix`, `source_kp`, `roles` логинами. **Удалить** `kind: contract` (не дублировать enum реестра).

**H2 ровно в порядке §6.4:**

1. Задачи JIRA — перенести существующее
2. Контрагент — ИНН/ЮЛ оставить; **телефоны убрать** (`+7 812 425-32-48`, `+7 903 551 01 31`); email допустим как рабочий контакт не-ПДн-паспорта, но телефон — нет по ТЗ
3. Суммы и сроки
4. ЮЛ и роли
5. Закупочная процедура — нынешняя секция «Решение по закупочной комиссии»
6. Выбор поставщика — таблица без телефонов в колонке «Контакты»
7. Предмет / состав работ — слить «Состав работ» + «Артефакты на выходе» (уже в файле; не выдумывать 5-й артефакт)
8. Открытые вопросы — КБК, ЭДО, держатель бюджета как есть
9. Журнал Q&A — секция есть, записей нет
10. Переписка
11. Источники

Убрать хвостовой «Резерв / отдельное» (смысл — в шаблоне/ТЗ, не дублировать обещание). PDF: если файла нет — не выдумывать; путь `artifacts/` + пометка «источник — вложение ADD-630106». Не парсить PDF.

**Тесты.** `test_pii_aggregate.py`: regex телефонов/«паспорт» по агрегату → 0 совпадений. Retrieve видит 11 H2. ИНН и 1411200 на месте.

### 6.4 `dwh-agent-qlever/artifacts/`

Пустой каталог + опц. `.gitkeep`. Ingest PDF — по команде, не в v0.1 автоматом из watch.

---

## 7. Пофайлово: скилл (волна G, после ОК)

### 7.1 `~/hermes-workspace/skills/productivity/contract-assistant/SKILL.md`

**Назначение.** Тонкий слой: триггеры, запрет выдумки, вызов CLI. Не дублировать бриф АДД 232 (`tutu-jira-contract-approval`).

**Обязательные правила в тексте скилла.**

- Триггеры: «какой ИНН у Qlever», «нужна ли комиссия», «что по договору», ContractAssistant, `ca ask`
- Факты **только** из CLI/`Entities/Contracts/`; нет cite → не `known`, сказать unknown/partial
- Не выдумывать КБК, суммы, сроки подписания, ИНН
- Вызов: `cd ~/USERTOOLS/ContractAssistant && venv_linux/bin/python -m contractassistant ask "..."`
- **ПОСТ ТОЛЬКО ПО OK САШИ.** Слова «отправь» / «OK» / «пости» в этом треде. Иначе только проект. Никогда не передавать `--apply --sasha-ok` без этой фразы
- Не создавать заявки АДД; не менять поля JIRA
- Эскалация unmatched: не создавать папку договора без команды Саши

**Тесты.** Ревью текста (исполнитель + `HF:docs-handoff`). Автотест: скилл-файл содержит запрет поста и вызов CLI (grep в `tests/` опционально, путь абсолютный хрупкий — лучше чеклист П15).

После появления файлов скилла синк — **`ORCH:shared-state`** (`restore-all-skills.sh` / `sync-to-hermes.sh default`). Исполнитель кладёт файлы в `hermes-workspace/skills/...`, симлинк в профиль не руками в `HF:impl` (оркестратор).

---

## 8. Что в `ORCH:shared-state` (исполнитель не делает)

Фаза после `HF:docs-handoff`. Workspace оркестратора: `dir:/home/tkachenkoav/WorkVault/Registries`.

1. **`EcosystemManifest.json`**
   - `applications.contract_assistant`: name `ContractAssistant`, category `usertool`, path `~/USERTOOLS/ContractAssistant`, tz_ref `TZ/ContractAssistant/ContractAssistant_TZ.md`, purpose по §1, `called_by`: скилл `contract-assistant` + кроны (спека; job_id пусты пока нет «ставь кроны»)
   - `skills.contract_assistant` (или аналог ключа): name `contract-assistant`, tools `[ContractAssistant]`, triggers из SKILL.md
   - `links`: reads api_jira / api_loop / api_exchange / ExchangeMonitor / ConfluenceSync / AnywhereContacts; writes api_telegram (escalation `:6556`), ErrorBus, WorkVault journal; writes api_jira/api_loop **только после OK Саши**
   - Не добавлять entity-детей договоров
2. **digest/render** — `EcosystemManifest.digest.md` + `render_manifest.py --check-drift`
3. **`restore-all-skills.sh`** — прогон `~/hermes-workspace/restore-all-skills.sh` (он зовёт `sync-to-hermes.sh default`); скилл подхватывается по `SKILL.md` в дереве, правки скрипта не нужны
4. **`entities.json`** — **не** добавлять `dwh-agent-qlever` и прочих детей. Зонтик `Contracts` (`kind: project`) уже есть — не дублировать
5. **`.env` / `jobs.json`** — не трогать. Кроны — отдельная команда «ставь кроны». Тогда же: копии `ca_watch.py`/`ca_answer.py` в `~/.hermes/scripts/` с `_ROOT=...`; `instrumentation_registry.json` Mode A для новых job_id
6. **MofsIndex** `mofs index docs` для ТЗ — шаг `tz-workflow` после финализации ТЗ, не вход в `HF:impl` (ТЗ §12 шаг 21)

`manifest_hints` исполнитель кладёт в `kanban_complete.metadata` на `HF:docs-handoff`, не в JSON манифеста.

---

## 9. Явно не делать

- `jobs.json`, кроны, restart Gateway
- Дети в `entities.json`, `kind: contract` в schema, `doc_type` MofsIndex
- Импорт `okrtool`, `requests` в Loop-клиенте, правка MFL `watermark.json` / `loop_rules.yaml`
- Пост в JIRA/Loop/почту из watch/answer без `--sasha-ok --apply`
- Телефоны/паспорта в агрегатах
- Перенос `Entities/trisigma/contract_vendor.md`
- Создание папки нового договора из `unmatched`
- Правка полей issue JIRA
- Сканирование произвольных каналов Loop по ключу
- Живые POST в CI

---

## 10. Матрица тестов (шаг 17, минимум)

| ID | Что | Файл |
|---|---|---|
| T1 | Qlever known: комиссия не проводилась, коридор 500к–5млн, cite агрегат+Rules, нет КБК | `test_classify.py`, `test_ask.py` |
| T2 | Qlever partial: КБК → partial, число КБК не появляется | `test_classify.py`, `test_ask.py` |
| T3 | known без cite → unknown | `test_classify.py` |
| T4 | match ADD-630106 / MIX-2162 | `test_match.py`, `test_registry.py` |
| T5 | skip self JIRA/Loop | `test_jira_client.py`, `test_watch.py` |
| T6 | journal format + идемпотентность + flock | `test_journal.py` |
| T7 | нет POST без OK; auto_post true не обходит | `test_post_gate.py` |
| T8 | MFL watermark mtime/хеш | `test_mfl_untouched.py` |
| T9 | loop_client без requests/httpx; keyword не вне Q4 | `test_loop_no_requests.py`, `test_loop_client.py` |
| T10 | ErrorBus argv `--tool ContractAssistant` | `test_errorbus.py` |
| T11 | нет телефонов в агрегате | `test_pii_aggregate.py` |
| T12 | Q6 второй договор `acme-parallel` — тот же classify/escalate контур | `test_ask.py` / `test_classify.py` |
| T13 | escalate карточка: проект + обоснование | `test_escalate.py` |

Живой smoke (не CI): GET comments ADD-630106 за VPN; Loop `users/me` curl; Exchange `fetch_inbox_since` — флаги integration.

---

## 11. Порядок файлов для исполнителя (`HF:impl`)

Не начинать без: ТЗ + «берём в работу» + этот план + `GATE:plan-approve` + бэкап (`HF:backup`) + ОК скилла перед волной G.

1. Волна 0: шаблон, `_sources.yaml`, правка `dwh-agent-qlever.md`, `artifacts/`
2. Каркас пакета + yaml + gitignore + venv
3. `config.py` `rules.py` `registry.py` + T4 registry
4. `state.py` + locking
5. `jira_client.py` (GET only) → `loop_client.py` → `exchange_watch.py`
6. `match.py` `watch.py` `scripts/ca_watch.py`
7. `retrieve.py` `classify.py` `answer.py`
8. `post_gate.py` `post_jira.py` `post_loop.py` `escalate.py` `journal.py`
9. `ask.py` `__main__.py` `scripts/ca_answer.py` `errorbus.py`
10. Полный pytest П16
11. README спека кронов
12. Скилл — только после отдельного ОК
13. `HF:test` → `HF:docs-handoff` (`manifest_hints`) → стоп для исполнителя
14. `ORCH:shared-state` — оркестратор

Мелкое отклонение ≤2 файла без смены архитектуры — сам. Крупное — стоп, доплан архитектора.

---

## 12. Креды и интерпретатор (проверка фактов плана)

| Факт | Проверено |
|---|---|
| LCD Loop-клиент = curl, не requests | `USERTOOLS/LoopChannelDigest/loop_channel_digest/client.py` |
| MFL `loop_api.py` = requests (не брать транспорт) | `USERTOOLS/MoveFromLoop/movefromloop/loop_api.py` |
| OKRTool `comment_issue` | `USERTOOLS/OKRTool/okrtool/jira.py` |
| `fetch_inbox_since` | `USERTOOLS/ExchangeMonitor/exchangemonitor/fetcher.py` |
| Username-тройка Exchange | `exchangemonitor/client.py` |
| MFL flock State | `movefromloop/state.py` |
| Cron `_ROOT` хардкод | `~/.hermes/scripts/mfl_urgent_check.py` |
| ErrorBus Mode A | `~/.hermes/scripts/report_error.sh` |
| Зонтик Contracts в реестре | `Registries/entities.json` ключ `"Contracts"` |
| Телефоны в черновике агрегата | да, снять при волне 0 |
| `restore-all-skills.sh` сканирует все `SKILL.md` | `hermes-workspace/sync-to-hermes.sh` |

venv: Python 3.11, как прочие USERTOOLS (`venv_linux`). ExchangeMonitor на path, не вендорить `exchangelib` без нужды (клиент создаётся как в `exchangemonitor.client`).

---

## Прогресс выполнения

- [ ] П0 Шаблон + агрегат Qlever H2 §6.4, без телефонов, журнал пустой
- [ ] П1 Каркас USERTOOL + venv + `auto_post: false` / `auto_post_slugs: []`
- [ ] П2 registry Qlever keys
- [ ] П3 state flock / TTL / lookback 10 мин
- [ ] П4 jira GET мок, skip self
- [ ] П5 loop curl, нет requests, контур Q4
- [ ] П6 exchange import fetcher, MFL state не тронут
- [ ] П7 watch dry-run inbox
- [ ] П8 retrieve комиссия → Rules+агрегат
- [ ] П9 classify known / partial КБК / unknown-без-cite
- [ ] П10 answer без эмодзи, ≤4000, обоснование
- [ ] П11 POST только `--apply` ∧ `--sasha-ok`
- [ ] П12 escalate карточка
- [ ] П13 journal flock + идемпотентность
- [ ] П14 `ca ask` эталоны + ErrorBus
- [ ] П15 скилл (после отдельного ОК)
- [ ] П16 полный набор тестов шага 17 + Q6 фикстура
- [ ] README спека кронов (job нет)
- [ ] `HF:docs-handoff` manifest_hints
- [ ] `ORCH:shared-state` манифест + restore-all-skills; детей в entities.json нет

Статус «completed» на весь план ставит только Саша.
