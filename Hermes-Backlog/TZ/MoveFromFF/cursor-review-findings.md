---
type: tz-review-findings
tool: MoveFromFF
target-section: "Планируемая доработка: вывод самари из apps_preview custom-скилла (2026-07-03)"
reviewer: Cursor (Opus 4.8)
date: 2026-07-03
verdict: needs-fixes
source-code-checked: "USERTOOLS/MoveFromFF/movefromff/{config,ff_schema,ff_client,renderer}.py, templates/summary.md.j2, tests/*"
---

# Ревью ТЗ MoveFromFF (apps_preview custom skill) — замечания и предложения

## Вердикт

**❌ Не готово к реализации as-is.** 2 блокера (реализация «по букве ТЗ» сломает прод и существующие тесты) + 3 уточнения. Идея (custom-skill → summary с fallback) корректна; fallback-ветка совпадает с кодом.

---

## Расхождения ТЗ ↔ реальный код

### D1 — [БЛОКЕР] §4.3 ломает `extended_sections` в GraphQL

- ТЗ §4.3: `extended_sections { title items text }`.
- Реальный код `ff_client.py::_MEETING_FIELDS_FULL`: `extended_sections { title content }`.
- `ff_schema.py` документирует: реальная схема FF `SummarySection` = `title/content`; `items/text` в текущем API **не приходят**.
- Последствия: GraphQL-ошибка `Cannot query field "items" on type "SummarySection"` → ломается весь fetch summary (custom + fallback). Падает существующий тест `test_query_full_includes_notes_and_extended_sections` (проверяет `content`) — противоречит критериям §6.3 и §6.8.
- **Фикс ТЗ:** в §4.3 оставить `extended_sections { title content }`, добавлять ТОЛЬКО блок `apps_preview`.

### D2 — [БЛОКЕР] §4.1 конфиг противоречит архитектуре `config.py`

- ТЗ §4.1: модульная константа `FF_CUSTOM_SKILL_TITLE = os.getenv(...).strip()`.
- Реальный `config.py`: pydantic `Settings` + ленивый `_ensure_env_loaded()` (`load_dotenv` только в `load_settings()`). Модульная константа выполнится при импорте ДО загрузки `.env` → значение из `.env` игнорируется, всегда дефолт.
- **Фикс ТЗ:** добавить `custom_skill_title: str = ""` в `Settings`, читать из env в `load_settings()`; renderer получает через settings/аргумент.

### D3 — [средний] §4.4 renderer читает глобал, тест §7.2 его не замокает

- §4.4: `from movefromff.config import FF_CUSTOM_SKILL_TITLE` (связывание при импорте) → monkeypatch в тесте §7.2 не подействует. ТЗ само оговаривает это в примечании — внутреннее противоречие.
- **Фикс ТЗ:** `render_summary(meeting, skill_title=...)` или чтение `settings.custom_skill_title` в теле функции.

### D4 — [средний] §7.4 фикстуры не в стиле репозитория

- §7.4 предлагает `tests/fixtures/*.json`, но каталога нет и ни один тест не грузит JSON с диска. Все тесты строят данные инлайн (dict/pydantic) + `MockSession`.
- **Фикс ТЗ:** собирать `apps_preview` инлайн, без файлов-фикстур.

### D5 — [низкий] референсы §2/§6 устарели / не подтверждены

- Локальный экспойз (`test_ff_apps_preview_results.json`, май) показывает title'ы `"1:1"`, `"Meeting Summary Generator"`, а не `"tkachenkoav ff summary prompt 01072026"`. Свежих (июльских) доказательств для id `01KWKPM0J86H0227T0PGHBF8WE` в репо нет.
- **Действие:** до кода — 1 живой запрос свежей встречи, подтвердить точный `title` и `app_id=6a44d3b8...`.

---

## Что корректно (не трогать)

- `apps_preview { outputs { app_id title response created_at } }` — snake_case подтверждён рабочим экспойзом.
- Fallback-ветка `render_summary` §4.4 текстуально совпадает с прод-кодом.
- `extra="ignore"` + `Optional` в `FFAppOutput`/`FFAppsPreview` — в стиле существующих моделей.
- §6.6 (3 сценария десериализации) согласуется с тестами `test_fetch_meeting_tolerates_*`.

---

## Открытые вопросы владельцу (нужно решение до реализации)

