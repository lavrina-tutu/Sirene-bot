---
name: hermes-managed-install
description: "Use when: откуда запущен Hermes; пересоздать gateway unit."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [hermes, managed-install, gateway, systemd, launch]
    related_skills: [hermes-upstream-check, hermes-gateway-setup, hermes-ops]
---

# Hermes managed-install: где реально живёт и запускается код

## Когда использовать

- Падают cron-задачи / gateway ведёт себя как «старый», хотя `hermes update` прошёл «зелёно».
- Нужно понять, откуда реально запущен gateway: checkout `~/hermes-agent` или managed-workspace.
- После `hermes update` надо пересоздать systemd-юнит/launcher gateway.

Современный Hermes перешёл на managed-install: **актуальный код** разворачивается через `hermes update` в
managed-workspace, а git-checkout остаётся легаси-форком. Разнобой между «где лежит новый код» и «откуда
реально запущен gateway/cron» — частая корневая причина сбоев после update (падающие крон-задачи при «зелёном»
апдейте).

## Два дерева кода

| Дерево | Путь | Роль |
|---|---|---|
| managed-workspace | `~/.hermes/installs/<install>/environments/<env>/workspace` | **новый код**, обновляется `hermes update` |
| git-checkout (легаси-форк) | `~/hermes-agent` | был источником раньше; может отставать от upstream на десятки тысяч коммитов |

**Источник кода для managed-update — owning checkout, НЕ workspace напрямую.** `hermes update`, запущенный из
managed-venv, РЕТАРГЕТИТСЯ к owning checkout: путь к нему записан в
`installs/<install>/inputs/.project-root`, а `hermes_cli/update_owning_install.py::retarget_to_owning_install`
(вызов в `main.py` до update) перезапускает `python -m hermes_cli.main update …` с `cwd=<owner>` и
`PYTHONPATH=<owner>` — обновляется и git-pull-ится именно checkout, затем пересобирается environment.
Следствие: **чтобы обновить managed, owning checkout должен быть свежим**. Если checkout отстал на десятки
тысяч коммитов (merge нереализуем), сперва приведи его к upstream (`git reset --hard origin/main`, свои
кастомные коммиты не переносим — они в reflog/fork), потом запускай managed-update. `git reset` мгновенен и
безопаснее ручного merge; «checkout как fallback» после этого = свежий снимок upstream, что лучше устаревшего.

## Диагностика source-of-truth (read-only)

Выясни, какое дерево РЕАЛЬНО запущено, прежде чем чинить что-либо:

```bash
# 1) на что указывает systemd-юнит gateway
systemctl --user cat hermes-gateway.service | grep -E 'ExecStart|WorkingDir'
# 2) managed-launcher лежит в venv/bin, НЕ в workspace/.hermes/bin
ls -la ~/.hermes/installs/*/environments/*/venv/bin/hermes 2>/dev/null
# активная environment: facts.json packages.venv.environment + pm-runtime/selected.json
# (environments МНОГО — это generations; свежая не всегда активна)
# 3) свежесть workspace vs апстрима
git -C ~/hermes-agent log -1 --format='%ci' origin/main   # последний апстрим
stat -c '%y' ~/.hermes/installs/*/environments/*/workspace  # дата развёртки workspace
```

**Симптом рассинхрона:** юнит указывает на checkout-launcher `~/hermes-agent/.hermes/bin/hermes` (тот ставит
`sys.path→~/hermes-agent`), значит gateway/cron крутятся на устаревшем коде, хотя в workspace уже лежит новый.
Проявляется как identity-ошибки внешнего cron-воркера (`ModuleNotFoundError`, циклический импорт `cron.scheduler`,
`exe=(deleted)` у живого процесса), при том что в workspace код исправный.

## Как переключиться на managed (штатно)

Правильный породитель launcher+unit в новой версии — штатная команда, НЕ ручная правка ExecStart:

```bash
hermes gateway install   # пересоздаёт launcher + systemd-юнит на managed-workspace путь
```

Механика: `hermes_cli/_launchers.py::runtime_command(repo_root)` генерит launcher (store Python isolated +
`hermes_bootstrap` lease выбранной generation); unit должен указывать на launcher с `repo_root = managed-workspace`.
Рестарт gateway после этого — отдельное действие владельца.

## Безопасный апдейт без авто-рестарта

- Флаг `hermes update --no-gateway-restart` есть только в managed-коде 14.10+ (grep `no.gateway.restart` в
  `environments/*/workspace/hermes_cli/update_cmd.py`). В checkout v0.20.0 (07.08) флага НЕТ — `hermes update`
  из checkout авто-рестартит fleet. Поэтому апдейт запускать строго из managed-launcher по АБСОЛЮТНОМУ пути
  `.../environments/<active>/venv/bin/hermes update --no-gateway-restart`, НЕ через `which hermes` (тот ведёт на checkout).
- `hermes gateway install` НЕ рестартит gateway (только daemon-reload+enable+подсказка «hermes gateway start»).
- Запуск managed-launcher из-под checkout-процесса физически не видит живой gateway (тот привязан к checkout-юниту)
  — временный «рассинхрон» selected.json (уже новый env) vs живой процесс (ещё checkout) безвреден: демоном правит один systemd-юнит.
- Перед обновлением проверить: ни одна cron-задача не должна хардкодить путь к checkout (grep `hermes-agent` в
  `~/.hermes/cron/jobs.json` — только в полях command, не в output-логах).

## Pitfalls

- Не путать три вещи: (1) `venv/bin/hermes` — это console-script (`from hermes_cli.main import main`), НЕ bootstrap-launcher (store python + `hermes_bootstrap`); он тем не менее корректно резолвит managed-workspace (`--version` покажет `Install directory: …/workspace`). (2) `pm/` — package-manager для СТОРОННИХ бинарных тулзов (llama.cpp/ffmpeg/node), его `pm update` перепинивает lockfile тулзов и НЕ обновляет код Hermes. (3) код Hermes в managed-режиме обновляется только `hermes update` через retarget к owning checkout. Не искать «managed-update команду» в `pm/cli.py` — её там нет.
- `hermes update --plan` — read-only диагностика (kind установки, сервисы, что рестартнет). Но если запуск ретаргетится к устаревшему checkout (v0.20.0), флаг отсутствует → `unrecognized arguments: --plan` само по себе подтверждает, что ретаргет увёл на старый checkout-код.
- При инвентаризации, «что из наших кастомных коммитов переносить в апстрим-мерж» — не гадать про исполнение, а классифицировать каждое расхождение двумя сигналами: (1) grep маркера фичи в `origin/main` (если апстрим уже поглотил логику, берём из upstream); (2) grep переменной/ключа в живом `~/.hermes/.env` (обе) и `config.yaml` (если используется в проде — переносить обязательно). Подсистему считается неиспользуемой только при явных маркерах: тест-запрет импорта (`assert "import <subsys>_" not in text`) или односторонняя миграция истории наружу (`migrate_*_history`). Перечислять расхождения по ВСЕМ локальным веткам (`for b in $(git branch); git log origin/main..$b`), не только `main`.
- `config migrate` — это схема конфига (env-over-YAML и т.п.), НЕ пересоздание gateway-юнита. Не путать с `gateway install`.
- Ручная правка `ExecStart` в `.service` вслепую ломает managed-запуск (launcher пишется через `runtime_command`). Только `hermes gateway install`.
- `systemctl --user cat` показывает юнит в user-изоляции, не `/etc/systemd/system` — искать user unit, а не системный.
- Состояние «gateway работает, но на stale-коде» не лечится простым `systemctl --user restart` — launcher всё равно ведёт на checkout. Нужно сначала `gateway install` (или update+install), потом рестарт.
