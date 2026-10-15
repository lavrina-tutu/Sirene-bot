---
type: hf-plan
title: "Ретро-план досбора exchange-contact-upsert (HF:plan, 08.09)"
slug: exchange-contact-upsert
case: CHANGE
phase: HF:plan
date: 2026-09-08
status: draft-plan
author: архитектор (cursor-grok-4.6-high, HF:plan)
source_audit: TZ/ProcessImprovement/appendix_exchange-audit_20260908.md
source_reliability: TZ/ProcessImprovement/appendix_exchange-finish-reliability_20260908.md
tz:
  - TZ/AnywhereContacts/AnywhereContacts_TZ.md (frontmatter 0.2.2, секция v0.3.0)
  - TZ/ExchangeOrgLookup/ExchangeOrgLookup_TZ.md (frontmatter 0.2.2, секция v0.3.0; общий slug)
code:
  - ~/USERTOOLS/AnywhereContacts/
  - ~/USERTOOLS/OrgLookup/
executor: composer-2.5
---

# HF:plan — досбор exchange-contact-upsert

Один план на общий slug `exchange-contact-upsert` (CHANGE, два инструмента, один контракт API). Это остаток PLAN-IMPL-TAIL, не новый TZ-WRITE. Код в этом вызове не писать. Объект для `GATE:plan-approve`.

Источники фактов (не выдумано): `appendix_exchange-audit_20260908.md`, `appendix_exchange-finish-reliability_20260908.md` (контур A), сверка диска 08.09. Контур B (безотказность цепочек) — другой CHANGE, сюда не входит.

Исполнитель идёт A2 → A3 → A4 сверху вниз. Промежуточные точки — молча. Новых сущностей нет.

Дом кода:

```
~/USERTOOLS/AnywhereContacts/     пакет anywhere_contacts
~/USERTOOLS/OrgLookup/            пакет orglookup (код ExchangeOrgLookup)
venv: ~/USERTOOLS/AnywhereContacts/venv_linux/
```

---

## 1. Ретро-таблица «факт на диске» (08.09)

Сверка audit appendix × диск. Колонка «диск» — что есть сейчас, не что должно быть после A2–A4.

