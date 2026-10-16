---
name: PIIScan
version: 1.3.0
status: released
created: 2026-08-27
updated: 2026-09-21
author: Cursor (claude-sonnet-5-thinking-medium)
depends_on: [ErrorBus, pii-privacy, MoveFromLoop, ExchangeMonitor]
---

# PIIScan (регресс-скан остаточного ПДн) — ТЗ

## §1. Цель

Еженедельный детерминированный (stdlib, без LLM) скан файловой системы Hermes/WorkVault на **остаточные** ПДн-«карточки людей» и **открытые креды/токены**, встающий в `vm_selfcheck` **после** завершения работ `~/WorkVault/Hermes-Backlog/TZ/pii-privacy/pii_impl_plan.md` — как регресс-контроль поверх вычищенной системы, с репортом находок через ErrorBus (`report_error.sh`, `--tool PIIScan`).

## §2. Контекст и отличие от pii-privacy

- **`pii-privacy`** (`TZ/pii-privacy/pii_impl_plan.md`) закрывает **источник** натекания: `render_contact`/`mask_contact` на всех точках вывода AnywhereContacts/OrgLookup, удаление `tutu-contacts.md`, блок на генерацию plaintext-контактов. Это профилактика на уровне кода-потребителя.
- **`PIIScan`** — **аудит остаточного факта** по всей охваченной ФС/сессиям/архиву: то, что уже осело на диск (в т.ч. до внедрения `pii-privacy`, или из источников, не относящихся к AnywhereContacts — свободный текст в WorkVault, крон-логи, session-архивы). Не пересекается по механике: `pii-privacy` меняет код-потребитель, `PIIScan` только читает файлы и репортит находки — никаких правок кода/данных.
- Встраивается **после** `pii-privacy`, потому что до неё поток свежих находок был бы бесконечным (источник ещё тёк) — скан имеет смысл как **регресс-контроль** над уже вычищенной системой.

## §3. Правило «ПДн-инцидент» (карточка человека) — ПЕРЕСМОТРЕНО 09.09.2026

**Инцидент = комбинация двух полей в одном контексте:**
1. **Идентификатор — ТОЛЬКО полное ФИО или хотя бы «Имя Фамилия» (2 слова с заглавной кириллицы).** Голый внутренний логин (`имя.фамилия`) без рядом стоящего ФИО — **НЕ ПДн** (дословно Саши 09.09: «если рядом с логином нет полного ФИО или хотя бы ФИ — это не ПДн»). Логин больше не входит в набор идентификаторов, `login+*` типы исчезают из новых находок.
2. **Атрибут связи** — email **или** телефон **или** messenger-handle (`@handle`) **или** должность.

Тревожит **только совпадение полей из (1) и (2) в одном контексте** (декартово `ФИО × атрибут` внутри контекста = это и есть связка). Одиночное упоминание ФИО без атрибута, email без идентификатора, и голый логин без ФИО — не инцидент. Итог: `field_type` реальных инцидентов — только `fio+email|fio+phone|fio+handle|fio+position`.

**Контекст** (порядок проверки, первое совпадение — победитель):
- для `.jsonl`/`.json`-документов — одно строковое поле = один контекст (рекурсивно по строковым значениям, **НЕ** декартово по соседним полям объекта; ФИО в одном поле + email в другом ≠ инцидент). `scan_json_file` — по каждому строковому полю отдельно, не декартово. При невалидном JSON — обрабатывать содержимое как текст (fallback-text), не бросать исключение.
  - **Длинное / многострочное строковое поле (v1.3.0, инцидент 19.09):** если значение содержит `\n` **или** длина > 500 символов — сканировать **построчно как текст** (окно ±1 строка), не как один контекст. Иначе dump в одном JSON-поле (`output` на 37 КБ) даёт декартово «все ФИО × все email» внутри поля (4764 ложных пар из ~15 истинных связок).
  - **Короткое однострочное поле** (нет `\n` и длина ≤ 500) — как сейчас: ФИО+email в одной строке JSON = инцидент (контракт `test_json_same_field_fio_email_is_pii` жив).
- для текстовых файлов (`.md`, логи) — одна строка; если не найдено — окно ±1 строка (для случаев «ФИО:\nEmail:» на соседних строках).

**Предохранитель пар (v1.3.0):** `MAX_PAIRS_PER_CONTEXT=32`. Пары сверх лимита — не finding; в summary прогона счётчик `truncated_pairs` (факт обрезки, без сырых значений).

## §4. Severity по месту находки

| Зона | Что | Severity | Сканируется |
|---|---|---|---|
| `~/.hermes/state.db` | живая переписка (рабочий контекст) | — | **НЕТ** (исключено целиком) |
| `~/.hermes/sessions/*.jsonl` | файловые архивы сессий | critical | да |
| `~/WorkVault` (кроме whitelist, §5) | архив vault | critical | да |
| `~/WorkVault_backup` | бэкапы | critical | да |
| `~/.hermes/cron/output/` | вывод кронов | critical | да |
| `~/.hermes/logs/` | логи | critical | да |
| `~/.hermes/error_bus/` | логи/БД шины ошибок | critical | да |
| `~/USERTOOLS/` | код и рабочие данные USERTOOLS; TaskRefresh `session/` сканируется (не whitelist), содержимое ограничено TTL 5 дней (§14.1) | critical | да |

