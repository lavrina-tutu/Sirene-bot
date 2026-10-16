---
module: E_1on1
parent: TZ_aggregate_main
version: 1.5
status: закрыт
date: 2026-06-29
updated: 2026-06-30 (Q-C1/C2/C3: единый формат PM Notes tasks/decisions/risks, маппинг секций, short_id; #N снят)
---

# Модуль E. 1‑1 и People

## Назначение
Обработать встречи типа `1on1` — извлечь agreements и commitments, обновить карточки контактов в `People/{login}/`.

## Карточка модуля

🎯 **Функция:** Из встречи типа 1-1 извлечь договорённости и задачи, обновить карточку контакта
⬅️ **Вход:** `MeetingSignals` от C + маршрут от B (`route: "1on1"`) + список участников
➡️ **Выход:** обновлённые артефакты `People/{login}/`
🔗 **Зависимости:** A (данные), B (маршрут + тип встречи), C (сигналы), AnywhereContacts (резолв имён)
📋 **Статус:** ✅ закрыт

## Архитектура артефактов (зеркало модуля D)

| Файл | Аналог в Projects/ | Содержание |
|---|---|---|
| `card.md` | `card.md` | Точка входа карточки контакта — frontmatter + навигация + dataviewjs-секции. |
| `commitments.md` | `action_items.md` | Двусторонние задачи: и мои обязательства, и обязательства контакта. Нумерация `#N` сквозная по контакту. |
| `agreements.md` | `decisions.md` | Долгосрочные договорённости — что решили вместе. Редко меняется. Append-only. |
| `meetings/<дата>.md` | `snapshots/` | Протокол каждой 1-1 встречи — инкремент. |
| `meetings.md` | `meetings.md` | Авто-индекс протоколов 1-1. |
| `snapshots/` | — | Генерируется G.Срез: `{login}-snapshot-YYYY-MM-DD.md` после каждой 1on1. Не редактировать вручную. |

`context.md` — **исключён** (не нужен для People/, контекст контакта живёт в `card.md` frontmatter + AnywhereContacts).

**Механика задач — Tasks-query (PD-035, обновление 29.06):** <!-- изменено 2026-06-29 --> по аналогии с `action_items.md` проектов, `commitments.md` — **query-агрегатор**. Сами commitment-задачи физически живут в 1on1-срезах G (`{login}-snapshot-YYYY-MM-DD.md`) с тегами контакта; `commitments.md` собирает их Tasks-query без дублирования. Закрытие чекбокса в query правит срез-источник. Дедуп между срезами — отдельная задача разработки (не MVP). PM закрывает чекбоксом или через `### PM Notes (tasks)`.

## Архитектура карточки `People/{login}/card.md`

### YAML frontmatter

```yaml
entity: person
login: kkrivorotov
fio: "Криворотов Кирилл"
display_name: "Кирилл"
department: "Продукт"
team: "AID"
position: "Tech Lead"
projects: ["antibot", "adm"]
syncs: ["sync-aid"]
last_meeting: 2026-06-12
meetings_count: 14
last_processed_at: 2026-06-19
```

### Секции тела (порядок)

1. **☑️ Открытые commitments** — dataviewjs (аналог `Projects/<slug>/card.md`), сборка из `People/{login}/commitments.md` по статусу `open`.
2. **🔗 Связанные проекты** — dataviewjs `WHERE contains(people, this.login)` по `Projects/*/card.md`.
3. **🗂 Связанные синки** — dataviewjs `WHERE contains(core_members, this.login)` по `Syncs/*/card.md`.
4. **Навигация** в конце карточки:
   `☑️ [[People/{login}/commitments]] · 🤝 [[People/{login}/agreements]] · 📅 [[People/{login}/meetings]]`

Секция «🧭 Контекст» — **исключена** (контекст контакта — в AnywhereContacts).

### PM Notes

После каждой секции — блок `### PM Notes (tasks|decisions|risks)` (единый формат для всех доменов, Q-C2/PD-056, см. TZ_G §5). Маппинг 1-1: commitments → `tasks`, agreements → `decisions`. **Сквозного PM Notes блока нет.** LLM читает прошлые PM Notes секций как контекст при следующей генерации.

### Резолв участников

Источник истины — **AnywhereContacts (AC)** через E.Люди. AC — **единственный writable store** алиасов контактов (C4). Нормализация алиасов через `ContactStore.add_alias(login, alias, source="aggregate_from")` (атомарный append под файл-локом, case-insensitive дедуп) + полный каскад `ContactStore.resolve_name()` (email → fio → alias → token_subset → fuzzy, threshold 0.85). Источники сигнала об участии: S2 (speaker labels из FF transcript) ∪ S3 (owners action items из FF). Поле `**Участники:**` в FF — ненадёжно, не используем как единственный источник.

**Ключ контакта — `login` из AC (латиница).** Везде используется `People/{login}/` (латиница). Кириллический путь `People/<Имя Фамилия>/` из research v0.1 / project-entity v0.1 — **устарел** (M2), оставлен только для исторических артефактов до миграции.

#### Контекстный резолв через AC.reports_to (M9, добавлено 2026-06-21)

Для разрешения коллизий имён в 1-1 (где у нескольких людей одинаковое first name — типичный кейс «Саша», «Александр») E использует поле `reports_to` из AC + `hierarchy_hint` от B (см. TZ_B §«Разрешение неоднозначных имён»).

**Источник данных об оргструктуре:**
- Единый источник истины — файл `~/WorkVault/Contacts/tutu-contacts.md` (таблица с полями `login`, `ФИО`, `aliases`, `reports_to` и др.)
- При старте AggregateFromMeetings пайплайн читает оргструктуру из tutu-contacts.md
- Поле `reports_to` определяет иерархию: kkrivorotov.reports_to = tkachenkoav, tkachenkoav.reports_to = aralov, и т.д.
- Если резолв неверный — правим в tutu-contacts.md (это единый источник истины, ВОП-3)

**Синхронизация с AC:**
- AnywhereContacts импортирует поле `reports_to` из tutu-contacts.md при синке
- Это обеспечивает `hierarchy_hint` для B.Роутера

**Приоритет в каскаде резолва имени-в-названии для route=1on1:**

0. **Hierarchy lookup (новое, перед token_subset):**
   - Пусть `hint = hierarchy_hint = {owner, manager, direct_reports}`.
   - Пусть `candidates_by_name = {c ∈ contacts | first_token(c.fio) ≈ name OR name in c.aliases}`.
   - Пересечение: `H = candidates_by_name ∩ ({hint.manager} ∪ hint.direct_reports)`.
   - Если `|H| == 1` → `resolved`, `match_type=hierarchy`, `confidence=high`. Tentative-маркер НЕ ставится.
   - Если `|H| == 0` — fallback на token_subset/fuzzy (как раньше).
   - Если `|H| >= 2` — `ambiguous`, в `unclear_names` с кандидатами из H (приоритетнее общих кандидатов).
1. Далее — стандартный каскад из v1.2 (token_subset → fuzzy).

**Конкретные кейсы для tkachenkoav (OWNER):**

| Название встречи | Участники | Резолв контрагента | Обоснование |
|---|---|---|---|
| «1-1 Кирилл» | tkachenkoav, kkrivorotov | `kkrivorotov` | единственный direct_report по имени Кирилл |
| «1-1 Саша» | tkachenkoav, aralov | `aralov` | `aralov` ∈ {manager}; `azhirov` — не direct_report tkachenkoav |
| «1-1 Илья» | tkachenkoav, isereda | `isereda` | алиас «Илья» + isereda.reports_to=aralov (peer); fallback на fio-token |
| «1-1 Саша Ж.» | tkachenkoav, azhirov | `azhirov` | алиас «Саша Ж.» однозначен — hierarchy не нужен |
| «Олег 1-1» (дата ≤ 2026-05) | tkachenkoav, opopkov | `opopkov` | hardcoded таблица B (бриф 21.06 В2); после мая 2026 opopkov ушёл из АИД, для новых встреч — каскад |
| «1-1 Даяна/Саша» | tkachenkoav, dnabiev | `dnabiev` | алиас «Даяна» однозначен (только один контакт с этим first name); «Саша» в этом контексте = OWNER (tkachenkoav) |
| «PR Ткаченко» / «1-1 Ткаченко» / «Zoom Meeting Ткаченко» | tkachenkoav, aralov | `aralov` | перформанс-ревью с руководителем (бриф 21.06 В4) |
| «Саша Саша 1-1» | tkachenkoav, aralov | `aralov` | бриф 21.06 В4 |
| «Юлия 1-1» | tkachenkoav, yalekseeva | `yalekseeva` | алиас «Юля/Юлия»; уточнение по контексту BI/Metabase (бриф 21.06 В9-доп) |
| «Катя 1-1» | tkachenkoav, eperetjatkova | `eperetjatkova` | алиас «Катя/Екатерина П.» |
| «Ольга 1-1» | tkachenkoav, okotelnikova | `okotelnikova` | алиас «Ольга/Котельникова» |

⚠️ Замечания по линейным руководителям АИД (бриф 21.06 В9-доп):
- `yalekseeva` (Алексеева Юлия), `eperetjatkova` (Перетяткова Екатерина), `okotelnikova` (Котельникова Ольга), `dnabiev` (Набиева Даяна) — все `reports_to: aralov`, peer-уровень с `tkachenkoav`, `isereda`, `azhirov`.
- `dnabiev` дополнительно ответственна за BI/Metabase — контекст «Metabase» в названии встречи усиливает кандидата `dnabiev`.

#### Правило-проверка для 1-1 с peer-сотрудниками (isereda/tkachenkoav и др.)

Если 1-1 происходит между двумя peer-логинами (один уровень иерархии — например isereda + dnabiev), то для разрешения «Саша» в названии используется правило: **«Саша» в peer-1-1 = `aralov`** (общий руководитель). Реализуется через проверку `c1.reports_to == c2.reports_to` в `hierarchy_hint` (см. TZ_B).

⚠️ Если `hierarchy_hint` отсутствует (B не передал) — E падает на старое поведение (token_subset/fuzzy). Hint обязателен только для route=1on1.

**Маркер в meeting note (m3, дополнено):**
- `<!-- ac: resolved as <login> via hierarchy -->` — когда срабатывает hierarchy lookup.

#### Tentative-резолв (M8)

При обработке встречи E делает резолв каждого упомянутого имени через `resolve_name()`:

| `ResolveResult.status` | `confidence` | Действие E |
|---|---|---|
| `resolved` | `high` | Пишет в `People/{login}/`, метка в meeting note: `<!-- ac: resolved as <login> via <match_type> -->` (m3, единый формат). |
| `resolved` | `medium` (token_subset / fuzzy) | **Tentative**: пишет в `People/{login}/`, метка `<!-- ac: tentative resolve as <login> via <match_type> -->`. Запись об имени уходит в очередь `state/unclear_names.jsonl` на подтверждение PM. |
| `ambiguous` / `not_found` | — | НЕ создаёт папку. Имя уходит в `state/unclear_names.jsonl`. Сигнал откладывается до подтверждения PM. |

#### Очередь `state/unclear_names.jsonl`

Append-only JSON Lines. Запись на каждое неподтверждённое имя:

```json
{
  "meeting_id": "2026-06-19 Sync.md",
  "name_raw": "KI",
  "resolve_result": "ambiguous|not_found|tentative",
  "suggested_login": "kkrivorotov",
  "match_type": "token_subset|fuzzy|null",
  "candidates": [["kkrivorotov", 0.86], ["kiselev.ivan", 0.81]],
  "timestamp": "2026-06-19T18:00:00"
}
```

Дальнейшая обработка — в F.Дирижёре: батчинг в дайджест → подтверждение PM → `ContactStore.add_alias()` → ретриг встреч → снятие tentative-маркера (см. TZ_F_orchestration, M8).

#### Exchange GAL fallback (PD-026/042) — батч

<!-- изменено 2026-06-29: PD-026/042 -->

Расширение каскада резолва для случаев, когда контакт не найден в ContactStore (`not_found` после `fuzzy`):

**Каскад (обновлён):** `email → fio → alias → token_subset → fuzzy → needs_gal`.

1. Если после `fuzzy` контакт не разрезолвен — имя кладётся в очередь `state/needs_gal.jsonl` (статус `needs_gal`), а не сразу в `unclear_names`. **Inline-обращения к Exchange нет** — основной цикл не блокируется сетевыми вызовами.
2. **Отдельный инструмент «Exchange Org Lookup» (bk-098)** проходит очередь **батчем**: по ФИО/фрагменту запрашивает Exchange GAL → возвращает `email` / `login` / `manager`.
3. Найденный контакт записывается в **ContactStore** (`ContactStore.add_alias()` / создание контакта), после чего основной цикл **ретригит** соответствующие встречи и забирает контакт штатно из ContactStore.
4. Если GAL ничего не вернул — имя уходит в `state/unclear_names.jsonl` на подтверждение PM (как раньше).

> Exchange Org Lookup оформляется **отдельным мини-ТЗ** (bk-098): вход — ФИО/фрагмент, выход — `email`/`login`/`manager`; режим — батч; писатель — ContactStore. Интерфейс и расписание батча — в мини-ТЗ. ContactStore остаётся единственным writable store алиасов контактов (C4); Exchange GAL — источник данных, не хранилище.

### Интеграция с AC: запись участия в проектах (M10, добавлено 2026-06-21)

Помимо алиасов, E пишет в AC **участие контактов в проектах** — поле `project_roles` (см. `schema.py`, входит в `CUSTOM_FIELDS`, коннекторы Exchange/Zulip его не перезаписывают).

**Правило для route=1on1:**
- Если 1-1 встреча отнесена B.Роутером к project slug `X` (поле `route_project_slug` читается из `MeetingPackage.route_project_slug` — заполняет B.Роутер, см. TZ_A §B2; ставится когда заголовок содержит проектный контекст, напр. «1-1 Кирилл / antibot»), то после успешного резолва обоих участников E вызывает:
  ```python
  store.add_project_role(login=owner_login,        slug=X, source="aggregate_from")
  store.add_project_role(login=counterpart_login,  slug=X, source="aggregate_from")
  ```
- Если у встречи нет привязки к проекту (`route_project_slug is None`) — `project_roles` не трогаем.
- `add_project_role` атомарен и идемпотентен: повторный вызов с тем же `(login, slug)` при наличии активной записи (`until is None`) ничего не добавляет и возвращает `False`. Роль не угадываем (роль = `None`); PM при необходимости проставит вручную.
- Закрытие участия (`close_project_role`) E **не делает** автоматически — это явное действие PM (через TG-команду в F.Дирижёр, фаза 2) или ручное.

**Где это используется на стороне Obsidian:**
- Поле `projects: [...]` в `People/{login}/card.md` frontmatter генерируется из `project_roles` (только активные записи, `until is None`) при следующей перегенерации карточки.

## Открытые вопросы
### Решённые
- ~~**В1 — Алгоритм определения 1-1**~~ ✅ **Закрыто 2026-06-19 (C1):** Маршрут `1on1` определяется B.Роутером (единая точка истины — `TZ_B_classification.md`, раздел «Алгоритм классификации»). E.Люди обрабатывает встречи с `route=1on1`. Дублирующий алгоритм в E удалён.
- ~~**В3 — Granularity карточек**~~ ✅ **Закрыто 2026-06-18:** Только прямые участники встречи. Упомянутые в тексте третьи лица — не создаём. В 1-1 фиксируются только договорённости между двумя участниками.
- ~~**В4 — Хранение ссылок на встречи**~~ ✅ **Закрыто 2026-06-18:** Список встреч с человеком хранится в `meetings/<дата>.md` (протоколы) + в `card.md` контакта поле `meetings_count` и `last_meeting`. Ссылки на summary доступны через `meetings/` подпапку.

## ВОП-8: Автоматическое создание People-карточек и cleanup (решение брифа 22.06)

### Автоматическое создание

Пайплайн **автоматически создаёт минимальные карточки** `People/<login>/index.md` при первом появлении человека:

```python
def ensure_people_card(login: str, vault_root: Path) -> Path:
    """Создаёт карточку если не существует. Возвращает путь."""
    card_path = vault_root / "People" / login / "index.md"
    if not card_path.exists():
        card_path.parent.mkdir(parents=True, exist_ok=True)
        card_path.write_text(f"""---
entity: person
login: {login}
fio: ""
created_at: {datetime.now().isoformat()}
auto_created: true
---

# {login}

_Карточка создана автоматически. Заполнить ФИО и другие поля._
""")
    return card_path
```

Метка `auto_created: true` позволяет найти автосозданные карточки.

### Механизм очистки (cleanup_people.py)

Скрипт `scripts/cleanup_people.py` для ручной очистки карточек с малым числом встреч:

```bash
# Показать автосозданные карточки с < 2 встречами
python scripts/cleanup_people.py --show-candidates

# Пример вывода:
# 📋 Карточки для ревью (auto_created=true, meetings_count < 2):
# - People/guest123/ — 1 встреча, последняя: 2026-01-15
# - People/unknown_bob/ — 0 встреч
# 
# Удалить: python scripts/cleanup_people.py --delete <login>
```

Функции скрипта:
- `--show-candidates` — показать кандидатов на удаление
- `--threshold N` — порог числа встреч (по умолчанию 2)
- `--delete <login>` — удалить конкретную карточку (в корзину/архив, не физически)
- `--archive <login>` — пометить как archived в frontmatter

### Остающиеся открытыми
1. ~~**В2 — Формат записи в commitments.md**~~ ✅ **Закрыто 2026-06-19** — Вариант В: двусторонние секции.
   Структура `commitments.md`:
   ```markdown
   ### Мои обязательства
   - [ ] [текст] ^abc11
   
   ### Обязательства [Имя]
   - [ ] [текст] ^abc12
   ```
   <!-- изменено 2026-06-30: формат #N снят -->
   ID сущностей — `^{login3}{hex}` (block reference, PD-057, см. TZ_G §5). Выполнение = чекбокс `[x]`; правка/перенос/удаление — через `### PM Notes (tasks)` (`_UPDATE`/`_DELETE`); невыполненные остаются открытыми в Tasks-query (перенос не требует команды).
2. **В5 — Слияние при смене ФИО / алиаса** (Кирилл → Кирилл Иванов) — миграция файлов? **Фаза 2.**
3. ~~⚠️ **[от модуля A, В5] pm_locked**~~ ✅ **Закрыто 2026-06-19** — pm_locked не нужен в People/ (всё append-only, перезаписей нет). Вместо этого: в каждый блок (`commitments.md`, `agreements.md`, `meetings/<дата>.md`) добавляется секция PM Notes — те же правила что в Projects/ (блоки `### PM Notes (...)`). LLM читает прошлые PM Notes как контекст при следующей генерации.
4. ⚠️ **[от модуля C, В4] Алиасы контактов** — куда записываем? В AnywhereContacts или в `People/<имя>/card.md`?
   - **В4а — API добавления алиасов в AC:** ✅ **Закрыто 2026-06-19** — Вариант А: новый метод `add_alias(login, alias, source="aggregate_from") -> bool` в `ContactStore` (атомарный append под файл-локом, дедупликация case-insensitive). E.Люди использует прямой Python-импорт. CLI — отдельная задача, не блокер.
   - **В4б — Механизм подтверждения PM + ручное управление:** ✅ **Закрыто 2026-06-19** — Вариант А: батч через F.Дирижёр (дайджест) + TG-команды ручного управления по аналогии с B.Роутер: `алиас [текст] → [login]`, `удали алиас [текст] из [login]`, `алиасы [login]`. Soft-delete (не физическое удаление). Симметрия с алиасами проектов в B.Роутер.
   - **В4в — Порядок резолва имён:** ✅ **Закрыто 2026-06-19** — Вариант В: полный каскад `email → fio → alias → token_subset → fuzzy` (threshold 0.85). Реализуется как `resolve_name()` в AC. При ошибке резолва PM корректирует вручную через `### PM Notes (...)` в срезе.

## Дополнительный контекст (из research)
- Два потока: `Projects/<slug>/` + `People/{login}/commitments.md` (research v0.1, В5).
- Источник истины по людям — AnywhereContacts; алиасы автоматически (research v0.1, В4).
- ⚠️ Папка `People/<Имя Фамилия>/` (кириллица) из project-entity v0.1, Блок 4 — **устарела (M2)**. Канонический путь — `People/{login}/` (латиница).
- Двусторонние линки: `commitments.md` содержит `[[Entities/<slug>/card]]`, `card.md → team` содержит `[[People/{login}]]` (project-entity v0.1, Q7).

## Назад
- ↑ [[../TZ_aggregate_main]]
