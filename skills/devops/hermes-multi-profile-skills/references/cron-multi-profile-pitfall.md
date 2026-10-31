# Cron multi-profile pitfall — cronjob tool и CLI не видят кроны из tz-dev

## Симптом

Из профиля `tz-dev` (или любого non-default профиля):
- `cronjob(action='list')` → `count: 0, jobs: []`
- `hermes cron list` → **видит** кроны, но `hermes cron run <name>` → "Job not found"
- При этом `~/.hermes/cron/jobs.json` содержит 30+ задач

## Причина

`cronjob` tool привязан к профилю сессии и читает cron-хранилище только из контекста текущего профиля. Кроны же живут в общем `~/.hermes/cron/jobs.json` и управляются шлюзом напрямую. CLI `hermes cron list` работает (читает jobs.json), но `hermes cron run` падает — видимо, ищет job в профильном контексте, а не в shared.

## Рабочие обходные пути

### 1. Ручной self-check (если нужно проверить VM прямо сейчас)

Выполнить проверки из промпта крона вручную через `terminal`:
```bash
systemctl --user status hermes-gateway.service --no-pager -l
df -h ~ | tail -1
curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 https://api.anthropic.com
free -h
ps aux --sort=-%mem | grep "hermes.*gateway" | grep -v grep
du -sh ~/WorkVault
ls -lt ~/.hermes/cron/output/5d16b96a9ed5/ | head -3
```

### 2. Подождать расписания

Кроны отрабатывают по расписанию — шлюз управляет ими напрямую, независимо от текущего профиля сессии.

### 3. Запуск из default-профиля

Если нужен именно ручной запуск через CLI — переключиться на default:
```bash
HERMES_PROFILE=default hermes cron run vm_selfcheck
```
Но на практике это тоже может не сработать (прецедент 09.08.2026).

## Broken pipe при выполнении крона

Ошибка `[Errno 32] Broken pipe` у крон-задач — transient. Обычно означает потерю stdout-канала при стриминге ответа от LLM (шлюз ТУТУ мог дропнуть соединение). Не системный — повторный запуск по расписанию работает.

Признаки transient (не чинить):
- Только 1 фейл за всё время
- Gateway не перезапускался (тот же PID)
- OOM-killer не срабатывал
- Предыдущий запуск был OK