`state.db` исключён из скана полностью (не читается ни в каком режиме) — не «зелёная зона в отчёте», а зона вне охвата инструмента (снижение нагрузки/конкурентного риска на живую БД гейтвея). `sessions/*.jsonl` — файловый архив тех же диалогов, покрывает архивную часть.

## §5. Whitelist (не сканируется вообще — ни ПДн-правило, ни креды)

- `~/WorkVault/Contacts/` (`contacts.enc` — зашифрован, штатное хранилище)
- `~/WorkVault/Entities/*` (открытые карточки людей/проектов — штатная рабочая база vault, легитимна по определению)
- `~/WorkVault/Inbox/`
- `~/WorkVault/UserManuals/`
- `~/WorkVault/Confluence/**` (уставы, минутки, корп. документы) — добавлено 09.09
- `~/WorkVault/Projects/**` — весь`Projects/`, добавлено 09.09. **Финальное решение Саши:** исключается вся зона (в т.ч. 1-1 заметки сотрудников). Перекрывает раннюю правку ревизора «только TrisigmaFull».
- `~/WorkVault/Meetings/**` (транскрипты встреч) — добавлено 09.09

**НЕ** в whitelist (сканировать): `~/USERTOOLS/TaskRefresh/session/` (там TTL 5 дней, §14.1), `Hermes-Backlog/TZ/**`, `~/.hermes/error_bus/tests/`.

Whitelist — **список путей**, проверяется префиксом абсолютного пути перед разбором файла (skip до чтения содержимого, не после).

**Обход (v1.3.0):** whitelist-корни WorkVault (`Contacts/`, `Entities/`, `Inbox/`, `UserManuals/`, `Confluence/`, `Projects/`, `Meetings`) **prune из `dirnames`** в `os.walk` — не генерировать пути и не `stat`. `~/USERTOOLS/`: prune всего дерева, кроме `TaskRefresh/session/`. Skip *после* генерации пути недостаточен (на инциденте 19.09 — лишние 2045+987 `stat`). `~/.hermes/state.db` в корни обхода не добавлять.

## §6. Категория «Креды/токены/секреты» (отдельно от ПДн-правила)

**Не смешивается с правилом «карточки» (§3).** У кредов своё правило: **наличие секрета в открытом виде = critical** (без комбинаторики двух полей — секрет сам по себе есть находка). Ищутся в тех же местах, что и ПДн (§4), **кроме** whitelist-папок (§5 — Inbox/UserManuals/Contacts/Entities тоже не смотрим для кредов).

Индикативные категории (детерминированные regex, финальный набор и точная калибровка — на этапе реализации):
- AWS-ключи (`AKIA[0-9A-Z]{16}`), OpenAI-подобные (`sk-[A-Za-z0-9]{20,}`), Telegram bot token (`\d{9,10}:[A-Za-z0-9_-]{35}`);
- `password/token/api[_-]?key/secret\s*[:=]\s*['"]?\S{6,}` (регистронезависимо; требователен к границе `(?<![A-Za-z0-9_])` перед ключевым словом — фикс 09.09);
- `Bearer [A-Za-z0-9\-_.]{20,}`;
- PEM-блоки приватных ключей (`-----BEGIN ... PRIVATE KEY-----`).

**Правка 09.09 — креды в URL-встраиваниях НЕ секрет:** `token=`/`boardAccessToken=`/`access_token=` в **query-string** (перед матчем `?`/`&`, слева `https://miro.com`, ключ `boardAccessToken`) — это штатный Miro/embed-механизм доступа по ссылке, не инцидент. Пропускается через `_is_miro_live_embed_query_token()` + lookbehind `(?<![A-Za-z0-9_])` (блокирует `token=` внутри `boardAccessToken=`). Секрет = только ключи/PEM/Bearer в открытом виде вне query-string.

**Carve-out фейковых токенов (v1.3.0, решение Саши 21.09):** заглушки в фикстурах/планах ТЗ **не** дают `category=credential`. Минимум подстрок в значении: `AAFake`, `Example`, `your_token_here` и разумные аналоги того же класса (`AAFakeYamlTokenValue`, `changeme`, `placeholder`). Живой Telegram-токен (`\d{9,10}:[A-Za-z0-9_-]{35}` без этих маркеров) остаётся critical. Пример `token: "8821170000:AAFakeYamlTokenValue________"` — не инцидент; бота не перевыпускать, файл-план не удалять.

## §7. Первый прогон — baseline

Первый запуск (файл состояния `~/.hermes/pii_scan/baseline.json` отсутствует) фиксирует всё найденное как **известное состояние**, без создания инцидентов:
- **один** сводный отчёт через `report_error.sh --tool PIIScan --severity info` — счётчики по категориям/путям (без деталей per-finding в Telegram, только сводка); индивидуальных сообщений в `events.db` на каждую находку **нет** (поэтому vanished для `status=baseline` резолвится напрямую, §8.4);
- **никаких `critical`** на первом прогоне;
- каждая находка записывается в `baseline.json` со статусом `baseline` и в `audit_history.jsonl` (`event: baseline_seen`).

Со второго прогона инциденты создаются **только по новым находкам** (прирост относительно `baseline.json`), не по всему объёму.

## §8. Дедупликация и жизненный цикл между прогонами

