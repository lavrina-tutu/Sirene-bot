---
name: cron-troubleshooting
description: "Use when: no_agent cron silent failures or venv mismatches."
version: 1.0.1
author: agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [cron, troubleshooting, no_agent, venv, sys.path, diagnostics]
    related_skills: [hermes-feature, hermes-ops]
---

# cron-troubleshooting

## Overview

Диагностика фоновых кронов Hermes: когда скрипт не работает, молчит, или выдаёт неожиданный результат.

## When to Use

- «Крон не работает» / «крон молчит» / «не получаю уведомления от крона»
- no_agent скрипт не выводит результат
- Подозрение на проблему с sys.path / venv в крон-окружении

## Diagnostic Steps

### 0. Самоидентификация (для агентных кронов)

Когда агентный крон (`no_agent=false`) запущен, `HERMES_CRON_JOB_ID` может быть пустым. Чтобы понять кто ты:

```python
import json
with open(f'{home}/.hermes/cron/jobs.json') as f:
    jobs = json.load(f)['jobs']
# Найти кроны, у которых last_run_at совпадает с временем старта сессии
# Поле ключа: 'id' (не 'job_id')
```

Или — посмотреть output-директории по времени изменения и сопоставить с `last_run_at`:
```bash
ls -lt ~/.hermes/cron/output/ | head -10
```

### 1. Проверить крон-реестр

```python
import json
with open("~/.hermes/cron/jobs.json") as f:
    jobs = json.load(f)["jobs"]
```

Искать по имени/скрипту. Проверить: `enabled`, `schedule`, `script`, `no_agent`, `workdir`, `last_status`, `last_run_at`.

### 2. Проверить логи выполнения

```python
import sqlite3
conn = sqlite3.connect("~/.hermes/cron/executions.db")
# columns: id, job_id, source, process_id, pid, process_started_at, status, claimed_at, started_at, finished_at, error
```

Или файлы логов: `~/.hermes/cron/output/<job_id>_*.txt`

### 3. Проверить окружение исполнения (КРИТИЧНО для no_agent)

no_agent скрипты запускаются интерпретатором из **venv Hermes-а** (обычно `hermes-agent/.venv/bin/python`),
а не из project-venv.

**Обязательная проверка:**
```python
import sys
print(f"Python: {sys.executable}")
print(f"sys.path: {sys.path}")
```

Если зависимости проекта (exchangelib, и т.д.) в другом venv — скрипт упадёт на импорте, но
в no_agent режиме stderr не доставляется → пользователь видит тишину.

### 4. Ручной запуск скрипта

Запустить скрипт напрямую, используя тот же интерпретер, что крон:
```bash
# Узнать какой Python использует крон:
hermes-agent/.venv/bin/python ~/.hermes/scripts/<script_name>.py 2>&1
```

### 5. Запуск через cronjob repeat=1

```python
cronjob(action='create', name='test-<x>', repeat=1, schedule='1m',
        script='<script_name>.py', no_agent=True, workdir='<workdir>', deliver='origin')
```

Вывод придёт в чат. Это надёжнее чем `hermes cron run` из CLI (не работает при мульти-профиле).

## Common Pitfalls

### sys.path / venv mismatch (ExchangeMonitor)

**Проблема:** Крон `no_agent=true` использует `hermes-agent/.venv/bin/python`, где нет `exchangelib`.
Скрипт падает на импорте, ошибка ловится в `try/except` → exit 0 → stdout пустой → тишина.

**Фикс:** Добавить project venv site-packages в `sys.path` перед импортом:
```python
_VENV = Path("/home/tkachenkoav/USERTOOLS/MoveFromLoop/venv_linux/lib/python3.11/site-packages")
if _VENV.exists():
    sys.path.insert(0, str(_VENV))
```

### «Claim job» — фантомные кроны с prompt='x'

**Проблема:** в реестре кронов есть записи с именем `claim job`, `prompt='x'` (1 символ), без `skills`/`context_from`, deliver=`local`. Модель «freestyle-ит» диагностику из system prompt. Множественные копии (до 9 шт.) жгут токены впустую.

**Диагностика:**
```bash
python3 -c "
import json
with open('$HOME/.hermes/cron/jobs.json') as f:
    jobs = json.load(f)['jobs']
for j in jobs:
    if 'claim' in j.get('name','').lower():
        print(f'{j[\"id\"]} | prompt={repr(j[\"prompt\"])} | skills={j.get(\"skills\")} | deliver={j.get(\"deliver\")}')
"
```

