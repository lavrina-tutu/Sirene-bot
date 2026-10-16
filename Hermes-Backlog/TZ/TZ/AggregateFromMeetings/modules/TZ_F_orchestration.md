---
module: F_orchestration
parent: TZ_aggregate_main
version: 1.5
status: закрыт
date: 2026-06-30
updated: 2026-06-30 (Q-C: единый формат PM Notes, инлайн-#N снят, маппинг доменов)
---

# Модуль F. Оркестрация пайплайна («Дирижёр»)

## Карточка модуля

🎯 **Функция:** Оркестрация всего пайплайна — запуск, **Шаг 1: реконсиляция PM Notes** (`pm_notes_reconciler`), контроль состояния, fan_out сигналов от C по scope в D/E/H, обработка ошибок, ретраи, логирование, дайджесты.
⬅️ **Вход:** триггер (cron каждые 2ч) + `Meetings/NewMeetings/` (новые файлы) + изменённые PM Notes в срезах + `MeetingSignals` от C
➡️ **Выход:** обновлённые артефакты во всех модулях + TG-дайджест PM + логи + state.json
🔗 **Зависимости:** все модули A–H, MoveFromFF (триггер), AC (ContactStore для подтверждённых алиасов)
📋 **Статус:** ✅ закрыт

## Два шага каждого прогона (PD-046/050, бриф 30.06)

<!-- изменено 2026-06-30: PM Notes reconciler -->

`AggregateFromMeetings` запускается **всегда** после MoveFromFF (и по крону), **даже если новых встреч нет**. Каждый прогон строго по порядку:

```
Шаг 1 — Реконсиляция PM Notes (pm_notes_reconciler):
  скан срезов с изменёнными блоками PM Notes за окно N=5 календарных дней
  (от старого к новому) → актуализация соответствующих разделов карточек.

Шаг 2 — Обработка новых встреч:
  обычный конвейер A → B → C → fan_out → {D|E|H} → G по новым срезам
  из текущего MoveFromFF.
```

Порядок Шаг 1 → Шаг 2 гарантирует: PM Note раннего среза «вшита» в карточку **до** обработки более поздней встречи (снимает структурный конфликт, PD-049).

### `pm_notes_reconciler` — отдельный модуль (PD-050)

**Назначение:** применить изменения блоков PM Notes из срезов к карточкам сущностей.

**Вызов:**
- F вызывает первым шагом каждого прогона (перед обработкой новых встреч).
- Ручной режим: `pm_notes_reconciler --only-pm-notes <slug | snapshot_path>` — **без ограничения окна** (для правок старше 5 дней).

**Окно:** `N = 5 календарных дней` — параметр конфига. Срезы старше окна штатно не сканируются (только ручным запуском).

**Алгоритм:**
```python
def reconcile_pm_notes(window_days=5, only=None):
    snapshots = select_snapshots(window_days, only)      # от старого к новому
    for snap in sorted(snapshots, key=lambda s: s.date):
        for idx, block in enumerate(extract_pm_blocks(snap)):  # ### PM Notes (tasks|decisions|risks)
            key = (snap.path, idx)
            h = sha256(block.text)
            if state.pm_notes_hashes.get(key) == h:
                continue                                  # no-op: не менялось
            section = block.section                       # раздел карточки (Решения/Задачи/Риски)
            apply_pm_note(entity=snap.entity, section=section, note=block.text)  # Haiku, CRUD
            state.pm_notes_hashes[key] = h                # применили ровно один раз
```

- **Гранулярность (PD-051):** хэш считается **по каждому блоку** `### PM Notes (tasks|decisions|risks)`, ключ `(snapshot_path, block_index)`, хранится в `state.json.pm_notes_hashes`. Изменился один блок → обрабатывается только соответствующий раздел карточки (один блок → один раздел → одна транзакция). Правка соседних секций среза агента не триггерит.
- **Идемпотентность:** каждая версия блока применяется ровно один раз (сравнение хэша). Если хэш не менялся — no-op без LLM-вызовов; за окно работа агента может быть нулевой.
- **Старшинство (PD-049):** обработка хронологическая; более свежий срез перекрывает раннюю PM Note по стандартным правилам резолва конфликтов D. Конфликт-пометок нет — PM переопределяет в PM Notes нового среза.
- **Полномочия (PD-052):** PM Note может **создавать / изменять / удалять** задачи, решения, риски (CRUD); тип «комментарий» — без структурного эффекта. Непонятное Haiku не применяет молча → дайджест PM.

## Граф вызовов пайплайна (C2 — решение ВП2)

C — единственный источник сигналов. F раздаёт их по `scope`. H ↔ D напрямую не связаны.

```
ВСЕГДА в начале прогона:
Шаг 1 → pm_notes_reconciler (окно 5 дней) → актуализация карточек по PM Notes

Затем Шаг 2 по новым встречам:
route=project   → A → B → C → F.fan_out → D                  → G(project-snapshot)
route=1on1      → A → B → C → F.fan_out → D(per project,
                                          source_sync=null) + E → G(1on1-snapshot)
route=multisync → A → B → C → F.fan_out → D(per project,
                                          source_sync=<slug>) + H → G(sync-snapshot)
route=unclear   → A → B → F.unclear_queue (C НЕ вызывается)
                  → PM-разметка через TG → re-trigger: A → B → C → F.fan_out → … → G
```

### Алгоритм F.fan_out

```python
def fan_out(meeting_signals: MeetingSignals, route: str, sync_slug: Optional[str]):
    for signal in meeting_signals.signals:
        if signal.scope == "project":
            D.apply(signal)         # source_sync уже заполнен C-обёрткой
        elif signal.scope == "person":
            E.apply(signal)
        elif signal.scope == "sync":
            assert route == "multisync"
            H.apply(signal)
```

⚠️ **Связки H→D нет.** Per-project сигнал со встречи синка приходит от C с `scope=project` + `source_sync=<sync_slug>` (заполняет код-обёртка C, не LLM, не H).

### Триггер G по route (M7 / ВП4)

| route | G-шаблон | project-snapshot для затронутых проектов? |
|---|---|---|
| `project` | project-snapshot | — |
| `1on1` | 1on1-snapshot | — |
| `multisync` | **только sync-snapshot** | ❌ НЕ генерируется (ВП4 = Вариант А). PM видит затронутые проекты через D.База + секцию «Затронутые проекты» в sync-snapshot. |
| `unclear` | G не вызывается | — |

## Решения брифа

- **В3 — Механизм завершения и состояния:** ✅ **Закрыто 2026-06-18, обновлено 2026-06-19 (M4 — добавлен модуль H).**
  Каждый модуль пишет статус в `state.json`:
  ```json
  {
    "pipeline_run": "2026-06-19T22:00:00",
    "modules": {
      "A": {"status": "done", "timestamp": "...", "count": 5},
      "B": {"status": "done", "timestamp": "..."},
      "C": {"status": "running", "timestamp": "..."},
      "D": {"status": "pending"},
      "E": {"status": "pending"},
      "H": {"status": "pending"},
      "G": {"status": "pending"}
    },
    "unclear_queue": [
      {"file": "2026-06-19 Sync.md", "title": "…", "date": "2026-06-19",
       "participants": [...], "candidates": {"project_slugs": [...], "sync_slug": null},
       "added_at": "2026-06-19T22:01:00"}
    ]
  }
  ```
  F опрашивает `state.json` после каждого шага. Падение → логирует, останавливает, пишет в TG.
  📌 **Фаза 2:** параллельный запуск D и E; перезапуск с точки падения.
  📌 **Фаза 3:** state.json → внешняя БД для распределённого запуска.

- **В4 — Обнаружение новых встреч:** ✅ **Закрыто 2026-06-18** — Вариант А.
  F запускается по крону каждые 2 часа. Сверяет файлы в `Meetings/NewMeetings/` с записями в `state.json` — файлы без записи = необработанные → запускает инкремент.
  `state.json` расширяется полем `processed_meetings: {filename: {status, timestamp, source, route, modules: {A,B,C,D,E,F,G,H}}}`.

- **В5 — Логирование, ретраи, уведомления:** ✅ **Закрыто 2026-06-18, обновлено 2026-06-19 (M4 — H в enum логов и дайджестах).**
  - **В5а — Формат логов:** JSON Lines (А). Haiku — главный читатель.
  - **В5б — Backoff:** 0 → 15 → 60 мин (А).
  - **В5в — Диагностика:** Haiku (А). Fallback: невалидный JSON → `escalate_pm`.
  - **В5г — Уведомления:** три сигнала — немедленно при критичных ошибках + вечерний дайджест 20:00 + еженедельный пн 09:00.

- **В6 — Связь F и G «Срез»:** ✅ **Закрыто 2026-06-18, обновлено 2026-06-19 (M7 / ВП4).** F вызывает G после fan_out в рамках одного прогона. Для `multisync` G генерирует **только sync-snapshot** (project-snapshot для затронутых проектов НЕ запускается). Для `unclear` G не вызывается.

## Обработка unclear (M5 / ВП3)

```
route=unclear → F кладёт в state.json.unclear_queue запись:
   { file, title, date, participants, candidates (project_slugs + sync_slug от B),
     added_at }
   → запись попадает в еженедельный дайджест PM (пн 09:00, см. ниже)
```

C НЕ вызывается. D/E/H/G не получают никаких сигналов с этой встречи до разметки.

### § LLM-fallback (R10) — пост-B шаг для unclear <!-- изменено 2026-06-22: MAJOR-A fix R10 -->

**После B.determine_route()** для встреч с `route=unclear` — F (run_pipeline / bootstrap.py) вызывает C.pre_classify() как пост-B шаг:

```python
# Алгоритм LLM-fallback в F (оркестратор):
if route.route == "unclear" and pkg.summary_text:
    result = C.pre_classify(
        summary_text=pkg.summary_text[:2000],
        title=pkg.title,
        known_projects=list(classification_memory.projects.keys()),
        context="bootstrap"  # или "increment"
    )
    if result.confidence >= 0.7:
        route.route = result.route
        route.project_slugs = [result.project_slug] if result.project_slug else []
        route.source = "llm_fallback"
        # → продолжить пайплайн: C → fan_out → D/E/H → G
    else:
        # оставить unclear + сохранить llm_hint для PM
        unclear_entry.llm_hint = result.reasoning
        # → F.handle_unclear()
```

**Принцип:** B остаётся чистым Python без LLM. LLM-fallback — ответственность оркестратора.

**После PM-разметки** (TG-команда `unclear <file> → <slug>` / `→ 1on1 <login>` / `→ multisync <slug>` / `→ trash`):
- `slug/1on1/multisync` → re-trigger: A → B (route обновляется по PM) → **полный прогон C → F.fan_out → {D | E | H} → G**.
- `trash` → встреча помечается `skip: true` в state.json, из unclear_queue удаляется.

## Обработка `unclear_names` (M8)

E.Люди пишет в `state/unclear_names.jsonl` записи о неразрезолвенных именах (см. TZ_E_1on1 «Очередь»). F.Дирижёр:

1. **Батчинг в дайджест:** в ежедневный/еженедельный дайджест добавляется блок «Новые имена для подтверждения»:
   ```
   👥 Новые имена для подтверждения (3):
   • "KI" из 2026-06-19 Sync.md → кандидаты: kkrivorotov (0.86) / kiselev.ivan (0.81) / новый контакт?
   • "Лена" из 2026-06-18 1-1.md → кандидаты: elena.smirnova (0.92)
   • "Юра" из 2026-06-17 Daily.md → нет кандидатов → создать?
   ```
2. **TG-команды PM:** `alias KI → kkrivorotov` / `создай контакт Юра <login>`.
3. **F вызывает `ContactStore.add_alias(login, alias)`**, помечает запись в `unclear_names.jsonl` как `resolved`.
4. **Ретриг встреч:** все встречи из state, где упомянуто это имя, перепрогоняются (C → fan_out → E → G).
5. **Снятие tentative-маркера:** в `People/<login>/meetings/<дата>.md` маркер `<!-- ac: tentative resolve as … -->` заменяется на `<!-- ac: resolved as <login> via pm_confirmed -->`.

## PM-блоки в артефактах (m7 — единое место с примерами)

Единый формат PM Notes (Q-B/Q-C, PD-053…058). Исторически было два формата; инлайн-`#N` снят и заменён новой моделью (см. §2 ниже).

### 1. Парный блок (секционная заметка)

Назначение: длинная заметка PM к секции карточки/среза/протокола.
Формат:
```markdown
## ✅ Решения

- Решение 1
- Решение 2

### PM Notes (decisions)
_ADD: <текст>            # создать запись
_DELETE: <id>            # удалить ошибочную строку
_UPDATE: <id> → <текст>  # перезаписать на месте
Свободный текст-комментарий (без структурного эффекта) — контекст для следующей агрегации.
```

Где встречается: `Projects/<slug>/card.md` и все ai/-артефакты, `People/{login}/card.md` и его файлы, `Syncs/<slug>/card.md` и его файлы, все snapshots/.

#### Операции PM Notes над карточкой (CRUD, PD-052, бриф 30.06)

<!-- изменено 2026-06-30 -->

Парный блок PM Notes в **срезе G** обрабатывается `pm_notes_reconciler` (Шаг 1) — Haiku интерпретирует свободный текст и применяет к соответствующему разделу карточки. Поддерживаемые операции:

| Объект | Создать | Изменить | Удалить/отменить |
|--------|---------|----------|------------------|
| **Задача** | + (текст, owner, срок) — в т.ч. не найденную роботом в summary | + (owner / срок / суть) | + |
| **Решение** | + (текст) | + (уточнение/исправление) | + (зачёркивание) |
| **Риск** | + (текст) | + | + (закрыть/смягчить) |
| **Комментарий** | + | — | — (свободный текст, без структурного эффекта; только контекст следующего среза) |

Примеры формулировок: «добавить задачу: Кирилл готовит спецификацию к 15.07»; «задача X — сдвинуть срок на 20.07, ответственный Юрий»; «задача X — отменить»; «решение про Y — неактуально»; «добавить риск: вендор задерживает»; «риск Z — снят».

Непонятную формулировку Haiku **не применяет молча** → пишет в дайджест PM.

Детект изменений и гранулярность — см. «`pm_notes_reconciler`» выше (хэш по блоку `(snapshot_path, block_index)`, один блок → один раздел карточки).

### 2. ~~Инлайн-блок (`#N`)~~ — СНЯТ (заменён новой моделью, 2026-06-30)

<!-- изменено 2026-06-30: формат #N снят, см. PD-054/056/057 -->

Старый инлайн-формат `<!-- pm: #N закрыто -->` с нумерацией `#N` **упразднён**. Эквиваленты в новой модели:

| Старое (`#N`) | Новое (PD-054/056/057) |
|---|---|
| `- #42 ... <!-- pm: #42 закрыто -->` | `- [x] ... ^slug3hex` (чекбокс = выполнено) |
| `<!-- pm: #43 не выполнено, переносим -->` | задача остаётся `- [ ]` → автоматически в Tasks-query (перенос без команды) |
| `<!-- pm: #N → @<login> -->` | `_UPDATE: <id> → ... @<login>` в `### PM Notes (tasks)` |
| нумерация `#N` сквозная | ID `^{slug3}{hex}` (block reference) |

Задачи во всех доменах (проект/1-1/синк) обрабатываются единым парсером `pm_notes_reconciler`.

## Что уже зафиксировано

- Два триггера: автоматически после MoveFromFF + ручной запуск (research v0.1, В8).
- Batch-режим: cron + on-demand, без realtime.
- Нотификации: telegram_sender для дайджеста.
- Секреты — через `~/.config/hermes/.env` (research v0.1, Приложение А).

---

## Система логирования

### Формат лог-файла (JSON Lines)

| Поле | Тип | Обязательное | Описание |
|------|-----|--------------|----------|
| `ts` | string | ✅ | ISO timestamp |
| `lvl` | enum | ✅ | `INFO`, `WARN`, `ERROR` |
| `module` | enum | ✅ | `A`, `B`, `C`, `D`, `E`, `F`, `G`, **`H`** (M4) |
| `event` | string | ✅ | Код события |
| `file` | string | — | Имя файла встречи |
| `project` | string | — | Slug проекта |
| `sync_slug` | string | — | Slug синка (для module=H) |
| `details` | string | — | Доп. информация |

### Расположение файлов

```
USERTOOLS/AggregateFromMeetings/
├── logs/
│   ├── pipeline-2026-06-19.log      ← JSON Lines, один файл в день
│   └── errors/
│       └── 2026-06-19T220120-C-llm_timeout.txt
├── state.json
├── state/
│   └── unclear_names.jsonl          ← очередь имён (M8)
└── modules/
```

---

## Система ретраев

(Без изменений — см. предыдущую версию.)

| err_type | Описание | Backoff |
|----------|----------|---------|
| `llm_timeout` | LLM не ответил за 30с | ✅ 0-15-60 |
| `llm_rate_limit` | Превышен лимит | ✅ 0-15-60 |
| `network` | VPN/сеть | ✅ 0-15-60 |
| `api_temp_error` | Временная 5xx | ✅ 0-15-60 |
| `parse_error` | Битый FF summary | → TG PM немедленно |
| `write_error` | Нет доступа к Obsidian | → TG PM немедленно |
| `content_refusal` | LLM отказ | → TG PM немедленно |
| `schema_error` | Невалидный JSON от LLM | → TG PM немедленно |

---

## Уведомления PM

### Немедленные алерты

Триггеры: ошибка с `can_retry=false` после исчерпания попыток, полное падение, Haiku `escalate_pm`.

### Ежедневный дайджест (20:00 МСК)

```
📊 AggregateFrom: дайджест 19.06

✅ Обработано: 5 встреч → 3 проекта + 1 синк (sync-aid) + 2 контакта
⚠️ Unclear: 2 встречи ждут разметки (см. еженедельный дайджест)
👥 Новые имена для подтверждения: 3 (см. блок выше)
🔄 Авторетраи: 1 (llm_timeout → успех)
```

Молчит, если нет новых встреч и ошибок.

### Еженедельный дайджест (пн 09:00 МСК) — включает unclear (m5)

```
📈 AggregateFrom: неделя 13-19.06

Статистика:
• Встреч обработано: 23 (project=12, 1on1=6, multisync=5)
• Проектов затронуто: 8
• Синков: 2 (sync-aid, data-talks)
• Ошибок: 2 (все решены авторетраем)

📋 Unclear на разметку (5):
• 2026-06-15 Random.md → нет алиасов, 3 участника, кандидаты: —
• 2026-06-17 Sync ???.md → нет алиасов, 5 участников
...

👥 Имена ждут подтверждения: 3
```

---

## Открытые вопросы

1. ~~Точная цепочка с MoveFromFF~~ → **Фаза 2**
2. ~~Идемпотентность~~ → ✅ state.json (см. C, M6)
3. ~~Восстановление после падения~~ → ✅ retry_pending
4. ~~Состояние~~ → ✅ `state.json` (см. главное ТЗ §8)
5. ~~TG-дайджест формат~~ → ✅ выше

---

## Назад

- ↑ [[../TZ_aggregate_main]]

### Протокол маркеров PM Notes (PD-056..058)

**Формат блока в срезе:**
```markdown
### PM Notes (tasks)
_ADD: <текст>
_DELETE: <id>
_UPDATE: <id> → <новый текст>
```

**Семантика:**
- `_ADD` → создать запись; для tasks — в `## ✅ Задачи (добавлено PM)` того же среза (PD-053)
- `_DELETE` → физически удалить строку из среза (ошибка распознавания, PD-054); выполнение = `[x]`
- `_UPDATE` → перезаписать текст на месте, без истории в срезе (PD-055)

**ID-формат (PD-057):** `^{slug3}{hex}` — Obsidian block reference:
- slug3 = 3-буквенный код проекта; hex = счётчик без ведущих нулей
- Счётчики в `state.json → last_ids: {slug3: {T: N, D: N, R: N}}`
- Поиск объекта для DELETE/UPDATE: Haiku по смыслу (PD-058)
- Тип сущности: из заголовка `### PM Notes (tasks|decisions|risks)` (PD-056)
