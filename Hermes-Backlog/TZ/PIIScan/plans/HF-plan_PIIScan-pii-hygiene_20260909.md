---
type: hf-plan
title: "Пофайловый план CHANGE PIIScan-pii-hygiene (HF:plan, 09.09)"
slug: PIIScan
case: CHANGE
phase: HF:plan
date: 2026-09-09
status: draft-plan
author: архитектор (cursor-grok-4.6-high)
source_tz: TZ/PIIScan/PIIScan_TZ.md v1.2.0
executor: composer-2.5
next_phases: REV:plan → GATE:plan-approve → HF:backup → HF:impl → HF:test → HF:docs-handoff → ORCH:shared-state → GATE:done
---

# HF:plan — PIIScan-pii-hygiene (CHANGE)

Кейс **CHANGE** (GLOSSARY §2 / §5.2): доработка существующего инструмента PIIScan по master-ТЗ v1.2.0 (released 09.09.2026). Этот файл — артефакт фазы **HF:plan** (Блок 1А `hermes-feature`). Код в этом вызове не писать. Объект для `REV:plan` и `GATE:plan-approve`.

Канон: master-ТЗ `TZ/PIIScan/PIIScan_TZ.md` v1.2.0. Согласованный план правил 09.09: `~/.hermes/skills/devops/pii-data-scanning/references/pii-rule-20260909.md`. Приложения ТЗ: «Изменения 09.09 v1.0.0→v1.1.0» + «Правки REV 09.09 v1.1.0→v1.2.0».

Новая сущность EntityRegistry / пакет USERTOOLS **не** предлагаются. Код сканера уже лежит в `~/.hermes/pii_scan/` (не скилл `scripts/`). Черновик 09.09 на диске **не** заменяет этот план и **не** есть `HF:impl` done.

---

## 0. Факт на диске (09.09)

Проверено чтением файлов 09.09 (не по списку постановщика). Каталог `~/.hermes/pii_scan/` существовал **до** этой фазы — легальный черновик, не `PREMATURE_IMPL`. Исполнитель сверяет с контрактом §2: совпадает — оставить; расходится — править. Новых имён файлов сверх §2 не плодить. **`pfs_batch` / ProtocolFromSummary / `jobs.json` запись `a6e62d06249f` — не трогать.**