**Фикс:** удалить лишние `hermes cron delete <id>`. Оставить максимум 1 с внятным промптом.

**Прецедент:** 14.08.2026 — 9 claim job созданы 07.08.2026, 6/9 отвечают `[SILENT]`, 3/9 — случайные диагностические заметки. Полный аудит: `references/claim-job-audit-2026-08-14.md`.

### no_agent symlink — блокировка крона (Blocked: resolves outside scripts/)

**Проблема:** no_agent крон падает с `Blocked: script path resolves outside the scripts directory`.
**Причина:** `~/.hermes/scripts/<script>` — симлинк на файл за пределами `~/.hermes/scripts/`. no_agent раннер резолвит симлинк и блокирует.

**Диагностика:** `ls -la ~/.hermes/scripts/<script>` — виден симлинк.
**Фикс — заменить симлинк на враппер:**
```bash
rm ~/.hermes/scripts/<script>        # удалить симлинк
cat > ~/.hermes/scripts/<script> << 'WRAPPER'
#!/bin/bash
# Wrapper: real script lives elsewhere; no_agent runner blocks symlinks
set -euo pipefail
exec bash "$HOME/<реальный_путь>/<script>"
WRAPPER
chmod 711 ~/.hermes/scripts/<script>
```

**Прецедент:** 15.08.2026 — `restore-skills-daily` (74c93fa1e357), симлинк `restore-all-skills.sh` → `~/hermes-workspace/restore-all-skills.sh`, падал с 04.08. Починена заменой на враппер.

**Связано:** `check-cron-results` → «no_agent Script — симлинк резолвится вне scripts/» — там описана диагностика.

### no_agent missing dependency — exit code 127 + «No such file»

**Проблема:** no_agent крон раньше работал, но после удаления/переименования скрипта-зависимости падает с `exit code 127` и `stderr: <path>: No such file or directory`.

**Диагностика:**
1. Прочитать output крона — найти `exit code 127`
2. stderr укажет какой файл не найден
3. Если крон — враппер/скрипт, проверить внутренние вызовы (`grep` на `$SCRIPT_DIR`, `source`, прямой вызов `.sh`)
4. Причина: зависимость (скрипт, который вызывает основной скрипт) удалена при чистке, а ссылка на неё осталась

**Фикс:**
- Если зависимость больше не нужна — убрать вызов из основного скрипта
- Если нужна — восстановить файл из бэкапа или переписать

**Прецедент:** 15.08.2026 — `GitHub автосинк` (5d16b96a9ed5). `restore-all-skills.sh` вызывал `link-tzdev-to-default.sh`, который был удалён при чистке tz-dev профиля. Починено удалением вызова.

### Bash-обёртка прячет traceback под голым exit-кодом

**Проблема:** `no_agent` крон падает (`last_status="error"`, `last_error="Script exited with code N"`), но ручной запуск самого `.sh`-скрипта возвращает ТОЛЬКО `exit N` без единой строки ошибки.

**Причина:** обёртка вызывает CLI через подстановку `OUTPUT=$(<cmd> 2>&1)` (stdout+stderr уходят в переменную) и в ветке ошибки делает `exit $EXIT_CODE`, не печатая `$OUTPUT`. Traceback перехвачен подстановкой и выброшен — на экране только код выхода. Это норм. для обёрток, которые пишут в свою шину/журнал, но убивает ручную диагностику запуском `.sh`.

**Фикс-диагностика — понять, какой интерпретер/venv и КАКУЮ команду зовёт обёртка (grep `source`/`activate`/`VENV`/`cd`/`$OUTPUT=$(`), затем запустить ГЛУБОЖЕ, напрямую CLI в том же venv, мимо обёртки:**
```bash
VENV="<путь из обёртки>/bin/activate"; DIR="<каталог из обёртки>"
cd "$DIR"; source "$VENV"; unset <переменные, что обёртка unset'ит>
<команда CLI> 2>&1   # напр. mofs run --mode=cron
```
Только прямой вызов CLI покажет настоящий traceback (NameError/import/прочее).

**Правило:** при «скрипт упал с кодом N, но stderr молчит» — не читать обёртку как источник ошибки; найти внутренний вызов и запустить CLI напрямую. Также смотреть в jobs.json `failure_streak`/`last_status`/`last_error` — они указывают правду уровня раннера.