### 8.1 Внутренний dedup_key (никогда не пишется на диск в открытом виде)
`dedup_key = sha256(category + "|" + normalized_path + "|" + field_type + "|" + raw_value)[:16]` — вычисляется **в памяти** над сырым (немаскированным) значением, на диск пишется **только хэш** (16 hex) + маскированное представление. Сырое значение никогда не персистится.

### 8.2 `~/.hermes/pii_scan/baseline.json`
```json
{
  "<dedup_key>": {
    "category": "pii_card|credential",
    "path": "~/WorkVault/...",
    "field_type": "fio+email|fio+phone|...|aws_key|...",
    "masked_value": "Ив***.* / tk****@tutu.ru",
    "status": "baseline|open|resolved",
    "first_seen": "2026-09-03T03:30:00",
    "last_seen": "2026-09-10T03:30:00",
    "error_bus_message": "<точный текст message, переданный в report_error.sh>"
  }
}
```
Записи **не удаляются** при резолве — статус меняется на `resolved`, `last_seen` фиксирует момент исчезновения. Для ключей v1.3.0+ `error_bus_message` = текст **сводного** message прогона (общий на пачку `new` этого прогона) либо пусто; поле **не** уникально per-finding.

### 8.3 `~/.hermes/pii_scan/audit_history.jsonl`
Append-only журнал (`event: baseline_seen|incident_new|resolved`, `dedup_key`, `masked_value`, `category`, `path`, `ts`) — исторический факт былой утечки сохраняется **навсегда**, без `DELETE`, независимо от текущего статуса в `baseline.json`.

### 8.4 Логика прогона (детерминированный скрипт, без LLM)

**Порядок (v1.3.0, инцидент 19.09, решение Саши 21.09):** сначала собрать `new` / `persisting` / `vanished` **целиком в памяти**. Репорт и резолв — **действия**; `baseline.json` сохранять чекпоинтами **после** соответствующих действий. Порядок «save всех ключей до репорта» отвергнут: убийство между save и репортом оставит ключи `persisting` без события в ErrorBus навсегда.

1. Обойти пути §4 (минус whitelist §5, prune §5), собрать находки (raw, in-memory).
2. Посчитать `dedup_key` для каждой находки → множество `current_keys`.
3. Если `baseline.json` не существует → режим **baseline** (§7), выход.
4. В памяти: `new = current_keys − known_keys`, `persisting = current_keys ∩ known_keys`, `vanished = known_keys(status=open ∪ baseline) − current_keys`.
5. **Репорт в ErrorBus — ровно 1 сводное событие за весь прогон** (не per-finding, не потолок `MAX_REPORTS_PER_RUN`):
   - `|new| > 0` → **один** вызов `report_error.sh --tool PIIScan --severity critical`. Message: счётчик новых находок. Detail: разбивка по файлам и категориям (`pii_card`/`credential` + `field_type`), **2–3 masked sample** (не сырьё). Пути в message/detail — `path={finding.path!r}` (пробелы экранируются repr).
   - `|new| = 0` → в ErrorBus **не писать ничего** (молчание). Сводка `новых=0` / `резолвнуто=N` / `truncated_pairs=…` — **только stdout** self-check.
   - Потолок-30 per-finding **не вводить** (отклонено 21.09).
6. **После** сводного репорта (п.5): для ключей `new` батчами `BATCH=20` — статус `open` в dict baseline, `audit_history.jsonl` `incident_new`, **затем** `save_baseline()`. Убитый прогон: уже записанные ключи на следующем = `persisting` (без повторного репорта); хвост `new` даст ещё одно сводное событие — приемлемо vs «никогда не репортить».
7. `vanished` — тоже **батч + чекпоинт** baseline (`BATCH=20`), не N spawn подряд (811 резолвов = тот же таймаут 280/560 с):
   - `status=baseline` — резолв **напрямую**: в `baseline.json` статус `resolved` + `audit_history.jsonl` `event: resolved`. **Без** поиска в `events.db` (для baseline-записей индивидуальных сообщений в `events.db` нет: baseline-прогон создаёт один сводный info-отчёт, §7).
   - `status=open`, ключ с **уникальным** legacy `error_bus_message` (per-finding события v1.2.0) — найти открытую запись в `events.db` по `tool=PIIScan AND message=<error_bus_message>` (read-only SELECT) → `error_bus_cli.py resolve <id> --note "PII-scan: находка не подтвердилась в прогоне <ts>"`; в `baseline.json` статус `resolved`; в `audit_history.jsonl` `event: resolved`. Батч резолвов → чекпоинт baseline.
   - `status=open`, ключ v1.3.0+ (сводный `error_bus_message` на пачку прогона, не уникален per-finding) — **только** baseline `resolved` + audit; **не** спавнить N `resolve` на одно и то же сводное message. Сводное событие прогона — отчёт о прогоне, не карточка находки; авто-резолв vanished отдельных ключей его не закрывает.
   - Резолвить в ErrorBus только если найдена ровно одна открытая (`status='open'`) запись; при 0 или >1 — предупреждение в stdout, не трогать `events.db`, не фейлить прогон (§15 риск 6).
8. `persisting` → обновить только `last_seen` в dict, **без** повторного `report_error.sh`. Чекпоинт baseline батчами после обновления dict.

**Атомарность `save_baseline()` (v1.3.0):** писать во tempfile в том же каталоге + `os.replace` (как atomic JSON write в Hermes). Kill mid-write не оставляет битый `baseline.json` — читается предыдущий валидный JSON.

