---
name: hermes-managed-update-drift
description: "Use when после hermes update валятся кроны/gateway (drift)."
version: 1.0.0
author: agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [hermes, managed-install, update, drift, cron, gateway, runtime]
    related_skills: [cron-troubleshooting, hermes-upstream-check, hermes-ops, hermes-gateway-setup]
---

# Hermes Managed-Update Drift

Диагностика рассинхрона после `hermes update`, когда Hermes переведён на managed-install
(`~/.hermes/installs/`), а gateway/cron продолжают исполнять старое окружение.

## Топология managed-инсталла (два дерева кода + два python)

После перехода на managed-install у Hermes есть **две копии кода**:
- **checkout** `~/hermes-agent/` — git-репозиторий (наш форк), может сильно отставать от upstream.
- **managed workspace** `~/.hermes/installs/<install>/environments/<hash>/workspace/` — актуальная версия, развёрнутая `hermes update`.

И **два интерпретера**:
- tools-python `~/.hermes/tools/python-<ver>…/bin/python3`; после пересоздания старый переименовывается в `.previous-<ver>…` и удаляется — процесс, который его держал, виден как `exe=(deleted)`.
- venv среды `~/.hermes/installs/<install>/environments/<hash>/venv`.

## Признаки рассинхрона (диагностировать по факту, не «что в YAML»)

```bash
systemctl --user show hermes-gateway.service -p ExecStart -p ExecStartPre
# ExecStart обычно = ~/hermes-agent/.hermes/bin/hermes gateway run  (launcher в checkout)
ls -l /proc/<gateway_pid>/exe /proc/<gateway_pid>/cwd
# exe → '…(deleted)' = процесс держит переименованный/удалённый бинарник
cat ~/.hermes/installs/<install>/facts.json | python3 -m json.tool
# packages.venv.environment = путь environment venv, ИЗ КОТОРОГО worker резолвит deps (НЕ pm-runtime/generations/selected.json)
diff -q ~/hermes-agent/cron/__init__.py ~/.hermes/installs/…/workspace/cron/__init__.py
# расходятся = две копии кода. NEW-фичи (scheduler_worker_env.py, worker_bootstrap.py) — маркер актуальной версии.
```

## Ключевые правила

1. **`hermes update` НЕ рестартит gateway.** После обновления процесс продолжает работать на
   старом бинарнике (`exe=(deleted)`) и старом checkout-коде. Единственный фикс — довести update
   И явно `systemctl --user restart hermes-gateway.service`; точечной правки одной настройки нет.
2. **Launcher `<checkout>/.hermes/bin/hermes` делает `sys.path.insert(0, <checkout>)`.** Значит код
   ядра берётся из CHECKOUT, а не из managed workspace — отсюда рассинхрон, если checkout отстал.
3. **Dependencies worker резолвит из environment venv в `facts.json` → `packages.venv.environment`.**
   `pm-runtime/generations/selected.json` — store-level и worker его НЕ читает. Чинить недостающий dep
   надо `pip --target <facts.json env venv>/lib/pythonX.Y/site-packages <pkg>`, а не в generation.
4. **Restart-safe cron worker запускается `sys.executable -m cron.scheduler`.** Если `cron/__init__.py`
   импортирует `from cron.scheduler import tick`, модуль уже в sys.modules при импорте пакета → runpy
   НЕ выполняет worker-`__main__` → «exited before ownership acknowledgement (exit 0)». Слой
   «No module named X» (exit 1) маскирует этот второй слой: починив dep, увидишь exit 0 — прогресс,
   а не регресс.
5. **`hermes update` — git-based и ретаргетится к owning checkout, а не обновляет managed сам по себе.**
   Updater требует `.git` в репо (git-based, не package-download). Запущенный из managed-venv
   (`.../environments/<hash>/venv/bin/hermes`), `hermes update` перенаправляется обратно на
   owning checkout через `retarget_to_owning_install` (путь в `installs/<install>/inputs/.project-root`).
   Значит source-of-truth обновления = checkout, а не managed workspace. Правильный порядок при
   большом отставании: сначала `git fetch` + `git reset --hard origin/main` в checkout (с git-тегом
   отката на старый HEAD), затем `hermes update` из managed-venv — он подхватит свежий checkout и
   переключит environment/generation. `hermes update --plan` — read-only диагностика, но ретаргетится
   точно так же (показывает, какой checkout будет обновлён).
6. **`hermes update --no-gateway-restart --yes`** откладывает рестарт (вывод «Gateway restart deferred»).
   Флаг есть только в свежих `update_cmd.py` — до полагания на него проверить `grep -c no-gateway-restart`
   в актуальном `hermes_cli/update_cmd.py`; на старом checkout флага нет.
7. **`hermes update` пере-сидирует `.env`/креды во ВСЕ профили, включая декомиссованные** → gateway
   отказывается стартовать: «Profile 'default' and '<name>' both configure telegram with the same
   credential — refusing to start the duplicate». Убранный ранее профиль «оживает» после update, если у него
   осталась копия `TELEGRAM_BOT_TOKEN` в собственном `.env`. Фикс — заархивировать/удалить декомиссованные
   профили (оставить только `default`), а не править токен: дубль креды уходит вместе с профилем.

## Verification Checklist

- [ ] Определён gateway unit + его ExecStart (launcher в checkout или managed)
- [ ] `/proc/<pid>/exe` проверен на `(deleted)`
- [ ] `facts.json` `packages.venv.environment` — правильный venv для чинки deps
- [ ] checkout vs managed workspace sync проверен (diff cron/gateway)
- [ ] Рестарт gateway выполнен ТОЛЬКО с явного разрешения + после него чеклист «После FF» (группа + DM)