**Следствие для ErrorBus:** `reconcile: cron run failed for job <id>` — это СИМПТОМ упавшего крона, а не ошибка reconcile. Чинить надо крон/CLI; событие в шине закроется само через auto-resolve, когда крон снова станет ok (см. раздел про auto-resolve). Починка упавшего крона — кейс BUGFIX → канбан-граф (`BUG:diagnose` → `GATE:diagnose-review`), не прямое вмешательство.

### Общий алгоритм фикса no_agent крона

1. Собрать диагностику: `cronjob(action='list')` → найти job_id с `last_status=error`
2. Прочитать output: `ls ~/.hermes/cron/output/<job_id>/` → последний файл → `cat/read_file`
3. Определить root cause:
   - `Blocked: script path resolves outside...` → симлинк → враппер
   - `exit code 127` + `No such file` → удалена зависимость → убрать вызов
   - `exit code 0 + пустой stdout` → тихая ошибка в скрипте → запустить вручную
4. При сложном root cause — вынести на разбор через канбан-карточку `BUG:diagnose` (Блок 6В hermes-feature): root cause + план П.1…П.N. Прямой `agent -p` архитектора на root-cause/план для крон-ошибки НЕ вызывать — только как воркер карточки `BUG:diagnose`.
5. Исправить по плану, проверить скрипт вручную, запустить `hermes cron run <id>` для верификации

### Дубли кронов при `multiplex_profiles: true` — падает не ваш крон

**Проблема:** `cronjob action='list'` и `~/.hermes/cron/jobs.json` показывают крон с `last_status=ok` и deliver в топик, но Саша получает в DM падающий отчёт того же имени. Ошибка и канал доставки не совпадают с активным реестром.

**Причина:** `config.yaml` → `cron.multiplex_profiles: true`. Один gateway исполняет кроны ВСЕХ профилей, у каждого свой `jobs.json`. Может существовать ДВА крона с одинаковым `id`/именем — в default и в др. профиле — с РАЗНЫМИ моделью, provider/base_url, расписанием и `deliver`. Активный профиль показывает только свой экземпляр.

**Диагностика — проверить реестры ВСЕХ профилей (не только default):**
```bash
python3 -c "
import json,glob
for p in glob.glob('$HOME/.hermes/profiles/*/cron/jobs.json')+glob.glob('$HOME/.hermes/cron/jobs.json'):
    try: d=json.load(open(p))
    except: continue
    for j in d.get('jobs',[]):
        if j.get('id')=='<job_id>': print(p, '| model=',j.get('model'),'| provider=',j.get('provider'),'| deliver=',j.get('deliver'),'| sched=',j.get('schedule_display'))
"
```
Ключевые расхождения, выдающие дубль: `model`/`base_url` (напр. default на `gemini-2.5-flash-lite`/tutu vs дубль на `gpt-5.5-pro`/api.openai.com), `deliver` (default в топик `-1004300127777:7` vs дубль в DM `400307920`), `schedule` (суббота vs ежедневно).

**Фикс:** удалить запись из `jobs.json` НЕактивного профиля (default — оставить рабочий). Сделать бэкап `cp ... jobs.json.bak-$(date +%Y%m%d)`, править Python'ом чтобы сохранить валидный JSON, не трогая остальные кроны. Изменения подхватываются БЕЗ рестарта gateway (он запрещён). Верифицировать: оба файла, `vm_selfcheck` отсутствует в openai и на месте с deliver=:7 в default.

**Прецедент:** 16.08.2026 — крон `vm_selfcheck` падал `[Errno 32] Broken pipe` (SSE-стрим на api.openai.com рвался 3 раза: «no SSE events for 12s after first byte»), отчёт слался в DM. Дубль в профиле `openai` (`gpt-5.5-pro`/custom→api.openai.com, deliver=`telegram:400307920`, ежедневно) против рабочего default (`gemini-2.5-flash-lite`/tutu, deliver=`telegram:-1004300127777:7`=топик Monitoring, суббота). Удалён openai-дубль. Рецепт: `references/duplicate-cron-multiplex-2026-08-16.md`.

### Открытые события ErrorBus «сыпят ошибками» после фикса скрипта