| Артефакт | На диске 09.09 | Цель плана | Делать на HF:impl |
|---|---|---|---|
| `~/.hermes/pii_scan/patterns.py` | **есть**, фиксы 09.09: логин не идентификатор, `_is_plausible_internal_login`, PHONE только `+7`/`8`, `SECRET_ASSIGNMENT` lookbehind, `CREDENTIAL_PATTERNS` | канон §3/§6 | keep; точечно сверить regex с ТЗ; не возвращать логин в идентификаторы |
| `~/.hermes/pii_scan/pii_scan.py` | **есть**: `detect_pii_in_context` только FIO; `scan_json_file` по полям + fallback `scan_text_file`; `path={finding.path!r}`; `mask_*` свои; whitelist +Confluence/Projects(весь)/Meetings; Miro-carve-out; vanished: `open`→ErrorBus, `baseline` напрямую | канон §3/§5/§6/§8.4/§9 | **дельта:** добавить корень `~/USERTOOLS/` в `iter_scan_files` (§4); убрать мёртвые импорты `INTERNAL_LOGIN*`; не сбрасывать `baseline.json` |
| `~/.hermes/pii_scan/redact.py` | **есть** `redact_fio_email_phone` (ФИО/email/тел/креды; логин/`@handle` не трогает) | §9 / §14.1 | keep; не импортировать `mask_pii` |
| `~/.hermes/scripts/pii_scan.sh` | **есть**, fail-soft `exit 0`; **PYTHONPATH тянет AnywhereContacts** | §10 / §14 | **убрать** PYTHONPATH на AnywhereContacts (маскирование своё, §9) |
| `~/.hermes/pii_scan/tests/{conftest.py,test_pii_scan.py}` | **есть**, 22 pytest в cache `nodeids` (login≠ПДн, Miro≠кред, JSON не-декартово, whitelist-зоны) | §17 п.10 | keep 22 имени; **добавить** 3–4 теста покрытия дыр (§3): JSON fallback, baseline-vanished, USERTOOLS-обход, нет `login+*` в новых находках |
| `~/.hermes/pii_scan/baseline.json` + `audit_history.jsonl` | **есть** (прогон 27.08, много `login+*` status=baseline) | §7/§8 | **не сбрасывать, не DELETE**; инкремент сам уведёт vanished `login+*` в `resolved` |
| `~/USERTOOLS/MoveFromLoop/movefromloop/formatter.py` | **есть** `format_post`: `first_line` через `redact_fio_email_phone`; `@username` не трогает; fail-soft import | §14.1 | keep, если контракт совпадает |
| `~/USERTOOLS/ExchangeMonitor/exchangemonitor/formatter.py` | **есть** `format_email`: `essence` через redact | §14.1 | keep |
| `~/.hermes/scripts/error_bus_cli.py` `cmd_show` | **есть** redact row/cron/log/session | §14.1 | keep; **не** расширять redact на `cmd_list` (ТЗ требует только `cmd_show`); **не** трогать `_db.py` |
| `~/hermes-agent/gateway/run.py` INFO inbound | **есть** (стр. ~16475): `inbound message: platform=%s user=%s chat=%s reply_to_id=%s` — без `msg=`/`reply_to_text=` | §14.1 | keep; **не** трогать инъекцию `reply_to_text` в `message_text` агента (это не лог). Pitfall merge — в docs-handoff |
| `~/hermes-agent.next/gateway/run.py` | есть (апстрим-кандидат) | §14 | **не трогать** |
| `~/USERTOOLS/TaskRefresh/taskrefresh/config.py` | **есть** `HISTORY_TTL_DAYS = 5` | §14.1 / §17 п.11 | keep |
| `~/USERTOOLS/TaskRefresh/taskrefresh/session_store.py` | **есть** `prune_history()` вызывается из `save_session`; `current.json`/`pending_apply.json` не трогает | §14.1 | keep |
| `~/USERTOOLS/TaskRefresh/tests/test_session_store.py` | **есть** `test_prune_history_removes_old_keeps_fresh` | §17 п.11 | keep |
| **Факт пути сессии TaskRefresh** | `VAULT_ROOT = ~/WorkVault/Tools/TaskRefresh` → `session/history/` **уже в обходе WorkVault** (не whitelist). ТЗ пишет `~/USERTOOLS/TaskRefresh/session/` — это **код** пакета, не runtime-кэш | §4/§5 | сканировать обе зоны; whitelist **не** расширять; в документах поправить фактический путь |
| `~/.hermes/scripts/llm_anomaly_scan.sh` | **есть** `find … -mtime +5 -delete` + компакт `{subtype,is_error,result}` | §14.1 | keep |
| `~/.hermes/skills/devops/hermes-cost-audit/SKILL.md` | **есть** питфолл TTL(5д)<цикла(7д) | pii-rule P1 | keep |
| `~/.hermes/skills/devops/pii-data-scanning/SKILL.md` | **есть** v1.1.0, правило 09.09; **нет** в `hermes-workspace/skills/` (не симлинк) | направление 6 | добить §4 USERTOOLS, §8.4 split-resolve, фактический путь TaskRefresh; version bump на docs-handoff |
| `…/references/pii-errorbus-triage.md` | **есть**, баннер «УСТАРЕЛО»; хвост «Направления фикса» противоречит ТЗ (whitelist TaskRefresh/TZ) | направление 6 | синхронизировать баннер + вычеркнуть противоречащие пункты 3–4 хвоста |
| `TZ/pii-privacy/pii_impl_plan.md` приложение 09.09 | **есть**; whitelist всё ещё «Projects/TrisigmaFull (НЕ весь Projects)» — **устарело vs ТЗ v1.2.0** | направление 6 | поправить на **весь** `Projects/` |
| `…/references/pii-rule-20260909.md` | **есть**, канон 09.09; пункт про `pfs_batch.sh`-обёртку **перекрыт** решением «не трогать pfs_batch» | направление 6 | пометка «pfs_batch — вне этой CHANGE» |
| `hermes-feature/references/hermes-upgrade-pattern.md` | **нет** питфолла `inbound msg=` | §14.1 | добавить строку на `HF:docs-handoff` |
| `jobs.json` `vm_selfcheck` п.12 | **уже есть** `bash ~/.hermes/scripts/pii_scan.sh` | §11/§14 | **не** пересоздавать крон; правку формулировки промпта («идентификатор=только ФИО») — только по явному императиву |
| `instrumentation_registry.json` | записи `PIIScan` **нет** | §13 | **не** добавлять |
| `pfs_batch` (`jobs.json` `a6e62d06249f`, `python -m protocolfromsummary run-pending`, `no_agent: false`) | живой агентный крон | §14 / §14.1 | **НЕ ТРОГАТЬ** (не no_agent, не redact-обёртка, не `__main__.py`) |
| `report_error.sh`, `_db.py`, `events.db` схема, `cron/scheduler.py`, `anywhere_contacts/logger.py`, `state.db`, `_Archives`, `mfl_digest.py` | на месте | §14 | **не трогать** |
| `TZ/PIIScan/PIIScan_TZ.md`, `MAIN_TZ_INVENTORY.md` | v1.2.0 released | — | **не трогать** исполнителем (уже финал) |
| `EcosystemManifest.json`, `restore-all-skills.sh`, `.env` | — | ORCH | **нет** (только `ORCH:shared-state`) |

---

## 1. Цель фазы и критерии «готово»

### 1.1 Цель HF:plan

Пофайловый план CHANGE: закрыть дельту ТЗ v1.2.0 поверх уже лежащих 09.09-фиксов (детектор, whitelist, гигиена на записи, TTL, 22 теста) **без** повторной реализации с нуля и **без** `pfs_batch`.

### 1.2 Критерии «готово» этой фазы (HF:plan)

