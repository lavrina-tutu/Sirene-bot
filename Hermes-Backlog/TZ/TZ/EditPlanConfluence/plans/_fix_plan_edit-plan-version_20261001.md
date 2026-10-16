# `_fix_plan_edit-plan-version_20261001` — edit-plan-confluence PUT version+1 (HTTP 409)

**Кейс:** BUGFIX скилла `productivity/edit-plan-confluence`. Не USERTOOL.
**Роль:** архитектор. Фаза: `BUG:diagnose`, read-only. Реализация — после `GATE:diagnose-review`.
**Канон:** DKP v0.4.2; GLOSSARY v0.2.12; SKILL.md `edit-plan-confluence` v0.2.1; `scripts/pipeline.py`, `scripts/conf_client.py`, `scripts/gantt_attachment.py`.

Оценка объёма (факт, не команда skip): **3 файла** кода+тестов (`pipeline.py` + `test_pipeline.py` + `test_rest_live.py`), без сущностей/cron/.env/манифеста, вне ядра канбана. Классификация **BUGFIX-LIGHT** — после `GATE:diagnose-review`, сужение делает **оркестратор**.

---

## 0. Диагноз одной фразой

`apply_plan` читает текущую версию страницы (fresh, напр. 18) и передаёт её в `put_page` **как есть** (`version.number=18`). Confluence REST требует на PUT-обновлении версию **текущая+1** (инкремент), иначе HTTP 409 `Version must be incremented. Current is: 18`.

Проверено по коду (read-only, с диска):

- `scripts/pipeline.py:174-176` (`apply_plan`):
```python
fresh = client.get_page(page_id, expand="version")
version = int(fresh["version"]["number"])   # текущая версия (напр. 18)
client.put_page(page_id, page["title"], storage, version)   # ← БАГ: шлём текущую, а не +1
```
- `scripts/conf_client.py:61-75` (`put_page`) корректно формирует `"version": {"number": version}` — просто ему передают **неверный** number. Сам клиент не виноват.
- `scripts/gantt_attachment.py:97-98` уже использует `conflictPolicy=override` для вложения — это работает, поэтому при `apply` вложение заливается, а PUT страницы падает 409. Симптом «два прогона оба 409» объясняется: при `apply_plan` вложение пересоздаётся (bump версии вложения), затем PUT страницы с `version=current` → 409 → страница не сохраняется → повторный прогон снова 409.

Риск-неточность в изначальной формулировке контекста (что «контекст был неполный»): фактически клиент НЕ добавляет +1 сам, и у `apply_plan` нет инкремента — версия передаётся как есть. Механизм re-read (174) есть, но отсутствует сам инкремент `+1`.

---

## 1. Пофайловый план

### 1.1 `scripts/pipeline.py:176` — единственная runtime-строка

Было:
```python
client.put_page(page_id, page["title"], storage, version)
```
Станет:
```python
client.put_page(page_id, page["title"], storage, version + 1)
```

Это сохраняет имеющийся optimistic-locking (re-read перед PUT на 174) и добавляет недостающий инкремент. **Почему не `conflictPolicy=override`:** re-read+increment — штатный optimistic-concurrency Confluence: если страницу изменили между re-read и PUT — Confluence сам вернёт конфликт, и прогон честно не перезапишет чужую правку. `conflictPolicy=override` отключил бы эту защиту (молча перезаписать) — НЕ рекомендуется для страницы плана. `conflictPolicy=override` оставить только там, где он есть (вложение, gantt_attachment.py), не трогать.

Примечание к тесту `test_apply_plan_confirm_order_upload_then_put` (test_pipeline.py:50-73): сейчас он жёстко ждёт `call_args[0][3] == 5` (текущая версия). После фикса станет `6`. Это **обязательное** изменение теста, иначе регресс.

### 1.2 `tests/test_pipeline.py`

1. **Обновить** `test_apply_plan_confirm_order_upload_then_put`: `assert client.put_page.call_args[0][3] == 6` (было `5`) — mock отдаёт `{"version": {"number": 5}}`, значит PUT обязан получить `5+1=6`.
2. **Добавить регресс-тест** `test_apply_plan_put_version_is_incremented` (прямой assert стратегии):
   - mock: `get_page.side_effect = [_mock_page_no_macro(), {"version": {"number": 18}}, ]` — вторая выборка (re-read) = 18;
   - `list_attachments.return_value = []`, `upload_gantt_json` → 1;
   - вызвать `apply_plan(client, "519501810", mpp_fixture, "лей")`;
   - `assert client.put_page.call_args[0][3] == 19` (18+1, НЕ 18). Это запирает баг: неверная реализация (без +1) упадёт.

### 1.3 `tests/test_rest_live.py`

