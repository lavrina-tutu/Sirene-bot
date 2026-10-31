---
name: usertools-llm-integration
description: "Use when diagnosing USERTOOLS LLM/env/cron failures."
version: 1.0.0
author: agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [usertools, PFS, MOFS, llm-config, cron, env-leak, dedup]
    related_skills: [protocolfromsummary, mofs-operations, hermes-feature, cursor-cli, pfs-mff-troubleshooting]
---

# USERTOOLS × LLM integration — диагностика и решения

Класс задач: инструменты в `~/USERTOOLS/*` (ProtocolFromSummary, MarkObjectsFromSummary,
MoveFromFF, ConfluenceSync, …), которые ходят к LLM через корпоративный шлюз
`llm-gateway.tutu.ru/api/openrouter/v1` и/или пишут реестры/состояние на диск. Здесь —
как диагностировать их сбои, которые НЕ видны в логах самого Hermes (state.db/agent.log).

## Ключевой принцип: внешние тулы обходят логи Hermes

Если в админке шлюза (`llm-gateway-admin.tutu.ru/usage`) виден расход модели, которого нет в
`state.db`/`agent.log` Hermes — источник, скорее всего, ВНЕ основного агента: внешний инструмент
из `~/USERTOOLS/`, использующий собственный API-ключ/модель/эндпоинт и не логирующийся в Hermes.
Пример: `deepseek-v4-pro` в статистике оказался PFS-дедупликацией, а не самим Hermes.

**Проверка «кто может звать LLM» (чеклист):**
```bash
# LLM-вызов в тулах (вне venv)
grep -rl "openai.OpenAI\|chat.completions.create\|llm-gateway" ~/USERTOOLS/*/ --include="*.py" 2>/dev/null | grep -v ".venv\|site-packages"
# модель в кронах Hermes
python3 -c "import json;d=json.load(open('~/.hermes/cron/jobs.json'));[print(j['id'],j.get('model'),j.get('provider'),j.get('script')) for j in d.get('jobs',[])]"
# auxiliary модели
grep -n "auxiliary\|model" ~/.hermes/config.yaml | head -40
```

## Питфолл 1: «убегающий» реестр/состояние → env-утечка TOOL_DIR/LOGS_PATH

Симптом: реестр инструмента пишется не в свою папку, а «переезжает» между соседними
`~/USERTOOLS/*`. Причина — в **общий** `~/.hermes/profiles/default/.env` по ошибке попали
generic-переменные `TOOL_DIR`/`LOGS_PATH` от другого тула. `pydantic-settings` даёт приоритет
`os.environ` над локальным `.env`, поэтому `tool_dir` (→ registry/lock/logs) утекает в чужую папку.

**Диагностика:**
```bash
grep -E "TOOL_DIR|LOGS_PATH" ~/.hermes/profiles/default/.env
find ~/USERTOOLS -name "_mark_objects_registry.json" 2>/dev/null   # блуждающие копии
# ВАЖНО: если .env чист, но в живом процессе env всё ещё есть — источник выше по цепочке:
env | grep -E "TOOL_DIR|LOGS_PATH"            # что реально видит процесс
grep -nE "TOOL_DIR|LOGS_PATH" ~/.bashrc ~/.bash_profile ~/.profile   # login-shell
tr '\0' '\n' < /proc/<pid>/environ | grep -E "TOOL_DIR|LOGS_PATH"    # родитель/сессия
systemctl --user show-environment | grep -E "TOOL_DIR|LOGS_PATH"     # systemd-user
```
**Фикс:** убрать утёкшие переменные из общего `.env` → вернуть их в `.env` конкретного тула →
слить блуждающие копии реестра в канонический (дедуп по ключу, при коллизии брать запись с max
`processed_at`, бэкап копий, атомарная запись tmp+os.replace, удалить осиротевшие `.mofs.lock`).
**Питфолл 1а (НЕОБХОДИМО): чистки только общего `.env` НЕДОСТАТОЧНО.** Это было уже сделано 17.08,
но реестр продолжал «убегать»: generic-переменные пережили чистку, т.к. лежали в живом окружении
долгоживущего процесса/сессии (источник выше .env-файла). Поэтому структурная профилактика —
**обязательна**, а не опция: уникальные имена (`MOFS_TOOL_DIR`/`MOFS_LOGS_PATH`) или
`load_dotenv(..., override=True)` в пакете, чтобы локальный `.env` тула имел приоритет над чужими
generic-переменными процесса. После фикса перепроверить в СВЕЖЕЙ сессии и в контексте крона
(не в текущей, где переменная могла «зависнуть»). Подробности: `references/env-leak-registry-merge-20260817.md`.