- Этот файл записан в `TZ/PIIScan/plans/HF-plan_PIIScan-pii-hygiene_20260909.md`.
- Покрыты ТЗ §1–§17 (цель, правило ПДн, зоны, whitelist, креды, baseline, дедуп/резолв, маскирование, компоненты, vm_selfcheck, registry, «не трогать», гигиена §14.1, риски, связи, 11 критериев готовности). §18 открытых вопросов нет — развилок на Сашу в этом плане нет.
- Код скилла / `pii_scan/*.py` / `gateway/*.py` / `USERTOOLS/*` / `scripts/*` / мастер-ТЗ / инвентарь / манифест **не** изменены этим вызовом.

Снятие `GATE:plan-approve` — **не** эта фаза. Реализация — `HF:impl` (исполнитель `composer-2.5`).

### 1.3 Критерии «готово» всей CHANGE (ориентир хвоста)

ТЗ §17, 11 пунктов. Коротко: `pii_scan.sh` fail-soft exit 0; baseline = один info без critical; инкремент = один critical на новую находку, `path={path!r}`; vanished `open`→`error_bus_cli resolve`, vanished `baseline`→напрямую без `events.db`; нет сырых ПДн/секретов в baseline/audit/message/stdout; whitelist+state.db не читаются; нет записи в `instrumentation_registry.json`; нет новых `login+*`; Miro URL-token ≠ кред; гигиена логов §14.1; 22 pytest зелёные; TaskRefresh TTL=5 / `prune_history`.

---

## 2. Пофайловый план

Python: stdlib (`re`, `hashlib`, `json`, `pathlib`, `sqlite3`). Интерпретатор: `~/hermes-agent/.venv/bin/python3`. AnywhereContacts **не** импортировать.

Общий контракт: исполнитель идёт сверху вниз. Если функция уже совпадает с сигнатурой/поведением ниже — не переписывать.

---

### 2.1 `~/.hermes/pii_scan/patterns.py` — regex §3/§6

**Назначение.** Детерминированные паттерны идентификатора/атрибутов/кредов. Логин **не** идентификатор ПДн.

**Ожидаемое состояние (уже на диске) vs дельта:**

| Уже есть | Править на HF:impl |
|---|---|
| `FIO_PATTERN` 2–3 слова кириллицы с заглавной | нет, если regex не сломан тестами |
| `INTERNAL_LOGIN_PATTERN` + `_is_plausible_internal_login` (файл.ext / TLD / `a.b.c` отсекаются) — **не** вызывается из `detect_pii_in_context` | **оставить** паттерн (может жить вне правила ПДн); не подключать обратно как идентификатор |
| `PHONE_PATTERN` только `(?<!\d)(?:\+7\|8)…` — ветки `\d{10,15}` нет | не возвращать `\d{10,15}` |
| `SECRET_ASSIGNMENT_PATTERN` с `(?<![A-Za-z0-9_])` | keep |
| `CREDENTIAL_PATTERNS`: aws/openai/tg/secret_assignment/bearer/pem | keep; AWS/sk-/Bearer/PEM не резать Miro-carve-out'ом |

**Сигнатуры (канон, не менять имена):**

```python
FIO_PATTERN: Pattern[str]
INTERNAL_LOGIN_PATTERN: Pattern[str]
def _is_plausible_internal_login(text: str, start: int, end: int) -> bool
EMAIL_PATTERN: Pattern[str]
PHONE_PATTERN: Pattern[str]
MESSENGER_HANDLE_PATTERN: Pattern[str]
POSITION_PATTERN: Pattern[str]
SECRET_ASSIGNMENT_PATTERN: Pattern[str]
CREDENTIAL_PATTERNS: tuple[tuple[Pattern[str], str], ...]
MAX_TEXT_FILE_BYTES: int  # 5 * 1024 * 1024
```

**Вход/выход:** модуль констант; вызывается из `pii_scan.py` и `redact.py`.

**Boundary / НЕ трогать:** не импортировать AnywhereContacts; не ослаблять lookbehind; не добавлять логин в набор идентификаторов.

**Кого вызывает:** `pii_scan.detect_*`, `redact.redact_fio_email_phone`.

---

### 2.2 `~/.hermes/pii_scan/pii_scan.py` — точка входа

**Назначение.** Обход §4 минус whitelist §5; детект §3/§6; дедуп §8; report/resolve; стерильные `mask_*` §9.

**Сигнатуры (канон — уже есть, не переименовывать):**

```python
def mask_identifier(value: str, kind: str) -> str
def mask_attribute(value: str, attr_kind: str) -> str
def mask_credential(value: str, field_type: str) -> str
def build_error_message(finding: Finding) -> str   # path={finding.path!r}
def build_error_detail(finding: Finding) -> str
def detect_pii_in_context(text: str, norm_path: str) -> list[Finding]
def _is_miro_live_embed_query_token(text: str, start: int) -> bool
def detect_credentials_in_context(text: str, norm_path: str) -> list[Finding]
def collect_string_values(obj: Any) -> Iterator[str]
def scan_json_file(path, norm_path, config, result) -> list[Finding]
def scan_jsonl_file(...) -> list[Finding]
def scan_text_file(...) -> list[Finding]          # строка, иначе окно ±1
def ScanConfig.whitelist_prefixes() -> list[Path]
def ScanConfig.is_whitelisted(path: Path) -> bool
def iter_scan_files(config: ScanConfig) -> Iterator[Path]
def run_baseline_mode / run_incremental_mode / run_scan / main
```