| # | Объект | На диске 08.09 | Дыра vs ТЗ v0.3.0 |
|---|---|---|---|
| 1 | AC `store.py` `upsert_from_source` | Жив: create / FILL_ONLY_EMPTY / `reports_to` conflict / reactivate inactive source / `dry_run` / `unchanged` без записи. Lookup по `contacts.get(login)`. | **email не required:** create пишет `"email": record.get("email") or ""`. ТЗ: email required; A2.3 — без email не создавать. |
| 2 | AC `__init__.py` | `__version__ = "0.1.0"`. Экспорт `ContactStore`. Grep `upsert_from_source` по файлу — пусто. | Нет реэкспорта `upsert_from_source` (явный шаг ТЗ). |
| 3 | AC тесты `tests/test_upsert_from_source.py` | 6 тестов по критериям v0.3.0: create, idempotent/`unchanged`, `reports_to` conflict, reactivate, FILL_ONLY_EMPTY, dry_run. Не заглушки. | Нет теста «create без email». Остальные 6 — закрыты. |
| 4 | OrgLookup `md_writer.py` | `upsert_gal_result` есть, зовёт `store.upsert_from_source`. `merge()` строит md-таблицу и при adapter ещё зовёт upsert. `merge_to_enc_only` определена, **вызовов снаружи нет** (grep: только определение). | Production persist bootstrap всё ещё через `merge`, не через цикл upsert / `merge_to_enc_only`. |
| 5 | OrgLookup `cli.py` `cmd_add` | VPN `check_vpn` → stderr + **exit 2**. `--dry-run` читается, уходит в `upsert_gal_result(..., dry_run=args.dry_run)`. | По коду cmd_add закрыт. **Тестов cmd_add нет.** |
| 6 | OrgLookup `cli.py` `cmd_bootstrap` | Persist: `ContactStoreAdapter` + `md_writer.merge("", results, contact_store=adapter)`. `--dry-run` early-return до merge. | **Нарушение ТЗ:** финальная запись через md-merge, не цикл `upsert_gal_result` / `merge_to_enc_only`. |
| 7 | OrgLookup тесты | `tests/test_md_writer.py`: ровно 4 теста на старый md-merge (`test_merge_new_row`, conflict reports_to, idempotent, ambiguous→unclear). Файла `test_upsert_gal.py` нет. Grep по `tests/` на `cmd_add`/`cmd_bootstrap`/`upsert_gal`/`dry.run` — пусто. | Нет критериев v0.3.0 (upsert create / dry-run / VPN exit 2 / login не теряется / KeyError-regression / bootstrap). «4/4» в инвентаре — не про эту доработку. |
| 8 | ТЗ оба | Секции `## Exchange upsert (v0.3.0, 08.09)` есть. Frontmatter **version 0.2.2**. Строка **«Реализация на диске: нет»**. Статус секции: «доработка ТЗ». | version 0.2.2 ≠ 0.3.0; статус в ТЗ не обновлён (HF:docs-handoff не закрыт). |
| 9 | Инвентарь | `MAIN_TZ_INVENTORY.md`: оба инструмента 0.2.2; AC «6/6 upsert + 45/45 регресс»; OrgLookup «4/4 регресс». | Инвентарь завышает OrgLookup (4/4 = старый md-merge). После A3 — переписать факт тестов. |
| 10 | Канбан | Графа `DEV/exchange-contact-upsert` нет (audit). | Вне A2–A4 (A6 оркестратора). Исполнитель канбан/манифест **не** трогает. |

**Что уже хорошо (не переписывать):** черновик upsert 07.09 заменён; lookup/status/идемпотентность/`reports_to`/reactivate/`dry_run` в AC — по семантике ТЗ; `cmd_add` — VPN exit 2, живой `--dry-run`, запись через `upsert_gal_result`; манифест исполнитель не писал; 07.09-граф не поднимали; AC-тесты 6 — живые.

**Порядок волн исполнителя:** сначала AC (реэкспорт + email required), потом OrgLookup (`cmd_bootstrap`), потом тесты обоих проектов, потом docs.

---

## 2. A2 — дыры кода

Фаза исполнителя: `HF:impl`. Файлы-мишени только из таблицы ниже. Не создавать новые пакеты/инструменты.

### A2.1 Реэкспорт `upsert_from_source` в `__init__.py`

**Файл:** `~/USERTOOLS/AnywhereContacts/anywhere_contacts/__init__.py`

**Факт:** `__version__ = "0.1.0"`; в `__all__` есть `ContactStore`, имени `upsert_from_source` нет.

**Сделать:** реэкспорт имени `upsert_from_source` в публичный API пакета (ТЗ: «реэкспорт из `anywhere_contacts/__init__.py`»). Метод на `ContactStore` уже есть — не дублировать логику, не менять сигнатуру в `store.py` ради реэкспорта.

**Не делать:** bump `__version__` пакета (мелочь audit; semver ТЗ 0.3.0 закрывается в A4 на master-ТЗ, не здесь). Не трогать остальные экспорты (`ContactMerger`, `render_contact`, crypto, lock).

**Проверка A2.1:**

- [ ] grep `upsert_from_source` по `__init__.py` — не пусто
- [ ] `from anywhere_contacts import ContactStore` по-прежнему работает
- [ ] публичное имя `upsert_from_source` доступно с пакета (реэкспорт, не копия логики)

### A2.2 `cmd_bootstrap` → цикл upsert, не md-merge persist

**Файл:** `~/USERTOOLS/OrgLookup/orglookup/cli.py` — только `cmd_bootstrap` (persist-ветка).

