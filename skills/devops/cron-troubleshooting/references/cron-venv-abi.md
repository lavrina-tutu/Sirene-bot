Diagnostics; fixes are allowed only within the authorized BUGFIX scope.

### sys.path / venv mismatch (ExchangeMonitor)

**Problem:** A `no_agent=true` cron uses `hermes-agent/.venv/bin/python`, which does not have `exchangelib`. The script fails on import; the error is caught in `try/except`, producing `ModuleNotFoundError` rather than silence.

**Fix — use the tool's own venv, not a hardcoded foreign site-packages path:** wrapper called by the cron:
```bash
#!/bin/bash
exec /home/tkachenkoav/USERTOOLS/<Tool>/venv_linux/bin/python3 /home/tkachenkoav/.hermes/scripts/<script>.py "$@"
```
Place the wrapper in `~/.hermes/scripts/`: no_agent resolves only this directory and blocks symlink calls.

**Do not hardcode `.../lib/pythonX.Y/site-packages` in `sys.path`** — see the ABI mismatch below.

### venv ABI versus the cron interpreter (`No module named 'lxml.etree'`, 11.10.2026)

**Problem:** A `no_agent` `.py` cron runs through the runner's `cron/scheduler_script.py::project_python` = `sys.executable` of the managed Hermes venv, not through its shebang. This Python may have a different major version from the tool's venv. If the script hardcodes a version-specific site-packages path in `sys.path` (e.g. `MoveFromLoop/venv_linux/lib/python3.11/site-packages`) while the runner uses 3.14, binary `.so` modules (`lxml.etree` built for `.cp311`) will not load: `No module named 'lxml.etree'`, even though the package exists on disk (lxml 6.1.1 in venv_linux). An upstream update that recreated the managed Hermes venv with a new Python version triggered this case.

**Diagnosis:** To distinguish an ABI mismatch from a missing package, test the import with the cron's own interpreter, not the tool's. If `python3.14 -c "from lxml import etree"` fails and `venv_linux/bin/python3 -c "..."` succeeds, the ABI differs and the package is present.

**Fix — use the tool venv's interpreter, not site-packages in sys.path:**
- Use a bash wrapper in `~/.hermes/scripts/` calling `exec <venv>/bin/python3 <script> "$@"`;
- or resolve site-packages through `venv`/`sysconfig.get_paths()['purelib']`, never `lib/pythonX.Y/`.
- Each cron entry script needs its own wrapper (see “Address the entire class” below).

### Address the entire class — multiple entry scripts with one root cause (11.10.2026)

The same error (`No module named 'lxml.etree'`) appeared in two tool entry scripts (`mfl_urgent_check.py`, `mfl_digest.py`), both hardcoding one python3.11 path. Fixing the first left the second failing; the user reported that the error remained.

> Context (RU): «ошибка не ушла после починки».

**Rule:** When addressing a cron error's root cause, grep **all** neighboring entry scripts and wrappers for that tool (`<tool>_*.py`, `*_check*`, `*_digest*`, shared `sys.path` helper), not just the reported entry. The fix plan must list **all** affected entries or a shared wrapper mechanism. Fixing just one entry leaves the class open, and the next tick of another cron will reproduce the error.