**Контракт `detect_pii_in_context`:** идентификаторы **только** `FIO_PATTERN`. Декартово `fio × attr` **внутри одного контекста**. `field_type` ∈ `fio+email|fio+phone|fio+handle|fio+position`. Голый логин без ФИО → пустой список ПДн.

**Контракт `scan_json_file`:** `json.loads` → каждое строковое поле отдельно (не декартово по соседним ключам объекта). `JSONDecodeError` → fallback-text (`scan_text_file`), **не** бросать исключение. (На диске так и есть.)

**Контракт message:** `path={finding.path!r}` — уже в `build_error_message` / `build_error_detail`.

**Контракт vanished §8.4 (уже есть):**

- `status=open` + `error_bus_message` → read-only SELECT `events.db` → ровно 1 open → `error_bus_cli.py resolve`; 0 или >1 → warning в stdout, прогон не фейлить.
- `status=baseline` → `resolved` в `baseline.json` + `audit_history.jsonl` `event: resolved`, **без** `events.db`.
- `persisting` → только `last_seen`, без повторного `report_error.sh`.
- Записи baseline **не удалять**.

**Дельты HF:impl (обязательные):**

1. **`iter_scan_files` — добавить корень `~/USERTOOLS/`** (ТЗ §4 v1.2.0: зона сканируется, TaskRefresh session **не** whitelist). Сейчас корни: `sessions/*.jsonl`, `WorkVault`, `WorkVault_backup`, `cron/output`, `logs`, `error_bus`. `USERTOOLS` отсутствует.
2. В `ScanConfig` поле `usertools: Optional[Path] = None` → default `home / "USERTOOLS"`. Тесты подменяют.
3. **Калибровка объёма (§15 риск 1, не новая сущность):** при обходе USERTOOLS (и желательно WorkVault) skip каталогов `.venv`, `venv`, `venv_linux`, `__pycache__`, `.git`, `node_modules`, `.pytest_cache`. Иначе скан утонет в site-packages. Это не whitelist ПДн, а skip бинарного/вендорного шума.
4. Удалить **мёртвый код**: импорты `INTERNAL_LOGIN_PATTERN`, `_is_plausible_internal_login`; неиспользуемую `_login_in_email_domain` (не вызывается после ухода логина из идентификаторов).
5. **Не сбрасывать** живые `baseline.json` / `audit_history.jsonl`. Старые ключи `login+*` уйдут в `resolved` следующим инкрементом (pii-rule: «baseline НЕ сбрасывать»).
6. Опционально: для vanished `status=baseline` инкрементировать `result.resolved_count` (сейчас счётчик только ErrorBus-resolve) — чтобы stdout «резолвнуто=N» не врал. Поведение на диск не меняет.

**Whitelist (уже есть, не сужать):**

`Contacts/`, `Entities/`, `Inbox/`, `UserManuals/`, `Confluence/`, `Projects/` (**весь**), `Meetings/`. Префикс абсолютного пути **до** чтения файла. `state.db` — `is_state_db`, не открывать.

**НЕ в whitelist:** `~/USERTOOLS/**` (в т.ч. код TaskRefresh), `~/WorkVault/Tools/TaskRefresh/session/` (фактический кэш, TTL 5д), `Hermes-Backlog/TZ/**`, `~/.hermes/error_bus/tests/`.

**Boundary / НЕ трогать:** `state.db`; `_db.py` / `report_error.sh`; SQL `UPDATE` в `events.db` (только CLI resolve); `mask_pii` AnywhereContacts; `pfs_batch`; `hermes-agent.next`.

**Кого вызывает:** `pii_scan.sh` → `main()` → `run_scan` → `report_error.sh` / `error_bus_cli.py resolve`.

---

### 2.3 `~/.hermes/pii_scan/redact.py` — гигиена на записи

**Назначение.** `redact_fio_email_phone(text)` для логов/дайджестов. Логины и `@handle` сохраняет. Не `mask_pii`.

**Сигнатуры:**

```python
def redact_fio_email_phone(text: str) -> str
def redact_fio_email_phone_preserve_handle(text: str) -> str  # alias, keep
```

**Дельта:** keep. Опционально убрать неиспользуемый импорт `MESSENGER_HANDLE_PATTERN`. Не менять семантику (не маскировать `@handle`).

**Кого вызывает:** MFL `format_post`, ExchangeMonitor `format_email`, `error_bus_cli.cmd_show`. Fail-soft `try/except ImportError → identity` у потребителей — оставить.

---

### 2.4 `~/.hermes/scripts/pii_scan.sh` — fail-soft обёртка

**Назначение.** Активация venv, запуск `pii_scan.py`, всегда `exit 0` (§17 п.1).

**Дельта:** убрать `PYTHONPATH` на `~/USERTOOLS/AnywhereContacts` и её `.venv/site-packages` (нарушает §9/§14: AnywhereContacts не используется для хранения). Оставить выбор python: `~/hermes-agent/.venv/bin/python3` с fallback `command -v python3`. `|| true` + `exit 0` сохранить.

