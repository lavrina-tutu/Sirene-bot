# Read-back итога фонового codex-exec прогона (evidance-verification)

## Проблема

Нотификация terminal-tool при завершении фонового `codex exec ... --json | tee evidence/<f>`-прогона
показывает только ХВОСТ лога (~171 символ) и `turn.completed` usage (`input_tokens/...`). Этого
недостаточно, чтобы знать, что роль реально сделала: какой коммит, сколько тестов прошло, какой
остаток заявлен. «exit code 0» ≠ «изменения сделаны», а «изменения есть в working tree» ≠
«коммит продвинулся». Продолжать серию раундов или объявлять закрытие части до read-back — нельзя.

## Штатный read-back (Python, execute_code)

```python
import re
D = "/home/tkachenkoav/WorkVault/..."          # каталог проекта
t = open(f"{D}/evidence/<файл>.log", encoding="utf-8", errors="replace").read()
msgs = re.findall(r'"type":"agent_message","text":"((?:[^"\\]|\\.)*)"', t)
last = msgs[-1] if msgs else "NO MESSAGES"
print(last.encode().decode('unicode_escape', errors='replace')[-4000:])
```

- Цель — ПОСЛЕДНЕЕ `agent_message` (роль в конце пишет итог: commit, команды+rc, passed, остаток,
  rollback).
- Кириллица в codex `--json` логе закодирована как unicode-escape: без `decode('unicode_escape')`
  вывод сырых JSON-эскейпов даёт кракозябры `ÐÐ¾Ð».`

## Сверить после read-back (не верить отчёту на слово)

Роль может заявить «закрыто / сделано», но фактически:
- `git log --oneline -1` не продвинулся (правка только в working tree) — проверить `git status --porcelain`.
- незакоммиченный срез может содержать зависающий тест — изолированная проверка `git checkout --`
  конкретных файлов и чистый повтор.
- коммит есть, но scope шире/уже разрешённого write-set.
Сверка: `git log --oneline -1`, `git status --short`, реже `git diff HEAD^ HEAD --name-status`.

## Правило

1. Фоновый `codex exec` завершился → нотификация. Это НЕ «нужно отвечать», это сигнал прочитать артефакт.
2. Read-back последнего отчёта из evidence-лога ОБЯЗАТЕЛЕН до любого следующего шага.
3. Фактическую проверку (git head / passed / worktree-чистоту) ставить по реальному выводу, не по декларации роли.
4. Сомнительный/прерванный срез → откат к стабильному HEAD и чистый повтор, не верить rc=0.
