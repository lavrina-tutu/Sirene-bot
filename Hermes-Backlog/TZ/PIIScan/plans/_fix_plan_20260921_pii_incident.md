---
type: incident-plan
title: "Починка PIIScan после шторма 19.09 + оценка Exchange/встреч"
slug: PIIScan
case: CHANGE
phase: HF:plan
date: 2026-09-21
status: draft-plan
author: архитектор (cursor-grok-4.6-high)
source_tz: TZ/PIIScan/PIIScan_TZ.md v1.2.0
executor: composer-2.5
deadline: "следующий vm_selfcheck 2026-09-26 03:30 MSK"
next_phases: согласование Саши → TZ:patch → REV:tz → TZ:finalize → GATE:brief-closed → «берём в работу» → HF:impl
forbidden: "код/конфиги/скиллы этим файлом не менять; Gateway не рестартовать; кроны не пересоздавать"
---

# План: инцидент PIIScan 19.09.2026

Канон: `TZ/PIIScan/PIIScan_TZ.md` v1.2.0. Код: `~/.hermes/pii_scan/pii_scan.py`. Обёртка: `~/.hermes/scripts/pii_scan.sh`. Шина: `report_error.sh` → `error_bus/_db.py`.

Этот файл — только план. Императив на П.1 (утилизация/резолв) и «берём в работу» на код — отдельные команды Саши.

---

## 1. Root cause (диагноз постановщика — подтверждён, с тремя уточнениями)

### Что подтверждено

1. **Атомарность сломана.** `run_incremental_mode()` (`pii_scan.py` 732–819): цикл `call_report_error` + `append_audit` **по одной находке**, `save_baseline()` **только в конце**. Прогон 19.09 убит до save.
   - `baseline.json` mtime **2026-09-12 03:32** (4.9 МБ, 12369 ключей) — не обновлён.
   - `audit_history.jsonl` mtime **2026-09-19 03:49** — **1621** строк `incident_new` за 19.09 (дубли двух попыток).
2. **Таймаут — не внутри сканера, а у terminal-tool агента `vm_selfcheck`.** Крон `30 3 * * 6` (не ~00:40). Промпт п.12 запускает `bash ~/.hermes/scripts/pii_scan.sh` как обычную команду. Агент дважды ждал 280 с и 560 с без stdout-резюме. Обёртка fail-soft, своего таймаута нет.
3. **Каждая находка = spawn `report_error.sh` + INSERT/UPDATE `events.db` + попытка Telegram в Errors `:11112`** (`_db.py`: новый INSERT всегда `notify=True`; `critical` не троттлится; `send_telegram_message` timeout 10 с). Это и съело бюджет 280/560 с.

### Уточнения (важны для починки)

**A. Шторм — не 809 «карточек людей», а декартово произведение внутри одного JSON-поля.**

Файл `~/.hermes/logs/process-results/proc_af300dff14f0.json` (43 КБ, mtime 17.09 08:48, `task_id=20260916_180915`, сессия TG-группы `:3`). Команда: heredoc `/tmp/scan_full2.py` + `exchangelib`, не MeetingScheduler. Поле `output` — **одна строка JSON** длиной 37102, 122 линии, **12 уникальных ФИО × 355 email = 4260** плюс 492 `fio+phone` + 12 `fio+position` = **4764 находки** из `scan_json_file` (каждая строка JSON = один контекст, внутри — полное декартово `ФИО × атрибут`, ТЗ §3). Реальных строк, где ФИО и email стоят рядом: **~15**. Сканер раздул 15 утечек в тысячи «инцидентов».

ErrorBus на 21.09: **811 open PIIScan** с `first_seen=2026-09-19` (не 810):

| path | n | тип |
|---|---|---|
| `~/.hermes/logs/process-results/proc_af300dff14f0.json` | 809 | pii_card (в основном fio+email) |
| `~/.hermes/logs/process-results/proc_1188151e7521.json` | 1 | pii_card |
| `TZ/TelegramGroupTopics/HF-plan_telegram-group-topics_20260916.md` | 1 | credential `secret_assignment` |