**НЕ трогать:** `report_error.sh` рядом в `scripts/`.

---

### 2.5 Гигиена логов — потребители `redact` / gateway

Все четыре точки **уже пропатчены 09.09**. На `HF:impl`: прочитать и сверить; править только при расхождении.

#### 2.5.1 `~/USERTOOLS/MoveFromLoop/movefromloop/formatter.py`

**Сигнатура:** `def format_post(post: dict, channel_display: str, author_username: str) -> str`

**Контракт:** `first_line = redact_fio_email_phone(truncate_first_line(message))`; строка `от @{author_username}` **без** redact (ТЗ: `@username` не трогать).

**НЕ трогать:** `mfl_digest.py` верхнеуровнево (§14).

#### 2.5.2 `~/USERTOOLS/ExchangeMonitor/exchangemonitor/formatter.py`

**Сигнатура:** `def format_email(...) -> str`

**Контракт:** `essence = redact_fio_email_phone(_build_essence(...))`. Поле `от {fio}` — отображаемое имя в дайджесте; **не** расширять redact на `fio` без новой команды (ТЗ говорит «суть (subject/сниппет)»).

#### 2.5.3 `~/.hermes/scripts/error_bus_cli.py`

**Сигнатура:** `def cmd_show(args) -> int`

**Контракт (уже есть):** redact строковых полей row; cron body `[:8000]`; `session_info`; `errors.log` tail. Import redact fail-soft.

**НЕ трогать:** `_db.py`, `resolve_error`, схему `events.db`, `cmd_resolve` SQL. `cmd_list` печатает `message[:50]` без redact — **не** расширять в этой CHANGE (ТЗ: только `cmd_show`).

#### 2.5.4 `~/hermes-agent/gateway/run.py`

**Контракт INFO:** без `msg=` / `reply_to_text=` в `logger.info("inbound message: …")`. На диске: `platform=%s user=%s chat=%s reply_to_id=%s`.

**НЕ трогать:** блок инъекции `reply_to_text` в `message_text` агента (~16258) — это runtime-контекст модели, не `gateway.log`. Не править `hermes-agent.next`. Не рестартовать Gateway.

**Документ (HF:docs-handoff, не impl-код):** в `hermes-feature/references/hermes-upgrade-pattern.md` строка: локальный патч INFO inbound разъедется при merge upstream — переносить руками вместе с retry в `DeliveryTransport`.

---

### 2.6 TTL 5 дней

#### 2.6.1 `~/USERTOOLS/TaskRefresh/taskrefresh/config.py`

**Уже есть:** `HISTORY_TTL_DAYS = 5`. Keep.

**Факт пути:** `VAULT_ROOT = ~/WorkVault/Tools/TaskRefresh`, `HISTORY_DIR = …/session/history`. Это **не** `~/USERTOOLS/TaskRefresh/session/`. В документах писать оба пути: код пакета vs runtime-кэш vault.

#### 2.6.2 `~/USERTOOLS/TaskRefresh/taskrefresh/session_store.py`

**Сигнатуры (уже есть):**

```python
def save_session(...) -> Path   # в конце: prune_history(history_dir, ttl_days=HISTORY_TTL_DAYS)
def prune_history(history_dir: Path = HISTORY_DIR, ttl_days: int = HISTORY_TTL_DAYS) -> int
```

**Контракт:** unlink только `history_dir/*.json` с mtime старше TTL; `current.json` / `pending_apply.json` не трогать. Keep.

#### 2.6.3 `~/.hermes/scripts/llm_anomaly_scan.sh`

**Уже есть:** после `mkdir -p` — `find "$OUTDIR" -maxdepth 1 -name 'LLM-anomalies_*.json' -mtime +5 -delete`; после прогона — компакт `{subtype,is_error,result}` без tool/conversation payload. Keep. Питфолл TTL<7д уже в `hermes-cost-audit/SKILL.md` — не дублировать логику.

---

### 2.7 Документы (направление 6) — предпочтительно `HF:docs-handoff`, мелкие правки допустимы в impl если исполнитель уже в файле

Мастер-ТЗ и инвентарь **не** трогать (v1.2.0 финал).

| Файл | Дельта |
|---|---|
| `~/.hermes/skills/devops/pii-data-scanning/SKILL.md` | Таблица зон: добавить `~/USERTOOLS/` (critical, сканируется). Split-resolve §8.4 (baseline vs open). Фактический путь TaskRefresh = `WorkVault/Tools/TaskRefresh/session/`. Убрать формулировки «баги детектора под фикс P0» как ещё открытые — они закрыты кодом; оставить как историю. PFS: «не трогать в этой CHANGE». Version bump (например 1.2.0) на docs-handoff. Скилл **нет** в `hermes-workspace/skills/` — ORCH решает, копировать ли для `restore-all-skills.sh` |
| `…/references/pii-errorbus-triage.md` | Баннер «УСТАРЕЛО» keep. Вычеркнуть/пометить противоречия: «расширить whitelist TaskRefresh/TZ», «доработать pfs_batch» — перекрыто ТЗ v1.2.0 |
| `…/references/pii-rule-20260909.md` | Пометка: `pfs_batch.sh`-обёртка / no_agent — **вне** этой CHANGE (решение Саши 09.09). Whitelist Projects = **весь** |
| `TZ/pii-privacy/pii_impl_plan.md` приложение 09.09 п.2 | Заменить «Projects/TrisigmaFull (НЕ весь Projects)» → **весь `Projects/`** (синхрон с ТЗ v1.2.0 §5) |
| `hermes-feature/references/hermes-upgrade-pattern.md` | Строка питфолла gateway INFO inbound (см. 2.5.4) |
| `hermes-cost-audit/SKILL.md` | keep (питфолл TTL уже есть) |