**Факт (нарушение ТЗ):** после сбора `results` и если не `--dry-run`:

```
adapter = md_writer.ContactStoreAdapter(store)
_, outcome = md_writer.merge("", results, contact_store=adapter)
```

**Сделать:** финальную запись заменить на цикл `md_writer.upsert_gal_result` по `results` **или** на `md_writer.merge_to_enc_only` (оба пути названы в appendix A2). Рекомендация: **цикл `upsert_gal_result`** — тот же write-path, что у `cmd_add`; `merge_to_enc_only` внутри всё ещё вызывает `merge()` (строит md в памяти). Persist markdown / `ContactStoreAdapter`+`merge` как write-path — запрещён.

Сохранить: VPN exit 2 в начале; `--dry-run` early-return **до** persist (уже есть); JSON outcome (`added`/`updated`/`conflicts`) на stdout.

**Не делать:** не переписывать `cmd_add` (уже upsert). Не менять `cmd_who` / `cmd_manager` / `cmd_tree` / `cmd_rooms`. Не удалять `merge()` — старые 4 теста md-merge остаются. Не обязаны подключать `merge_to_enc_only` в CLI, если выбран цикл `upsert_gal_result`.

**Проверка A2.2:**

- [ ] в `cmd_bootstrap` persist-ветке нет `md_writer.merge(..., contact_store=adapter)`
- [ ] persist идёт через `upsert_gal_result` (цикл) или `merge_to_enc_only`
- [ ] `--dry-run` по-прежнему не пишет в store

### A2.3 Email required на create

**Файл:** `~/USERTOOLS/AnywhereContacts/anywhere_contacts/store.py` — ветка create в `upsert_from_source`.

**Факт:** при отсутствии контакта создаётся запись с `"email": record.get("email") or ""`. ТЗ v0.3.0: поле `email` — required.

**Сделать:** create без email (нет / пустая строка) → **не создавать** контакт, вернуть `status="unchanged"` + `conflicts[]` (форма как у `reports_to`: `login`, `field`, `current`, `incoming`, `source`), диск не писать. Update существующего с пустым incoming email — не раздувать: A2.3 только create.

**Тест (вместе с A2, файл уже есть):** в `tests/test_upsert_from_source.py` — один кейс create без email: статус unchanged, conflicts с `field=email`, `get_contact(login)` is None.

**Проверка A2.3:**

- [ ] create без email не добавляет login в `contacts`
- [ ] ответ: `unchanged` + непустой `conflicts`
- [ ] create с email по-прежнему `created` (регресс 6 существующих тестов)

---

## 3. A3 — тесты OrgLookup + прогон обоих проектов

Фаза: `HF:test`. Без реального EWS (как AC: fixture / mock).

### A3.1 Новый файл

**Создать:** `~/USERTOOLS/OrgLookup/tests/test_upsert_gal.py`

Критерии (appendix A3; в ТЗ OrgLookup это п.1–4 и 6; «login не теряется» = KeyError-regression: новый контакт не проглатывается):

| # | Критерий | Что проверить |
|---|---|---|
| 1 | upsert create | `upsert_gal_result` / `cmd_add` при отсутствии login создаёт запись в `contacts.enc` (не только JSON). |
| 2 | dry-run не трогает enc | `--dry-run` / `dry_run=True`: mtime/содержимое enc без изменений. |
| 3 | VPN → exit 2 | mock `check_vpn()==False` на `cmd_add`: return 2, store не тронут, сообщение на stderr. |
| 4 | login не теряется | после create `get_contact(login)` не None; login в результате upsert совпадает с record. |
| 5 | KeyError-regression | сценарий «login ещё нет в store» больше не теряется (исторический `add_alias`+`KeyError pass`). Контакт появляется в enc. |
| 6 | bootstrap без md-merge persist | persist-путь `cmd_bootstrap` не зовёт `md_writer.merge` для записи; цикл upsert / `merge_to_enc_only`; mock resolver/VPN. |