Прогон успел отрепортить **809 из 4764**. Следующий полный прогон при живом файле попытается **все 4764 как new** (ключей нет в baseline) — повторный шторм × масштаб ~6.

Две попытки 19.09 оставили след: `count` по строкам 1…21; 287 строк с `count=2–4` переклассифицированы шиной в `error` (`classify()`, порог critical `count≥5`); 524 остались `critical`; `Σ(count)≈1624` ≈ 1621 audit. В Telegram ушло **262** (не 811) — всё равно шторм.

**B. `state.db` 1.9 ГБ в обход не входит.** Корни §4: `sessions/*.jsonl`, WorkVault, WorkVault_backup, USERTOOLS, `cron/output`, `logs`, `error_bus`. `~/.hermes/state.db` рядом, `is_state_db()` защитный. Self-check 19.09 ошибся, списав таймаут на 1.9 ГБ. Тяжесть 19.09 = **репорт+Telegram**, не чтение БД гейтвея. Обход сам по себе умеренный (~2500 файлов WorkVault, из них 2045 whitelist skip **после** `os.walk`; USERTOOLS 987 путей skip после walk). Whitelist/USERTOOLS не прунятся в `dirnames` — лишняя работа, не причина шторма.

**C. CRED в HF-plan — ложное срабатывание, не живой токен.** Совпадение `token: "8821170000:AAFakeYamlTokenValue________"` в примерах тестов плана (стр. ~519, ~580). `TELEGRAM_BOT_TOKEN_PATTERN` = 0 матчей. Перевыпускать бота **не нужно**. Файл не удалять.

**D. Авто-резолв vanished этот инцидент не закроет.** Vanished = ключи **уже в baseline** со статусом `open|baseline`, которых нет в текущем скане. 809 ключей в baseline не попали. Удаление файла ≠ закрытие 811 событий. Питфолл `pii-data-scanning` («удали файл — следующий прогон закроет») для этой пачки **неверен**.

**E. USERTOOLS уже skip** (кроме `TaskRefresh/session/`) — `is_usertools_skip_path()`, тест `test_usertools_skipped_except_taskrefresh_session`. «Фикстуры ловятся» — устаревший факт до 09.09.

### Источник остаточного ПДн

Не баг назначения встреч. Одноразовый скрипт в фоновом terminal свалил таблицу календаря в stdout → Hermes записал receipt `process-results/proc_*.json`. `redact_terminal_output` маскирует **секреты**, не ФИО/email. TTL receipts: 7 дней / max 64 файла, prune **при следующей записи/чтении** receipts, не кроном. На 21.09 файл жив (4 суток); на 26.09 может ещё жить, если prune не сработал.

---

## 2. План действий (приоритет)

Дедлайн кода атомарности+потолка: **до 26.09 03:30**. П.1 — сразу по «делай», даже без «берём в работу» на CHANGE.

### П.1 — Немедленная утилизация (операторка, до кода)

**Зачем.** ПДн на диске до ~24–26.09; 811 open в ErrorBus; любой повторный `pii_scan.sh` до фикса = до 4764 critical + Telegram.

**Что сделать (одним императивом «делай П.1», не этим файлом):**

1. **Не запускать** `pii_scan.sh` / п.12 self-check вручную, пока нет П.2.
2. **Удалить** `~/.hermes/logs/process-results/proc_af300dff14f0.json`. По желанию просмотреть `proc_1188151e7521.json` (1 карточка, вывод `agent -p` по промпту Аралова) — redact или удалить.
3. **HF-plan не трогать** (фейковый токен в примере). Не крутить `TELEGRAM_BOT_TOKEN`.
4. **Закрыть 811 событий одним процессом**, не 811 spawn `error_bus_cli.py` и не vanished-скан:
   - импорт `resolve_error` из `~/.hermes/error_bus/_db.py` (инкапсуляция шины, не сырой SQL руками);
   - фильтр: `tool='PIIScan' AND status='open' AND first_seen LIKE '2026-09-19%'`;
   - `--note` вида `PII-incident 20260921: source file removed / fake-token fixture`;
   - сначала dry-run счётчик (=811), потом resolve.
