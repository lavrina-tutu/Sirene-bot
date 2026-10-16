---
appendix_of: MarkObjectsFromSummary_TZ.md
title: MOFS v1.0.0 — LLM-фолбэк проектов, авто-rematch по хэшу entities.json, реорганизация reindex, TG-уведомление об unmatched
status: draft
version: 1.0.0
author: Opus (архитектор; ТЗ по решениям Саши 22.07.2026)
created: 2026-07-22
last-section-added: 2026-07-22 — первичная фиксация решений Q1–Q7
scope: доработка штатного пайплайна `mofs run --mode=cron`; НЕ трогает backfill-contacts, bootstrap, review, edit
depends_on:
  - MarkObjectsFromSummary v0.9.0 (pipeline.py, llm_fallback.llm_fallback, registry.py)
  - MofsIndex v0.4.0 (reindex_batch hook — уже вызывается из pipeline)
  - EntityRegistry v0.2.0 (entities.json — единственный источник алиасов и slug'ов)
  - Anthropic API (`claude-haiku-4-5` — существующий канал `_call_llm` в llm_fallback.py)
---

# MOFS v1.0.0 — ТЗ на доработку

## 1. Цель

Довести MOFS до устойчивой ежечасной эксплуатации: (а) закрыть слепую зону, когда детерминированный матч по `entities.json` вернул `projects=[]` — прогонять тело summary через Haiku и записывать проект во frontmatter, если LLM уверен; (б) при изменении алиасов `entities.json` автоматически перематчить только затронутые встречи; (в) отделить дорогой полный ребилд индекса от ежечасного крон-такта; (г) присылать в TG отчёт о встречах, где ни детерминизм, ни LLM не нашли проект.

## 2. Scope

**Что подпадает:**

- `pipeline.py` (шаг 4 «LLM-фолбэк»): дополнительный вызов `llm_classify_project` когда `entity_hits_projects == []`.
- `llm_fallback.py`: новая функция `llm_classify_project(...)`.
- `registry.py`: поле `entities_hash` на уровне корня registry; чтение/запись + утилита сравнения.
- Новый модуль `entities_diff.py`: `get_entities_hash`, `diff_entities`, `find_meetings_to_rematch`.
- Новый артефакт `WorkVault/Registries/mofs_unmatched.md` — таблица «есть предположение, но confidence<0.90» + «ничего не найдено».
- `~/.hermes/scripts/mofs_run_cron.sh` — убрать `mofs-index index`, добавить TG-нотификацию по unmatched.
- Новый скрипт `~/.hermes/scripts/mofs_index_rebuild.sh` + новый крон `mofs_index_rebuild` (23:00 ежедневно, no_agent, deliver=local).
- Тесты — на каждый новый модуль/функцию.

**Что НЕ подпадает:**

- `OBJECTS_VERSION` — остаётся `"0.6.0"`, версия объектной схемы не меняется.
- Корзины `tools/rooms/contacts` — логика без изменений (LLM-классификация только для `projects`).
- `mofs backfill-contacts` — не трогаем.
- CLI: новых подкоманд не появляется; изменения только внутри `pipeline.run(...)`.
- Ежечасная частота — оставляем `0 * * * *` (Q4).

## 3. Пофайловый план

### 3.1 `markobjectsfromsummary/llm_fallback.py` — добавить `llm_classify_project`

Сигнатура (новая функция, не заменяет `llm_fallback`):

```python
def llm_classify_project(
    summary_body: str,
    entities: dict[str, dict],       # entities.json["entities"], фильтруем только kind != "tool"
    *,
    model: str = "claude-haiku-4-5",
    max_body_tokens: int = 2000,     # ~ max_body_tokens * 4 символов
    confidence_threshold: float = 0.90,
    logger=None,
) -> tuple[str | None, float]:
    """
    Классифицирует встречу к одному из проектов из entities.json.

    Промпт:
      - Список известных проектов: slug, display_name, aliases.
      - Тело summary (обрезано до max_body_tokens*4 символов).
      - Просьба вернуть строго JSON {"slug": "...|null", "confidence": 0..1}.

    Возвращает:
      - (slug, confidence) если LLM выдал валидный slug из списка И confidence >= threshold;
      - (None, confidence) — LLM выдал предположение, но ниже порога → уходит в unmatched;
      - (None, 0.0) — LLM не ответил / нет ключа / невалидный JSON / slug не из списка.

    Никаких исключений наружу — только graceful fallback.
    Логирует событие 'llm_classify_project' с полями {slug, confidence, model, chars_sent}.
    """
```

Детали:
- Использует существующий `_call_llm(prompt, model)`.
- Множество допустимых `slug` формируется как `{s for s, e in entities.items() if e.get("kind") != "tool"}`.
- Промпт строится помощью `_build_classify_prompt(body_trimmed, projects_list)`.
- Парсер JSON — новый `_parse_classify(raw) -> tuple[str|None, float]`; извлекает первый `{...}` regex'ом, обрабатывает и `null`, и лишний текст.

### 3.2 `markobjectsfromsummary/entities_diff.py` — новый модуль

```python
def get_entities_hash(entities_path: pathlib.Path) -> str:
    """SHA-256 файла entities.json, первые 8 hex-символов (стабильно, детерминированно)."""

def diff_entities(
    old_snapshot: dict[str, dict] | None,
    new_snapshot: dict[str, dict],
) -> set[str]:
    """
    Возвращает set slug'ов, у которых изменился хотя бы один из полей:
      - display_name
      - aliases (как set — порядок не важен)
      - kind
      - parent
    Плюс новые slug'и (появились в new). Удалённые slug'и — тоже включаются
    (по ним могут быть старые матчи, которые надо снять).
    Если old_snapshot is None (первый запуск с этим механизмом) → set() —
    ничего не перематчиваем, просто фиксируем hash.
    """

def find_meetings_to_rematch(
    changed_slugs: set[str],
    registry: dict,
) -> list[str]:
    """
    Возвращает список meeting_id, у которых в реестре
    (projects.matched[].slug ∪ tools.matched[].slug) есть хоть один slug из changed_slugs.
    ВАЖНО: включает и встречи, где changed_slug пока НЕ упомянут, но появился новый alias —
    для них rematch тоже нужен (иначе новые синонимы не поймаем). Реализация:
    если changed_slugs непусто → возвращаем ВСЕ meeting_id из registry (см. §7 «Открытые вопросы»
    — компромисс на v1.0.0; узкий diff оставлен на v1.1.0).
    """
```

Хранение снапшота `entities` для diff'а — рядом с реестром:  
`WorkVault/Registries/_mark_objects_entities_snapshot.json` (полный снимок `entities.json["entities"]` по состоянию на последний прогон). Обновляется атомарно вместе с `entities_hash` в registry.

### 3.3 `markobjectsfromsummary/registry.py` — поле `entities_hash`

- В корне `_mark_objects_registry.json` добавляется ключ `entities_hash: str | null`.
- Функция `load_entities_hash(reg) -> str | None`.
- Функция `set_entities_hash(reg, h: str) -> None`.
- Миграция: если ключа нет — трактуется как `None`, при первом прогоне пишется без rematch'а (см. §3.2).

### 3.4 `markobjectsfromsummary/pipeline.py` — вызов LLM-классификатора и pre-cron rematch

**А. В `run(...)` до итерации по файлам** — блок «Авто-rematch по изменению entities.json»:

```python
# Только для mode=cron (в rematch/backfill вручную — не трогаем)
if mode == "cron":
    entities_path = settings.entities_json_path
    new_hash = get_entities_hash(entities_path)
    old_hash = registry.load_entities_hash(reg)
    if old_hash is None:
        registry.set_entities_hash(reg, new_hash)
        _write_entities_snapshot(entities_path, snapshot_path)  # первичная инициализация
    elif old_hash != new_hash:
        old_snap = _read_entities_snapshot(snapshot_path)
        changed = diff_entities(old_snap, entities)
        if changed:
            to_rematch = find_meetings_to_rematch(changed, reg)
            for mid in to_rematch:
                m = reg["meetings"].get(mid, {})
                m.pop("objects_version", None)  # заставит pipeline пересчитать
            logger.event("mofs_auto_rematch", changed_slugs=sorted(changed), meetings=len(to_rematch))
        registry.set_entities_hash(reg, new_hash)
        _write_entities_snapshot(entities_path, snapshot_path)
```

**Б. В `process_one_meeting(...)` — после шага 4 «LLM-фолбэк», перед шагом 6 «обновить frontmatter»**:

```python
# Шаг 4b — LLM-классификация проекта, если проектов не нашли
llm_classify_low_conf: tuple[str, float] | None = None
project_hits_now = [h for h in entity_hits if h.kind != "tool"]
if do_entities and not project_hits_now:
    slug, conf = llm_classify_project(
        body,                             # исходный markdown (не text_plain) — там больше контекста
        entities,
        model=settings.llm_model,
        confidence_threshold=0.90,
        logger=logger,
    )
    if slug and conf >= 0.90:
        ent = entities[slug]
        entity_hits.append(EntityHit(
            slug=slug, display_name=ent.get("display_name", slug),
            kind=ent.get("kind", "project"),
            tags=ent.get("tags", []) or [],
            is_tool=False,
        ))
        llm_matches.append(LLMMatch(candidate="<classify>", slug=slug, confidence=conf))
        # тот же provenance-путь, что и llm_fallback → provenance="mofs_llm_fallback"
        logger.event("mofs_llm_classify_ok", meeting_id=meeting_id, slug=slug, confidence=conf)
    elif slug and conf < 0.90:
        llm_classify_low_conf = (slug, conf)
        logger.event("mofs_llm_classify_low_conf", meeting_id=meeting_id, slug=slug, confidence=conf)
    else:
        llm_classify_low_conf = None  # ничего не предложил — тоже кандидат в unmatched
        logger.event("mofs_llm_classify_none", meeting_id=meeting_id)
```

**В. Накопление unmatched-встреч в разрезе прогона** — новый список `unmatched_meetings: list[dict]` в `PipelineStats` (или отдельная структура рядом), куда `process_one_meeting` пишет строку, если после всех шагов у встречи `projects=[]`:

```python
{
  "meeting_id": meeting_id,
  "date": fm.get("date"),
  "llm_slug": llm_classify_low_conf[0] if llm_classify_low_conf else None,
  "llm_confidence": llm_classify_low_conf[1] if llm_classify_low_conf else None,
  "body_excerpt": _first_meaningful_sentence(text_plain, 120),
}
```

**Г. В конце `run(...)`** — вызов `unmatched_writer.write_unmatched(unmatched_meetings, settings.unmatched_md_path)` (см. §3.5). JSON-сводка на stdout получает поле `"unmatched_projects": N`.

### 3.5 `markobjectsfromsummary/unmatched_writer.py` — новый модуль

```python
UNMATCHED_MD = "WorkVault/Registries/mofs_unmatched.md"

def write_unmatched(
    entries: list[dict],   # см. поля выше
    path: pathlib.Path,
    *,
    logger=None,
) -> None:
    """
    Полностью перезаписывает mofs_unmatched.md текущим состоянием.
    Формат — три секции с MD-таблицами (projects / contacts / tools);
    v1.0.0 заполняется только projects, две другие остаются пустыми
    заголовками-плейсхолдерами (структура зафиксирована для будущего).

    Идемпотентно: если entries пуст — пишет заголовок и три пустые таблицы.
    """
```

Формат (стабильный, см. решение Саши):

```markdown
# MOFS Unmatched

_Последнее обновление: 2026-07-22 14:00 (mofs run --mode=cron)_

## projects
| Встреча | Дата | LLM предположение | Confidence | Тело (фрагмент) |
|---|---|---|---|---|
| [[2026-04-02 10-00-00 Синк ПМО - summary]] | 2026-04-02 | trisigma | 0.82 | «Фокус на срочные функции…» |

## contacts
| Встреча | Дата | ФИО | Источник |
|---|---|---|---|

## tools
| Встреча | Дата | Упоминание | Предположение |
|---|---|---|---|
```

Правила: строки сортируются по `date` DESC, потом по `meeting_id`; `body_excerpt` экранируется (`|` → `\|`, перевод строки → пробел); wikilink на файл `NewMeetings/…-summary.md` (без пути, только имя без расширения — Obsidian сам разрешит).

### 3.6 `~/.hermes/scripts/mofs_run_cron.sh` — реорганизация

Изменения:

1. Убрать блок `mofs-index index 2>/dev/null || true` (Q3 — инкрементальный ребилд делает `reindex_batch` внутри пайплайна).
2. Расширить парсер JSON-вывода: извлекать не только `processed`, но и `unmatched_projects`.
3. Если `unmatched_projects > 0` — добавить в TG-строку хвост:  
   `⚠️ MOFS: N встреч без проекта → WorkVault/Registries/mofs_unmatched.md`
4. Если `processed == 0` и `unmatched_projects == 0` — по-прежнему молчим (exit 0 без вывода).
5. Если `processed == 0`, но `unmatched_projects > 0` (перематчили старые, но не смогли классифицировать) — сообщение уходит: одна строка про unmatched, без «X новых встреч».

### 3.7 `~/.hermes/scripts/mofs_index_rebuild.sh` — новый скрипт

```bash
#!/bin/bash
# Полный ребилд индекса MofsIndex — раз в сутки в 23:00.
# Молчит при exit=0, при ошибке — печатает stderr (пойдёт в deliver=local → алерт).
set -euo pipefail
VENV="/home/tkachenkoav/USERTOOLS/ProtocolFromSummary/.venv"
source "$VENV/bin/activate"
OUT=$(mofs-index index --rebuild 2>&1)
CODE=$?
if [ $CODE -ne 0 ]; then
    echo "ERROR: mofs-index index --rebuild → code=$CODE"
    echo "$OUT"
    exit $CODE
fi
exit 0
```

*(Проверить, что у `mofs-index index` есть флаг `--rebuild`; если нет — использовать эквивалент, см. §7 «Открытые вопросы».)*

Новый крон в `~/.hermes/cron/mofs_index_rebuild.yaml`:
```yaml
name: mofs_index_rebuild
schedule: "0 23 * * *"
no_agent: true
command: /home/tkachenkoav/.hermes/scripts/mofs_index_rebuild.sh
deliver: local
```

## 4. Тесты

### 4.1 `tests/test_llm_classify_project.py` (новый)

| # | Кейс | Ожидание |
|---|---|---|
| 1 | Валидный JSON `{"slug":"trisigma","confidence":0.95}`, slug в списке | вернёт `("trisigma", 0.95)` |
| 2 | Валидный JSON с conf=0.7 | вернёт `(None, 0.7)` |
| 3 | Валидный JSON, slug НЕ из списка entities | вернёт `(None, conf)` (не пропускаем чужой slug) |
| 4 | `_call_llm` вернул None (нет ключа) | `(None, 0.0)`, событие `llm_ner_error` не критично |
| 5 | Мусорный ответ без JSON | `(None, 0.0)` |
| 6 | Пустой `entities` | `(None, 0.0)`, `_call_llm` даже не вызывается |
| 7 | Тело > 8000 символов | обрезается до `max_body_tokens*4`; проверка через мок `_call_llm` (аргумент содержит обрезанное тело) |
| 8 | `entities` содержит только tools | в prompt список пустой; возврат `(None, 0.0)` |

Мок `_call_llm` — через `monkeypatch.setattr("markobjectsfromsummary.llm_fallback._call_llm", ...)`.

### 4.2 `tests/test_entities_diff.py` (новый)

| # | Кейс | Ожидание |
|---|---|---|
| 1 | `get_entities_hash` детерминистичен: два вызова на неизменном файле → равные строки, len==8 |
| 2 | Изменили один alias у одного slug → `diff_entities` возвращает `{slug}` |
| 3 | Новый slug появился в new → включён в результат |
| 4 | slug удалён из new → включён в результат |
| 5 | `display_name` менялся, aliases те же → включён |
| 6 | `old_snapshot is None` → возвращает `set()` |
| 7 | `find_meetings_to_rematch(non-empty, registry)` — возвращает все meeting_id (v1.0.0 стратегия «на изменение entities — полный rematch»); тест на этом контракте, чтобы v1.1.0 сузила осознанно |

### 4.3 `tests/test_unmatched_writer.py` (новый)

| # | Кейс | Ожидание |
|---|---|---|
| 1 | Пустой список → файл создан, три пустых таблицы с заголовками |
| 2 | Одна запись с llm_slug/conf → строка в секции projects, wikilink корректен |
| 3 | Спец-символы в excerpt (`|`, `\n`) → экранируются |
| 4 | Сортировка: две встречи разных дат → более свежая сверху |
| 5 | Повторный вызов с новым списком — полностью перезаписывает, старых строк нет |

### 4.4 `tests/test_pipeline_llm_classify.py` (новый)

| # | Кейс | Ожидание |
|---|---|---|
| 1 | detmatch нашёл 1 проект → `llm_classify_project` не вызывается (важно: не тратим токены) |
| 2 | detmatch=[], LLM вернул (slug, 0.95) → `projects` в frontmatter содержит этот slug, provenance=`mofs_llm_fallback`, `confidence=0.95` в registry |
| 3 | detmatch=[], LLM вернул (slug, 0.80) → frontmatter пуст, запись в `unmatched_meetings` со slug и conf |
| 4 | detmatch=[], LLM вернул (None, 0.0) → запись в unmatched без slug |
| 5 | Смоук: полный прогон с одним синтетическим summary, `write_unmatched` пишет файл в tmp_path |

### 4.5 `tests/test_pipeline_auto_rematch.py` (новый)

| # | Кейс | Ожидание |
|---|---|---|
| 1 | entities_hash отсутствует в registry → после `run(mode=cron)` hash записан, встречи НЕ перематчиваются |
| 2 | hash совпадает → snapshot не обновляется, встречи skipped как раньше |
| 3 | hash изменился, diff непуст → у всех встреч registry сбрасывается `objects_version`, они прогоняются снова; snapshot и hash обновлены |
| 4 | mode=rematch/backfill → блок авто-rematch НЕ срабатывает (защита от рекурсии) |

### 4.6 Обновить `tests/conftest.py` / фикстуры

Существующие фикстуры `settings` должны получить поля `unmatched_md_path`, `entities_snapshot_path`. Дефолты — в tmp_path.

## 5. Порядок реализации (минимально-инкрементальный)

Каждый шаг заканчивается зелёными тестами и мануальным smoke.

**Шаг 1 — `llm_classify_project` + тесты.**  
Изолированная функция в `llm_fallback.py`. Без интеграции в pipeline. Тесты 4.1 зелёные.  
**Checkpoint 1:** `pytest tests/test_llm_classify_project.py -v` → 8/8; `git commit -m "MOFS v1.0.0 step1: llm_classify_project"`.

**Шаг 2 — `unmatched_writer.py` + тесты.**  
Тоже изолированно, без вызова из pipeline.  
**Checkpoint 2:** `pytest tests/test_unmatched_writer.py -v` → 5/5.

**Шаг 3 — интеграция LLM-классификации в `pipeline.py`.**  
Правки в `process_one_meeting` (шаг 4b) + сбор `unmatched_meetings` + вызов `write_unmatched` в конце `run`. JSON-вывод обогащается полем `unmatched_projects`.  
**Checkpoint 3:** тесты 4.4 (5/5) + все прежние 148 тестов должны остаться зелёными; ручной прогон `mofs run --dry-run` на одной свежей встрече без явного проекта — убедиться, что LLM вызывается и unmatched.md пишется.

**Шаг 4 — `entities_diff.py` + `registry.entities_hash` + тесты.**  
Модуль и утилиты в registry, без интеграции в pipeline. Snapshot-файл читается/пишется атомарно (через `write_atomic` из существующей кодовой базы, если есть; иначе `tempfile → os.replace`).  
**Checkpoint 4:** `pytest tests/test_entities_diff.py -v` → 7/7.

**Шаг 5 — интеграция авто-rematch в `pipeline.run`.**  
Блок до итерации по файлам; только `mode=cron`. Первый прогон — инициализация hash без rematch.  
**Checkpoint 5:** тесты 4.5 (4/4); ручной прогон: (1) первый `mofs run --mode=cron` пишет hash; (2) добавить alias в entities.json (в dev-копию) → следующий `mofs run --mode=cron` перематчивает архив; лог содержит `mofs_auto_rematch`.

**Шаг 6 — `mofs_run_cron.sh` + `mofs_index_rebuild.sh` + новый крон.**  
Убираем `mofs-index index` из ежечасного, парсим `unmatched_projects`, добавляем TG-строку. Пишем новый скрипт ребилда, регистрируем крон `mofs_index_rebuild` (23:00, no_agent, deliver=local).  
**Checkpoint 6:** ручной прогон `bash ~/.hermes/scripts/mofs_run_cron.sh` — если unmatched=0 и processed=0 → тихо; ручной прогон `bash ~/.hermes/scripts/mofs_index_rebuild.sh` → exit 0, тихо; `hermes cron list` показывает `mofs_index_rebuild`.

**Шаг 7 — обновление документации.**  
- Обновить главное ТЗ `MarkObjectsFromSummary_TZ.md`: строка v1.0.0 в разделе «Приложения», bump version в frontmatter главного ТЗ на `1.0.0`, добавить секцию «Доработка v1.0.0 — LLM-классификация + авто-rematch + reindex-split (22.07.2026) — РЕАЛИЗОВАНО» по образцу v0.9.0.
- Обновить `MAIN_TZ_INVENTORY.md`: version `1.0.0`.

**Checkpoint 7 (финальный):**
1. Полный `pytest` в `USERTOOLS/MarkObjectsFromSummary/` → все тесты зелёные (148 + новые).
2. `mofs run --mode=cron` на боевом vault отработал без ошибок; `mofs_unmatched.md` создан.
3. `hermes cron list` показывает два крона: `mofs_run` (ежечасно) и `mofs_index_rebuild` (23:00).
4. `git log --oneline | head -7` — семь коммитов по шагам.

## 6. Что НЕ меняется (защита от расползания scope)

- `OBJECTS_VERSION = "0.6.0"` — не трогать. LLM-классификация не меняет схему объектной части frontmatter, только даёт дополнительный путь к тем же полям.
- Логика корзин `tools/rooms/contacts` — без изменений; `mofs_unmatched.md` в v1.0.0 заполняет только секцию `projects`, две другие остаются заголовками-плейсхолдерами.
- `mofs backfill-contacts` — отдельная подкоманда, не связана.
- CLI: сигнатуры `mofs run/rematch/edit/review/bootstrap/backfill-contacts` не меняются.
- Провайдер и модель — `claude-haiku-4-5` через существующий `_call_llm`. Никаких новых зависимостей, никакого нового rate-limit слоя.

## 7. Открытые вопросы

1. **Узкий diff в `find_meetings_to_rematch`.** V1.0.0 при любом изменении `entities.json` перематчивает ВЕСЬ архив (просто и безопасно). Реалистично, потому что: (а) архив ~575 встреч, при `objects_version` совпавшем каждая встреча — это 1 skipped-строка без чтения файла; (б) реально пересчитываются только те, где текст содержит новый alias. Но при росте архива до тысяч встреч и частых правках entities это станет заметно. **Предложение:** зафиксировать v1.0.0 «полный rematch», а на v1.1.0 сузить до «встречи, в чьём body встречается хотя бы один из changed aliases» через `MofsIndex.search_text` (FTS уже есть). Просьба к Саше: подтвердить, что для v1.0.0 «полный rematch» приемлем — или сразу делать узкий.

2. **`mofs-index index --rebuild` — есть ли флаг.** Не проверял в коде MofsIndex. Если флага нет — либо (а) `mofs-index rebuild` как отдельная команда, либо (б) удалить БД и запустить `index`. Уточнить перед реализацией шага 6.

3. **Тело для промпта: `body` (markdown) или `text_plain`?** ТЗ выше берёт `body` — там больше сигнала (заголовки, bullet-структура). Альтернатива — `text_plain`, короче и дешевле. Разница: ~10–20% токенов; качество классификации, вероятно, выше на markdown. Готов остановиться на `body` — но открыто на решение Саши.

4. **`mofs_unmatched.md` — атомарность записи.** Файл в `WorkVault/Registries/` в vault. Если пишем в момент, когда Obsidian его открыл, — конфликтов не будет (Obsidian перечитает). Но синхронизация с git-vault-репо: файл будет часто меняться → шум в diff'ах. **Предложение:** добавить `mofs_unmatched.md` в `.gitignore` vault-репо (если репо есть); либо оставить как есть — Саша решит.

5. **Локали дат в `mofs_unmatched.md`.** Даты берём из `fm["date"]` (ISO `YYYY-MM-DD`) — консистентно с уже применённым форматом v0.9.0.

## 8. Критерии успеха v1.0.0

1. Все существующие тесты (148) + новые (≥24) — зелёные.
2. За неделю ежечасной эксплуатации: минимум одна встреча получила проект через LLM-классификацию с conf≥0.90 (проверка `grep mofs_llm_classify_ok ~/.hermes/logs/mofs*.log`).
3. `mofs_unmatched.md` актуален: обновляется после каждого крон-прогона.
4. Полный ребилд индекса перестал случаться в ежечасном такте (`grep mofs-index ~/.hermes/logs/cron/mofs_run.*` — пусто).
5. При правке `entities.json` (добавление alias) первый следующий `mofs run --mode=cron` перематчивает архив без ручной команды `mofs rematch`.
6. Если после крон-прогона `unmatched_projects > 0` — в TG-топик пришла строка со ссылкой на файл.

## 9. Ссылки

- Главное ТЗ: `TZ/MarkObjectsFromSummary/MarkObjectsFromSummary_TZ.md`
- Существующее приложение (образец форматирования): `TZ/MarkObjectsFromSummary/appendix_ner_archive_contacts_TZ.md`
- Реестр: `WorkVault/Registries/entities.json`, `~/USERTOOLS/MarkObjectsFromSummary/_mark_objects_registry.json`
- Крон-скрипт: `~/.hermes/scripts/mofs_run_cron.sh`
- Хук индекса: `mofs_index.hooks.reindex_batch`
