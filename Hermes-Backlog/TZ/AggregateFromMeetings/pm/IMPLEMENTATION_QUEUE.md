---
tool: AggregateFromMeetings
type: implementation-queue
created: 2026-06-25
updated: 2026-06-30
status: phase-a-done
blocked_by: "PM: ревью ТЗ (бриф 30.06) → команда «начинай Фазу B». H3-rework — гейт-блокер внутри Фазы B (IQ-B10a)"
---

# Implementation Queue — очередь для агента реализации

> Заполняется PM + LLM брифа. Выполняет **агент реализации** (Cursor + hermes-vm).
> Статус очереди: **Фаза A выполнена 29.06** (ТЗ обновлено по брифу 29.06, PD-026…044). Дальше — **пауза на ревью ТЗ PM**, затем «начинай Фазу B» (код).

## Легенда

| Поле | Значение |
|------|----------|
| `IQ-xxx` | ID шага |
| `blocked_by` | что блокирует (OQ, PM, GATE) |
| `PD/OQ` | ссылки на решения/вопросы |
| `[ ]` | не начато |
| `[~]` | в работе / заблокировано |
| `[x]` | сделано |

---

## Фаза A — ТЗ (до кода)

| | ID | Шаг | blocked_by | PD/OQ | BUILD_CHECKLIST |
|---|-----|-----|------------|-------|-----------------|
| [x] | **IQ-A01** | ~~timeline = Dataview~~ → **статический список** (PD-043) — внесено в TZ_D | done 29.06 | PD-043 | — |
| [x] | **IQ-A02** | TZ_D: decisions хронология + strikethrough; блокеры `[blocker]` | done 29.06 | PD-024, PD-032 | — |
| [~] | **IQ-A03** | action_items → **Tasks-query** (PD-035) внесено; ⚠️ default «+5 раб. дней» (PD-023) в ТЗ НЕ внесён — см. Q-A3 в brief-back | частично | PD-035, PD-023 | — |
| [x] | **IQ-A04** | TZ_G: snapshot = 1 дата = 1 протокол (уже было) | done 29.06 | PD-022 | — |
| [x] | **IQ-A05** | Opus полностью deprecated (не только D) — TZ_C/main | done 29.06 | PD-021, PD-028 | — |
| [~] | **IQ-A06** | golden compare (Sonnet) описан в TZ_C; критерии recall детализировать в Фазе C | частично | PD-020, PD-041 | — |
| [x] | **IQ-A07** | answered OQ закрыты в main §6 + OPEN_QUESTIONS → in_tz | done 29.06 | OQ-* | — |

---

## Фаза B — Код (increment-path)