**Резолв через Вариант 2 (§«Закрытие инцидента» брифа):** сам факт находки не исчезает из истории (`audit_history.jsonl` + `baseline.json` со статусом `resolved`), закрывается только текущий open-статус в ErrorBus (для legacy per-finding).

## §9. Маскирование (Вариант 1 — полное)

В отчёте/detail/инциденте — **только**: путь + тип + количество + маскированное значение (`tk****@tutu.ru`, «Иванов И.\\*»). Сканер **не размножает** ПДн — сырые значения не пишутся ни в `baseline.json`, ни в `audit_history.jsonl`, ни в `message`/`detail` `report_error.sh`, ни в stdout/логи самого скрипта.

**Правка 09.09:** для **стерильного** хранения (baseline/audit) используются **собственные** стерильные `mask_identifier`/`mask_attribute`/`mask_credential` в `pii_scan.py` (email маскируется и local, и domain; короткие ≤3 → `****`). `mask_pii` из `AnywhereContacts/logger.py` **НЕ используется** для хранения — она оставляет домен открытым и не маскирует короткие строки (питфолл 27.08). Общий хелпер гигиены логов — `~/.hermes/pii_scan/redact.py::redact_fio_email_phone()` (на базе patterns.py; вырезает ФИО/email/тел/креды, логины и `@handle` сохраняет).

## §10. Компоненты

```
~/.hermes/scripts/
  pii_scan.sh                # bash-обёртка: активация venv (если нужен), запуск pii_scan.py, exit 0 (fail-soft)

~/.hermes/pii_scan/
  pii_scan.py                 # точка входа: обход путей §4, категории §3/§6, дедуп §8, report_error/resolve вызовы
  patterns.py                 # regex-паттерны (ФИО/логин/email/phone/messenger/должность-лексикон; креды §6 + carve-out фейковых токенов v1.3.0)
  redact.py                   # redact_fio_email_phone(text) — гигиена логов (§9), без mask_pii AnywhereContacts
  baseline.json                 # состояние между прогонами (§8.2)
  audit_history.jsonl            # append-only исторический журнал (§8.3)
```

Никакого сервиса/демона — bash+python3 stdlib (`re`, `hashlib`, `json`, `pathlib`, `sqlite3` для read-only чтения `events.db` на шаге резолва vanished для записей `status=open`). Маскирование — собственные `mask_*` в `pii_scan.py` (§9); AnywhereContacts не импортируется.

## §11. Встраивание в `vm_selfcheck`

- Новый пункт **№12** в промпте крона `vm_selfcheck` (после текущего п.11 «LLM-аудит за последние 7 дней»), по аналогии с п.11 (`llm_anomaly_scan.sh`):
  ```
  bash ~/.hermes/scripts/pii_scan.sh
  ```
  Скрипт сам формирует находки, вызывает `report_error.sh` (v1.3.0: **не более одного** critical за инкрементальный прогон; `|new|=0` — без вызова шины) / резолвит vanished через `error_bus_cli.py` (legacy per-finding, батчами), выводит на stdout компактное резюме (baseline / N новых / N резолвнуто / `truncated_pairs`) для включения в отчёт self-check — **в том числе при нуле новых**.
- **Предусловие явное в тексте промпта:** пункт активируется только после того, как `pii_impl_plan.md` помечен реализованным (это условие фиксируется руками при внедрении — Cursor не проверяет автоматически статус другого плана).
- Изменение промпта `vm_selfcheck` — правка `jobs.json` (промпт хранится только там, отдельного master-файла self-check нет — см. §12). Side-effect по императиву (после «берём в работу»), крон **не пересоздаётся** автоматически.

## §12. Почему ТЗ — отдельный файл `TZ/PIIScan/`, не `TZ/SelfCheck/`

Рассмотрены два варианта: (а) `TZ/SelfCheck/SelfCheck_TZ.md` как мастер-ТЗ на весь `vm_selfcheck`, (б) отдельный `TZ/PIIScan/PIIScan_TZ.md`.

**Выбор — (б), по прецеденту `LLMAnomalyScan`** (`ErrorBus_TZ.md` §11.2: «`llm_anomaly_scan.sh` вызывает `report_error.sh` ... Mode A, без собственного `--job-id` в реестре»): у `vm_selfcheck` **нет и не создаётся** master-ТЗ — промпт крона живёт только в `jobs.json`, пункты 1-11 никогда не документировались отдельными ТЗ-файлами (это операторские проверки, не самостоятельные инструменты). `PIIScan`, в отличие от них, имеет собственную нетривиальную логику (правило комбинаций §3, baseline/резолв §8, дедуп, отдельный State-файл) — заслуживает master-файла по инварианту tz-workflow «один master-файл на инструмент», но **не тянет за собой** создание `SelfCheck_TZ.md` — это осталось бы недокументированной операторской практикой, как и раньше (вне рамок этой задачи; если Саша решит документировать весь `vm_selfcheck` как мастер-ТЗ — отдельная задача).

## §13. Регистрация в `instrumentation_registry.json`

**Решение — без новой записи**, по тому же прецеденту (`ErrorBus_TZ.md` §11.2, `LLMAnomalyScan`): `pii_scan.sh` — Mode A (self-report), вызывается **внутри** уже существующего `job_id: vm_selfcheck` (зарегистрирован как `"agent"`), а не как отдельный top-level cron `job_id`. Отдельная запись `{"pii_scan": "self"}` избыточна и не соответствует семантике реестра (`job_id → режим`, а не `скрипт → режим`). Аудит `error_bus_cli.py audit` не найдёт здесь конфликта A/B — как и с `LLMAnomalyScan`.

