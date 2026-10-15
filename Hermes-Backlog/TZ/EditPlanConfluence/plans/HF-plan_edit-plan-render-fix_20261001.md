---
type: hf-plan
title: "Пофайловый план render-fix: гант пуст + однострочное «Итого»"
slug: edit-plan-render-fix
case: BUGFIX
phase: HF:plan
date: 2026-10-01
status: draft-plan
author: архитектор (cursor-grok-4.6-high, HF:plan)
card: t_3b43500a
root: DEV/edit-plan-render-fix
source_tz: TZ/EditPlanConfluence/EditPlanConfluence_TZ.md v0.2.2
source_diagnose: skills/productivity/edit-plan-confluence/_fix_plan_20261001.md
executor: composer-2.5
next_phases: REV:plan → GATE:plan-approve → HF:backup → HF:impl → HF:test → HF:docs-handoff → ORCH:shared-state → GATE:done
---

# HF:plan — DEV/edit-plan-render-fix

Кейс **BUGFIX** (GLOSSARY §2 / §5.2): полный `PLAN-IMPL-TAIL`. Объём **4 файла** кода+тестов — по критерию LIGHT (≤3 файла) **не** укладывается. Сужение графа — оркестратор, не эта карточка. Код в этом вызове **не** писать.

Канон: master-ТЗ **v0.2.2** (`TZ:patch` + `TZ:finalize` 01.10 уже на диске). Диагноз: `_fix_plan_20261001.md` (`BUG:diagnose` `t_0352f5a4`). Этот файл — объект `REV:plan` / `GATE:plan-approve` и инструкция исполнителю `HF:impl` / `HF:test`.

Новая сущность EntityRegistry / пакет USERTOOLS **не** предлагаются (reuse-first: правка существующего скилла `productivity/edit-plan-confluence`).

Открытых вопросов Саше нет. Operator-hold нет (`depends: operator:` нет; класс S). Live Confluence / `EDITPLAN_LIVE` в пакет не входят.

---

## 0. Факт на диске (01.10) — не трогать работающее вне дельты

Проверено чтением 01.10. Каталог скилла **есть** (легальный черновик v0.2.1, не premature-impl).

| Место | Факт | Цель пакета |
|---|---|---|
| `scripts/mpp_convert.py:65` `build_event_tree` | `rows = [r for r in tasks if r.get("id") and r["id"] != "0"]`; `lvl = int(r["outline_level"])` | фильтр + безопасный парс уровня |
| `scripts/mpp_convert.py:91` | `ValueError("No root task…")` если `root is None` | оставить |
| `scripts/mpp_convert.py:247` `convert_mpp_csv` | `root, rows = build_event_tree`; `rows` → `max_used` и `build_dependencies` | сигнатуру не менять; узкий `rows` закрывает deps/max_used |
| `scripts/itogo.py:16` `ITOGO_LINE2_RE` | только `человек-часа`, без обёртки `<p>` | расширить вырез |
| `scripts/itogo.py:72` `build_itogo_html` | две `<p><strong>…</strong></p>` включая Трудозатраты | одна строка дат/N; `m_hours` в сигнатуре оставить |
| `scripts/itogo.py:78` `patch_itogo` | патч только если line1 **и** line2; иначе препенд (дубликат «Итого:») | всегда вырезать line2; патч line1 независим |
| `scripts/itogo.py:100` `apply_itogo` | есть line1 → `patch_itogo`; нет → вставка двухстрочного HTML | вырез line2 в обеих ветках |
| `scripts/itogo.py:37` `compute_itogo_from_csv` | уже `outline_level == "1"` и `id != "0"`; кортеж 4 элементов | **не менять** |
| `scripts/gate_diff.py:52` | `Итого: {d1} — {d2}, {n} р.д., {m} ч-ч` | не этот пакет (текст гейта ≠ storage) |
| `scripts/pipeline.py:124,164,177,241` | зовёт `build_itogo_html` / `apply_itogo` с `(d1,d2,n,m)` | не менять; однострочный HTML придёт сам |
| `tests/test_itogo.py:23,36,50` | ждут `"Трудозатраты: 2 356…"` / `"2 356" in out` | переписать под однострочный канон |
| `tests/test_mpp_convert.py` | фикстура 080926: шапка `id=0, outline_level=0` → баг 1 не ловится | синтетика id=217 без нового файла CSV |
| `tests/fixtures/ab_080926_пункт12__tasks.csv` строка id=0 | имя «Антибот внедрение…», `outline_level=0` | не менять файл; клон полей в тесте |
| `tests/fixtures/…__tasks.csv` строка id=1 | «Доработки АБ-платформы ТУТУ до Trisigma - оценка», `outline_level=1`, 33 события flat | эталон корня после фикса |
| `SKILL.md:66` / `:79` | «две строки над макросом»; питфолл «M «Итого»» | **HF:docs-handoff**, не impl |
| `references/mpp-to-gantt.md:29` | корень = outline_level=1, про шапку 0 с ненулевым id молчит | **HF:docs-handoff** |
| `~/USERTOOLS/MppReader/read_mpp.py` | контракт CSV не менять | не трогать |
| ConfluenceSync | другой хост `conf.tutu.ru`; только `.env` токена | не трогать |

