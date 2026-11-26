# Установка инфраструктуры I/R (paused/local staging) — пошаговый рецепт

Применяется после REV APPROVE плана (в поездах Б55: после §5.1 «REV → backup → impl → install»), когда полномочие Саши на один doorbell-job и один webhook route уже есть. Установку делает КООРДИНАТОР (оркестратор), не исполнитель: executor готовит компоненты, координатор ставит в active-home.

## 1. Проверка before (HF:backup, обязательно до первой записи)

- `ls ~/.hermes/scripts/` — имя script свободно (absent-before); если занято чужим — СТОП, не перезаписывать.
- `grep -o '"name": *"[^"]*"' ~/.hermes/cron/jobs.json` — имя job свободно.
- `ls ~/.hermes/webhook_subscriptions.json` — файла нет = absent (не заявлять «пустой исходник»).
- Приватный архив `~/.hermes/_Archives/hermes-backup-<UTC>/infra-iter*/`: dir 0700, файлы 0600; cp -p jobs.json + config.yaml; sha256sum; скопировать копию в /tmp и сверить sha (проверка извлечения).
- before.json в evidence: permission_ref+SHA, absent-before по script/job/route, свободные имена, ownership.

## 2. Установка script + binding (координатор)

```bash
cp -p <src>/devworkflow_b55_doorbell.py ~/.hermes/scripts/devworkflow_b55_doorbell.py
cp -p <src>/devworkflow_b55_doorbell.json ~/.hermes/scripts/devworkflow_b55_doorbell.json
chmod 0700 ~/.hermes/scripts/devworkflow_b55_doorbell.py
chmod 0600 ~/.hermes/scripts/devworkflow_b55_doorbell.json
sha256sum ~/.hermes/scripts/devworkflow_*          # должны совпасть с source SHA
```

- Проверить `os.path.realpath(script)` внутри `<active-home>/scripts/` (script-root gate, наружный symlink не проходит).
- Binding — строгий шаблон ровно с 3 ключами (`dev_state_root`, `ecosystem_config_path`, `slug`), пустыми значениями. Фактические значения root/config/slug записываются координатором ПЕРЕД разрешённым прогоном (изолированный run-root §6.2), до этого не выдумывать.

## 3. Native cron create — paused/local staging

```bash
~/.hermes/scripts/../../hermes-agent/.venv/bin/hermes -p default cron create '* * * * *' \
  --name dw-b55-pipelines-doorbell --script devworkflow_b55_doorbell.py --no-agent \
  --timezone Etc/UTC --grace-minutes 0 --deliver local --failure-deliver local \
  --paused --paused-reason 'addressed inbound receiver is not bound'
```

- Job-id берётся из РЕАЛЬНОГО вывода CLI (`Created job: <id>`), затем readback из jobs.json (полная definition: no_agent, schedule, deliver, enabled=false, paused_reason).
- partial-success = сверить созданный id, не повторять create вслепую. jobs/subscriptions JSON руками не редактировать.

## 3b. Проверь скрипт под интерпретатором cron ПЕРЕД активацией (обязательно)

Крон запускает no_agent `.py`-скрипт НЕ на том venv, где гоняются component-тесты, а на интерпретаторе dependency-venv поезда — `project_python(repo)` под `~/.hermes/installs/<hash>/environments/<hash>/venv/bin/python` (резолв в `cron/scheduler_script.py::_posix_cron_script_argv`). Тестирование под `hermes-agent/.venv` или системным `/usr/bin/python3` не доказывает, что скрипт запустится из cron: если он импортирует `usertools_config` (тянет `yaml`) или иную зависимость, которой нет на dependency-venv, первый scheduled-тик упадёт `ModuleNotFoundError`, exit 1, с catch-all `... detector failed`, а ручные прогоны останутся rc=0 — расхождение, которое выглядит «магией».

Перед resume/активацией воспроизведи запуск тем же interpreter'ом, которым cron реально поднимет скрипт:

```bash
PP=$(cd /home/tkachenkoav/hermes-agent && .venv/bin/python -c \
   'from pm.environments import project_python; from pathlib import Path; print(project_python(Path(".")))')
ECOSYSTEM_CONFIG_PATH= HERMES_DISABLE_LAZY_INSTALLS=1 "$PP" ~/.hermes/scripts/devworkflow_b55_*.py; echo "rc=$?"
```

Если venv-зависимость критична, вынеси loader-импорт из зависимого модуля или добавь site-packages нужного venv в `sys.path` скрипта до `from usertools_config import ...` — не меняя логики детектора и не трогая jobs.json. Менять только то, что согласовано на этой итерации, затем обновить SHA/binding evidence.

## 4. Route НЕ ставится до решения receiver

Webhook subscribe создаёт agent-mode route с ОТДЕЛЬНОЙ session identity — не текущую процедуру; `--paused` у subscribe нет. Route остаётся спецификацией в плане, receiver решается отдельно архитектором/ревизором (новый согласованный объём, если нужен bridge/смена контекста).

## 5. install.json (evidence/infra-iter*/)

Поля: permission_ref+SHA, script source/installed+SHA/mode, binding keys+mode, resolved binding root / YAML root с равенством (после заполнения binding), job-id + readback, route_name=NOT_INSTALLED. Отсутствующие поля — `null`/`NOT_INSTALLED`, не выдуманные id/времена.

## Клининг и защитные границы

- Регресс до install: `pytest pipeline/tests -k 'not procedure_trace and not pilot_trace'` — на прежнюю базу наслаивается test_b55_infra.py (root gate A/B, A/A, B/B, relative/~, missing/disabled YAML); итог = старое зелёное + новые.
- Секреты в evidence/команды не выводить; .env/auth не читать.
- После install статус: I = STAGING ONLY (paused/local, доставки нет), R = NOT_INSTALLED, IAC-16.pre = FAIL readiness — это ожидаемое состояние удержания, а не сбой поезда.