Моки: `ews_client.check_vpn`, `resolver.resolve`, `hierarchy.get_manager_login`, tmp `ContactStore` (как AC-тесты). Не ходить в GAL.

Старые 4 теста `test_md_writer.py` **не удалять** и не «чинить» под новый persist CLI — это регресс md-merge.

### A3.2 Прогон обоих проектов

Интерпретатор: `~/USERTOOLS/AnywhereContacts/venv_linux/bin/python3 -m pytest` (канон OrgLookup `pyproject.toml`; свой venv OrgLookup не создавать).

```
cd ~/USERTOOLS/AnywhereContacts && ../AnywhereContacts/venv_linux/bin/python3 -m pytest tests/ -q
cd ~/USERTOOLS/OrgLookup && PYTHONPATH=~/USERTOOLS/AnywhereContacts ~/USERTOOLS/AnywhereContacts/venv_linux/bin/python3 -m pytest tests/ -q
```

**Проверка A3:**

- [ ] `test_upsert_gal.py` покрывает 6 строк таблицы выше (не заглушки)
- [ ] AC `tests/test_upsert_from_source.py` по-прежнему green (+ кейс email-required)
- [ ] OrgLookup `tests/test_md_writer.py` 4/4 green
- [ ] полный `pytest tests/` обоих проектов — green
- [ ] в отчёте — фактические N/N, не копировать «4/4 регресс» из инвентаря 08.09

---

## 4. A4 — docs-handoff

Фаза: `HF:docs-handoff`. Только после green A2–A3. Манифест / `EcosystemManifest.json` / digest/render / `.env` / `jobs.json` / `entities.json` — **не** исполнитель (ORCH).

### Файлы

| Файл | Правка |
|---|---|
| `TZ/AnywhereContacts/AnywhereContacts_TZ.md` | frontmatter `version` → **0.3.0**. В секции v0.3.0: статус **«реализовано 08.09»**; убрать **«Реализация на диске: нет»**. Не переписывать семантику API. |
| `TZ/ExchangeOrgLookup/ExchangeOrgLookup_TZ.md` | то же: version **0.3.0**, статус **«реализовано 08.09»**, убрать «на диске: нет». |
| `TZ/MAIN_TZ_INVENTORY.md` | обе строки → version **0.3.0**; инвентарь = факт тестов после A3 (AC: 6 upsert + email-required + регресс; OrgLookup: 4 md-merge **плюс** N из `test_upsert_gal.py`). Не оставлять формулировку «4/4 регресс» как покрытие v0.3.0. |

README у OrgLookup на диске нет — не создавать.

**Проверка A4:**

- [ ] grep по обоим `*_TZ.md`: нет строки «Реализация на диске: нет»
- [ ] frontmatter обоих ТЗ: `0.3.0`
- [ ] секции v0.3.0: «реализовано 08.09»
- [ ] инвентарь 0.3.0 и счётчики тестов совпадают с выводом pytest A3
- [ ] `EcosystemManifest.json` не в diff исполнителя

---

## 5. Критерии приёмки по под-фазам

### A2 (HF:impl) — код

1. `__init__.py` реэкспортирует `upsert_from_source`.
2. `cmd_bootstrap` persist не через `md_writer.merge(..., contact_store=adapter)`.
3. Create без email: не создаёт контакт, `unchanged` + `conflicts`.
4. `cmd_add` / VPN / `--dry-run` / `upsert_gal_result` — поведение 08.09 сохранено.
5. Diff не содержит файлов из «Не трогать».

### A3 (HF:test) — тесты

1. Есть `OrgLookup/tests/test_upsert_gal.py` с шестью критериями таблицы A3.1.
2. Оба проекта: полный `pytest tests/` green на `venv_linux`.
3. Нет живого EWS в default-прогоне.

