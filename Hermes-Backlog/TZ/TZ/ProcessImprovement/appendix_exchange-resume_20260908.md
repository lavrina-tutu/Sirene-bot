---
type: appendix
title: "Анализ этапа + план продолжения exchange-contact-upsert (архитектор 08.09)"
date: 2026-09-08
source: архитектор session e3b5b860 (cursor-grok-4.6-high)
status: draft (согласуется Сашей)
related: AnywhereContacts/appendix_exchange-upsert.md, ExchangeOrgLookup/appendix_exchange-upsert.md
---

# exchange-contact-upsert: анализ этапа + план продолжения

## 1. Текущий этап
Разработка остановилась **до записи master-ТЗ**: каркас v0.3.0 есть только в appendix, мастер-файлы не обновлены (оба v0.2.1, 29.08), до планирования и кода не дошли. По новому канону это **CHANGE** (доработка двух существующих инструментов), не DEV и не BUGFIX.

## 2. Что есть / чего нет
**Есть:** срез A (не новый инструмент, доработка); appendix 07.09 в обоих каталогах; баг `md_writer.py:217-221` (KeyError pass) на месте; в парсере `cmd_add` флаг `--dry-run` есть, но мёртвый (в функции не читается); VPN exit 2 — в cmd_bootstrap/cmd_rooms, но не в cmd_add; открытых архитектурных вопросов нет.

**Нет:** master-ТЗ v0.3.0 на диске (оба 0.2.1); `upsert_from_source` в секции сигнатур; честный upsert в md_writer/cmd_add; обработка `--dry-run`; VPN exit 2 в cmd_add; критерии успеха/«что не трогать»/контракты/атомарные шаги; пофайловый план, бэкап, закрытые тесты.

**Важно — про «код»:** на диск 07.09 вечером **утекли черновики** теневой ветки: `store.py` (upsert_from_source ~150 строк, логика сырая) + `tests/test_upsert_from_source.py` (опечатки). Это **НЕ** готовая реализация и **не** основание пропускать ТЗ/план.

## 3. Кейс и цепочка
**Кейс: CHANGE** (CHG). Один корень `DEV/exchange-contact-upsert` (контракт общий: API в AnywhereContacts → потребитель OrgLookup), не две параллельные.

**Цепочка:** `BRF(light)` → `BRIEF-CLOSE` → `TZ-WRITE(full)` → `TAKE-INTO-WORK` → `HF-COMPRESS` → `PLAN-IMPL-TAIL`
- `TZ-WRITE(full)`: stabilize → compress → patch → **REV:tz (включить)** → finalize
- Дальше: take-into-work → HF:compress → HF:plan → plan-approve → backup → impl → test → docs → ORCH → done

**Бриф:** полный пере-бриф не нужен (срез A зафиксирован, вопросов нет). Appendix достаточен как вход BRF(light) — зачесть каркас, не переспрашивать архитектуру. Но нужен короткий бриф в TG + `GATE:brief-closed`.
**Ревизор:** `REV:tz` — да (2 мастер-ТЗ, контракт API); `REV:plan` — нет.
«Делай в 1 проход» — только после TZ:finalize на диске.

## 4. Шаги продолжения (порядок)
1. `BRF(light)` в TG: зачесть appendix, CHANGE, один slug, ревизор на ТЗ.
2. `GATE:brief-closed` + **новый граф** (не unarchive старых карточек).
3. `TZ:stabilize` — оба мастера 0.2.1, пути, mtime (НЕ no-op).
4. `TZ:compress` — два экстракта с диска.
5. `TZ:patch` — развернуть appendix в секции v0.3.0 **обоих** ТЗ: сигнатура upsert, критерии, не трогать, контракты; черновик store.py/тестов — «заменить целиком»; KeyError pass, --dry-run, VPN exit 2 — must-fix. Код: `USERTOOLS/OrgLookup/`.
6. `REV:tz` (claude-sonnet-5-medium).
7. `TZ:finalize` — запись обоих *_TZ.md + bump инвентаря; проверить файлы на диске.
8. Ждать «берём в работу» (или one-pass).
9. `HF:compress` → `HF:plan` (пофайлово: сначала AC, потом OrgLookup; тесты + регресс).
10. HF-TAIL.

## 5. Риски (чего избегать)
- Принять утечку 07.09 (store.py+тесты) за сделанный HF:impl.
- Воскресить архив с TZ:analyze/TZ:architect.
- TZ:finalize только на один инструмент — контракт разъедется.
- Свести к BUGFIX из-за двух багов и обойти полный ТЗ.
- One-pass до v0.3.0 на диске.
- md_writer про markdown-merge+add_alias — ТЗ должно сказать: пишем только contacts.enc через upsert, plaintext не возвращать.