# Cron diagnostic recipes

These are diagnostic examples. Creating, deleting, or changing crons requires the corresponding authorization. Route fixes through BUGFIX; do not create repeat=1 without the explicit instruction quoted below. Run scripts manually only if their side effects are authorized. Historical references to missing files have been removed; the surviving source details are retained here.

> Context (RU): «ставь кроны»

## 0. Self-identification for agent crons

When an agent cron (`no_agent=false`) runs, `HERMES_CRON_JOB_ID` can be empty. Identify the job by matching its start time:

```python
import json
with open(f'{home}/.hermes/cron/jobs.json') as f:
    jobs = json.load(f)['jobs']
# Find crons whose last_run_at matches the session start time
# Key field: 'id' (not 'job_id')
```

Or compare output directory modification times with `last_run_at`:

```bash
ls -lt ~/.hermes/cron/output/ | head -10
```

## 1. Inspect the cron registry

```python
import json
with open("~/.hermes/cron/jobs.json") as f:
    jobs = json.load(f)["jobs"]
```

Search by name or script. Check `enabled`, `schedule`, `script`, `no_agent`, `workdir`, `last_status`, and `last_run_at`.

## 2. Inspect execution logs

```python
import sqlite3
conn = sqlite3.connect("~/.hermes/cron/executions.db")
# columns: id, job_id, source, process_id, pid, process_started_at, status, claimed_at, started_at, finished_at, error
```

Alternatively inspect `~/.hermes/cron/output/<job_id>_*.txt`.

## 3. Inspect the execution environment (critical for no_agent)

no_agent scripts run with **Hermes venv** Python (usually `hermes-agent/.venv/bin/python`), not the project venv. Verify:

```python
import sys
print(f"Python: {sys.executable}")
print(f"sys.path: {sys.path}")
```

If project dependencies such as exchangelib are in another venv, an import can fail. In no_agent mode stderr may not be delivered, so the user may see silence. Compare actual output and delivery before concluding that silence is a failure.

## 4. Manual script execution

When side effects are authorized, run the script directly using the cron interpreter:

```bash
# Identify the Python used by cron:
hermes-agent/.venv/bin/python ~/.hermes/scripts/<script_name>.py 2>&1
```

## 5. Execution through cronjob repeat=1

Create this only with the explicit authorization quoted above; a one-off cron is still cron creation:

```python
cronjob(action='create', name='test-<x>', repeat=1, schedule='1m',
        script='<script_name>.py', no_agent=True, workdir='<workdir>', deliver='origin')
```

The historical source says output arrives in chat and this is more reliable than `hermes cron run` under multiprofile; it also presents `hermes cron run` as a verification method elsewhere. Verify current applicability against code and environment.

## `claim job` entries with prompt='x'

Inspect entries named `claim job` with a one-character `prompt='x'`, no `skills`/`context_from`, and deliver=`local`. The model may improvise diagnostics from the system prompt; multiple copies can waste tokens.

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

Confirm which entries are redundant before deleting any within authorized scope using `hermes cron delete <id>`; the historical remedy retained at most one with a clear prompt.

> Context (RU): Прецедент 14.08.2026 — 9 claim job созданы 07.08.2026, 6/9 отвечают `[SILENT]`, 3/9 — случайные диагностические заметки. Полный исторический документ отсутствует.

## Duplicate crons with `multiplex_profiles: true`

If `cronjob action='list'` and `~/.hermes/cron/jobs.json` show `last_status=ok` and delivery to a topic, but a failing report with the same name arrives in DM, inspect all profiles. With `config.yaml` → `cron.multiplex_profiles: true`, one gateway runs crons from all profiles, each with its own `jobs.json`. The same `id`/name may have different model, provider/base_url, schedule and `deliver`; the active profile shows only its own instance.

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

Compare `model`/`base_url` (e.g. `gemini-2.5-flash-lite`/tutu versus `gpt-5.5-pro`/api.openai.com), `deliver` (topic `-1004300127777:7` versus DM `400307920`), and schedule (Saturday versus daily). Within authorized scope, the historical remedy removed the confirmed duplicate from the inactive profile, kept the working default, backed up with `cp ... jobs.json.bak-$(date +%Y%m%d)`, and edited using Python to preserve valid JSON and other jobs. Verify both files: `vm_selfcheck` absent in openai and present with deliver=:7 in default. Changes were picked up without a gateway restart; do not restart without Sasha's explicit permission.

> Context (RU): Прецедент 16.08.2026 — `vm_selfcheck` падал `[Errno 32] Broken pipe`: SSE на api.openai.com трижды рвался с «no SSE events for 12s after first byte», отчёт приходил в DM. Дубль `openai` (`gpt-5.5-pro`/custom→api.openai.com, deliver=`telegram:400307920`, ежедневно) удалён; рабочий default (`gemini-2.5-flash-lite`/tutu, deliver=`telegram:-1004300127777:7`, топик Monitoring, суббота) сохранён. Исторический документ отсутствует.