**Проблема:** Саша говорит «опять сыпет ошибками» по инструменту, хотя основной скрипт/крон **уже починен** и работает штатно. Причина — ошибки, которые крон через `_report_error_bus`/`report_error.sh` записал в шину (`~/.hermes/error_bus/events.db`), остаются со `status='open'` (не `resolved`). Механизм доставки ErrorBus повторно тянет `open`-события в Errors-топик, поэтому «сыпет» продолжается ещё долго после устранения корня.

**Диагностика — сначала отличи«правду» от «хвоста шины»:**
1. **Не верь списку событий как признаку текущей поломки.** Проверь `last_seen` каждого события, а не наличие записи:
   ```python
   import sqlite3
   c=sqlite3.connect('/home/tkachenkoav/.hermes/error_bus/events.db')
   for r in c.execute("SELECT id, tool, stage, message, severity, count, last_seen, status FROM errors ORDER BY last_seen DESC"):
       print(r)
   ```
   Если все `last_seen` старые (а «сейчас» больше часа назад), а крон-выводы свежие и `silent`/ok — **новая поломки нет**, это исторический хвост шины.
2. **Проверь крон-вывод напрямую** (не шину): `~/.hermes/cron/output/<job_id>/` последний файл → `Status: silent (empty output)` = штатная работа no_agent крона, это НЕ ошибка.

**Root cause двух типичных «симптомов-двойников», которые решают одним фиксом:**
- `KeyError: 'tag'` в `config.py` при импорте cron-скрипта — если импорт падает, крон «script failed». В `ProtocolFromSummary` это сущность в `entities.json` с блоком `pfs` без ключа `tag`; фикс `pfs.get("tag")` вместо `pfs["tag"]` (обсуждается в `references/errorbus-channel-separation-2026-08-26.md`, разбор PFS).
- `stale pending notifications` с несуществующим `meeting_id` (напр. `new1`) — **запись может быть тестовой фикстурой**: `tests/test_notify_pending.py` использует `meeting_id="new1"`. В реальном реестре записи нет. Проверить: `python3 scripts/notify_pending.py --dry-run` — если stale-WARN нет, всё работает; старое событие в шине — просто не закрытый хвост.

**Фикс хвоста шины:** `open`-событие закрыть как `resolved` (с `resolved_note`), а НЕ удалять — сохраняем историю реальных ошибок, но убираем повторную доставку. Делать после устранения корня + подтверждения, что крон больше не генерит новое.

**Правило:** при «сыплет» в Errors сначала сверь `last_seen` шины со свежими крон-выводами. Если рассинхрон — это хвост старых `open`-событий, а не живая поломка. Не рестартовать gateway (запрещено).

**Структурная причина «вечно висящих open-кейсов»** (две независимые проблемы — полный разбор и план фикса в `references/errorbus-stale-open-rootcause-2026-08-27.md`):
- **Нет авто-resolve в коде вообще.** `report_error`/`reconcile` создают события только на failed-прогонах; `reconcile.py` уже умеет определять «починилось» через `recovery_index`/`is_recovered`, но использует это лишь чтобы **не создавать новое** событие, а старые `open`-строки не закрывает. Единственный путь закрытия — ручной `error_bus_cli.py resolve <id> --note`.
- **`digest_rows_stale_open` фильтрует только по `first_seen`, игнорируя `last_seen`** → событие старше 3 дней светится в «Всё ещё открыто» каждый день бесконечно, даже без повторов.

**Индикатор шумности — `last_seen` события (реально живое или нет), а не `status`.** Если все `last_seen` старые, а крон-выводы свежие и silent — это мёртвый хвост, а не живая поломка.

**✅ Авто-закрытие неактивных open РЕАЛИЗОВАНО (ErrorBus v0.3.0, 27.08.2026)** — ручное закрытие через `error_bus_cli.py resolve` больше **не требуется** как штатный шаг. Теперь open-кейсы закрываются сами (см. `references/errorbus-auto-resolve-impl-2026-08-27.md`):
- **SQL-фикс** `digest_rows_stale_open` — добавлено условие `AND last_seen >= datetime('now','-7 days')` (константа `STALE_RECENCY_DAYS=7` в `_db.py`) → в блок «Всё ещё открыто» попадают только реально повторяющиеся инциденты, а не весь исторический open-мусор.
- **Авто-resolve по факту восстановления** — `auto_resolve_recovered(conn, recoveries)` в `_db.py`, вызывается в конце `reconcile()` по готовому `recovery_index` (job_id, `last_seen < recovered_at`) → закрывает open-строку инструмента, когда крон снова заработал.
- **Дормант-fallback для событий без job_id** — `auto_resolve_dormant(conn, days=DORMANT_DAYS=5)` в `_db.py`, вызывается в `digest.py` перед `digest_rows_stale_open`.
- История сохраняется (`UPDATE status='resolved'`, **без `DELETE`**); путь свежего мониторинга (`report_error`/wrap/severity/`already_reconciled`/`is_recovered`) не тронут. Тесты 41/41 зелёные.

