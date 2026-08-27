---
name: proxy-check
description: >-
  Use when user says "проверь proxy" or "протестируй proxy".
---

# Проверка прокси (proxy-check)

Скилл включается по словам «проверь proxy» / «протестируй proxy». Даёт рабочую
проверку HTTP(S)-прокси: живость, TCP/HTTP/HTTPS, гео/ASN/PTR/тип IP, вердикт
ACCEPT/REJECT. Инструмент установлен на ВМ, Go не нужен.

## Местоположение и запуск

Инструмент установлен:
```text
/home/tkachenkoav/USERTOOLS/proxycheck/linux-agent/
```
Запуск строго из этого каталога.

### Единичная проверка (`-proxy`)

```bash
cd /home/tkachenkoav/USERTOOLS/proxycheck/linux-agent
python3 -m proxycheck_linux -proxy HOST:PORT -user LOGIN -pass 'PASSWORD'
```
Вердикт REJECT даёт код 0 (проверка выполнена). Код 2 — ошибка запуска.

### Пакетная проверка списка (`-input`)

Для списка прокси (файл или переданный текст, до 5000+) — пакетный режим. Результат
пользователю — **`.xlsx`** (открывается в Excel с кириллицей и отдельными столбцами),
полный JSON — в файл, в stdout — только сводка.

```bash
cd /home/tkachenkoav/USERTOOLS/proxycheck/linux-agent
python3 -m proxycheck_linux -input <список.txt> [-xlsx out.xlsx] [-output out.json]
```

Формат входного списка: `host:port` / `host:port:user:pass`, либо CSV с заголовком
`ip,port,login,password` (распознаётся автоматически; заголовок и пустые/`#`-строки пропускаются).

При ненулевом коде процесса (краш/OOM/исключение верхнего уровня) — **сбой всего прогона**:
запускать через `error_bus_wrap.sh` (см. ниже), одиночные REJECT в шину НЕ идут.

## Запуск с логированием ошибок в шину (ErrorBus)

Сбои процесса/прогона целиком помещать в шину ошибок Hermes через готовую обёртку
`~/.hermes/scripts/error_bus_wrap.sh` (решение A+wrap). Вместо прямого вызова:

```bash
cd /home/tkachenkoav/USERTOOLS/proxycheck/linux-agent
~/.hermes/scripts/error_bus_wrap.sh --tool ProxyCheckLinux --job-id proxycheck_linux -- \
  python3 -m proxycheck_linux -input <список.txt> -xlsx <отчёт.xlsx>
```

Обёртка прозрачно возвращает stdout/stderr/exit code; при ненулевом коде сама пишет в `events.db`
и шлёт в Telegram-топик Errors. **Одиночные `REJECT`/`internal error` по прокси — не в шину**, это
данные отчёта.

## Что вернуть пользователю

- **Единичный (`-proxy`)**: весь stdout без сокращений — таблицу `PROXY VERDICT TCP HTTP HTTPS
  TARGETS COUNTRY REGION EXIT_IP MYIP_RU IP_TYPE CONF ASN_ORG REASON`, строку «Итого», полный JSON.
- **Пакетный (`-input`)**: краткую сводку (Итого, разбивку REJECT по стадиям) + **путь к `.xlsx`**
  и JSON-файлу, НЕ дампать файлы целиком в чат.

## Правила

- Пароль прокси в чате не повторять; в отчёте — только `user=...`.
- Не резать ответ единичного режима (запрещено «ЕСТЬ/НЕТ» без таблицы+JSON). Не заменять вызовами curl.
- Не менять Windows-сборку (`proxycheck.exe`, `cmd/`, `internal/`).
- Не убирать FAIL по yandex/гео/ASN — часть полного отчёта.
- Пакетных `.xlsx`/JSON — не коммитить, не прикладывать к ТЗ/скиллам.