### A4 (HF:docs-handoff) — документы

1. Оба master-ТЗ: version 0.3.0, статус «реализовано 08.09», нет «на диске: нет».
2. Инвентарь синхронизирован с фактом тестов.
3. Манифест не изменён исполнителем.

План считается пройденным по точкам выше (галочки). Статус «completed» на весь кейс — не этот файл: после A4 ещё A5 `REV:tz` и A6 граф (оркестратор), затем ORCH и `GATE:done`. Исполнитель A2–A4 это не делает.

---

## 6. Не трогать

Из обоих ТЗ v0.3.0 и audit:

- `ContactMerger.merge()` / batch-синк коннекторов (`merger.py` логика)
- схема `contacts.enc` / `schema_version` 2.0, PK `login`
- PII: `render_contact`, `*_for_display`, maskers (`display.py`, `logger.py`)
- команды `who` / `manager` / `tree` / `rooms` (кроме общих хелперов, если уже используются upsert)
- `ews_client`, `resolver`, `hierarchy` — контракты GAL
- AggregateFromMeetings, `needs_gal.jsonl`, LDAP
- plaintext `tutu-contacts.md` (guard `PlaintextContactsMdForbidden` остаётся)
- `EcosystemManifest.json`, digest/render, `restore-all-skills.sh`, `.env`, `jobs.json`, `entities.json`
- ядро канбана / DevKanbanPipeline / GLOSSARY / скиллы (контур B)
- не unarchive граф 07.09
- не удалять 4 старых теста md-merge
- не писать новый USERTOOL

---

## 7. Пофайловый чеклист исполнителя

| Волна | Файл | Действие |
|---|---|---|
| A2.1 | `AnywhereContacts/anywhere_contacts/__init__.py` | изменить: реэкспорт |
| A2.3 | `AnywhereContacts/anywhere_contacts/store.py` | изменить: email required на create |
| A2.3 | `AnywhereContacts/tests/test_upsert_from_source.py` | изменить: тест без email |
| A2.2 | `OrgLookup/orglookup/cli.py` | изменить: только persist `cmd_bootstrap` |
| A3 | `OrgLookup/tests/test_upsert_gal.py` | **создать** |
| A3 | прогон pytest оба проекта | не код |
| A4 | `TZ/AnywhereContacts/AnywhereContacts_TZ.md` | изменить: статус/version |
| A4 | `TZ/ExchangeOrgLookup/ExchangeOrgLookup_TZ.md` | изменить: статус/version |
| A4 | `TZ/MAIN_TZ_INVENTORY.md` | изменить: 0.3.0 + факт тестов |

`md_writer.py`: менять только если A2.2 без этого нельзя (цикл `upsert_gal_result` уже в файле — правки md_writer не обязательны). `merge()` / `merge_to_enc_only` не переписывать «заодно».

---

## Прогресс выполнения

- [ ] A2.1 реэкспорт `__init__.py`
- [ ] A2.2 `cmd_bootstrap` persist = upsert-цикл / `merge_to_enc_only`
- [ ] A2.3 email required на create + тест AC
- [ ] A3 `test_upsert_gal.py` (6 критериев) + pytest оба проекта green
- [ ] A4 оба ТЗ 0.3.0 «реализовано 08.09» + инвентарь
- [ ] Diff без «Не трогать»

---

## Вне скоупа этого плана (не исполнитель A2–A4)

Из `appendix_exchange-finish-reliability` контур A, после docs:

- **A5 `REV:tz`** — прогон ревизора по двум секциям; снимать только явной фразой Саши.
- **A6 граф** — завести `DEV/exchange-contact-upsert`; off-board фазы. Канбан исполнителю A2–A4 закрыт.
- **Контур B** (GLOSSARY / скиллы / preflight) — отдельный CHANGE.

`GATE:done` по slug — только после A1–A6 (этот файл = A1).