1. **Несколько outputs с одинаковым нужным title** — брать первый непустой по порядку (рекоменд.) или max по `created_at`?
2. **Идентификация скилла: `app_id` vs `title`.** `title` нестабилен (переименование), `app_id=6a44d3b8...` стабилен. Рекомендация: искать по `app_id` с fallback на `title`.
3. **`FF_CUSTOM_SKILL_TITLE`: `Settings` vs модульная константа** (см. D2). Рекомендация: `Settings`.
4. **`created_at`** — оставить `Optional[Any]` (сырьё), пока нет сортировки по дате из п.1.

---

## Промпт для LLM-реализатора (после решений владельца по §14/открытым вопросам)

> Скопировать в новую сессию Cursor в контексте проекта `MoveFromFF`. **Не запускать без явной команды владельца «берём в работу».**

```
Ты — исполнитель доработки инструмента MoveFromFF (Python, Fireflies → Obsidian).

ОБЯЗАТЕЛЬНО перед стартом:
1. Прочитай правила: WorkVault/Hermes-Backlog/TZ/_TZ-WORKFLOW-RULES.md.
2. Прочитай ТЗ: WorkVault/Hermes-Backlog/TZ/MoveFromFF/MoveFromFF_TZ.md,
   секцию "Планируемая доработка: вывод самари из apps_preview custom-скилла (2026-07-03)".
3. Прочитай ревью: WorkVault/Hermes-Backlog/TZ/MoveFromFF/cursor-review-findings.md
   — учти исправления D1–D5, они ОБЯЗАТЕЛЬНЫ и имеют приоритет над дословным текстом ТЗ.
4. Прочитай реальный код: movefromff/{config,ff_schema,ff_client,renderer}.py,
   templates/summary.md.j2, tests/test_{ff_schema,renderer,ff_client}.py.

ЗАДАЧА: реализовать вывод результата Custom AI Skill из apps_preview.outputs как
основного контента summary.md, со стандартным шаблоном как fallback.

КРИТИЧЕСКИЕ ОГРАНИЧЕНИЯ (из ревью):
- D1: в _MEETING_FIELDS_FULL НЕ трогай summary/extended_sections. Оставь
  `extended_sections { title content }` как в проде. ДОБАВЬ только блок:
      apps_preview { outputs { app_id title response created_at } }
  Проверь, что существующий тест test_query_full_includes_notes_and_extended_sections
  остаётся зелёным.
- D2: НЕ вводи модульную константу в config.py. Добавь поле custom_skill_title
  в pydantic-класс Settings, читай из env FF_CUSTOM_SKILL_TITLE в load_settings()
  (дефолт "" = фича off). Следуй существующему паттерну Settings/_ensure_env_loaded.
- D3: render_summary должен получать skill_title как аргумент (или из settings-объекта),
  НЕ через top-level import константы — иначе тесты не смогут переопределить значение.
- D4: тесты — инлайн (dict/pydantic + MockSession), как в существующем tests/.
  НЕ создавай tests/fixtures/*.json.
- D5: перед smoke сверь актуальный title/app_id скилла живым запросом свежей встречи.

РЕАЛИЗАЦИЯ ПО ФАЙЛАМ:
1. ff_schema.py: модели FFAppOutput, FFAppsPreview, поле apps_preview: Optional в FFMeeting,
   хелпер find_custom_skill_output(meeting, skill_title) (точное совпадение title после strip,
   пустой response = нет результата). Учти решение владельца по выбору при нескольких outputs
   и по app_id-vs-title (см. открытые вопросы §ревью).
2. ff_client.py: добавить apps_preview в _MEETING_FIELDS_FULL (см. D1). _MEETING_FIELDS_LIST не трогать.
3. config.py: Settings.custom_skill_title (см. D2) + .env.example.
4. renderer.py: ветвление в начале render_summary (см. D3) — если найден custom output,
   рендерить новый шаблон, иначе текущий стандартный путь без изменений.
5. templates/summary_custom.md.j2: H1 "# Саммари: {{ title }}" + body (response as-is). summary.md.j2 не трогать.

ТЕСТЫ: покрыть позитив (custom), 4 fallback-ветки (нет output / mismatch title /
пустой response / фича off), десериализацию (None / [] / отсутствие ключа),
строку query. Прогнать pytest tests/ -v — всё зелёное, существующие ожидания не править.

ПОСЛЕ РЕАЛИЗАЦИИ: обновить master-ТЗ до v2.2 (frontmatter version+date, новая
датированная секция), MAIN_TZ_INVENTORY.md, снапшот по правилам archiving.md.
НЕ рестартовать gateway. НЕ трогать Projects/People/Meetings/Contacts.

НЕ начинай, пока владелец не подтвердил решения по 4 открытым вопросам ревью.
```
