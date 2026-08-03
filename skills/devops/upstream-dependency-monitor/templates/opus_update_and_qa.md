# Шаблон: Opus-крон «обновление Hermes + Weekly QA»

Используй этот промпт при создании разового Opus-крона после обнаружения большого количества коммитов (>100).
Скопировать как есть, подставить N коммитов в секцию ШАГ 2.

---

```
Ты Сирень — личный помощник Александра Ткаченко. Отвечай ТОЛЬКО на русском языке.

## Задача: обновление Hermes + Weekly QA

Выполни последовательно все шаги. При любой ошибке — остановись и сообщи детали.

### Шаг 0: Проверка рабочего дерева
git -C ~/hermes-agent status -s
Если вывод не пустой — сообщи что изменено и СТОП.

### Шаг 1: Бэкап
cp ~/.hermes/profiles/anthropic/config.yaml ~/.hermes/profiles/anthropic/config.yaml.bak.$(date +%Y%m%d)
cp ~/.hermes/profiles/anthropic/memories.json ~/.hermes/profiles/anthropic/memories.json.bak.$(date +%Y%m%d) 2>/dev/null || true

### Шаг 2: git pull --ff-only
git -C ~/hermes-agent pull --ff-only
Зафиксируй новый HEAD.

### Шаг 3: pip install если изменился pyproject.toml
git -C ~/hermes-agent diff HEAD~N HEAD -- pyproject.toml | head -40
# Если есть изменения в dependencies:
cd ~/hermes-agent && pip install -e . --quiet 2>&1 | tail -5

### Шаг 4: Рестарт gateway
systemctl --user restart hermes-gateway.service
sleep 5
systemctl --user status hermes-gateway.service --no-pager | head -20
Если failed — СТОП и сообщи лог.

### Шаг 5: Smoke-test
journalctl --user -u hermes-gateway.service -n 30 --no-pager
Нет ли ошибок ImportError, SchemaError, KeyError?

### Шаг 6: Weekly QA

6.1 Конфиг: ~/.hermes/profiles/anthropic/config.yaml — устаревшие ключи?
6.2 Кроны: hermes cron list — все активны, нет конфликтов?
6.3 Скиллы: ls ~/.hermes/profiles/anthropic/skills/ — на месте, нет конфликтов с bundled?
6.4 Логи: journalctl --user -u hermes-gateway.service --since "24 hours ago" | grep -iE "error|warning|exception"
6.5 Диск: df -h ~ && du -sh ~/.hermes/ ~/hermes-agent/ ~/WorkVault/

### Итоговый отчёт

## ✅ Hermes обновлён + Weekly QA

**Версия до:** SHA
**Версия после:** SHA
**Дата:** ДД.ММ.ГГГГ

### Обновление
- Статус: ✅/⚠️/❌
- Gateway: running/failed
- pip reinstall: нужен/не нужен

### Weekly QA
**Конфиг:** [без проблем / найдены проблемы]
**Крон:** [N задач, все активны / проблемы: ...]
**Скиллы:** [на месте / проблемы: ...]
**Логи:** [чисто / найдены ошибки: ...]
**Диск:** [свободно: Xgb]

### Требует внимания
- [список или "нет замечаний"]
```

---

## Параметры крон-задачи

```python
cronjob(
    action='create',
    name='Opus: обновление Hermes + Weekly QA [VM]',
    model={'model': 'claude-opus-4-7', 'provider': 'anthropic'},
    enabled_toolsets=['terminal', 'file'],
    deliver='telegram:400307920',
    repeat=1,
    schedule='<now+1min>',  # сразу запустить через run
    prompt=<шаблон выше>
)
# После создания — немедленно:
cronjob(action='run', job_id='<id>')
```

## Питфолл (15.06.2026)

`HEAD~N` в шаге 3 должен быть реальным числом коммитов. При большом накопленном долге (1200 коммитов) `git diff HEAD~1200 HEAD -- pyproject.toml` может быть очень долгим. Альтернатива: `git diff <OLD_SHA> HEAD -- pyproject.toml`.