5. Опционально: `rm -f /tmp/scan_full2.py` (вне охвата скана, гигиена).

**Не делать:** полный прогон PIIScan «чтобы сам зарезолвил»; `DELETE` из `events.db`; сброс `baseline.json`; правку `jobs.json`; рестарт Gateway.

**Риск:** низкий, если фильтр узкий по дате. Чужие open PIIScan (в baseline сейчас 106 `open` старых) не трогать.

**Готово когда:** файла `proc_af300dff14f0.json` нет; `SELECT COUNT(*) … first_seen LIKE '2026-09-19%' AND status='open'` = 0; baseline mtime по-прежнему 12.09 (не сброшен).

---

### П.2 — Атомарность baseline + потолок репорта (код, до 26.09)

**Зачем.** Даже после удаления файла следующий крупный dump снова убьёт прогон и зациклит шторм.

**Файлы:** `~/.hermes/pii_scan/pii_scan.py`, тесты. ТЗ §8.4 — точечная правка (см. согласование №1–2). **ErrorBus / `report_error.sh` / `_db.py` не менять** (ТЗ §14).

**Механика (рекомендация):**

1. Собрать `new/persisting/vanished` в памяти, как сейчас.
2. Репорт **батчами с чекпоинтом**, не «все → save в конце»:
   ```
   for batch in chunks(new_keys, BATCH=20):
       report batch
       обновить dict baseline (status=open)
       save_baseline()   # fsync на диск
       append_audit для батча
   ```
   Убитый прогон: уже отрапортованное в baseline → на следующем = persisting, без повтора. Хвост дорепортится.
3. **Потолок на прогон:** не больше `MAX_REPORTS_PER_RUN` (рекомендация **30**) вызовов `report_error`. Остаток new — в baseline со статусом `open` **без** вызова шины, плюс **один** сводный `critical`: `PIIScan: обрезано, ещё N находок в K файлах; следующий прогон продолжит`. Иначе 4764 × Telegram снова взорвут 560 с.
4. Vanished `status=open`: тоже батч `call_resolve` + чекпоинт baseline (811 spawn резолва — тот же таймаут).
5. `call_report_error`: без изменения ErrorBus нельзя выключить Telegram. Лечится **числом** вызовов (п.3 + П.3 декартово).

Порядок «save до репорта всех ключей» **отвергнут**: убийство между save и репортом оставит ключи persisting → ErrorBus-событий не будет никогда.

**Риск:** средний. Чекпоинт каждые 20 — порча `baseline.json` при kill во время `write_text`. Митигация: писать во tempfile + `os.replace` (как atomic_json_write в Hermes).

**Готово когда:** тест «убить после N репортов → baseline содержит N, повтор не репортит их снова»; тест «>MAX_REPORTS → ровно MAX вызовов report_fn + 1 сводка»; живой прогон на копии фикстуры в tmp < 60 с.

---

### П.3 — Декартово внутри длинного JSON-поля (ядро ложных 4764)

**Зачем.** Без этого потолок П.2 только режет Telegram, а baseline раздувается тысячами ложных пар «чужое ФИО × чужой email».

**Файлы:** `pii_scan.py` `scan_json_file` / `detect_pii_in_context`; тесты. ТЗ §3 — уточнение, не отмена правила.

**Механика (рекомендация):** строковое JSON-поле с `\n` **или** длиной > 500 символов сканировать **как текст** (окно ±1 строка), не как один контекст. Короткое однострочное поле — как сейчас (ФИО+email в одной строке JSON = инцидент, тест `test_json_same_field_fio_email_is_pii` жив). Доп. предохранитель: `MAX_PAIRS_PER_CONTEXT=32`; лишнее — не finding, счётчик `truncated_pairs` в summary.