| | ID | Шаг | blocked_by | PD/OQ | BUILD_CHECKLIST |
|---|-----|-----|------------|-------|-----------------|
| [ ] | **IQ-B01** | ff_parser: надёжный парсинг блоков Решения + Action items | IQ-A02, A03 | PD-024, PD-023 | — |
| [ ] | **IQ-B02** | D: append decisions из summary (increment, не Opus) | IQ-B01 | PD-024 | 9.6 |
| [ ] | **IQ-B03** | D: action_items + AC resolve + default +5 раб. дней | IQ-B01 | PD-023 | 9.6 |
| [ ] | **IQ-B04** | D: timeline = статический список встреч (дата+wikilink), генерация каждый прогон | IQ-A01 | PD-043 | — |
| [ ] | **IQ-B05** | G: snapshot per meeting date | IQ-A04 | PD-022 | 8.x |
| [ ] | **IQ-B06** | Кросс-проектные приоритизации → обычный decision в сущность-источник (E/H/D) | IQ-A02 | PD-045 | — |
| [ ] | **IQ-B07** | Дедуп задач cross-meeting (stable-id) — **в MVP, блокер перед H6** | IQ-B12 | PD-019, Q-A3 | — |
| [ ] | **IQ-B08** | Прогон E (People) в sandbox | IQ-B02 | — | 9.7 |
| [ ] | **IQ-B09** | Прогон H (Syncs) в sandbox | IQ-B02 | — | 9.8 |
| [ ] | **IQ-B10** | C: единый Haiku-проход (bootstrap = хронологический реплей, накопленный инкремент как контекст); убрать Opus-агрегацию | IQ-B01 | PD-028, PD-030, PD-036 | 9.x (H3 переоткрыт) |
| [ ] | **IQ-B10a** | **H3-rework (GATE, блокер Фазы B):** прогнать Haiku на выборке H0, собрать сигналы в структуру `_archive/opus-signals-2026-06-22/`, построить таблицу **Сущность / тип (project/1on1/multisync) / сигналы Opus / сигналы Haiku** с подсветкой смысловых расхождений → `pm/sessions/h3-rework-comparison.md` → вердикт PM | IQ-B10 | Q-A2, PD-028 | H3-rework |
| [ ] | **IQ-B11** | D: `risks.md` — авто-риски Haiku из Bullet/Notes (`src=inferred`, confidence), дедуп `(text,risk,slug)` | IQ-B10 | PD-031, PD-034, PD-038, PD-039 | — |
| [ ] | **IQ-B12** | Tasks-query интеграция: задачи в срезах G (теги), `action_items.md`/`commitments.md` = query; закрытие чекбокса правит срез; **stable-id для дедупа (Q-A3)** | IQ-B05 | PD-033, PD-035, PD-019 | — |
| [ ] | **IQ-B13** | D: блокеры в `decisions.md` (`[blocker]` формат, дедуп по `type=blocker`) | IQ-B10 | PD-032 | — |
| [x] | **IQ-B14** | ~~scope=portfolio~~ упразднён (PD-045) — кросс-проектное = decision в сущность-источник; см. IQ-B06 | n/a | PD-045 | — |
| [ ] | **IQ-B15** | A/C: Confluence-устав как «встреча №0» (сид decisions/action_items/risks) | IQ-B10 | PD-030 (C4) | — |
| [ ] | **IQ-B16** | A: идемпотентность — FF не пересинкиваются; ручной режим переобработки | — | PD-037 | — |
| [ ] | **IQ-B17** | Инструмент **Exchange Org Lookup** (bk-098): батч-резолв GAL → ContactStore → ретриг; очередь `needs_gal.jsonl` (мини-ТЗ готов, Фаза A.2) | IQ-B01 | PD-026, PD-042, PD-047 | — |
| [ ] | **IQ-B18** | **`pm_notes_reconciler`** (Шаг 1): скан PM Notes за окно 5 дней, хэш по блоку `(snapshot,idx)`, CRUD задач/решений/рисков, ручной `--only-pm-notes`; интеграция в F первым шагом | IQ-B05, IQ-B12 | PD-046, PD-049…052 | 7.x |
| [ ] | **IQ-B19** | F: два шага прогона (Шаг 1 reconciler → Шаг 2 встречи); запуск всегда после MoveFromFF | IQ-B18 | PD-046, PD-050 | 7.11 |

---

## Фаза C — Приёмка

| | ID | Шаг | blocked_by | PD/OQ | BUILD_CHECKLIST |
|---|-----|-----|------------|-------|-----------------|
| [ ] | **IQ-C01** | Golden compare: ml-platforma vs pageId 490169504 | IQ-B02, B03 | PD-020 | 9.9 |
| [ ] | **IQ-C02** | Golden compare: trisigma vs pageId 490170597 | IQ-B02, B03 | PD-020 | 9.9 |
| [ ] | **IQ-C03** | PM ревью 3–5 проектов → GATE H6 | PM | OQ-012 | 9.9 |
| [ ] | **IQ-C04** | Cleanup sandbox, CL.1–CL.3 | H6 | — | CL.* |
| [ ] | **IQ-C05** | Golden compare через **Sonnet**: предложение задач к закрытию → подтверждение PM через PM Notes (авто-закрытие запрещено) | IQ-B10..B12 | PD-041 | 9.9 |
| [ ] | **IQ-C06** | Recall авто-рисков на golden ref ml-platforma | IQ-B11 | PD-039 | 9.9 |

---

## Шаблон нового шага

```markdown
| [ ] | **IQ-XNN** | _описание_ | _blocked_by_ | PD-xxx | _checklist ref_ |
```