`_fix_plan_20261001.md` в каталоге скилла — артефакт diagnose, **не** править на impl.

---

## 1. Цель и критерии «готово»

### 1.1 Два бага (I1 / I2 из ТЗ § TZ:patch 01.10)

**I1 (критический).** Служебная шапка MPP с `outline_level≤0` и настоящим id (воспроизведено: `id=217`) проходит текущий фильтр → становится `eventsData[0]`. Два порядка CSV:

1. шапка первая → корень-шапка, реальный id=1 ребёнок, `count_tasks=34`;
2. шапка не первая → `root` перезаписывается шапкой без детей → плагин «No records to display».

**I2.** `build_itogo_html` всегда пишет `Трудозатраты: M человек-часа`. `patch_itogo` при обеих строках **обновляет** line2, не удаляет. Требование v0.2.2 §9: в storage только `Итого: с DD.MM.YY по DD.MM.YY - N рабочих дней`; line2 не создавать и вырезать, если есть.

### 1.2 Готово этой фазы

- Этот файл на диске.
- Пофайловый план + таблица IAC с `covers AC-###`.
- Код / SKILL.md / master-ТЗ / манифест / соседи **не** изменены этим вызовом.

### 1.3 Готово пакета (хвост, не эта карточка)

AC-001…005 из master-ТЗ секции `TZ:patch 2026-10-01 — render-fix`. Класс S. После `HF:test`: `pytest -m "not live"` зелёный; diff только 4 файла impl (+ docs на `HF:docs-handoff`).

---

## 2. Рекомендация (одна, закрытая)

Фильтровать служебные узлы **в одном месте** — при сборке `rows` в `build_event_tree` (`id` непустой, `id != "0"`, `outline_level` парсится как число **> 0**). Тот же безопасный парс использовать для `lvl` в цикле стека (иначе `"1.0"` пройдёт фильтр и упадёт на `int("1.0")`). Отдельного «skip в стеке» нет.

Блок «Итого»: `build_itogo_html` — одна `<p><strong>…</strong></p>`; хелпер вырезает line2 целиком (обёртка `<p>`, варианты «человек-часа/часов/человеко-часов», NBSP); `patch_itogo` / `apply_itogo` всегда вырезают line2 и не пишут её. Сигнатура `(…, m_hours)` сохраняется — без каскада в `pipeline.py` / `gate_diff.py` / `child_page.py`.

Не предлагается: правка `read_mpp.py`, фильтр «только стек / rows оставить», выкидывание тестов ради LIGHT, правка `gate_diff.py` (M в тексте гейта — не storage).

---

## 3. Что НЕ трогать (жёсткий список impl)

Файлы **вне** пакета `HF:impl`:

- `scripts/cli.py`, `scripts/pipeline.py`, `scripts/child_page.py`, `scripts/gate_diff.py`, `scripts/conf_client.py`, `scripts/gantt_attachment.py`, `scripts/macro.py`, `scripts/env.py`, `scripts/mpp_calendar.py`, `scripts/mpp_input.py`
- `SKILL.md`, `references/mpp-to-gantt.md`, `references/empty-gantt-template.json` (docs — `HF:docs-handoff`)
- `~/USERTOOLS/MppReader/read_mpp.py`, скилл `read-mpp`, пакет `USERTOOLS/ConfluenceSync`
- живая AB `519492935`; live REST; `tests/test_rest_live.py`
- новый файл фикстуры CSV на диске
- `EcosystemManifest.json`, digest, `restore-all-skills.sh`, `.env`, `jobs.json`, `entities.json` (`ORCH:shared-state`)
- master-ТЗ (уже 0.2.2)
- `compute_itogo_from_csv` / `compute_itogo_from_gantt` (четвёртый элемент кортежа остаётся)
- сигнатуры `build_event_tree`, `build_itogo_html(..., m_hours)`, `patch_itogo(..., m_hours)`, `apply_itogo(..., m_hours)`
- поведение стека при **нескольких** узлах `outline_level=1` (не этот баг)

Ожидаемый побочный эффект **без** правки `gate_diff.py` / `pipeline.py`: `format_itogo_pair` / `itogo_after` станут одной строкой дат/N (раньше две). Строка гейта `:52` (`…N р.д., M ч-ч`) не меняется. `tests/test_pipeline.py::test_apply_plan_itogo_above_new_macro` проверяет только позицию `"Итого:"` над макросом — зелёный. `tests/test_gate_diff.py` не ждёт «Трудозатраты».

---

## 4. Пофайловый план `HF:impl`

Корень скилла: `/home/tkachenkoav/hermes-workspace/skills/productivity/edit-plan-confluence/`.  
Интерпретатор тестов: тот же, что сейчас (`python3 -m pytest` из каталога скилла; `tests/conftest.py` кладёт `scripts/` в `sys.path`).

Порядок: П.1 + П.2 вместе (фильтр без теста шапки не закрывает I1) → П.3 + П.4 вместе (HTML без правки assert сломает текущий `test_itogo.py`). Один проход impl допустим.

### П.1 — `scripts/mpp_convert.py` · `build_event_tree`

**Назначение.** Не пускать служебную шапку MPP в дерево и в возвращённый `rows`.

**Добавить** модульную функцию (имя зафиксировать):

```python
def _parse_outline_level(raw: str | None) -> int:
    """Пустое / мусор / нечисло → 0. '1.0' → 1. Не бросать ValueError."""
```

Реализация: `str(raw).strip()`; пусто → 0; `int(float(s))` в `try`; `ValueError`/`TypeError` → 0. Не использовать голый `int("")`.

**Заменить фильтр** (`:65`) на:

```python
rows = [
    r for r in tasks
    if r.get("id") and r["id"] != "0" and _parse_outline_level(r.get("outline_level")) > 0
]
```

**В цикле** (`:69`) заменить `lvl = int(r["outline_level"])` на `lvl = _parse_outline_level(r.get("outline_level"))`. Это **не** второй фильтр стека: все элементы `rows` уже `lvl > 0`; парс нужен, чтобы `"1.0"` не ронял конвертер.

**Не менять:** сигнатуру `build_event_tree`; сообщение `ValueError` на `:91`; `fill_parent_fields` / `flatten_events` / `build_dependencies` / `build_assignments` / `convert_mpp_csv`. После узкого `rows`: шапка не в `flat` → связь `from`/`to` == 217 не создаётся (`p in flat and tid in flat`); назначение на `task_id` шапки уже skip (`eid not in flat`); `max_used` не раздувается id шапки.

Идемпотентность: фикстура 080926 (шапка `id=0`) и CSV без шапки дают то же дерево, что сейчас.

### П.2 — `tests/test_mpp_convert.py` · регресс шапки

Нового файла фикстуры **нет**. Хелпер в этом же тестовом модуле (не в `scripts/`):

1. `read_csv_rows(tasks_csv)` (импорт из `mpp_convert`).
2. Взять строку `id=="1"` как донор дат/имени; собрать служебную: `id="217"`, `outline_level="0"`, `summary="True"`, `predecessors="[1]"`, остальные поля с донора (как в diagnose).
3. Прогон через `convert_mpp_csv` (чтобы закрыть `dependenciesData`): записать временный tasks CSV в `tmp_path` через `csv.DictWriter` с `fieldnames` исходного файла; `resources_csv` / `assignments_csv` / `gantt_test_template` — штатные фикстуры.

**Тест A (обязательный)** — шапка **первая**: `[header_217] + original_rows`.

Assert:

- `eventsData[0]["id"] == 1`
- имя корня содержит «Доработки АБ-платформы»
- `count_tasks(root) == 33`
- `217 not in flatten_events(root)`
- ни у одного элемента `dependenciesData` нет `from==217` или `to==217`
- `len(flatten_events(root)) == 33`

**Тест B (обязательный в том же файле)** — шапка **не первая**: вставить header_217 сразу после строки `id=="1"`. Тот же корень id=1; `root["children"]` не пустой; `count_tasks==33`; 217 нет в дереве/deps. Это путь «No records to display» (перезапись `root`).

**Тест C (тот же файл, узкий)** — `_parse_outline_level`: `""` / `None` / `"0"` / `"0.0"` / `"abc"` → 0; `"1"` / `"1.0"` / `"2"` → 1 / 1 / 2.

**Тест D (тот же файл)** — только шапка 217, без узлов `outline_level>=1` → `pytest.raises(ValueError)` на `build_event_tree` или `convert_mpp_csv`. Шапку как корень не подставлять.

Существующие `test_convert_task_count` / `test_tree_structure` / `test_fs_dependencies_only` / `test_id_counter_not_300000` / `test_naim_resource_added` **не слабеть**.

### П.3 — `scripts/itogo.py` · HTML без Трудозатрат + вырез из storage

#### 3.1 `build_itogo_html`

Возвращать **только**:

```python
f"<p><strong>Итого: с {d1} по {d2} - {format_thousands(n_days)} рабочих дней</strong></p>"
```

Параметр `m_hours` **оставить** с тем же именем (не `_m_hours`). В HTML не подставлять. Не добавлять `_ = m_hours`, если в файле нет такого паттерна; unused arg допустим.

#### 3.2 Хелпер выреза (имя зафиксировать)

```python
def strip_trudozatraty(storage: str) -> str:
    """Удалить абзац/текст «Трудозатраты: …» целиком. Идемпотентно."""
```

База — нынешний `ITOGO_LINE2_RE`. Расширить до block-regex (можно заменить константу одним выражением или оставить ядро + обёртка):

- `IGNORECASE`
- число: `\d[\d\s\xa0]*` (пробел тысячи и NBSP)
- хвост: `человеко?-часов?` / явно `человек-часа` | `человек-часов` | `человеко-часов`
- если вокруг есть `<p>…</p>` (опционально `<strong>`) — съесть **весь** абзац, не оставлять `<p></p>`
- без `<p>` / без `<strong>` — съесть сам текст «Трудозатраты: …человек-час…»
- минимальный контракт: канон `<p><strong>Трудозатраты: N человек-часа</strong></p>`

Не создавать line2 ни в одной ветке.

#### 3.3 `patch_itogo`

1. `storage = strip_trudozatraty(storage)`
2. Если `ITOGO_LINE1_RE.search(storage)` — `sub` даты/N (`count=1`), **не** трогать хвост 70%. `m_hours` / `m_fmt` в подстановку не использовать.
3. Иначе — `return build_itogo_html(...) + storage` (storage уже без line2).
4. Условие «line1 **и** line2» **убрать**.

Сигнатуру `(storage, d1, d2, n_days, m_hours)` не менять.

#### 3.4 `apply_itogo`

- есть line1 → `return patch_itogo(...)` (он вырезает line2);
- нет line1 → `storage = strip_trudozatraty(storage)`, затем однострочный HTML над макросом (`insert_itogo_above_macro`) или в начало.

Итог: старая Трудозатраты не остаётся ни при патче, ни при вставке. `insert_itogo_above_macro` не менять.

### П.4 — `tests/test_itogo.py`

| Тест | Было | Стало |
|---|---|---|
| `test_itogo_from_csv_080926` | d1/d2/n/m | **не менять** (M в кортеже остаётся) |
| `test_format_thousands` | 1 960 / 2 356 | **не менять** |
| `test_build_itogo_html` | ждёт «Трудозатраты: 2 356…» | оставить строку «Итого: с 28.09.26 по 18.05.27 - 154 рабочих дней»; `assert "Трудозатраты" not in html`; `assert "70%" not in html`; **убрать** ожидание line2 |
| `test_patch_existing_itogo` | `"2 356" in out` | новые даты и `154`; `"Трудозатраты" not in out`; нет старых трудозатрат `100` как line2 (допустимо: `"человек-часа" not in out`); `"2 356" not in out`; хвост «Загрузка 70%» на месте |
| `test_insert_itogo_above_macro_no_block` | `"2 356" in out` | позиция «Итого:» над макросом; `count("Итого:") == 1`; `"154" in out`; `"Трудозатраты" not in out`; **не** требовать `"2 356"` |

