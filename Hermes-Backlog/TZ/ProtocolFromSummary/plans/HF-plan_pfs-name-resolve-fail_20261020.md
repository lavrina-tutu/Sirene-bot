# План HF:impl — §35 резолв имён «Имя Фамилия» (pfs-name-resolve-fail)

Кейс: **BUGFIX / DEV/pfs-name-resolve-fail**. Фаза: **HF:plan**.
Архитектор: cursor-grok-4.6-high (Путь 2 — резолв имён в shared-модуле).
Исполнитель следующих фаз: composer (HF:impl, HF:test).
Код в этой фазе **не** писать.

Канон: `WorkVault/Hermes-Backlog/TZ/ProtocolFromSummary/ProtocolFromSummary_TZ.md`
**v1.30.0 §35** (резолв имён «Имя Фамилия», AC-001..010, IAC-01..07).
Контракт метода: `WorkVault/Hermes-Backlog/TZ/AnywhereContacts/AnywhereContacts_TZ.md`
v0.3.1 §«find_contacts: token-set fallback» (строки 419–438).
Диагноз: `_fix_plan_20261020*` (Fireflies Custom AI Skill сменил формат имён с 19.10).
Режим: **one-pass**. Рабочие директории:
- `~/USERTOOLS/AnywhereContacts` (владелец `find_contacts`);
- `~/USERTOOLS/ProtocolFromSummary` (потребитель `_resolve_one`, аддитивные тесты).

---

## 0. РЕЗЮМЕ ДИСКА (проверено чтением)

| Место | Факт с диска | Отношение к §35 |
|---|---|---|
| `AnywhereContacts/anywhere_contacts/store.py:69-87` | `find_contacts`: substring `q in login|fio|email|aliases`, single pass, возвращает всё | **изменяемый** (добавить Pass 2) |
| `AnywhereContacts/tests/test_store_roundtrip.py` | эталон живого store: `generate_key()`, `ContactStore(tmp_path/"contacts.enc", key)`, `store.write(data)` | переиспользовать паттерн фикстуры |
| `ProtocolFromSummary/protocolfromsummary/contacts_resolver.py:80-173` | `_resolve_one`: §12 `_split_surname_initials` → `store.find_contacts(surname)` → substring `find_contacts(raw)` → §11.3 DEFAULT_ASSIGNEE_LOGIN → userkey/Confluence fallback | **не менять**; `find_contacts(raw)` с Pass 2 даст reverse-хиты |
| `ProtocolFromSummary/tests/test_contacts_resolver.py` | `FakeStore.find_contacts` = substring-only (своя копия); тесты §12 и §11.3 на FakeStore | §12/§11.3-тесты **не переписывать** (IAC-05); новые — **живой** `ContactStore` |
| `AnywhereContacts/pyproject.toml` | `version = "0.1.0"` (py/egg-info) — но ТЗ v0.3.1; бамп 0.3.0→0.3.1 уже сделан в ТЗ на finalize, в pyproject **не** трогать по §35 (версия пакета ≠ схема) | вне раунда |
| `AnywhereContacts_TZ.md:419-438` | контракт Pass 2 **уже записан** (finalize) | документирование не повторять |
| `TaskRefresh`, `MarkObjectsFromSummary`, `OrgLookup`, `MeetingScheduler`, `route.py` | потребители `find_contacts` / shared-модуля | **не патчить** (AC-008) |

**Факт исполнителю нельзя «поправить по памяти»:** Pass 1 обязан остаться
неизменным и возвращаться первым (AC-003); Pass 2 — только при пустом
Pass 1 и ≥2 токенах (AC-005); неоднозначность N>1 → возвращать **всех**
(AC-004), выбор делает PFS (§11.3).

---

## 1. ИТОГОВАЯ РЕКОМЕНДАЦИЯ (one-pass)

Добавить аддитивный token-set **Pass 2** в `ContactStore.find_contacts`
(AnywhereContacts). Pass 1 (substring) не трогать и возвращать сразу,
если непуст. Иначе, при ≥2 токенах в query, искать контакты, где каждый
токен query содержится в множестве токенов `fio ∪ display_name ∪ aliases`
(lowercase, целые слова, `split()`); вернуть 0/1/N без скоринга.
PFS/`_resolve_one`/`task_slug` **не** патчить — тот же вызов, больше хитов.
Puть 1 (правка промпта самари Fireflies / `ff_summary.json`) — **отдельный
пакет, НЕ этот HF:impl** (Q-1 §35, рекомендация архитектора).