**Не создавать** `SelfCheck_TZ.md`. **Не** писать `EcosystemManifest.json`.

---

### 2.8 Тесты — `~/.hermes/pii_scan/tests/`

См. §3. `conftest.py`: whitelist-зоны Confluence/Projects(весь, в т.ч. Other)/Meetings уже создаются. **Добавить** в фикстуру `scan_env`: `home/USERTOOLS/` (+ опц. фейковый `.venv` для проверки skip).

---

### 2.9 Явно не создавать / не трогать

- `pfs_batch`: крон `a6e62d06249f`, промпт, `no_agent`, `USERTOOLS/ProtocolFromSummary` (`python -m protocolfromsummary run-pending`), stdout в `cron/output/a6e62d06249f/`.
- `report_error.sh`, `_db.py`, схема `events.db`, `cron/scheduler.py`, `mfl_digest.py`.
- `anywhere_contacts/logger.py` (`mask_pii`).
- `~/.hermes/state.db` (даже read-only).
- `hermes-agent.next`, `_Archives`.
- `instrumentation_registry.json`, `jobs.json` (п.12 уже вставлен; крон не пересоздавать, Gateway не рестартовать).
- Мастер-ТЗ, `MAIN_TZ_INVENTORY.md`.
- Сброс/TRUNCATE `baseline.json` / `audit_history.jsonl`.

---

## 3. Тест-план

**Канон запуска (`HF:test`):**

```bash
cd ~/.hermes/pii_scan
~/hermes-agent/.venv/bin/python3 -m pytest tests/test_pii_scan.py -q
```

Интерпретатор тот же, что `pii_scan.sh`. Сеть не нужна. Живой `~/WorkVault` / живой `baseline.json` тесты **не** читают (`scan_env` = tmp_path).

### 3.1 Двадцать два обязательных pytest (уже на диске — имена не менять)

Критерий §17 п.10: все 22 зелёные. Соответствие cache `nodeids` 09.09:

| # | Тест | Критерий pass |
|---|---|---|
| 1 | `test_baseline_run_creates_baseline_and_info_report` | mode=baseline; 1× severity=info; 0× critical; `baseline.json` status=baseline; audit `baseline_seen` |
| 2 | `test_incremental_new_finding_reports_single_critical` | ровно 1 critical на новую находку; persisting без повторного critical |
| 3 | `test_vanished_finding_resolves_open_error` | `status=open` → `resolve` ровно 1 id; audit `resolved`; строки не DELETE |
| 4 | `test_sterile_mask_examples` | email маскирует local **и** domain; ≤3 → `****` |
| 5 | `test_no_unmasked_values_in_outputs` | нет сырого ФИО/email/AWS в baseline/audit/message/detail/stdout |
| 6 | `test_whitelist_and_state_db_not_opened` | Contacts/Entities/Inbox/UserManuals и `state.db` не в `opened_paths` |
| 7 | `test_pii_rule_requires_identifier_and_attribute` | только ФИО или только email → 0 pii; связка → pii |
| 8 | `test_credential_detected_without_pii_combo` | секрет без ФИО → credential |
| 9 | `test_dedup_message_format_masked` | message без сырых значений, есть `pii_card` |
| 10 | `test_login_without_fio_is_not_pii` | голый логин+email/@handle/должность → 0 pii_card |
| 11 | `test_login_plus_fio_plus_attr_is_pii` | логин + «Иванов Иван» + email → `fio+email` |
| 12 | `test_two_word_fio_is_identifier` | «Иван Петров»+email → инцидент |
| 13 | `test_miro_board_token_not_credential` | `https://miro.com/…?boardAccessToken=…` → 0 credential |
| 14 | `test_bare_token_assignment_still_credential` | `password: supersecretvalue123` → `secret_assignment` |
| 15 | `test_filename_not_login` | `файл.md`/`config.yaml`+должность → 0 pii, нет `login+*` |
| 16 | `test_domain_not_login` | `tutu.ru`/`dom.tutu`+email → 0 pii |
| 17 | `test_tg_id_not_phone` | `-100…` / unix + ФИО → нет `fio+phone` |
| 18 | `test_plus7_phone_with_fio_is_pii` | «Иван Петров +7 999 123-45-67» → `fio+phone` |
| 19 | `test_json_no_cartesian_across_fields` | JSON `name` и `email` в **разных** полях → 0 pii |
| 20 | `test_json_same_field_fio_email_is_pii` | ФИО+email в **одном** строковом поле → pii |
| 21 | `test_message_quotes_path_with_spaces` | path с пробелом → `path='…foo bar.md'` (`!r`) |
| 22 | `test_whitelist_new_zones_not_scanned` | Confluence / Projects/TrisigmaFull / Projects/Other / Meetings нет в baseline; `Hermes-Backlog/TZ` есть |

