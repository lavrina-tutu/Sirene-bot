# USERTOOLS cron: venv/sys.path pitfall + exchangelib quirks

> Проверено 2026-08-26 при починке MoveFromLoop digest: `No module named 'exchangelib'` → `Unknown field path 'message_class' on folders`.
> Канон обновлён 2026-10-12 (`DEV/mfl-digest-lxml`, §16): обёртка — не гибрид. Гибрид «процесс 3.14 + site-packages 3.11» дал ErrorBus id 1825 (urgent) и id 1828 (digest).

## Питфолл 1: Hermes cron игнорирует shebang и гоняет .py через управляемый venv

**Симптом:** крон-скрипт USERTOOLS падает с `ModuleNotFoundError` на зависимости, которые лежат только в venv самого инструмента (например `exchangelib` / `lxml` в `MoveFromLoop/venv_linux/lib/python3.11/site-packages`). Ошибка может быть «поглощена» (исключение ловится, `exit 0`) — `last_status=ok` крона **не** равен успеху Exchange-блока.

**Корневая причина:** `hermes-agent/cron/scheduler.py` (`_posix_cron_script_argv()` → `project_python(repo)`) выполняет Python-скрипты через `sys.executable` управляемого venv Hermes (Python 3.14), а НЕ через shebang запускаемого скрипта и НЕ через venv инструмента. `project_python` оборачивает только `.py`; shebang `#!/usr/bin/env python3` не действует. Бинари инструмента — ABI 3.11 (`etree.cpython-311-*.so`, `exchangelib`) — под процесс 3.14 не импортируются, даже если в `sys.path` вставлен site-packages 3.11. Гибрид «процесс 3.14 + site-packages 3.11» недопустим.

**Фикс-канон (обязателен для КАЖДОГО USERTOOLS-скрипта, у которого инструмент имеет собственный venv):** крон исполняет скрипт через **shell-обёртку** с `exec` интерпретатора venv инструмента:

```bash
# ~/.hermes/scripts/mfl_<name>_cron.sh
set -euo pipefail
exec "/home/tkachenkoav/USERTOOLS/MoveFromLoop/venv_linux/bin/python3" \
     "/home/tkachenkoav/.hermes/scripts/mfl_<name>.py" "$@"
```

и у существующего cron-job поле `script` указывает на обёртку (`.sh`). Раннер для `.sh` запускает bash+exec; stdout и `no_agent` работают (проверено в проде). MoveFromLoop имеет **два** cron-entry: urgent `f61b26cbbdf5` → `mfl_urgent_check_cron.sh`, digest `2865cc674493` → `mfl_digest_cron.sh` — оба через свою venv_linux-обёртку. Паттерн экосистемы для чужого venv — `.sh` wrapper (`ofc_sync.sh`, `mofs_run_cron.sh`).

Внутри самого скрипта site-packages инструмента резолвятся от **активного** интерпретатора, без литерала версии:

```python
import sysconfig
_EXM = Path("/home/tkachenkoav/USERTOOLS/ExchangeMonitor")  # где лежит модуль
sys.path.insert(0, str(_EXM))
site = sysconfig.get_path("purelib")   # под venv_linux = venv_linux/lib/python3.11/site-packages
if site not in sys.path:
    sys.path.insert(0, site)
```

Запасной резолв (когда `purelib` не указывает в venv инструмента): `Path(sys.executable).resolve().parent.parent / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"`. Формула `Path(sys.executable).parent.parent / "site-packages"` неверна. Хардкод `.../lib/python3.11/site-packages` фиксом не считать.

**Правило:** ни один новый `.py`-джоб, импортирующий инструмент с собственным venv, не должен вызываться кроном на сырой скрипт. Не думай, что shebang или окружение cron'а подхватит venv инструмента. Утверждение, что shell-обёртка мешает no_agent-скриптам, ложно: no_agent-скрипты через обёртку работают (urgent в проде). Проверку не гонять через управляемый venv Hermes — это и есть баг.

## Питфолл 2: exchangelib 5.6.0 — `message_class` нельзя в `.only()`

**Симптом:** при EWS-fetch: `Unknown field path 'message_class' on folders (Inbox(...)) in only()`.

**Корневая причина:** поле `message_class` недоступно как path в QuerySet `.only()`/`.filter()`/`.order_by()` для папок в exchangelib 5.6.0. Валидное поле рядом — `item_class`.

**Фикс:** в `.only()` использовать `"item_class"`, а атрибут `message_class` выставлять ЛОКАЛЬНО как суррогат:

```python
.only("id", "subject", ..., "item_class")   # БЕЗ "message_class"
items = list(qs[:limit])
for item in items:
    ic = getattr(item, "item_class", None)
    if ic and not getattr(item, "message_class", None):
        object.__setattr__(item, "message_class", ic)   # message_class = item_class локально
```

**Проверка после фикса:** `grep -rn "message_class"` — в `.only()`/`.filter()`/`.order_by()` не должно остаться `message_class` (только атрибут-суррогат). Прогон тем же интерпретатором, что cron: `bash ~/.hermes/scripts/mfl_digest_cron.sh` → `exit_code=0`, stderr без `lxml.etree` / `Exchange FAIL`.

## Косвенная заметка
ErrorBus не запускает USERTOOLS — он лишь репортит их ошибки через `report_error.sh`. «Стали падать ошибки MFL после добавления errorbus» = добавленный `_report_error()` просто сделал ранее существовавшие сбои заметными. Ищи причину в самом крон-запуске, а не в errorbus.