**Новые тесты (тот же файл):**

1. `test_apply_itogo_strips_line2_updates_line1` — storage line1+line2 (как в `test_patch_existing_itogo`) → `apply_itogo` → line1 обновлена (28.09.26 / 18.05.27 / 154), `"Трудозатраты" not in out`, хвост 70% на месте, `count("Итого:") == 1`.
2. `test_apply_itogo_line2_only_inserts_line1` — storage **только** `<p><strong>Трудозатраты: 100 человек-часа</strong></p>` + макрос (`build_macro_html`) → `apply_itogo(..., macro_start=…)` → `"Итого:"` над макросом, `count("Итого:") == 1`, `"Трудозатраты" not in out`.
3. `test_strip_trudozatraty_variants` (узкий): канон `<p><strong>…человек-часа</strong></p>` → пусто; вариант `человеко-часов`; NBSP в числе (`2\xa0356`); без `<strong>`; повторный вызов идемпотентен. После выреза нет пустого `<p></p>` для канон-обёртки.

`test_patch_existing_itogo` с **только** line1 (без line2) можно добавить одной строкой в тот же файл: патч обновляет даты, не препендит второй «Итого:», не добавляет Трудозатраты. Рекомендуется — закрывает бывший дубликат.

---

## 5. Документы — не `HF:impl` (чеклист `HF:docs-handoff`)

Исполнитель impl эти файлы **не** трогает. Следующая фаза после `HF:test`:

| Файл | Правка |
|---|---|
| `SKILL.md` frontmatter `version` | бамп **0.2.1 → 0.2.2** (согласовать с ТЗ) |
| `SKILL.md` шаг 4 прогона | «две строки над макросом» → одна строка дат/N; Трудозатраты не создавать / вырезать; 70% не создавать |
| `SKILL.md` питфолл «M «Итого»» | M считается внутри / в тексте гейта; в storage блока «Итого» нет |
| `references/mpp-to-gantt.md` eventsData | корень = первый узел `outline_level>=1`; шапку `outline_level≤0` (в т.ч. с настоящим id) отбрасывать вместе с пустым id и id=0 |

Манифест / restore — `ORCH:shared-state`, если воркер той фазы решит, что бамп скилла требует sync. `manifest_hints` на docs: `tools.edit_plan_confluence` version 0.2.2 при наличии поля; не выдумывать новую сущность.

---

## 6. Таблица IAC

Синтаксис Блок 1А `hermes-feature`. Исполнитель на `HF:test` гоняет `verify` молча. Класс S, нет `depends: operator:`.

| IAC-## | phase_from→phase_to | path | verify | depends | covers AC-### |
|---|---|---|---|---|---|
| **IAC-01** | HF:impl→HF:test | `scripts/mpp_convert.py` (`build_event_tree` + `_parse_outline_level`); `tests/test_mpp_convert.py` | из каталога скилла: `python3 -m pytest tests/test_mpp_convert.py -q` → passed; среди них тесты шапки id=217 (первая и не первая) | — | **AC-001** (корень id=1, 33 задачи, нет 217 в дереве/deps; фикстура 080926 без регресса) |
| **IAC-02** | HF:impl→HF:test | `scripts/itogo.py`; `tests/test_itogo.py` | `python3 -m pytest tests/test_itogo.py -q` → passed | — | **AC-002** (HTML без Трудозатрат, строка дат/N 154); **AC-003** (патч/apply вырезает line2; только line2 → вставка line1) |
| **IAC-03** | HF:test | весь оффлайн-набор скилла | `python3 -m pytest -m "not live" -q` → passed (0 failed; live deselected) | IAC-01, IAC-02 | **AC-004** |
| **IAC-04** | HF:impl→HF:test | diff пакета | `git diff --name-only` (и untracked) относительно входа impl: только `scripts/mpp_convert.py`, `scripts/itogo.py`, `tests/test_mpp_convert.py`, `tests/test_itogo.py`. Нет `read_mpp.py`, `USERTOOLS/ConfluenceSync`, `scripts/gate_diff.py`, `519492935` | IAC-01, IAC-02 | **AC-005** |