## Питфолл 2: не переводить LLM-зависимый agent-крон в no_agent script вслепую

Если agent-крон молча падает (пустые ответы, rate-limit) — соблазн «перевести в скрипт». Но если
LLM — **ядро логики** (напр. PFS semantic dedup: «есть ли у того же исполнителя такая же по смыслу
задача» — `dedup.py` через `llm_fn`), скрипт-режим убьёт функциональность. Правило:
- хрупкость от LLM чинить **алертингом на N подряд пустых/ошибок прогонов**, не удалением LLM;
- решение script vs agent принимать только после чтения кода (`grep llm_fn|_dedup_llm_fn`);
- если в коде LLM-ступень обязательна — крон остаётся agent/скриптом, запускающим оркестрацию.

## Питфолл 3: НОВЫЕ LLM-функциональности инструментов — только из default-конфига, без хардкода (правило Саши)

**Правило (Саша, 26.09.2026):** любой LLM-инструмент/функциональность в USERTOOLS должен брать
модель и эндпоинт из DEFAULT настроек системы — `model.default` + `model.provider` +
`custom_providers[name=...]` (base_url, api_key) из `~/.hermes/config.yaml` — **без хардкода
строки модели/эндпоинта в коде**, чтобы при смене модели в настройках функциональность менялась
вслед за базовой Hermes автоматически. Новых констант вроде `SOME_LLM_MODEL`/URL в коде не плодить;
если из YAML модели/endpoint нет — fail-soft без вызова, а не подставлять СВОЮ строку модели.

Это касается и новых контуров внутри существующего тула: если тул уже читает свой LLM-конфиг
(например PFS `LLM_CONFIG` через `_load_llm_config()`), новый LLM-шаг использует тот же
транспорт/модель, не отдельный хардкод. Утилизировать существующий общий LLM-клиент тула
(для PFS — как у semantic dedup), а не заводить параллельный канал. Разделять по смыслу: контур
«встреча → проекты» (MOFS) и «задача → слаг» (PFS) — это РАЗНЫЕ пакеты, каждый сам по default.

**Владелец фичи — тоже решение канона, не «сделай где удобнее» (Саша, 26.09.2026).** При
доработках с похожей механикой в соседних тулах явно спросить, КТО владеет контуром. Пример:
слаг задач ставит ТОЛЬКО PFS (в `task/text` чекбокса при публикации); MOFS слагами задач НЕ
занимается — не расширять MOFS под слаги («Слаг в MOFS не устанавливаем, работаем только в PFS»).
Проверять перед постановкой, не пытается ли решение зацепить чужой пакет, — если ответов по
объёму нет, аргументировать разделение на отдельные графы один на инструмент.

Примечание по механике «по default»: не импортировать конфиг чужого тула (PFS `LLM_CONFIG` —
не библиотека для MOFS). Либо скопировать чтение трёх полей YAML 1:1 без запасных литералов,
либо общий ридер, либо вызов Hermes `call_llm` — выбор по «один CHANGE везде vs раздельно»;
не хардкодить строку модели ни в одном из вариантов.