---

## 2. ИЗМЕНЯЕМЫЕ ФАЙЛЫ КОДА

### 2.1. `~/USERTOOLS/AnywhereContacts/anywhere_contacts/store.py` — `find_contacts`

Заменить тело метода (сохранив Pass 1 логику 1-в-1) на:

```python
def find_contacts(self, query: str) -> Dict[str, Dict[str, Any]]:
    q = (query or "").strip().lower()
    if not q:
        return {}
    data = self.read().get("contacts", {})

    # --- Pass 1: substring (как было, не менять; побеждает) ---
    results: Dict[str, Dict[str, Any]] = {}
    for login, c in data.items():
        if q in login.lower():
            results[login] = c
            continue
        if q in (c.get("fio") or "").lower():
            results[login] = c
            continue
        if any(q in (e or "").lower() for e in [canonical_email(c)] +
               [s.get("email", "") for s in (c.get("sources") or {}).values() if isinstance(s, dict)]):
            results[login] = c
            continue
        if any(q in a.lower() for a in (c.get("aliases") or []) if isinstance(a, str)):
            results[login] = c
    if results:
        return results

    # --- Pass 2: token-set fallback «Имя Фамилия» (§35 v0.3.1) ---
    # Только при пустом Pass 1 и >=2 целых словах. Токен = целое слово
    # split() (whitespace), lowercase. Лишний токен -> 0. Однословные
    # запросы остаются чистым Pass 1 (AC-005).
    q_tokens = q.split()
    if len(q_tokens) < 2:
        return results
    out: Dict[str, Dict[str, Any]] = {}
    for login, c in data.items():
        hay = " ".join(
            [c.get("fio") or "", c.get("display_name") or ""]
            + [a for a in (c.get("aliases") or []) if isinstance(a, str)]
        ).lower()
        if set(q_tokens).issubset(set(hay.split())):
            out[login] = c
    return out
```

Заметки исполнителю:
- Никаких других изменений в `store.py` (upsert/merger/schema/PII не трогать).
- `canonical_email`, `Dict`, `Any` уже импортированы.
- «Фамилия И.О.» (`Ткаченко А.В.`) — НЕ обязан матчиться Pass 2
  (токен `а.в.` ≠ `александр`); это §12 в PFS до `find_contacts(raw)`
  (AC-006).

### 2.2. Файлы, которые **не** меняем

`ProtocolFromSummary/protocolfromsummary/contacts_resolver.py`,
`task_slug.py`, `pipeline.py`, `route.py`, `dedup.py`, `playground_*`,
`notifier.py`; `TaskRefresh/**`, `MarkObjectsFromSummary/**`, `OrgLookup/**`,
`MeetingScheduler/**`, `ExchangeMonitor/**`; `EcosystemManifest.json`,
`jobs.json`, `.env`, `ff_summary.json` (AC-007, AC-008, Non-goals §35).

---

## 3. ТЕСТЫ (аддитивные, no live API)

### 3.1. Новый `~/USERTOOLS/AnywhereContacts/tests/test_find_contacts_pass2.py`

Фикстура — живой store (паттерн `test_store_roundtrip.py`):

```python
import pytest
from anywhere_contacts import ContactStore, generate_key, empty_payload
from anywhere_contacts.schema import now_iso


def _mk_store(tmp_path, contacts: dict, *, login="tkachenkoav"):
    key = generate_key()
    store = ContactStore(tmp_path / "contacts.enc", key)
    payload = empty_payload()
    for _login, c in contacts.items():
        contacts_map = payload.setdefault("contacts", {})
        contacts_map[_login] = {
            "login": _login,
            "fio": c.get("fio", ""),
            "display_name": c.get("display_name") or c.get("fio", ""),
            "department": "", "team": "", "position": "", "is_room": False,
            "active": True, "reports_to": "", "synced_at": now_iso(),
            "sources": {"test": {"email": c.get("email", ""),
                                 "synced_at": now_iso(), "active": True}},
            "aliases": list(c.get("aliases", [])),
            "messenger_ids": {}, "notes": "", "project_roles": [],
            "custom_updated_at": None,
            "confluence_userkey": c.get("userkey"),
        }
    store.write(payload)
    return store
```