Эффект на инцидент: 4260 → порядка **15** истинных fio+email.

**Риск:** низкий. Ложные негативы: ПДн, размазанные по длинному JSON без переводов строк. Редкость; предохранитель 32 пары логирует факт обрезки.

**Готово когда:** фикстура «JSON `{output: "12 ФИО\\n355 email"}`» даёт ≪ 12×355 находок; старые 26+ тестов зелёные; новый тест на multiline JSON.

---

### П.4 — Производительность обхода

**Зачем.** После П.2/П.3 репорт больше не доминирует; обход станет следующим узким местом (еженедельный агент 280 с).

**Файлы:** `iter_scan_files` / `_iter_root_files`.

1. **Prune `dirnames`:** whitelist-корни WorkVault (`Contacts/Entities/Inbox/UserManuals/Confluence/Projects/Meetings`) не обходить. USERTOOLS: prune всего, кроме `TaskRefresh/session/`. Сейчас skip **после** генерации пути — 2045+987 лишних `stat`.
2. `state.db` не добавлять в корни (уже так). Self-check 19.09 поправить в питфолле скилла: не винить 1.9 ГБ.
3. Крупные бинарники USERTOOLS (`MofsIndex/state/index.sqlite` 107 МБ) уже отсекаются skip-префиксом; после prune не `stat`.
4. Таймаут агента 280/560 **не раздувать** как основной фикс. Сканер должен укладываться сам. `jobs.json` не трогать без «ставь кроны».

**Риск:** низкий. Ошибка prune (обрезать `TaskRefresh/session`) закрывается существующим тестом skip.

**Готово когда:** `opened_paths` не содержит whitelist-префиксов и `state.db`; число обойдённых путей WorkVault ≪ 2527; прогон dry на боевых корнях с mock report < 120 с.

---

### П.5 — `process-results`: сканировать / whitelist / redact-on-write

**Рекомендация: оставить в охвате скана + redact-on-write в ядре Hermes (отдельное согласование) + П.3, чтобы dump не взрывал декартово.**

| вариант | плюс | минус | вердикт |
|---|---|---|---|
| A. Сканировать как сейчас | видит регресс | шторм без П.2/П.3 | недостаточен один |
| B. Whitelist `logs/process-results/` | тишина | следующий dump невидим | **нет** |
| C. Redact-on-write `output`/`command` через `redact_fio_email_phone` в `hermes-agent/tools/process_registry_results.py` (уже есть `redact_terminal_output` по секретам, `force=True`) | закрывает канал на записи; TTL 7д/64 не suff. | ядро Hermes, merge-питфолл vs upstream; **отдельное согласование** | **да, отдельно от PIIScan CHANGE** |
| D. Только TTL | файл сам умрёт | prune не крон; ПДн дни на диске; ErrorBus не закроется | как дополнение, не фикс |

П.3+П.2 закрывают **сканер**. П.5.C закрывает **источник оседания**. Без C агент снова может напечатать календарь — PIIScan корректно поднимет 1 сводку на файл, не 4000 Telegram.

**Не делать в том же HF:impl, что PIIScan**, пока Саша не скажет отдельно: «можно трогать `process_registry_results.py`». `hermes-agent.next` не трогать (ТЗ §14).

**Готово (ветка C, если согласована):** новый receipt с таблицей «ФИО email» на диске не содержит сырых ФИО/email; секрет-редact не регрессирует (тесты `test_redact.py` / `test_completed_process_results.py`); PIIScan на таком файле = 0 new pii_card.

---

### П.6 — Exchange / MeetingScheduler / скиллы встреч

**Вердикт: инструмент назначения встреч чинить не нужно. Это не источник инцидента 19.09.** Источник — ад-хок `/tmp/scan_full2.py` в terminal.

Оценка каналов:

| канал | ФИО+email в одном контексте? | PIIScan | действие |
|---|---|---|---|
| `MeetingScheduler/cli.py` JSON (`attendees` отдельно, `subject` отдельно) | нет (ТЗ §3: не декартово по полям JSON) | не инцидент | не менять CLI |
| ТЗ MeetingScheduler: «email маскируется в логах» | заявлено; в пакете `logging.getLogger`, отдельного mask нет | логи процесса, если попадут в files | не блокер 19.09 |
| `_trisigma_freebusy.py` `print(name, …)` | да, если запустить как terminal | да | разовый скрипл; не продукт |
| скилл `exchange-meeting`: «Ты имеешь в виду [Имя] ([email])?» | да, в TG | `state.db` вне охвата; `sessions/*.jsonl` **сканируются** | питфолл в скилл: в чат — логин/`Имя (login)`, не email; уточнение кандидата — одно имя |
| `exchange-meeting-bulk` / `exchange-recurring-meetings` | то же | то же | одна строка питфолла |
| `ExchangeMonitor/formatter.py` | уже `redact_fio_email_phone` | закрыт 09.09 | не трогать |
| `ExchangeMeeting/create_meeting.py` | poc, print subject/id | низкий | не трогать |
| `SyncAralov` | использует MeetingScheduler, без дампа участников | нет | не трогать |

**Доработка скиллов (узкая, SKILL-CHANGE, не USERTOOLS):** 5–10 строк Pitfalls в `exchange-meeting` (+ ссылка из bulk/recurring): запрет ад-хок `exchangelib` + print списка участников/тем; календарь смотреть через CLI JSON; в TG не печатать пары ФИО+email. Код MeetingScheduler не открывать.

**Готово:** питфолл в скилле; регресса CLI-тестов нет (скилл-only).

---

### П.7 — Тесты регресса (обязательны в том же HF:impl, что П.2–П.4)

Добавить в `~/.hermes/pii_scan/tests/test_pii_scan.py` (сейчас 26 функций; cache nodeids ещё содержит устаревшее `test_usertools_is_scanned_not_whitelisted` — не ориентир):

1. `test_incremental_checkpoint_survives_interrupt` — mock `report_fn`, исключение после 3-го вызова; baseline содержит 3; повторный `run_scan` не репортит их.
2. `test_max_reports_per_run_emits_summary` — 50 new, `MAX_REPORTS_PER_RUN=5` → 5 critical + 1 сводка.
3. `test_json_multiline_output_not_cartesian` — 3 ФИО × 3 email на разных строках одного JSON-поля → находки только с той же строки, не 9.
4. `test_json_short_same_field_still_pii` — существующий контракт короткого поля.
5. `test_whitelist_dirs_not_walked` — prune: путь под `Entities/` нет в `opened_paths` и нет `stat` через track, если добавим `walked_dirs`.
6. `test_fake_telegram_token_fixture_not_credential` — `token: "8821170000:AAFakeYamlTokenValue________"` ≠ кред (если примем согласование №4).
7. `test_atomic_save_baseline_replace` — после mock-падения mid-write читается предыдущий JSON.

Живые 26 тестов не ломать. Критерий CHANGE: все pytest в `tests/` зелёные.

---

### П.8 — Документы / питфоллы (HF:docs-handoff, не блокирует П.2)

- `TZ/PIIScan/PIIScan_TZ.md`: §3 (multiline JSON), §8.4 (чекпоинт+потолок), §15 риск «шторм per-finding + Telegram»), §14.1 канал `process-results`. Версия 1.2.0 → 1.3.0 после TZ:finalize.
- `MAIN_TZ_INVENTORY.md` — после записи ТЗ.
- `skills/devops/pii-data-scanning/SKILL.md`: исправить питфолл «удали файл → авто-резолв»; дописать атомарность+декартово JSON; не винить `state.db`.
- `pii-protection/SKILL.md` — **устарел** (логин ещё идентификатор, креды «вне скоупа»). Либо синк с 09.09, либо баннер «канон = pii-data-scanning».
- Скиллы встреч — П.6, если согласовано.