## §14. Что НЕ трогать

- `report_error.sh`/`_db.py`/схему `events.db` — не менять, использовать как есть (`--tool PIIScan`).
- `error_bus_cli.py resolve` — использовать штатную команду, не писать свой SQL `UPDATE` по `events.db` (нарушение инкапсуляции ErrorBus).
- Consumer-логику контактного матчинга (`contacts_resolver`, matcher в `AggregateFromMeetings`/PFS/MOFS) — их полный доступ к email легален (внутренняя логика), скан их не касается.
- Whitelist-папки (§5) — не сканировать вообще, ни для ПДн, ни для кредов.
- `~/.hermes/state.db` — не читать, не открывать соединение, даже read-only.
- Маскирующие функции `anywhere_contacts/logger.py` — **не импортировать** (`mask_pii` оставляет домен, не маскирует короткие строки). Для хранения — собственные `mask_identifier`/`mask_attribute`/`mask_credential` в `pii_scan.py` (§9). AnywhereContacts **НЕ** используется для хранения.
- Планировщик кронов (`cron/scheduler.py`) — не менять (как и в ErrorBus §6).
- Не создавать `SelfCheck_TZ.md` в рамках этой задачи (§12).
- Крон `vm_selfcheck` не пересоздаётся/не рестартуется автоматически — правка промпта только по явному императиву.
- **Не менять** `_db.py`/`report_error.sh`/`mfl_digest.py` верхнеуровнево; `~/.hermes/scripts/error_bus_cli.py` — только redact на выводе `cmd_show`. `pfs_batch` — **НЕ трогать** (решение 09.09).
- `hermes-agent.next` и `_Archives` — не править.
- **Ядро Hermes не трогать (решение Саши 21.09):** `hermes-agent/tools/process_registry_results.py` вне скоупа этого CHANGE. Redact-on-write ФИО/email на записи receipt — отдельная задача, только по отдельному императиву.
- MeetingScheduler CLI / ExchangeMeeting / ExchangeMonitor CLI — **не менять** (решение Саши 21.09; инцидент 19.09 — не баг назначения встреч, источник — ад-хок `exchangelib` в terminal).
- ErrorBus (`report_error.sh` / `_db.py` / схема) — не менять; лечится **числом** вызовов со стороны PIIScan (§8.4), не выключением Telegram в шине.
- `jobs.json` / крон `vm_selfcheck` — не пересоздавать; таймаут агента 280/560 **не раздувать** как фикс. Сканер должен укладываться сам.

**HF:docs-handoff (скиллы, не код USERTOOLS; v1.3.0 решение Саши №4):** питфолл в скилл `exchange-meeting` (+ ссылка из `exchange-meeting-bulk` / `exchange-recurring-meetings`): без ад-хок exchangelib-скриптов с печатью участников/тем; календарь смотреть через CLI JSON; в чат — имена/логины, без пар ФИО+email. Это пункт docs-handoff, не `HF:impl` PIIScan.

## §14.1. Гигиена логов на записи (решение 09.09)

Каналы, где PIIScan видит critical: `~/.hermes/logs/{agent,errors,gateway}.log` + `~/.hermes/cron/output/**`. Правило: **хранить только логины, не писать ФИО/тел/email** в телах и `inbound msg=`. Затронутые файлы:
- `~/hermes-agent/gateway/run.py` — из INFO `inbound message` убраны `msg=`/`reply_to_text=` (живой код; **локальный патч разъедётся при merge upstream — фиксировать pitfall в hermes-feature**).
- `~/USERTOOLS/MoveFromLoop/movefromloop/formatter.py::format_post` — `first_line` тела Loop через `redact_fio_email_phone`; `@username` НЕ трогать. ExchangeMonitor `formatter.py::format_email` — суть (subject/сниппет) через redact.
- `~/USERTOOLS/TaskRefresh/taskrefresh/session_store.py` — TTL `prune_history()` (5 дней) при `save_session`; `HISTORY_TTL_DAYS=5` в `config.py`.
- `~/.hermes/scripts/llm_anomaly_scan.sh` — TTL `find ... -mtime +5 -delete` + перезапись файла компактом `{subtype,is_error,result}` (без tool/conversation payload) после прогона.
- `~/.hermes/scripts/error_bus_cli.py::cmd_show` — redact при выводе row/cron/log/session.
- **PFS `pfs_batch` НЕ менять, НЕ переводить в no_agent** (решение 09.09; отдельная задача).

**Канал `~/.hermes/logs/process-results/` (v1.3.0, инцидент 19.09):** receipts терминала (`proc_*.json`, TTL 7 дней / max 64 файла, prune при следующей записи/чтении receipts, не кроном) **остаются в охвате скана**. Whitelist этой папки **запрещён** (следующий dump календаря стал бы невидим). `redact_terminal_output` в ядре маскирует **секреты**, не ФИО/email — поэтому dump участников в `output` детектируется сканером; после §3/§8.4 это 1 сводка на прогон, не тысячи Telegram. Ядро Hermes (`process_registry_results.py`) — вне скоупа, см. §14.