**Контрпример (известный долг, чинить отдельным CHANGE):** MOFS `llm_fallback.py` до сих пор с
хардкодом `claude-haiku-4-5`/`claude-haiku-3-5` через Anthropic (`ANTHROPIC_API_KEY`), НЕ читает
`config.yaml` — смена модели Hermes на MOFS не действует. Правка «заодно» в чужой пакет не
вписывается; перенос MOFS на `model.default` — отдельный CHANGE (маленький: `_call_llm` → тот же
паттерн, что PFS).

## Питфолл 4: единая env-схема USERTOOLS и smoke-тест на нужном venv

С 20.08.2026 внедрён общий env-loader `~/.hermes/lib/usertools_env.py`:
- Бизнес-секреты (CONTACTS_ENCRYPTION_KEY, LOOP_TOKEN, FIREFLIES_API_KEY, TELEGRAM_BOT_TOKEN и др.) живут в едином `~/.config/hermes/.env`; локальные `.env` тулов держат только не-дубли (CONFLUENCE_TOKEN, OWNCLOUD_*, пути).
- Подключение в тул (паттерн пилота MoveFromLoop):
  ```python
  sys.path.insert(0, str(Path.home()/".hermes"/"lib"))
  import usertools_env
  usertools_env.load_usertools_env(local_env_path=<тул/.env>)  # локальный приоритетнее центрального
  ```
- **Loader вызывать ПЕРВЫМ в конфиге, до собственного чтения env**: loader на `os.environ.setdefault`, т.е. уже установленную переменную НЕ перезапишет. Если код тула прочитал env раньше — setdefault не сработает.
- Удаление дублей из локальных `.env`: только ключи, которые есть в `~/.config/hermes/.env`; уникальные ключи тула оставить. Бэкап локальных `.env` перед правками → `~/.hermes/_Archives/usertools-env-pilot-rollout-YYYYMMDD/`. Не звать письмо если ключ не в центральном.

**Питфолл 4а: ПОРЧЕННЫЙ секрет в центральном `.env` перекрывает валидный локальный — и это выглядит как «всё сломалось».** Не-дуп-ключ тула (напр. `CONFLUENCE_TOKEN`) может быть ДУБЛЕМ в рабочем виде также и в центральном `~/.config/hermes/.env` (если туда случайно/OverlayConfig-скриптом записали значение). Из-за паттерна бутстрапа (`load_usertools_env()` заполняет центральный env первым, а валидный локальный фоллбек срабатывает только `if key not in os.environ`) повреждённый центральный экземпляр «глушит» исправный локальный. Диагностировать смотрением НА ДЛИНУ/СОДЕРЖИМОЕ, а не «наличие ключа»: распечатать `CONFLUENCE_TOKEN` из обоих файлов и сравнить (`bad.startswith(valid)` + лишние байты = порча, часто мусор приписан в конец). Лечить по канону: не дублировать не-дуп-ключ в центральном `.env` вовсе — тогда фоллбек сам подхватит валидный локальный. **Маскирующий признак Confluence: HTTP 404 с телом `{"statusCode":404,"data":{"authorized":false,"valid":true,...}}` на КАЖДОЙ странице — это ОТКАЗ АВТОРИЗАЦИИ сломанным токеном, а не отсутствие страниц/миграция/устаревшие page_id.** Прежде чем грешить на URL/id/миграцию — пробить ту же страницу валидным токеном: если 200, виноват секрет, не страница.

**Smoke-тест — важный питфолл:** НЕ тестировать конфиг тула системным `python3` — там нет зависимостей тула (requests/exchangelib/pydantic), получишь ложный `ModuleNotFoundError`, не связанный с изменением. Берём venv самого тула (`$TOOL/venv_linux/bin/python3` или `$TOOL/.venv/bin/python3`), а тулы на exchangelib (MeetingScheduler, ExchangeMeeting) гонять через `MoveFromLoop/venv_linux` или `AnywhereContacts/venv_linux`. Минимальный smoke с чистым окружением:
```bash
env -i $TOOL/.venv/bin/python3 -c "import sys,os; sys.path.insert(0,'$TOOL'); import $pkg.config; print('OK', 'CONTACTS_ENCRYPTION_KEY' in os.environ)"
```
После удаления дублей проверить `grep -qE '^KEY=' ~/.config/hermes/.env` для каждого снятого ключа — секрет не потерян.