`restore-all-skills.sh` — только после правок скиллов, по правилу профиля.

---

## 3. Что требует согласования Саши

Пять пунктов. Реализация кода — после ответов по №1–2 (блокируют ТЗ). №3–5 можно параллельно решать, не блокируют П.1.

1. **Формат ErrorBus (меняет ТЗ §8.4).** Сейчас: один `critical` на каждую пару ФИО×атрибут.  
   - **1)** чекпоинт + потолок 30 per-finding, как в ТЗ по смыслу «на каждую новую»;  
   - **2) (рекомендация)** 1 событие на `(path, category)` + count + 2–3 masked sample, per-finding только в baseline/audit.  
   Рекомендация: **2** — Errors `:11112` не должен получать сотни масок.
2. **Потолок `MAX_REPORTS_PER_RUN`.** 10 / **30 (рек.)** / 100 / без потолка.
3. **Трогать ли ядро Hermes `process_registry_results.py` (П.5.C)?** да в отдельной задаче / нет, только сканер. Рек.: **да, отдельным CHANGE** после PIIScan, не в том же impl.
4. **Фейковые токены `AAFake*` в планах ТЗ.** carve-out в `patterns.py` / оставить, baseline проглотит после П.2. Рек.: **carve-out** (`AAFake`, `Example`, `your_token_here`) — иначе каждый новый HF-plan с примером YAML = CRED.
5. **Питфолл в `exchange-meeting` (П.6, без кода USERTOOLS).** да / нет. Рек.: **да**, дёшево, закрывает повторение сценария «напечатай календарь».

Не согласовывать (уже решено фактами): удалять HF-plan — нет; перевыпускать TG-бота — нет; чинить MeetingScheduler CLI — нет; whitelist process-results — нет; читать `state.db` — нет; рестарт Gateway / пересоздание `vm_selfcheck` — нет.

---

## 4. Порядок и параллельность

```
П.1 утилизация          ── независим, сразу по «делай П.1»
        │
        │  (не запускать pii_scan до merge П.2)
        ▼
TZ:patch (§3, §8.4, §15) ── после ответов №1–2
        │
HF:impl П.2 + П.3 + П.4 + П.7  ── один пакет, один исполнитель
        │         ┌────────────── параллельно после №3/№5
        │         │  П.5.C ядро Hermes (отдельный CHANGE, если «да»)
        │         │  П.6 скилл exchange-meeting (SKILL-CHANGE, если «да»)
        ▼
HF:test → HF:docs-handoff (П.8) → ORCH:shared-state (скиллы)
        ▼
GATE: следующий vm_selfcheck 26.09 03:30 должен
      уложиться <280с, 0 шторма, stdout-резюме в отчёте.
```

**Не параллелить с П.1:** повторный боевой `pii_scan.sh`.

**Оценка объёма PIIScan CHANGE:** `pii_scan.py` + `tests/test_pii_scan.py` + секция ТЗ (+ опционально `patterns.py` под №4). Это не CHANGE-LIGHT, если трогаем ТЗ §3/§8.4 и >3 файлов. Ревизор `REV:tz` / `REV:plan` — по канону GLOSSARY (не лёгкий BUGFIX ≤3 файла).

**Зависимости от чужого:** ErrorBus не открываем. `pii-privacy` уже «источник контактов»; этот инцидент — другой канал (terminal receipts).

---

## 5. Критерий «инцидент закрыт»

- Файла-дампа календаря нет; 811 событий 19.09 resolved.
- Следующий субботний п.12: stdout `новых=0` или единицы; нет таймаута 280/560; `baseline.json` mtime = дата прогона.
- Повторный синтетический dump 12×355 в JSON `output` → не более десятков находок и не более потолка репортов.
- MeetingScheduler/EWS-скиллы не ломались (нет diff USERTOOLS, кроме опционального SKILL.md).