Тесты (по одному на AC):

| # | Тест | AC |
|---|---|---|
| 1 | `test_reverse_two_word_unique` — один контакт `tkachenkoav` fio «Ткаченко Александр Владимирович», userkey задан; `find_contacts("Александр Ткаченко")` → `{"tkachenkoav": ...}` ровно 1 | AC-001 |
| 2 | `test_reverse_pairs` — пары (fio, raw): («Криворотов Кирилл», «Кирилл Криворотов»), («Галашов Владислав», «Владислав Галашов»), («Жиров Александр», «Александр Жиров») → каждый ровно 1 | AC-001 |
| 3 | `test_three_word_permutation` — fio «Ткаченко Александр Владимирович»; `find_contacts("Александр Владимирович Ткаченко")` → 1 | AC-001 |
| 4 | `test_canonical_still_pass1` — `find_contacts("Ткаченко Александр Владимирович")` → 1 (Pass 1, не удвоение) | AC-003 |
| 5 | `test_pass1_login_email_alias_unchanged` — `"tkachenkoav"`, substring email, substring alias → тот же хит, что до пакета; nonempty Pass 1 **не** union-ит Pass 2 | AC-003 / IAC-03 |
| 6 | `test_two_iwanov_reverse_ambiguous` — `fio="Иванов Иван Петрович"` и `"Иванов Иван Сергеевич"`; `find_contacts("Иван Иванов")` → **2** логина | AC-004 |
| 7 | `test_extra_token_zero` — `find_contacts("Александр Ткаченко Х")` → `{}` (лишний токен) | AC-001/(§35 канон) |
| 8 | `test_single_word_no_pass2` — 2 контакта c «Александр» в fio; `find_contacts("Александр")` → substring-хит N≥1 (Pass 2 не запускается) | AC-005 |

Проверка: `cd ~/USERTOOLS/AnywhereContacts && python -m pytest tests/test_find_contacts_pass2.py -v`

### 3.2. `~/USERTOOLS/ProtocolFromSummary/tests/test_contacts_resolver.py` (дописать)

Добавить тесты на **живом** `ContactStore` (импорт из `anywhere_contacts` +
та же фикстура, что 3.1). FakeStore-тесты §12/§11.3 **не трогать** (IAC-05).

| # | Тест | AC |
|---|---|---|
| 9 | `test_live_reverse_resolve_to_userkey` — живой store `tkachenkoav` fio «Ткаченко Александр Владимирович», userkey `8a8383...`; `resolve_participants(["Александр Ткаченко"], ...)` → `resolved=True, login="tkachenkoav", userkey="8a8383..."` | AC-002 |
| 10 | `test_live_reverse_as_assignee_same_resolver` — делегирование: тот же raw, `_resolve_one` (отдельный вызов) → тот же login (доказывает: оба контура через один резолвер, AC-002; diff не добавляет резолв в `task_slug.py`) | AC-002 |
| 11 | `test_live_unknown_fail_soft` — `resolve_participants(["Незнамов Иван"], ...)` → `resolved=False`, исключения нет | AC-009 |

### 3.3. Регресс существующих наборов

```
cd ~/USERTOOLS/AnywhereContacts && python -m pytest -q
cd ~/USERTOOLS/ProtocolFromSummary && python -m pytest -q -m "not live_confluence"
```

Зелёные; новые тесты аддитивны; нет правок `jobs.json` / `.env` / манифеста /
`ff_summary.json` / сигнатур боевого пути PFS (AC-010). (AnywhereContacts без
pytest.ini `-m` — просто `pytest -q`; PFS как в AC-010.)

---

## 4. ПОРЯДОК РЕАЛИЗАЦИИ ДЛЯ ИСПОЛНИТЕЛЯ (поэтапно)

> Bite-sized: каждый шаг — отдельное действие + коммит. Исполнитель —
> composer (HF:impl → HF:test). Коммиты по факту каждого зелёного шага.