## §15. Риски

| # | Риск | Митигация |
|---|---|---|
| 1 | Полный обход `~/WorkVault` + `~/WorkVault_backup` может быть медленным/тяжёлым (тысячи файлов) на еженедельном кроне | Лимит размера файла на разбор (skip >5MB текстовых, бинарные — эвристика null-byte в первых байтах), общий тайм-бюджет скрипта, лог факта пропуска — не критично, скан лучше частичный, чем зависший |
| 2 | Ложные срабатывания regex ФИО (Cyrillic capitalized 2 слова — совпадает с названиями проектов/организаций) | Точное совпадение допускается как известный trade-off MVP; калибровка списка исключений — на этапе реализации по фактическим находкам первого baseline-прогона |
| 3 | Должность (§3, атрибут связи) — не regex, а лексикон-эвристика; расширяемый список, не покрывает все варианты | Задокументировать как приближение; при необходимости расширять список без изменения архитектуры |
| 4 | `sessions/*.jsonl` могут быть большими (архив всех сессий) — риск долгого прохода построчного JSON-парсинга | Построчный стриминг (не грузить файл целиком в память), инкрементальный разбор |
| 5 | Первый прогон при уже большом накопленном объёме находок может дать очень объёмный baseline-отчёт | Сводка только по счётчикам категорий/путей (§7), не по каждой находке — детали остаются в `baseline.json`/`audit_history.jsonl`, не в Telegram |
| 6 | Резолв через поиск строки `message` в `events.db` может дать 0 или >1 совпадений (если сообщение не уникально/уже резолвлено руками) | Резолвить только если найдена ровно одна открытая (`status='open'`) запись; при 0 или >1 — залогировать предупреждение в stdout скрипта, не трогать `events.db`, не фейлить весь прогон |
| 7 | Изменение сигнатур/структуры файлов в `pii-privacy` (после реализации) может изменить набор находок непредсказуемо на первом «регресс»-прогоне после неё | Ожидаемо и штатно — baseline берётся именно **после** завершения `pii_impl_plan.md`, а не до |
| 8 | Шторм per-finding `report_error` + Telegram в Errors `:11112` (инцидент 19.09: 809 spawn, 262 Telegram, таймаут 280/560 с агента `vm_selfcheck`; baseline не сохранён) | **Закрыто 21.09 решением Саши №1:** ровно 1 сводное событие за прогон; `|new|=0` — молчание шины. Чекпоинт baseline `BATCH=20` после действий + tempfile/`os.replace` (§8.4). Per-finding и потолок-30 — не вводить |
| 9 | False-token fixtures в планах ТЗ (`AAFake*`, `Example`, `your_token_here`) дают `category=credential` на каждый новый HF-plan | **Закрыто 21.09 решением Саши №3:** carve-out в `patterns.py` (§6). Живой токен без маркера заглушки остаётся critical |

## §16. Связи с экосистемой

- **ErrorBus** — единственный канал доставки находок (`report_error.sh --tool PIIScan`), резолв через `error_bus_cli.py resolve`. Новых полей/схемы не требует. v1.3.0: инкрементальный прогон шлёт **не более одного** critical (сводка), либо ноль при `|new|=0`.
- **pii-privacy** (`TZ/pii-privacy/pii_impl_plan.md`) — предшествующая работа, закрывающая источник; `PIIScan` — регресс-контроль поверх неё, встраивается строго после.
- **AnywhereContacts** (`AnywhereContacts_TZ.md` v0.2.0) — экосистемный сосед; маскирование собственное (`mask_identifier`/`mask_attribute`/`mask_credential` в `pii_scan.py`, §9). AnywhereContacts **НЕ** используется для хранения.
- **vm_selfcheck** (`jobs.json`, `job_id: vm_selfcheck`) — точка встраивания, новый пункт №12 в промпте, Mode A self-report без новой записи в `instrumentation_registry.json` (§13).
- **MoveFromLoop/ExchangeMonitor** — не связаны напрямую; упомянуты в `depends_on` фронтматтера как экосистемные соседи по шаблону self-report (не архитектурная зависимость).

## §17. Критерии готовности (проверяемые)