Если «сыпет» снова после этой доработки — сначала сверь `last_seen` свежих open-событий с крон-выводами: если событие в окне 24ч и повторяется — живая поломка; если только старые хвосты — авто-resolve сам их закроет на ближайшем reconcile/digest.

### Reconcile «догоняет» старые упавшие прогоны и ре-нотифицирует (второй источник «сыпет»)

Если «сыпет ошибками» продолжилось ПОСЛЕ закрытия open-событий — проверь, что это не `error_bus_reconcile.py` заново создаёт события о старых падениях.

**Проблема:** `~/.hermes/error_bus/reconcile.py::reconcile()` делает `hermes_cron_runs(limit=200)` **БЕЗ фильтра по времени**, и для КАЖДОГО run в `FAIL_STATUSES={"failed","timeout","error","unknown"}` вызывает `report_error(..., send_telegram=True)`. `already_reconciled()` дедуплицирует только по точному `run_id` в detail. Если крон падал серией (напр. `pfs_notify` каждые 5 мин из-за `KeyError` в 17:40–18:10) — каждый прогон даёт новый `run_id`, и reconcile со следующего запуска создаёт event на каждый исторический фейл как «новый» критический алерт, не уважая ни разрастворенный `resolved`, ни возраст run.

**Диагностика — смотри `created` в dry-run, а не только open-статус:**
```bash
/usr/bin/python3.11 ~/.hermes/error_bus/reconcile.py --dry-run
# → {"created": N, "skipped": M, "backfilled": 0}
```
`created: N` (>0) при том, что крон давно работает штатно = reconcile хочет заново поднять исторические фейлы. Это второй источник «сыпет», отличный от «хвоста open-событий» выше.

**Фикс-направление (минимальный, в reconcile.py):**
- Ввести **окно свежести**: создавать событие только для `run.ts` в пределах N минут/часов от текущего/от `.last_reconcile` (метка есть: `~/.hermes/error_bus/.last_reconcile`). Старые фейлы не создают событие/алерт.
- **Уважать resolved**: если тот же `job_id`+detail/run_id уже было записано (в т.ч. resolved) — не генерить повторно.
- Механизм при этом должен продолжать ловить СВЕЖИЕ падения (не глушить мониторинг).

**Правило:** если после починки крона и закрытия open-событий «сыпет» не утихает — подозревай reconcile, а не скрипт. `created` в dry-run — индикатор. Не рестартовать gateway.

Полный разбор: `references/errorbus-reconcile-spam-2026-08-26.md`.

### Log файл crumpled (mtime уже после фикса, но крон всё равно silent)

**Проблема:** no_agent крон `Status: silent (empty output)`, но это НЕ обязательно поломка — для скрипта, который шлёт уведомления по своему каналу (напр. `notify_pending.py` через deliver), `silent` = штатно (нет новых pending). Путать с реальной ошибкой нельзя: сравни с соседними тиками — если раньше был `script failed` с traceback, а теперь стабильно `silent` и mtime config.py между ними — фикс подхвачен.

### Модель недоступна для API-ключа (HTTP 400)

**Проблема:** агентный крон падает с `RuntimeError: HTTP 400: model "<name>" is not allowed for this API key`.

**Диагностика:** проверить `model` и `provider` упавшего крона в `jobs.json`.

**Фикс:** `hermes cron edit <id> --model <доступная_модель> --provider <provider>`.
Подкоманда — `edit`, не `update` (`hermes cron` → `list|create|add|edit|pause|resume|run|remove|rm|delete|status|runs|history|notepad|tick`; `update` не существует).

**Pitfall — суффикс `-low` в имени модели:** слаг вида `deepseek/deepseek-v4-pro-low` — это НЕ модель, а ошибочная склейка имени модели с режимом мышления. «Thinking low» — отдельный параметр `reasoning_effort`, а не часть слага. Валидная модель — `deepseek/deepseek-v4-pro`; низкое мышление задаётся отдельно (см. ниже). Склейка даёт ровно этот HTTP 400.