### 3.2 Добавить на HF:impl (сверх 22; §17 п.10 не ломают)

Не заменять 22. Новые имена:

| Тест | Вход | Ожидание |
|---|---|---|
| `test_invalid_json_fallback_text` | файл `.json` с невалидным JSON, в тексте «Иван Петров email: a@b.ru» | не exception; инцидент как у текста |
| `test_baseline_vanished_resolves_without_events_db` | ключ `status=baseline` исчез → `resolved` + audit `resolved`; `resolves==[]` |
| `test_no_login_star_field_type_in_new_findings` | тексты с логином | ни один `field_type` не начинается с `login+` |
| `test_usertools_is_scanned_not_whitelisted` | `USERTOOLS/foo.md` с ФИО+email в tmp home | файл в `opened_paths` / baseline; `.venv` внутри USERTOOLS **не** открывается |

TaskRefresh: существующий `test_prune_history_removes_old_keeps_fresh` гонять на `HF:test` из `~/USERTOOLS/TaskRefresh` (не вместо 22).

### 3.3 Ручные / интеграционные (HF:test, не live-Telegram)

- `bash ~/.hermes/scripts/pii_scan.sh` → exit 0 всегда (даже если python упал).
- Grep INFO `inbound message` в свежем `gateway.log` — нет `msg=` / `reply_to_text=`.
- `error_bus_cli.py audit` — нет новой записи `PIIScan` в registry (конфликтов A/B нет).
- Не гонять полный прод-скан WorkVault+USERTOOLS на HF:impl без нужды (тяжёлый, §15.1); достаточно pytest + точечный прогон на `scan_env`.

---

## 4. Откат (Блок 5 `hermes-feature`)

### 4.1 Конфиг Hermes

`HF:backup` (координатор) **до** `HF:impl`. Эта CHANGE **может** затронуть `~/hermes-agent/gateway/run.py` (уже патч на диске — бэкапить дерево hermes-agent + `~/.hermes/pii_scan` + затронутые USERTOOLS + `scripts/{pii_scan,llm_anomaly_scan,error_bus_cli}`). `config.yaml` / `jobs.json` исполнитель **не** меняет. Путь архива: `~/.hermes/_Archives/hermes-backup-YYYYMMDD-HHMMSS/`. Хранение 2 недели.

Gateway **не** рестартовать ни при impl, ни при откате (правило профиля).

### 4.2 Код

Откат авария / по ОК Саши: вернуть файлы §2 из архива `HF:backup`. Не `git push --force`. Не чистить `_Archives` моложе 2 недель.

`baseline.json` / `audit_history.jsonl` при откате детектора **не** откатывать вслепую (исторический журнал §8.3). Если impl по ошибке перезаписал baseline — восстановить копию из backup, не из пустого файла.

### 4.3 Кроны / ErrorBus

Кроны не создавались и не пересоздавались — откатывать `jobs.json` нечего. Открытые ErrorBus-строки PIIScan руками не резолвить пакетом (закроются инкрементом).

---

## 5. Риски

| # | Риск | Митигация |
|---|---|---|
| 1 | Добавление `~/USERTOOLS/` без skip `.venv` сделает еженедельный скан непригодным (тысячи файлов site-packages) | skip вендор-каталогов §2.2 п.3; лимит 5MB / null-byte уже есть |
| 2 | Следующий инкремент после фикса правил даст волну vanished `login+*` (тысячи baseline-ключей) + новые находки из USERTOOLS | baseline не сбрасывать; vanished `baseline` без `events.db`; stdout — счётчики, не Telegram на каждую |
| 3 | Ложные ФИО (названия проектов 2 слова с заглавной) | известный trade-off MVP (§15.2); калибровка исключений — после факта, не в этой CHANGE |
| 4 | Локальный патч `gateway/run.py` разъедется при merge upstream | питфолл в `hermes-upgrade-pattern.md`; не патчить `hermes-agent.next` |
| 5 | Fail-soft import redact в MFL/EM: если `redact.py` пропадёт с `sys.path`, гигиена молча отключится | не перемещать `redact.py`; тест import-path не обязателен, но не удалять `pii_scan/` |
| 6 | Исполнитель «допилит» `pfs_batch` по старому pii-rule п.3 | явный запрет §0/§2.9; ревизор смотрит diff ProtocolFromSummary = block |
| 7 | Резолв по `message` 0 или >1 совпадений | уже в коде: warning, не фейл (§15.6) |
| 8 | PYTHONPATH AnywhereContacts в `pii_scan.sh` может снова подтянуть `mask_pii` при случайном импорте | удалить PYTHONPATH в impl |
| 9 | Расхождение пути TaskRefresh (ТЗ USERTOOLS vs факт WorkVault/Tools) | сканировать обе; документы поправить; whitelist не ставить |

Новых сущностей план не вводит.

---

## 6. Прогресс выполнения

Чекбоксы для устойчивости к сбою. Эту фазу отмечает архитектор; хвост — исполнитель/координатор/оркестратор по своим карточкам.

