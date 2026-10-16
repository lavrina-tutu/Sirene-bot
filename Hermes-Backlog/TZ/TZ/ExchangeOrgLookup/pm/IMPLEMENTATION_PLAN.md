---
tool: ExchangeOrgLookup
type: implementation-plan
version: 0.1
date: 2026-07-06
status: draft (waiting Sasha's answers on TZ open questions)
refs:
  - ../ExchangeOrgLookup_TZ.md
  - WorkVault/Hermes-Backlog/research/bk-098-exchange-org-lookup.md
---

# Implementation Plan — ExchangeOrgLookup (bk-098)

> ⚠️ **Реализация НЕ стартует, пока Саша не ответит на открытые вопросы в §8 ТЗ (Q1 частота батча / Q2 политика ambiguous / Q3 fallback при пустом manager) и явно не скажет «берём в работу».** Согласование ТЗ ≠ команда на реализацию (см. `_TZ-WORKFLOW-RULES.md` §«Agreement ≠ start of work»).

## 1. Файловая структура

```
~/USERTOOLS/OrgLookup/
├── orglookup/
│   ├── __init__.py
│   ├── ews_client.py      # тонкая обёртка над MeetingScheduler.exchange_client
│   ├── resolver.py        # ResolveNames + disambiguation + transliteration
│   ├── hierarchy.py       # цепочка manager → reports_to (с кешем)
│   ├── md_writer.py       # парс/merge ~/WorkVault/Contacts/tutu-contacts.md + ContactStore.add_alias
│   └── cli.py             # who / manager / add / bootstrap / tree
├── translit.yaml          # ГОСТ + ручные исключения (Жиров: Zhirov, …)
├── cache.jsonl            # локальный кеш EWS-ответов, TTL 14 дней
├── tests/
│   ├── fixtures/          # снимки EWS-ответов в JSON (см. §4)
│   ├── test_resolver.py
│   ├── test_hierarchy.py
│   └── test_md_writer.py
└── pyproject.toml         # переиспользуем venv_linux/ из AnywhereContacts

~/.hermes/profiles/anthropic/plugins/orglookup/   # Hermes-плагин-обёртка
```

## 2. Порядок реализации и зависимости

| # | Модуль | Что делает | Зависит от | Оценка |
|---|---|---|---|---|
| 1 | `ews_client.py` | `resolve_names(query) -> list[Contact]`; авторизация через `MeetingScheduler.exchange_client.get_account()`; retry на сетевых ошибках; проверка VPN. | — | 0.5 ч |
| 2 | `resolver.py` | Транслит ФИО (`translit.yaml` + ГОСТ); `resolve(name_raw, hint_department=None) -> ResolveResult(confidence, contact | ambiguous | not_found)`; disambiguation по `department`. | (1) | 1.0 ч |
| 3 | `hierarchy.py` | `get_manager_login(employee_email) -> login | None`: двухшаговый резолв (`email → contact.manager (str) → ResolveNames → manager.email → local-part`); `cache.jsonl` TTL 14д; fallback при пустом `manager` → пишет в `state/missing_manager.jsonl` (см. Q3 ТЗ). | (1), (2) | 1.0 ч |
| 4 | `md_writer.py` | Парс `tutu-contacts.md` (табличный MD); idempotent merge; diff перед записью; `ContactStore.add_alias(login, alias, source="exchange_gal")`; лог конфликтов в `~/WorkVault/_meta/OrgLookup/_log.jsonl`. | (2), (3) | 1.5 ч |
| 5 | `cli.py` | `orglookup who <name>` / `manager <login>` / `add <name> [--dept X]` / `bootstrap [--field reports_to]` / `tree --dept X`. Возвращает JSON или ascii-дерево. | (2), (3), (4) | 1.0 ч |
| 6 | `tests/` | Fixture-based, без сети (см. §4). Покрытие ≥80% для `resolver`/`hierarchy`/`md_writer`. | (2)–(5) | 1.0 ч |
| 7 | Hermes-плагин | `~/.hermes/profiles/anthropic/plugins/orglookup/` — команды `org_who`, `org_manager`, `org_add`, `org_tree` (subprocess-обёртка над CLI). | (5) | 0.5 ч |
| | **Итого MVP** | | | **~6.5 ч** |

**Опционально (не MVP, +2 ч):** ascii-дерево отдела (сценарий C), Telegram-автозаполнение из `phone_numbers[BusinessFax]`.

## 3. Контрольные точки (milestones)

| M | Условие завершения | Проверяемый результат |
|---|---|---|
| M1 | (1)+(2) готовы | CLI-скрипт `python -m orglookup.resolver "Krivorotov"` возвращает 1 контакт с `email=krivorotov@tutu.ru, manager="Tkachenko Alexander"`. |
| M2 | (3) готов | `python -m orglookup.hierarchy krivorotov@tutu.ru` → цепочка `tkachenkoav → aralov → khrupov` (fixture или живой EWS). |
| M3 | (4) готов | Прогон `md_writer.merge()` на копии `tutu-contacts.md` даёт корректный diff, `ContactStore.add_alias` вызван (проверка через мок). Ручные `reports_to` не перезаписаны. |
| M4 | (5) готов | `orglookup bootstrap --dry-run` печатает план для 30+ строк `tutu-contacts.md` без ошибок. |
| M5 | (6) — тесты зелёные | `pytest ~/USERTOOLS/OrgLookup/tests/ -v` → all pass, покрытие ≥80% для core-модулей. |
| M6 | (7) готов | Из Hermes работает `org_who "Krivorotov"` и возвращает ответ в чат. |
| **DONE** | Все 7 критериев успеха из §4 ТЗ выполнены на реальных данных | `orglookup bootstrap` резолвит ≥80% строк `tutu-contacts.md` с `reports_to ∈ {—, ?}`; конфликты залогированы; ambiguous ушли в дайджест. |

## 4. Тестовый план

**Философия:** fixture-based, без живого EWS. Реальный прогон против EWS — только smoke-test при финальной приёмке (Саша + `orglookup bootstrap --dry-run` на живой `tutu-contacts.md`).

### 4.1. Что мокать

`ews_client.resolve_names(query)` — единственная точка сети. Мокается фабрикой из `tests/fixtures/*.json`:

- `fixtures/krivorotov.json` — 1 кандидат, `manager="Tkachenko Alexander"`, все поля заполнены.
- `fixtures/khrupov_ambiguous.json` — 3 кандидата, разный `department` (для disambiguation).
- `fixtures/ivanov_no_dept.json` — 5+ кандидатов, `department` не различает → `ambiguous`.
- `fixtures/ceo_no_manager.json` — 1 кандидат, `manager=None` (для Q3 fallback).
- `fixtures/notfound.json` — пустой результат.
- `fixtures/cyrillic.json` — `No results were found` (проверка требования «только латиница»).
- `fixtures/manager_chain.json` — цепочка Tkachenko → Aralov → Khrupov (для `hierarchy.py`).

### 4.2. Кейсы тестов

**`test_resolver.py`:**
- `test_resolve_single_hit_high_confidence` (Krivorotov)
- `test_resolve_ambiguous_multiple_candidates` (Ivanov)
- `test_resolve_disambiguate_by_department` (Khrupov + hint="АИД" → 1)
- `test_resolve_not_found` (пустой ответ)
- `test_resolve_cyrillic_rejected` (переводит `"Криворотов"` через translit.yaml → `"Krivorotov"`, повторяет запрос)
- `test_transliterate_fallback_gost` (нет в yaml → ГОСТ-транслит)

**`test_hierarchy.py`:**
- `test_manager_chain_two_step` (email → manager str → resolve → login)
- `test_manager_chain_terminated_at_none` (CEO без manager, fallback → `missing_manager.jsonl`)
- `test_cache_hit_no_network` (2-й вызов не бьёт по `ews_client`)
- `test_cache_ttl_expired` (14 дней прошло → повторный запрос)

**`test_md_writer.py`:**
- `test_merge_new_row` (строки нет → добавляется, `add_alias` вызван)
- `test_merge_conflict_manual_reports_to_preserved` (стоит `reports_to=malina`, GAL даёт `aralov` → diff+лог, значение НЕ перезаписано)
- `test_merge_idempotent` (2 прогона подряд → нет изменений на 2-м)
- `test_ambiguous_writes_to_unclear_names` (не пишет в ContactStore, пишет в очередь)

### 4.3. Прогон

```bash
cd ~/USERTOOLS/OrgLookup
source ../AnywhereContacts/venv_linux/bin/activate   # переиспользуем venv
pytest tests/ -v --cov=orglookup --cov-report=term-missing
```

## 5. Оценка трудозатрат (из исследования bk-098)

| Этап | Часы |
|---|---|
| `ews_client.py` + `resolver.py` (resolve + disambiguate + transliterate) | 1.5 |
| `hierarchy.py` (manager-chain, кеш, missing_manager fallback) | 1.0 |
| `md_writer.py` (парс таблицы, idempotent merge, diff, ContactStore) | 1.5 |
| CLI (`who/manager/add/bootstrap/tree`) | 1.0 |
| Тесты (fixture-based, без реального EWS) | 1.0 |
| Hermes-плагин-обёртка | 0.5 |
| **Итого MVP** | **~6.5 ч** |

Сценарий C (ascii-дерево отдела) и Telegram-автозаполнение — +2 ч сверху, вне MVP.

## 6. Риски и питфоллы (из исследования)

1. **Транслит-словарь**. ГОСТ покрывает ~90%, для остатка (`Жиров: Zhirov`) — ручной `translit.yaml`, пополняется по факту.
2. **EWS-запросы небыстрые** (~300–800 мс). Кеш `cache.jsonl` TTL 14 дней обязателен.
3. **VPN-зависимость**. Без корп-VPN → инструмент падает с понятным сообщением (см. критерий успеха §4.7 ТЗ), очередь `needs_gal` не портится.
4. **Cyrillic-поиск в EWS не работает** — только через транслит. Тест `test_resolve_cyrillic_rejected` обязателен.
5. **Никогда не перезаписывать вручную заполненные `reports_to`/`aliases`** — diff + лог. Тест `test_merge_conflict_manual_reports_to_preserved` обязателен.

## 7. Что дальше — блокеры на старт

Перед первой строкой кода Opus/Sasha дожидаются:

1. Явный ответ Саши на Q1 (частота батча) → в `cli.py`/cron-конфиг.
2. Явный ответ на Q2 (политика ambiguous) → в `resolver.py::_disambiguate`.
3. Явный ответ на Q3 (fallback при пустом manager) → в `hierarchy.py::get_manager_login`.
4. Явное «берём в работу» от Саши.
5. Бэкап согласно Блоку 5 скилла `hermes-feature`.