**`reasoning_effort` (thinking level) в Hermes:**
- Уровни: `none | minimal | low | medium | high | xhigh | max | ultra`.
- Задаётся ТОЛЬКО в `config.yaml`: `agent.reasoning_effort` (глобально) или `agent.reasoning_overrides: {модель: уровень}` (per-model, спеллинг-толерантно). Hermes шлёт на гейтвей как `reasoning: {enabled: true, effort: <level>}`.
- **Per-крон настройки reasoning НЕТ** — ни в инструменте cronjob, ни в `hermes cron edit` (только `--model`/`--provider`), ни в `cron:`-секции конфига. Уровень резолвится по модели (`resolve_reasoning_config(cfg, model)` в `cron/scheduler.py`).
- Следствие: если крон и основной чат на одной модели (напр. `deepseek-v4-pro`), развести «low для крона, medium для чата» штатно нельзя — любой способ занижения (глобальный `agent.reasoning_effort` или per-model override) заденет и чат. Для изоляции дешевизны — другая модель крона (напр. `google/gemini-2.5-flash-lite` как у backlog-analyst).

**Прецедент:** 13-14.08.2026 — `backlog-collector` падал из-за `deepseek-v4-pro-low`. Проверено живым curl к гейтвею (рецепт: `references/model-reasoning-verification.md`): `deepseek/deepseek-v4-pro` + `reasoning: {enabled:true, effort:"low"}` → 200; `deepseek-v4-pro-low` → 400 «model not allowed».

### Diagnostic Script: `scripts/diagnose_exchange.py`
Универсальный диагностический скрипт для Exchange cron. Проверяет Python-интерпретер, venv,
импорты, пакеты. Использовать как шаблон для аналогичных диагностик.

## References
- `references/cron-symlink-fix-2026-08-15.md` — полный рецепт фикса двух разновидностей падающих no_agent кронов: симлинк-блокировка и удалённая зависимость (exit 127). Точные команды + верификация.
- `references/duplicate-cron-multiplex-2026-08-16.md` — прецедент дубля cron `vm_selfcheck` при `multiplex_profiles:true` (профили default vs openai, разные модели/deliver), Broken pipe на api.openai.com, фикс удалением дубля.
- `references/errorbus-channel-separation-2026-08-26.md` — корневая причина «no_agent крон молчит на exit 0» (scheduler стирает stderr при exit 0); отсюда правило экосистемы: бизнес → Monitoring, тех. инфа/сбои → шина ошибок SQLite + Errors (прямой POST мимо deliver), тротлинг, exit 0 после обработки.
- `references/errorbus-reconcile-spam-2026-08-26.md` — второй источник «сыпет»: `error_bus_reconcile.py` без фильтра времени ре-создаёт события о старых failed runs (`created` в dry-run = индикатор), фикс-направление «окно свежести + уважать resolved».
- `references/errorbus-stale-open-rootcause-2026-08-27.md` — структурная причина «вечно висящих open-кейсов в сводке»: нет авто-resolve (reconcile использует rebuild `recovery_index` только для подавления новых, а не для закрытия старых) + `digest_rows_stale_open` фильтрует только по `first_seen` без `last_seen`. План гибридного фикса (SQL-фильтр + авто-resolve по recovery_index + дормант-fallback).
- `references/errorbus-auto-resolve-impl-2026-08-27.md` — **фактическая реализация фикса (ErrorBus v0.3.0)**: функции `auto_resolve_recovered`/`auto_resolve_dormant` в `_db.py`, SQL-фикс `digest_rows_stale_open`, интеграция в `reconcile.py`/`digest.py`, константы `STALE_RECENCY_DAYS=7`/`DORMANT_DAYS=5`, тесты, верификация 41/41, что НЕ вошло (фаза 12 — кроны). Показывает, что ручное закрытие open теперь автоматизировано.

## Verification Checklist

- [ ] Определён job_id и проверен `last_status`/`last_run_at`
- [ ] Проверен `sys.executable` — тот ли Python запускает скрипт
- [ ] Проверены зависимости в этом venv
- [ ] Ручной запуск с тем же интерпретером подтвердил/исключил проблему
- [ ] После фикса — крон repeat=1 подтвердил работоспособность
