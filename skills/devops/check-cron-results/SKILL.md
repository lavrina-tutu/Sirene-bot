---
name: check-cron-results
description: "Проверить последние результаты кронов Сирени. Загружать когда ждёшь ответа от Opus-крона или Саша спрашивает о статусе задачи."
triggers:
  - "проверь крон"
  - "что там с кроном"
  - "жду результата"
  - "opus ответил"
---

# Check Cron Results

## Когда загружать
- Когда ждёшь завершения Opus-крона
- Когда Саша спрашивает «что там по крону X»
- Когда нужно убедиться что задача выполнена

## Инструкция

### Шаг 1 — читай журнал
```
read_file("~/.hermes/cron-journal.md", limit=60)
```
Последние строки журнала = самые свежие результаты.

### Шаг 2 — если нужны детали по конкретному крону
Из строки журнала возьми `output: <путь>` и прочитай файл:
```
read_file("<путь из журнала>")
```
Ищи секцию `## Response` — там полный отчёт агента.

### Шаг 3 — если журнал пустой или задача не нашлась
Проверь напрямую:
```bash
ls -lt ~/.hermes/cron/output/ | head -10
cat ~/.hermes/cron/output/<job_id>/<файл>.md
```

## 🔴 Известные реальные проблемы (требуют починки)

### no_agent Script с `&&` — Script not found
**Симптом:** крон падает с `Script not found: /path/script.sh && bash /path/other.sh`
**Причина:** `no_agent=True` раннер передаёт всё поле `script` как путь к файлу — `&&` и всё после него трактуется как часть имени.
**Диагностика:** `last_status: error` в `cronjob list`, в output-файле крона — `Script not found: <длинная строка с &&>`
**Починка:** обновить крон через `cronjob action=update`, вынести составную команду в отдельный `.sh`-скрипт-враппер, в поле `script` указать только путь к нему.
```bash
# Пример враппера ~/.hermes/scripts/autosync_full_with_cleanup.sh
#!/bin/bash
bash ~/.hermes/scripts/autosync_github.sh && bash ~/.hermes/scripts/cleanup_after_sync.sh
```

---

## ⚠️ Известные ложные тревоги (не считать PROBLEM)
- `DialogBacklog` не имеет `.venv` — нормально, только stdlib
- Нет юнита `hermes-cron.service` — нормально, кроны идут через `hermes-gateway`
- Windows-пути в DEFAULT_DB / DEFAULT_FILE в старых скриптах — исправлено 03.06, не блокируют работу
- `hermes-gateway.service` запущен — это и есть основной процесс, отдельный cron-юнит не нужен

## Если Саша говорит «потерял связь с ТГ» / gateway не отвечает

Сразу проверить:
```bash
systemctl --user status hermes-gateway.service --no-pager | head -10
```
Если `failed` или `inactive` — рестартовать:
```bash
systemctl --user restart hermes-gateway.service && sleep 3 && systemctl --user status hermes-gateway.service --no-pager | head -5
```

Причину падения смотреть через лог (journalctl недоступен без прав adm/wheel):
```bash
cat ~/.hermes/logs/gateway.log | tail -60
```
Ключевые паттерны в логе:
- `SIGTERM` + `drain timed out` → systemd убил gateway, drain 180s не завершился, exit code 1
- `Restart=on-failure` должен поднять сам, но если не поднял — рестартовать вручную
- `httpx.ReadError` / `RemoteProtocolError` → сетевая ошибка ТГ, gateway восстанавливается сам (attempt N/10)

## Формат сводки vm_dialogbacklog
См. `references/dialogbacklog-report-format.md` — актуальный шаблон отчёта с датами `updated::` (реализован 25.06.2026, bk-094).

## Что сообщить Саше
- Статус (OK / PROBLEM)
- TL;DR из журнала
- Если PROBLEM — ключевые детали из полного отчёта
- Если крон ещё не завершился — сказать явно