Добавить live-тест (за env-гвардом `EDITPLAN_LIVE=1`, как существующий), который доказывает, что PUT с `version+1` реально проходит на тестовой странице 519501810:

```python
def test_live_apply_plan_ok(monkeypatch):   # только при EDITPLAN_LIVE=1
    # стрелять в тестовый 519501810 полным apply_plan с моком upload_gantt_json
    # (чтобы не плодить вложения), но с РЕАЛЬНЫМ ConfluenceClient
    # → assert результат ApplyResult, исключений ConfluenceError(409) нет
```

Назначение: смоук подтверждения, что инкремент принимается боевым Confluence. Не часть обязательной CI-фазы (live-гвард); в стационарном прогоне скипается.

### 1.4 Что не менять этим багфиксом

- `scripts/conf_client.py` — `put_page` формирует payload корректно; сигнатура/тело не меняются.
- `scripts/gantt_attachment.py` — `conflictPolicy=override` для вложения оставить.
- SKILL.md (docs) — формулировка «PUT storage» корректна, описание стратегии версии в план-файле; в SKILL отдельная правка не нужна (если оркестратор захочет — отдельной строкой, НЕ в объём LIGHT).
- Живая AB `519492935` — не трогать; live-тест только на `519501810`.

---

## 2. IAC (LIGHT: 1–3 строки)

| IAC | path | verify | depends | covers |
|---|---|---|---|---|
| **IAC-01** | `scripts/pipeline.py:176` (`+1`) | `python3 -m pytest tests/test_pipeline.py -k "put_version or order_upload_then_put" -q` → оба passed | — | PUT несёт `version+1` (инкремент) |
| **IAC-02** | `tests/test_pipeline.py` (регресс `put_version_is_incremented` + обновлённый order-тест) | `python3 -m pytest tests/test_pipeline.py -q` → весь файл зелёный | IAC-01 | нет регресса; баг заперт |
| **IAC-03** | `tests/test_rest_live.py` (live-смоук) | `EDITPLAN_LIVE=1 python3 -m pytest tests/test_rest_live.py -q` → applies без 409 | IAC-01 | боевой Confluence принимает PUT |

Нет `depends: operator:` (класс S).

---

## 3. Точки проверки (HF:test / приёмка)

1. `apply_plan` со свежей версией страницы 18 → PUT получает `19` (не 18).
2. Регресс: mock версии 5 → PUT получает 6 (не 5).
3. Live (519501810, `EDITPLAN_LIVE=1`): полный `apply_plan` НЕ кидает `ConfluenceError` 409; результат — `ApplyResult` с `page_url`.
4. Порядок вызовов не изменился: upload → put (существующий тест `order_upload_then_put`).
5. Вложение по-прежнему уходит с `conflictPolicy=override` (gantt_attachment.py не тронут).
6. Оффлайн-конверсия / guard живой AB не тронуты (тесты `build_plan_*`, `live_ab_guard`).

---

## 4. Классификация после GATE:diagnose-review

| | |
|---|---|
| Семейство | **BUGFIX** (баг скилла, root cause известен) |
| Сужение LIGHT | **да, рекомендовать** оркестратору: ≤3 файла (`pipeline.py`, `test_pipeline.py`, `test_rest_live.py`), без сущностей/cron/.env/манифеста, не shared-модуль ядра. Хвост GLOSSARY §5.2 BUGFIX-LIGHT: `TZ:patch` → `TZ:finalize` → take-into-work → `HF:impl` → `HF:test` → docs → `GATE:done`. Skip `HF:plan` / REV / backup / ORCH. План = этот файл. |
| Не LIGHT если | оркестратор решит править SKILL.md (docs) или conf_client в том же графе (тогда риск >3 файлов) |

Архитектор граф не строит и LIGHT не включает — сужение за `GATE:diagnose-review`.

---

## 5. Риски

| Риск | Митигация |
|---|---|
| `version+1` при изменённой между re-read и PUT странице → Confluence вернёт новый 409 | это **желаемо** (optimistic lock); retry = повторный прогон `apply` с новым re-read |
| Обновлённый тест order_upload_then_put (`==6`) сломает не-обновлённый код | в одном графе с `pipeline.py` фиксом; тест+код в одной итерации |
| Live-тест мутирует реальную страницу 519501810 | только по `EDITPLAN_LIVE=1`, только тестовая страница, вложение мокается (`upload_gantt_json` mock) |
| Ложное «клиент виноват» → рефакторинг conf_client | НЕ трогаем: payload корректный, bug в передаче номера |
| `conflictPolicy` на страницу → перезапись чужой правки | НЕ используем для страницы; только re-read+increment |

Открытых вопросов Саше нет.