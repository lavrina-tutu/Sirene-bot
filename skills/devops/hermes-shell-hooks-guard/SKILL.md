---
name: hermes-shell-hooks-guard
description: "Use when: guard до обхода скиллов через pre_tool_call."
version: 1.0.0
author: Sirene
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [hermes, hooks, guard, enforcement, pre_tool_call, skills-first]
    related_skills: [hermes-feature, hermes-prompt-architecture, exchange-meeting]
---

# Hermes Shell-Hook Guard — системное принуждение работы через скиллы

Когда текстовая декларация («всегда через скилл») не даёт гарантии — агент всё равно может вызвать низкоуровневый API через `terminal`/`execute_code` (пример-инцидент: bk-172, создание встречи через голый `exchangelib.CalendarItem` вместо `create_meeting()` → потеряны Привет!/Zoom/Loop).

Единственный код-уровневый механизм Hermes, который видит `tool_name`+`args` **до** исполнения и может `block`/`approve`/`modify` — нативный shell-hook `hooks: pre_tool_call`. Это НЕ Cursor-хуки (`.cursor/hooks.json`) и НЕ гейты `skills.guard_agent_created`/`write_approval` (те про запись скиллов агентом, не про вызов API).

## Конфигурация

```yaml
# ~/.hermes/config.yaml
hooks:
  pre_tool_call:
    - matcher: "terminal|execute_code"
      command: "~/.hermes/agent-hooks/guard-calendaritem.sh"
      timeout: 5
```

- `matcher` — `tool_name` (regex): `terminal|execute_code`, или конкретный тул.
- Скрипт получает **JSON на stdin** (`tool_input.command`), возвращает **JSON на stdout**: `{}` → allow; `{"decision":"block","reason":"..."}` → блок.
- Управляй через `hermes config set hooks.pre_tool_call '[...]'` или ручную правку YAML. Бэкап конфига перед правкой.

## Критические питфоллы

### 1. НЕТ поля `fail_closed` в Hermes `ShellHookSpec`

(`agent/shell_hooks.py`, поля только event/command/matcher/timeout). Если скрипт крашится, таймаутит или возвращает невалидный JSON — хук **молча fail-open**: `logger.warning(...)` + `return None`, вызов tool идёт дальше БЕЗ блокировки.

=> Проектируй guard-скрипт zero-dependency bash/grep/python3, который НИКОГДА не крашится: никаких `set -e`, неотловленных исключений; не гибни при отсутствии `jq` — use `python3 -c`.

### 2. Consent для non-TTY (gateway/Telegram/cron) — обязателен, иначе хук тихо не регистрируется

При первом использовании в не-интерактивном процессе хук требует одно из:
- запись в `~/.hermes/shell-hooks-allowlist.json`:
  ```json
  {"approvals":[{"event":"pre_tool_call","command":"~/.hermes/agent-hooks/guard-calendaritem.sh"}]}
  ```
- либо `hooks_auto_accept: true` в config.yaml (глобально, небезопасно),
- либо `HERMES_ACCEPT_HOOKS=1`.

Без этого хук есть в конфиге, но НЕ работает, и пользователь не видит ошибки (только warning в логах). Проверка: `hermes hooks list` → хук должен быть `✓ allowed`. Держать `hooks_auto_accept: false` и добавлять точечно в allowlist — безопаснее.

## Паттерн guard-скрипта (bash, fail-open-safe)

```bash
#!/usr/bin/env bash
set +e
main() {
    payload="$(cat -)" || { echo '{}'; return 0; }
    [ -z "$payload" ] && { echo '{}'; return 0; }
    cmd="$(printf '%s' "$payload" | python3 -c "
import sys, json
try:
    d=json.load(sys.stdin); print(d.get('tool_input',{}).get('command',''), end='')
except Exception: pass
" 2>/dev/null)" || { echo '{}'; return 0; }
    [ -z "$cmd" ] && { echo '{}'; return 0; }
    # не наш точный target → allow
    if ! printf '%s' "$cmd" | grep -qF 'LOWLEVEL_API('; then echo '{}'; return 0; fi
    # whitelist легитимных путей → allow
    if printf '%s' "$cmd" | grep -qE 'create_meeting\\(|MeetingScheduler\\(|add_participant\\(|guard-override:'; then echo '{}'; return 0; fi
    cat <<'EOF'
{"decision":"block","reason":"Низкоуровневый вызов запрещён: используй скилл X (TODO причина). Для легитимных кейсов добавь # guard-override: <причина>."}
EOF
    return 0
}
main "$@"
```

## Правила проектирования

- **Отличай create от update.** `API(` (конструктор) → вероятно create, блокируем. `.get(...)` + `.save(...)` без конструктора → обычно легитимный путь скилла (update), не триггерит guard.
- **Оператор `# guard-override: <причина>`** — явный маркер в коде, чтобы guard пропускал задокументированные легитимные кейсы (напр. личные события с `participants == []`) без ручного вмешательства каждый раз.
- **False positive на диагностику.** `grep API file`, `cat util.py` тоже матчатся. Принять как безопасный компромисс (лучше false positive на read-only, чем false negative на создание). Опционально исключить команды, начинающиеся с `grep|cat|less|head|tail`.
- **Обфускация** (`"Calendar"+"Item("`) не закрывается регэксп-guard-ом — известное ограничение, задокументировать, не пытаться регэкспами.
- **Порядок внедрения:** системный guard ставить ПЕРЕД новым легитимным функционалом, который он должен пропускать (сначала guard, потом функционал, чей путь в whitelist — иначе новый легитимный вызов сразу упрётся в false positive).

## Верификация

- `hermes hooks list` → хук виден, `✓ allowed`.
- `hermes hooks test pre_tool_call --for-tool terminal --payload-file <file>` (если подкоманда есть).
- `hermes hooks doctor` → exec-bit, mtime drift, JSON validity.
- Синтетика: скормить скрипту JSON на stdin — target вызов без whitelist → `block`; с whitelist/override → `{}`.
- Верифицировать САМ на диске (`cat` артефакта, прогон тестов), не доверять self-report исполнителя (см. `hermes-feature` pitfall про gpt-6.1-sol).
- **PII-маскировка вывода может выглядеть как порча кода.** Hermes маскирует/транслитерирует чувствительное в agent/terminal-выводе: ФИО → «Ткаченko», телефон → «+792****2133». Если smoke-вывод исполнителя показывает «испорченную» строку — проверь реальный файл напрямую (`sed -n`, `read_file`): на диске данные корректны, искажение только в канале вывода. Не «чини» ложную проблему.

## Связанные скиллы

- `hermes-feature` — dev-процесс, роли архитектор/исполнитель через codex CLI / invoke-role (gpt-6-astra / gpt-6.1-sol)
- `hermes-prompt-architecture` — почему текстовые декларации в MEMORY/layers не блокируют tool-call
- `exchange-meeting` — пример применения (guard против прямого `CalendarItem`)