### HF:plan (эта карточка)

- [x] Прочитаны GLOSSARY, `hermes-feature` Блок 1А, master-ТЗ v1.2.0 §1–§18
- [x] Сверка диска: `pii_scan/{patterns,pii_scan,redact,tests}`, `pii_scan.sh`, MFL/EM formatter, TaskRefresh TTL, `llm_anomaly_scan.sh`, `error_bus_cli.cmd_show`, gateway INFO inbound, документы скилла, `pii_impl_plan` appendix, `jobs.json` п.12, `pfs_batch` не трогать
- [x] План-файл записан: `TZ/PIIScan/plans/HF-plan_PIIScan-pii-hygiene_20260909.md`
- [ ] `REV:plan` (ревизор) — **не эта фаза**
- [ ] `GATE:plan-approve` — ждёт Сашу / one-pass

### HF:backup → HF:impl (после approve)

- [ ] `HF:backup`: архив `pii_scan/`, `scripts/{pii_scan,llm_anomaly_scan,error_bus_cli}.sh|.py`, MFL/EM formatter, TaskRefresh config/session_store, `gateway/run.py`
- [ ] `patterns.py` — keep 09.09, логин не идентификатор
- [ ] `pii_scan.py` — USERTOOLS в `iter_scan_files` + skip venv; мёртвые импорты убраны; baseline не сброшен
- [ ] `pii_scan.sh` — PYTHONPATH AnywhereContacts убран; exit 0
- [ ] `redact.py` + потребители MFL/EM/`cmd_show`/gateway — сверка, правки только при расхождении
- [ ] TaskRefresh TTL=5 / `prune_history` — сверка keep
- [ ] `llm_anomaly_scan.sh` компакт + find -mtime +5 — сверка keep
- [ ] Тесты: 22 имени на месте + 4 добавленных §3.2
- [ ] `pfs_batch` / ProtocolFromSummary / `jobs.json` / `state.db` / `_db.py` — не в diff

### HF:test

- [ ] pytest `tests/test_pii_scan.py` — 22 + новые зелёные
- [ ] `test_session_store.py::test_prune_history_removes_old_keeps_fresh` зелёный
- [ ] `bash ~/.hermes/scripts/pii_scan.sh` → exit 0
- [ ] Нет сырых email в тестовом baseline/audit
- [ ] `instrumentation_registry.json` без `PIIScan`

### HF:docs-handoff → ORCH:shared-state → GATE:done

- [ ] SKILL.md v1.2.0: USERTOOLS, split-resolve, путь TaskRefresh, pfs_batch запрет
- [ ] `pii-errorbus-triage.md` хвост не противоречит ТЗ
- [ ] `pii_impl_plan.md` appendix: весь Projects/
- [ ] pitfall gateway inbound в `hermes-upgrade-pattern.md`
- [ ] `manifest_hints` отданы оркестратору (скилл `pii-data-scanning` живёт только в `~/.hermes/skills/`, не в hermes-workspace)
- [ ] `ORCH:shared-state`: restore + манифест (не исполнитель)
- [ ] `GATE:done` после preflight

---

## Приложение A. Карта модулей → вызовы

```
pii_scan.sh
  └─ pii_scan.main / run_scan
        ├─ iter_scan_files (§4: sessions, WorkVault, WorkVault_backup,
        │                     cron/output, logs, error_bus, USERTOOLS)
        │     minus whitelist_prefixes (§5) minus state.db
        ├─ scan_json_file / scan_jsonl_file / scan_text_file
        │     ├─ detect_pii_in_context (FIO × attr)
        │     └─ detect_credentials_in_context (+ Miro carve-out)
        ├─ mask_identifier / mask_attribute / mask_credential
        ├─ report_error.sh --tool PIIScan   (baseline: 1× info; new: critical)
        └─ error_bus_cli.py resolve         (только vanished status=open)

redact.redact_fio_email_phone
  ├─ MoveFromLoop.formatter.format_post
  ├─ ExchangeMonitor.formatter.format_email
  └─ error_bus_cli.cmd_show

TaskRefresh.save_session → prune_history (HISTORY_TTL_DAYS=5)
llm_anomaly_scan.sh → find -mtime +5 -delete + compact JSON
gateway/run.py INFO inbound — без msg=/reply_to_text=
```

## Приложение B. Соответствие 7 направлениям постановщика

| # | Направление | Статус на диске | Действие HF:impl |
|---|---|---|---|
| 1 | patterns.py логин/PHONE/SECRET/Miro | сделано | keep |
| 2 | detect_pii / scan_json / quoting path | сделано | keep + USERTOOLS-обход + cleanup импортов |
| 3 | whitelist +Confluence/Projects/Meetings | сделано (весь Projects) | keep |
| 4 | redact + MFL/EM/cmd_show/gateway/llm compact | сделано | сверка keep |
| 5 | TTL TaskRefresh + llm find -delete | сделано | keep |
| 6 | SKILL / triage / pii_impl_plan | частично устарело | точечный sync §2.7 |
| 7 | 22 pytest | 22 имени есть | keep + 4 теста дыр |
| — | pfs_batch | не менялся | **не трогать** |