Live / `EDITPLAN_LIVE=1` **не** в IAC. `conflictPolicy=override` на страницу не вводится (не этот diff).

Промежуточная точка после П.1+П.2: IAC-01. После П.3+П.4: IAC-02. Перед complete `HF:test`: IAC-03 + IAC-04.

---

## 7. Риски / edge (исполнителю)

| Риск | Что делать |
|---|---|
| Не все MPP дают шапку level=0 | фильтр идемпотентен; 080926 (`id=0`) зелёный |
| Шапка с ненулевым id | тест A |
| Шапка не первая → пустой гант | тест B обязателен |
| Нет узлов level≥1 | тест D: существующий `ValueError` |
| `outline_level` пустой / `"0.0"` / `"1.0"` / мусор | `_parse_outline_level` + тест C; тот же парс для `lvl` |
| Несколько узлов level=1 | не этот баг; не расширять скоуп |
| `predecessors="[1]"` у шапки | после фильтра нет 217 в `flat` → ребра нет (тест A/B) |
| Назначение на task_id шапки | `eid not in flat`; сумма work `compute_itogo_*` не меняется |
| Трудозатраты без `<strong>` / «человеко-часов» / NBSP | `strip_trudozatraty` + тест вариантов; минимум — канон с `<p><strong>` |
| Только line1 | обновить, не добавлять line2, не дублировать «Итого:» |
| Только line2 | вырезать, вставить line1 над макросом |
| Хвост 70% | не трогать (`test_patch_existing_itogo`) |
| `m_hours` unused | оставить аргумент |
| `format_itogo_pair` станет однострочным | ожидаемо; `gate_diff.py` не править |
| 4 файла > LIGHT | факт; граф не укорачивать с impl |

---

## 8. Откат

`HF:backup` до impl (хвост графа). Откат пакета = revert четырёх файлов. Runtime Confluence не пишется этим пакетом.

---

## 9. Класс кейса (факт, не skip)

| Критерий LIGHT | Факт |
|---|---|
| ≤3 файла кода+тесты | **Нет: 4** — `mpp_convert.py`, `itogo.py`, `test_mpp_convert.py`, `test_itogo.py` |
| Вне shared / без сущностей / cron / .env / манифеста | Да |
| Нет USERTOOLS | Да |

Полный BUGFIX: `REV:plan` + `GATE:plan-approve` + `HF:backup` + `HF:impl` + `HF:test` + `HF:docs-handoff` + `ORCH:shared-state` + `GATE:done`. Сжать до 3 файлов, выкинув тест одного бага, нельзя: 080926 не ловит I1; I2 ломает текущие assert `test_itogo.py`.

---

## Прогресс выполнения

- [ ] П.1 `mpp_convert.py` — `_parse_outline_level` + фильтр `rows` + `lvl`
- [ ] П.2 тесты шапки 217 (A первая, B не первая, C парс, D ValueError)
- [ ] П.3 `itogo.py` — однострочный HTML + `strip_trudozatraty` + patch/apply
- [ ] П.4 `test_itogo.py` — старые assert + apply line1+line2 + только line2
- [ ] IAC-01 pytest `test_mpp_convert.py`
- [ ] IAC-02 pytest `test_itogo.py`
- [ ] IAC-03 pytest `-m "not live"`
- [ ] IAC-04 границы diff
- [ ] HF:docs-handoff (не impl): SKILL.md 0.2.2 + mpp-to-gantt.md

---

## AC пакета (напоминание исполнителю / GATE:done)

Класс S. Источник — master-ТЗ v0.2.2.

- **AC-001** — корень дерева не шапка (`id==1`, 33, нет 217).
- **AC-002** — одна строка «Итого» в HTML, нет «Трудозатраты».
- **AC-003** — патч/apply вырезает Трудозатраты; хвост 70% жив; только line2 → вставка line1.
- **AC-004** — оффлайн pytest `-m "not live"` passed.
- **AC-005** — diff без `read_mpp.py`, ConfluenceSync, `gate_diff.py`, живой AB.