1. `pii_scan.sh` запускается вручную (`bash ~/.hermes/scripts/pii_scan.sh`), завершается `exit 0` в любом случае (fail-soft).
2. Первый прогон на тестовых данных создаёт `baseline.json` + ровно один `report_error.sh`-вызов с `severity=info`, без единого `critical`.
3. Второй прогон: `|new|>0` → **ровно один** `critical` (сводное событие: счётчик + разбивка + 2–3 masked sample), без повторных вызовов шины по persisting и без per-finding spawn. `|new|=0` → **ноль** вызовов `report_error.sh`, сводка только в stdout. В message/detail путь — `path={finding.path!r}`.
4. Прогон после исчезновения: для `status=open` **legacy** (уникальный per-finding `error_bus_message` v1.2.0) — батч-резолв открытой записи в `events.db` (`error_bus_cli.py resolve` по `tool=PIIScan AND message=<error_bus_message>`); для `status=open` v1.3.0+ (сводный message) и `status=baseline` — напрямую `resolved` в `baseline.json` + `audit_history.jsonl` `event: resolved`, без N spawn на одно сводное событие и без поиска в `events.db` для baseline. Строка в `audit_history.jsonl` остаётся (нет `DELETE` ни в одном файле/БД).
5. Ни в `baseline.json`, ни в `audit_history.jsonl`, ни в `message`/`detail` `report_error.sh`, ни в stdout — нет ни одного немаскированного значения (email/ФИО/секрет).
6. Whitelist-пути (`Contacts/`, `Entities/*`, `Inbox/`, `UserManuals/`, `Confluence/`, `Projects/` (весь), `Meetings/`) и `~/.hermes/state.db` не открываются на чтение содержимого при скане (проверяется по логу обхода/трассировке путей).
7. `instrumentation_registry.json` не получает новой записи (§13); `error_bus_cli.py audit` не показывает конфликтов/пробелов по `PIIScan`.
8. Ни в baseline/audit/message/detail нет `login+*` field_type (правило 09.09); Miro URL-token не даёт credential.
9. Гигиена логов (§14.1): `msg=`/`reply_to_text=` отсутствуют в INFO gateway.log; MFL/ExchangeMonitor суть — через redact; llm-anomaly-audits хранится компактом + TTL 5д.
10. Живые pytest в `tests/test_pii_scan.py` проходят (login≠ПДн, Miro≠кред, JSON не-декартово, whitelist-зоны) **плюс 7 новых** из раздела «Изменения v1.3.0».
11. TaskRefresh: TTL 5 дней / `prune_history()` при `save_session` (`HISTORY_TTL_DAYS=5` в `config.py`, §14.1).
12. JSON-поле `{output: "N ФИО\\nM email"}` не даёт декартово N×M; короткое однострочное поле по-прежнему инцидент. Фейковый `AAFake*` ≠ credential. `save_baseline` через tempfile+`os.replace`.

## §18. Открытые вопросы

Нет. Развилки 27.08.2026 закрыты (§1–13). Калибровка regex-констант (исключения ФИО, лексикон должностей, тайм-бюджет обхода) — не архитектурный вопрос, на реализацию по факту baseline (§15, риски 2–3).

Пять решений Саши 21.09 (инцидент 19.09) закрыты и внесены в §3/§6/§8.4/§14/§14.1/§15: (1) 1 сводное ErrorBus-событие за прогон, 0 new = молчание; (2) ядро Hermes не трогать; (3) carve-out фейковых токенов; (4) питфолл `exchange-meeting` — docs-handoff; (5) MeetingScheduler/ExchangeMeeting/ExchangeMonitor CLI не трогать. Потолок-30 и per-finding — отклонены.

## Приложения к ТЗ

### Изменения 09.09.2026 (v1.0.0 → v1.1.0)

Реализованы по согласованному плану `references/pii-rule-20260909.md` (архитектор + ревизор):
1. **Правило ПДн §3** — идентификатор только ФИО/ФИ, логин убран (нет `login+*`).
2. **Whitelist §5** — + Confluence/Projects(весь)/Meetings (финальное решение Саши: весь Projects/, перекрывает правку ревизора «только TrisigmaFull»).
3. **Креды §6** — Miro URL-token (boardAccessToken в query-string, слева `https://miro.com`) не секрет; lookbehind `(?<![A-Za-z0-9_])`.
4. **JSON-контекст** — `scan_json_file` (по каждому строковому полю отдельно, не декартово), fallback text.
5. **Путь с пробелами** — `path={finding.path!r}` в message/detail.
6. **Гигиена логов §14.1** — redact.py, gateway run.py (уберёт msg=), MFL/ExchangeMonitor, error_bus_cli, llm_anomaly_scan (компакт).
7. **TTL 5 дней** — TaskRefresh `prune_history`, llm-anomaly-audits find-delete.
8. **Тесты** — 22 pytest в `tests/test_pii_scan.py` (в т.ч. login≠ПДн, Miro≠кред, JSON не-декартово, whitelist-зоны).
9. **pfs_batch НЕ трогать** (решение Саши 09.09).

### Правки REV 09.09 (v1.1.0 → v1.2.0)

Одобрены Сашей по вердикту REV:tz CHANGES_REQUIRED:
1. **§16 AnywhereContacts** — не reuse-first источник `mask_pii`; маскирование собственное (`mask_identifier`/`mask_attribute`/`mask_credential` в `pii_scan.py`, §9); AnywhereContacts не используется для хранения, только экосистемный сосед. Синхрон с §9 и §14.
2. **frontmatter `depends_on`** — добавлен ExchangeMonitor (модифицируется в §14.1 наравне с MoveFromLoop).
3. **§5 whitelist** — `~/USERTOOLS/TaskRefresh/session/` абсолютный путь; зона `~/USERTOOLS/` отражена в §4 (сканируется, TaskRefresh session/ не в whitelist, TTL 5 дней).
4. **§8.4 п.5 vanished** — резолв разведён: `status=baseline` напрямую в `baseline.json` + `audit_history.jsonl` без `events.db`; поиск в `events.db` только для `status=open`. Синхрон с §7 (один сводный info-вызов).
5. **§3 правило ПДн** — fallback-text при невалидном JSON (не бросать исключение); `scan_json_file` по каждому строковому полю отдельно, не декартово.
6. **§8.4 и §17** — путь в message/detail: `path={finding.path!r}` (пробелы экранируются repr).
7. **§17 критерии** — 22 pytest в `tests/test_pii_scan.py`; TaskRefresh TTL 5 дней / `prune_history`.
8. **frontmatter** — `version: 1.2.0`, `updated: 2026-09-09`.