## Питфолл 6: единый конфиг-лоадер имеет ХАРД `import yaml` — каждый тул-кронов venv обязан его держать

При переносе тула на общий не-секретный конфиг (`~/.hermes/lib/usertools_config.py`, вызов
`from usertools_config import load_tool_config` в `config.py`) лоадер делает **топ-level
`import yaml`** — это НОВАЯ жёсткая зависимость для ЛЮБОГО тула, который его подключает, даже если
сам тул никогда yaml не импортировал. Недостающая `yaml` в venv крона = `ModuleNotFoundError`
на КАЖДОМ тике → тул молча не работает (встречи не переносятся, уведомления не идут).

**Почему тест не ловит:** если конфиг проверять (или приёмочный тест гонять) через СМЕЖНЫЙ venv,
где yaml есть (напр. `ProtocolFromSummary/.venv` — у него `pyyaml>=6` в pyproject, `ConfluenceSync`
тоже), а боевой крон тула идёт через СВОЙ venv (`$TOOL/.venv/bin/python`) — там yaml может
отсутствовать. `import` падает только на СВОЁМ venv. Гонять на чужом venv = маскировать дефект.

**Подтверждённый вердикт архитектора (12.10.2026, cursor-grok):** PyYAML ставится в **боевой venv каждого тула** (requirements + install). НЕ заводить общий venv на все тулы — PyYAML с C-ускорителем ABI-привязан к версии Python, одна копия не поедет и на 3.11, и на 3.14. **Ленивый `import yaml` (внутри функции) — НЕ делать**: он лишь отодвигает `ModuleNotFoundError` с импорта модуля до первого вызова и ухудшает диагностику; любой `load_tool_config`/`explain`/`resolve_key` всё равно требует yaml, т.е. top-level `import yaml` — правильный fail-loud. Разделять «зависимость от лоадера» и «исправление лоадера» нельзя: это runtime-зависимость общего лоадера, а не удобство импорта.

**Правило (обязательный AC при переносе на единый конфиг):**
1. Снять фактический боевой интерпретатор из БОЕВОГО входа (jobs.json / crontab / wrapper `*.sh` → `venv_linux/bin/python3`), НЕ python3 из сессии теста. Верифицировать конфиг-перенос на СВОЁМ venv тула (том, что реально гонит крон), не на соседнем — тест на чужом venv маскирует дефект (приёмочный прогон через venv PFS был зелёный, а боевой крон MFF падал).
2. После добавления `load_tool_config` в `config.py` — добавить зависимость лоадера (`pyyaml` для `usertools_config`) в `requirements*.txt`/`pyproject.toml` тула (если файла зависимостей нет — завести минимальный, НЕ оставлять «поставили руками») И установить в боевой venv. Проверка боевым бинарником: `$TOOL/.venv/bin/python -c "import yaml; print(yaml.__version__)"`.
3. **Эмуляция реального запуска (правило Саши):** приёмочный тест обязан включать реальный запуск инструмента через разовый крон (`cronjob repeat=1`) ТОЙ же командой/скриптом, что боевой крон, тем же venv — инструмент должен сделать реальный тик с 0 ошибок импорта и реальным вызовом. НЕ ограничиваться dry-run/pytest в тестовом venv (он реализует другой контур и не закрывает риск «лоадер импортирует пакет, которого нет в окружении инструмента»). На этапе диагностики перед приёмкой минимум — `import yaml` в боевом интерпретаторе = OK.
4. Опциональный IAC: при `ImportError` в лоадере дописывать в сообщение `sys.executable` — сразу видно, в какой интерпретатор забыли пакет (это косметика, НЕ замена install).

