---
tool: AggregateFromMeetings
type: open-questions-registry
created: 2026-06-25
updated: 2026-06-29
status: active
---

# Open Questions — AggregateFromMeetings

> Единый реестр открытых вопросов. Ответ → поле **Answer** → статус `answered` → перенос в ТЗ → `in_tz`.
> Источники: TZ §6, бэклог, ревью 25.06.

## Сводка

| Статус | Кол-во |
|--------|-------:|
| `open` | 0 |
| `answered` | 1 |
| `in_tz` | 15 |

> Обновлено 2026-06-29 (Фаза A): все 14 OQ (OQ-001…OQ-014) отвечены в брифе 29.06 и перенесены в ТЗ. Решения зафиксированы в [[pm/PM_DECISIONS_LOG]] (PD-026…PD-044) и отражены в модулях ТЗ. См. также [[pm/sessions/2026-06-29_MASTER-HANDOFF]].

---

## Отвечены и перенесены в ТЗ (`in_tz`) — бриф 29.06

<!-- изменено 2026-06-29: все OQ ниже переведены open → in_tz -->

| ID | Вопрос | Источник | Материалы | Answer |
|----|--------|----------|-----------|--------|
| **OQ-014** | Когда давать команду **«начинай обработку»** — после всех замечаний или поэтапно? | процесс 25.06 | [[pm/sessions/2026-06-25_gate-h6-review]] | Поэтапно: после брифа Cursor дорабатывает ТЗ и задаёт новые вопросы; каждая фаза (A→B→C) запускается отдельной командой PM |
| **OQ-013** | **Синхронизация закрытия задач** между срезом и `action_items.md` — один файл-источник, Tasks plugin, Dataview, или скрипт? | ревью 25.06 | [[Entities/_template/status_snapshot]] | Tasks plugin (Obsidian): задачи в срезах G с тегами, action_items.md = query; закрытие в query правит источник (PD-033) |
| **OQ-012** | **GATE H6** — разрешение писать в боевой WorkVault после ревью? | BUILD_CHECKLIST | [[_review/Projects/]] | H6 после golden compare (IQ-C01+C02) + ручного ревью PM 3–5 проектов (IQ-C03) — полный цикл Фазы C |
| **OQ-011** | **GATE H4** — Opus уже прогнан ($2.49) — считать тестом или новый прогон после смены подхода? | sandbox 22.06 | `USERTOOLS/.../_sandbox/opus_run.log` | GATE H4 закрыть без разметки — сигналы Opus устарели (PD-021), приёмка через golden compare IQ-C01/C02; сигналы перенесены в _archive/opus-signals-2026-06-22 |
| **OQ-010** | **GATE H5b** — когда ревью `classification_memory.json`? | BUILD_CHECKLIST | [[classification_memory.json]] | После IQ-B01 (парсер готов), перед IQ-C01 — в человекочитаемом формате для ручной сверки PM |
| **OQ-009** | **Golden refs** для остальных 13 проектов — нужны Confluence URL? | ревью 25.06 | [[pm/GOLDEN_REFS]] | Добавляем по мере готовности — реализацию не блокирует, IQ-C01/C02 покрывает два эталона |
| **OQ-008** | **pro-pm** — влить в `adm` / оставить / исключить? | ревью | [[_review/Projects/pro-pm/]], [[_review/signals/pro-pm]] | Оставить отдельным slug — агрегировать как самостоятельный проект |
| **OQ-007** | Какая **модель LLM** для сборки decisions + conflict resolution (или только парсинг без LLM)? | ревью | [[modules/TZ_C_extractors]] | Haiku — весь pipeline включая bootstrap; Opus deprecated и убирается полностью |
| **OQ-006** | **Достаточно ли качества FF-summary** для парсинга decisions/action_items? | ревью | golden ref, 3–5 встреч ml-platforma | Считаем достаточным — парсим как есть, gap увидим на golden compare в Фазе C (IQ-C01/C02) |
| **OQ-005** | **Privacy/skip-list** встреч — фильтр на уровне A или B? | TZ §6.5 | [[TZ_aggregate_main#6]] | Фильтр не нужен — все встречи попадают в агрегацию; если нужна корректировка, РП пишет в блоке PM Notes |
| **OQ-004** | **Резолв конфликтов** signal vs прошлый статус — модуль C или D? | TZ §6.4 | [[modules/TZ_D_projects]], [[modules/TZ_C_extractors]] | Модуль D — при сборке decisions хронологически, позднее зачёркивает раннее |
| **OQ-003** | **Идемпотентность:** FF summary пересинхронизировался задним числом — что делать? | TZ §6.3 | [[modules/TZ_A_sources]] | Пропустить — если встреча уже обработана, не перепрогонять |
| **OQ-002** | **bk-095:** Haiku vs Sonnet для шага C — нужен ли тест? | бэклог | [[CURSOR_CONTEXT]] | Bootstrap — Haiku; инкремент в проде (шаг 2) — Sonnet; после выхода в прод PM переключает модель вручную (напоминалка создана) |
| **OQ-001** | **bk-101:** формат и качество action_items Trisigma — отдельная проверка? | бэклог | golden ref trisigma | Достаточно автосравнения в Фазе C (IQ-C02) — ручная сверка до реализации не нужна |

---

## Отвеченные (`answered`) — ждут переноса в ТЗ

| ID | Вопрос | Answer | Дата | TZ ref |
|----|--------|--------|------|--------|
| **OQ-A02** | Граница AggregateFrom vs StatusSnapshot | G = срез на встречу, D = база истории; F триггерит G | 2026-06-18 | TZ §6.2 (частично `in_tz`) |
| **OQ-A01** | Выбор LLM (В3) | Haiku шаг 1, Opus шаг 2 | 2026-06-18 | TZ §6.1 ✅ `in_tz` |

---

## Закрытые в ТЗ (`in_tz`)

| ID | Вопрос | TZ ref |
|----|--------|--------|
| — | Реестр 16 slug, adm, parsing umbrella | TZ §3.2, [[briefs/brief_round2_results]] |

---

## Как ответить

1. Найти строку по ID
2. Заполнить **Answer**
3. Сменить статус на `answered`
4. После правки ТЗ → `in_tz` + TZ ref

## Шаблон нового вопроса

```markdown
| **OQ-NNN** | _вопрос_ | _источник_ | _ссылки_ | |
```