### Изменения v1.3.0 (21.09.2026, инцидент 19.09)

План: `TZ/PIIScan/plans/_fix_plan_20260921_pii_incident.md`. Пять решений Саши 21.09 закрыты в этом патче. **Код `~/.hermes/pii_scan/` этим файлом не меняется** — реализация после «берём в работу». Это не CHANGE-LIGHT: трогаются §3/§8.4 и >3 файлов кода; `REV:tz` по канону.

**Спека (уже в теле ТЗ):**
- §3 — multiline/длинные JSON-поля построчно (окно ±1); короткое однострочное — как было; `MAX_PAIRS_PER_CONTEXT=32` + `truncated_pairs`.
- §5 — prune whitelist/`USERTOOLS` из `dirnames` при обходе.
- §6 — carve-out `AAFake` / `Example` / `your_token_here` (и аналоги).
- §8.4 — 1 сводное ErrorBus-событие за прогон; `|new|=0` = молчание шины; vanished батч+чекпоинт; `save_baseline` после действий, tempfile+`os.replace`; сначала new/persisting/vanished в памяти. Потолок-30 и per-finding — нет.
- §14 / §14.1 — ядро Hermes вне скоупа; `process-results/` в охвате скана; MeetingScheduler/ExchangeMeeting/ExchangeMonitor CLI не трогать; docs-handoff питфолл `exchange-meeting`.
- §15 риски 8–9 закрыты решениями №1 и №3.

#### Пофайловый план исполнителя (`HF:impl`, composer-2.5)

Код: `~/.hermes/pii_scan/`. ErrorBus / `report_error.sh` / `_db.py` / `jobs.json` / Gateway / USERTOOLS CLI — **не открывать**.

| Файл | Что сделать |
|---|---|
| `pii_scan.py` | `scan_json_file` / `detect_pii_in_context`: длинное (`>500` или `\n`) строковое JSON-поле — построчный скан, окно ±1; короткое однострочное — без регресса. `MAX_PAIRS_PER_CONTEXT=32`, счётчик `truncated_pairs` в summary/stdout. `run_incremental_mode`: собрать new/persisting/vanished в памяти → **1** `call_report_error` если `|new|>0` (message=счётчик, detail=разбивка по файлам/категориям + 2–3 masked sample) → иначе 0 вызовов шины. Затем чекпоинт baseline `BATCH=20` **после** репорта/резолва. Vanished `status=open` legacy — батч `call_resolve` + чекпоинт; v1.3.0+ shared message — только baseline+audit. `save_baseline`: tempfile + `os.replace`. `iter_scan_files` / `_iter_root_files`: prune `dirnames` (whitelist WorkVault + USERTOOLS кроме `TaskRefresh/session/`); `state.db` не в корнях. |
| `patterns.py` | Carve-out фейковых токенов (§6): `AAFake`, `Example`, `your_token_here` и разумные аналоги не дают `category=credential`. Живой Telegram-токен без маркера — по-прежнему critical. |
| `tests/test_pii_scan.py` | Семь новых тестов (живые ~26 не ломать; cache nodeid `test_usertools_is_scanned_not_whitelisted` — не ориентир). Весь `tests/` зелёный. |

**Тесты (П.7 плана, тест №2 заменён под решение №1):**

1. `test_incremental_checkpoint_survives_interrupt` — mock `save_baseline` (или обёртка чекпоинта): исключение после 3-го успешного чекпоинта `BATCH=20`; baseline содержит ключи уже сохранённых батчей; повторный `run_scan` не репортит их как new (1 сводный репорт только на хвост, если остался).
2. `test_one_summary_report_per_run` — **вместо** `test_max_reports_per_run_emits_summary`. 50 new → **ровно 1** вызов `report_fn` (critical, счётчик 50, detail с разбивкой, ≤3 masked sample). 0 new → 0 вызовов `report_fn`, сводка только в возвращаемом/stdout summary.
3. `test_json_multiline_output_not_cartesian` — 3 ФИО × 3 email на разных строках одного JSON-поля → находки только с той же строки, не 9.
4. `test_json_short_same_field_still_pii` — существующий контракт короткого однострочного поля.
5. `test_whitelist_dirs_not_walked` — prune: путь под `Entities/` нет в `opened_paths` (и нет `stat` через track, если есть `walked_dirs`).
6. `test_fake_telegram_token_fixture_not_credential` — `token: "8821170000:AAFakeYamlTokenValue________"` ≠ credential.
7. `test_atomic_save_baseline_replace` — после mock-падения mid-write читается предыдущий валидный JSON.

**Вне этого `HF:impl` (не пакет PIIScan):**
- П.1 утилизация 811 событий 19.09 — операторка, отдельный императив «делай П.1».
- П.5.C `process_registry_results.py` — **нет** (решение №2).
- П.6 питфолл `exchange-meeting` (+ bulk/recurring) — `HF:docs-handoff` / SKILL-CHANGE, строка в §14.
- Скиллы `pii-data-scanning` / `pii-protection` — `HF:docs-handoff` (питфолл vanished, не винить `state.db`). `restore-all-skills.sh` только после правок скиллов.

**Готово когда:** 7 новых + живые тесты зелёные; синтетический dump 12×355 в JSON `output` → порядка десятков находок и **1** репорт; прогон с mock report на боевых корнях < 120 с.