Ручной прогон PFS-го / PFS-цепи должен повторять ТОЧНЫЙ контур крона, включая его venv и флаги
(напр. `export PFS_POST_SWITCH=1` у `run-pending`) — отклонение от контура крона воспроизводит
другой режим и может на время записать не туда (пост-switch off пишет строки на цели, а не только
на площадку), что потом приходится чистить вручную.

### Питфолл 6b: общий лоадер с ЯВНЫМ `keys=` отбрасывает shared-ключи — `load_settings` требует их из env

Пакет (`config.py`) зовёт `usertools_config.load_tool_config(tool_key, keys=_MFKT_CONFIG_KEYS)`
с явным списком, а затем `load_settings()` читает shared-переменную (напр. `WORKVAULT_PATH`, лежащую
в `shared:` блоке `EcosystemConfig.yaml`) напрямую из `os.environ`. При явном `keys=` лоадер наполняет
env **только** перечисленными ключами — shared-ключ, не входящий в список, в env не попадает, и
`load_settings` падает `RuntimeError: Missing required config/env: X (shared)` в ЖИВОМ запуске, хотя
зн��чение есть в YAML и schema-валидация зелёная.

**Правило:** любой ключ, который `load_settings()`/последующий код читает из `os.environ` (в т.ч.
shared `WORKVAULT_PATH`), обязан входить в `_MFKT_CONFIG_KEYS` (или собираться через `keys=None` —
тогда лоадер подтянет и shared-блок). Проверять полным `--mode test` (без `--dry-run`), иначе
«конфиг грузится» в dry-run может отличаться от живого (dry-run прошёл по shared, но только потому,
что не дошёл до `load_settings`).

## Питфолл 5: Cursor CLI требует git — в USERTOOLS нет корневого репо

`agent -p` не запускается вне git-репозитория. Корень `~/USERTOOLS` — НЕ git-репо (внутри тулы лежат вложенные `.git`). Либо работать в `~/WorkVault` (git-adv), либо временно `git init` в корне USERTOOLS ради раскатки и после `rm -rf .git`. Не забыть: временный корневой `.git` вызовет drift `usertool_not_in_manifest` в `render_manifest.py --check-drift` — убрать его после.

Всегда независимо верифицировать результат Cursor-исполнителя по реальному строю: `grep -rl usertools_env`, реальные smoke-прогоны на нужных venv, `git diff` конфигов (секреты не попали в коммит), сверка снятых ключей с центральным `.env`.
- Двухступенчато: fuzzy (порог 80%, `SequenceMatcher`) по задачам с тем же `assignee_userkey` →
  LLM batch для остатка. Промпт кодирует правило: «разные исполнители = разные задачи, даже при
  100% совпадении текста».
- **Пробел:** `_llm_check_tasks` строит пул `all_published` из ВСЕХ исполнителей; фильтр «тот же
  исполнитель» держится только текстом промпта, не структурно. Надёжно — программно отфильтровать
  пул по `assignee_userkey` перед LLM-вызовом (per-candidate пул).

## Связанные
- `references/usertools-env-loader-rollout-20260827.md` — детали раскатки единой env-схемы на 11 тулов: бэкап, снятые дубли, таблица правильных venv для smoke-тестов.
- `references/usertools-cron-venv-syspath.md` — **крон USERTOOLS игнорирует shebang, гоняет скрипты через hermes-agent/.venv**: тул со своим venv (например exchangelib в MoveFromLoop/venv_linux) надо явно `sys.path.insert` в крон-скрипт; + exchangelib 5.6.0 `message_class` нельзя в `.only()`. Проверено 2026-08-26.
- `protocolfromsummary` / `mofs-operations` — подробности конкретных инструментов (user-owned).
- `hermes-feature` — полный dev-цикл фич (ТЗ → план → код → тесты).
- `cursor-cli` — вызов архитектора/исполнителя через Cursor CLI.