**Шаг 1. Тест-фикстура живо** — файл 3.1 `test_find_contacts_pass2.py`
с фикстурой `_mk_store` и **тестом 1** (`test_reverse_two_word_unique`).
Прогнать: `python -m pytest tests/test_find_contacts_pass2.py -k test_reverse_two_word_unique -v`
→ FAIL (сейчас 0 кандидатов, ключа нет).

**Шаг 2. Pass 2 в `store.py`** — применить diff §2.1. Тот же тест → PASS.

**Шаг 3. Остальные AC-тесты 3.1** (2–8) — дописать, прогнать весь файл →
все PASS. Коммит: `feat(anywhere_contacts): add token-set Pass 2 to find_contacts (§35) + tests`.

**Шаг 4. PFS аддитивные тесты** — файл 3.2 (тесты 9–11) в
`tests/test_contacts_resolver.py` (живой store). Прогнать файл → все PASS.
Коммит: `test(pfs): live-store reverse name resolve + fail-soft (§35 AC-002/009)`.

**Шаг 5. Полный регресс** — §3.3 обе пачки зелёные.
Коммит финальный: `feat: §35 pfs-name-resolve-fail — Pass 2 token-set резолв имён (v1.30.0)`.

> Как должен стопориться: на любом шаге, где expected-результат не достигнут,
> НЕ гадать — смотреть фактический вывод, сравнивать с §35 каноном поведения
> (строки 8288–8314 ТЗ) и чинить в рамках того же diff. Расширение scope
> (правка `task_slug.py`, промпта, MOFS) — запрещено, это отдельный пакет.

---

## 5. ТОЧКИ ПРОВЕРКИ (критерии приёмки кода -> HF:test)

| # | Что проверить | Как | Ожидание |
|---|---|---|---|
| K1 | Pass 1 не сломан (substring / login / email / alias) | `pytest -q` AnywhereContacts + PFS offline | зелёные |
| K2 | reverse «Имя Фамилия» → тот же login/userkey | тест 3.1 (#1,#2,#3) + PFS (#9) | 1 кандидат → mention |
| K3 | неоднозначность N>1 → всех, не «первый» | тест 3.1 #6 | 2 логина; PFS `resolved=False` |
| K4 | лишний токен → 0 | тест 3.1 #7 | `{}` |
| K5 | однословные → чистый Pass 1 + §12 живы (FakeStore-тесты не переписаны) | тест 3.1 #8 + существующие `test_surname_with_*` | зелёные |
| K6 | fail-soft публикации | тест PFS #11 | `resolved=False`, без исключения |
| K7 | diff чистый (нет MOFS/TaskRefresh/route/ff_summary/§34-пробела) | `git diff --stat` vs изменяемые файлы §2 | только `store.py` + тестовые файлы |

---

## 6. ПОСТРАДАВШИЕ ДАННЫЕ / ОПЕРАЦИОНКА (вне HF:impl)

Republish встречей 19.10 (площадка `523032632`) — операционка **после**
HF:impl/HF:test, не hold `GATE:done` (§35 связи, строка 8409). Новые ingest
20.10+ несут `<ac:link>` по мере импорта. Backfill существующих строк на
площадке — отдельное решение Саши, вне пакета.

---

## 7. КАРТА AC → ФАЙЛ

| AC | Файл | Где |
|---|---|---|
| AC-001, 003, 004, 005 | `AnywhereContacts/tests/test_find_contacts_pass2.py` | store |
| AC-002, 009 | `ProtocolFromSummary/tests/test_contacts_resolver.py` (живой store) | resolver |
| AC-005, 006 | FakeStore-тесты (регресс, не переписывать) | resolver |
| AC-007, 008 | diff (нет правок чужих инструментов / §34 пробела) | repo |
| AC-010 | `pytest -q` обе пачки | CI/локально |

`REV:tz` уже APPROVE (t_459fa0a9). Gate `plan-approve` — auto-pass (t_597beaf9).
`HF:backup` — t_450aaf5b (бэкап перед правкой). Крон не ставим.

## Прогресс выполнения

- [ ] Шаг 1 — Фикстура + тест 1 (FAIL)
- [ ] Шаг 2 — Pass 2 в store.py (PASS)
- [ ] Шаг 3 — AC-тесты 3.1 (PASS)
- [ ] Шаг 4 — PFS аддитивные тесты 3.2 (PASS)
- [ ] Шаг 5 — полный регресс 3.3 (зелёные)