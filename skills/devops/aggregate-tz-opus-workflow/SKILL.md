---
name: aggregate-tz-opus-workflow
description: "Обязательный рабочий процесс Opus при работе с ТЗ AggregateFromMeetings — pre-check целостности перед любыми правками. Не для DEV-пайплайна (tz-workflow/hermes-feature/GLOSSARY §2)."
version: "1.0.1"
triggers:
  - "любая задача по ТЗ AggregateFromMeetings"
  - "правки ТЗ Aggregate"
  - "верификация Aggregate"
  - "обновление плана Aggregate"
tools: [read_file, patch, write_file, terminal]
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [aggregate, tz, opus, verification, workflow]
---

# Opus: рабочий процесс с ТЗ AggregateFromMeetings

## ПРАВИЛА (от PM — неуклонно исполнять)

1. **Opus всегда работает с полным ТЗ** — читает все TZ_A–H + main + plan перед правками.
2. **Cursor всегда получает полный пакет** — TZ_A–H + main + plan + brief + audit + tutu-contacts. Никаких ограничений «это уже проверяли» — запрещено.
3. **Бриф ведётся поштучно** — один вопрос, рекомендация с обоснованием, ждать ответа. Не группировать вопросы. Не использовать clarify() без рекомендаций.
4. **Атомарность** — при изменении концепции в одном файле сразу обновить все связанные файлы в той же задаче.

## ОБЯЗАТЕЛЬНЫЙ PRE-CHECK перед любыми правками

Перед тем как вносить изменения, Opus обязан:

### 1. Прочитать ВСЕ файлы ТЗ
```bash
cat ~/WorkVault/Tools/AggregateFromMeetings/TZ_aggregate_main.md
cat ~/WorkVault/Tools/AggregateFromMeetings/IMPLEMENTATION_PLAN.md
cat ~/WorkVault/Tools/AggregateFromMeetings/modules/TZ_A_sources.md
cat ~/WorkVault/Tools/AggregateFromMeetings/modules/TZ_B_classification.md
cat ~/WorkVault/Tools/AggregateFromMeetings/modules/TZ_C_extractors.md
cat ~/WorkVault/Tools/AggregateFromMeetings/modules/TZ_D_projects.md
cat ~/WorkVault/Tools/AggregateFromMeetings/modules/TZ_E_1on1.md
cat ~/WorkVault/Tools/AggregateFromMeetings/modules/TZ_F_orchestration.md
cat ~/WorkVault/Tools/AggregateFromMeetings/modules/TZ_G_snapshot.md
cat ~/WorkVault/Tools/AggregateFromMeetings/modules/TZ_H_syncs.md
```

### 2. Проверить внутреннюю целостность (до правок)
- Все ли термины используются одинаково во всех модулях?
- Нет ли противоречий между модулями?
- Соответствует ли IMPLEMENTATION_PLAN текущей версии ТЗ?
- Все ли шаги алгоритма B согласованы между TZ_B и планом?

### 3. Только после этого — вносить правки

### 4. Атомарность изменений
Когда концепция меняется в одном файле — **обязательно** обновить ВСЕ файлы где она упоминается в той же задаче. Никаких «поправлю потом».

### 5. После правок — проверить целостность снова
Убедиться что изменения не создали новых противоречий.

### 6. Обновить версию
В TZ_aggregate_main.md история версий + frontmatter `version:`.

## Режим брифа (правило Саши)
Вопросы задавать строго поштучно — один вопрос, рекомендация с обоснованием, ждать ответ. Не задавать несколько вопросов сразу. Не использовать clarify() без рекомендации.

## Правила передачи в Cursor
- Cursor всегда получает ПОЛНЫЙ пакет: TZ_A–H + main + plan + brief + audit + tutu-contacts
- Cursor проверяет ВСЁ целиком, без исключений
- Никаких указаний «это уже проверяли» — запрещено

## Правила брифа с PM (Саша)
- Вопросы ТОЛЬКО поштучно — один вопрос, ждём ответ, следующий
- Каждый вопрос с рекомендацией и обоснованием
- Ответы записывать сразу (в classification_memory, бэклог, ТЗ)
- Не задавать несколько вопросов сразу — это правило неуклонно
- README для Cursor: только история версий + что изменилось. Никаких «не смотри на это», «это APPROVED» — это создаёт лишние циклы верификации

## ⚠️ АНТИПАТТЕРНЫ (то что привело к многократным циклам 22.06)
- **Запрещено** отправлять Cursor частичный пакет с инструкцией «проверяй только X» — Cursor всё равно найдёт проблемы в остальном, и будет ещё один цикл
- **Запрещено** при правке одного файла ТЗ не трогать связанные файлы — это гарантированно создаёт рассинхрон (пример: TZ_B поменяли, план — нет → 2 лишних итерации верификации)
- **Запрещено** «умничать» с оптимизацией процесса верификации — полный пакет, полная проверка, всегда

## Режим брифа с PM
- Вопросы задавать **поштучно** — один вопрос, ждать ответа, следующий
- К каждому вопросу: рекомендация с обоснованием
- Записывать ответы по мере получения, не ждать конца брифа
- Никогда не давать несколько вопросов сразу в режиме брифа

## ИСТОРИЯ ВЕРИФИКАЦИЙ (краткая карта)

| Версия | Статус | Ключевые правки |
|--------|--------|-----------------|
| v1.5.1 | ✅ APPROVED | базовая |
| v1.5.3 | переработка | R1–R9: transcript-парсер, ContactStore, owner-rule |
| v1.5.4 | переработка | MAJOR-1/2: алгоритм шагов B |
| v1.5.5 | переработка | I1–I5: синхронизация плана с TZ_B |
| v1.5.6 | переработка | J1: каскад owner+2+ в TZ_A |
| v1.5.7 | в работе | n1 + Этап 9.0 код |

**Урок повторяющихся циклов:** каждый раз когда правился TZ_B без синхронного обновления IMPLEMENTATION_PLAN — Cursor находил расхождение. Решение: атомарность (правило выше).

## Manual overrides: применение решений брифа в Bootstrap

После брифа unclear-встреч PM-решения можно закрепить в `classification_memory.json` как `manual_overrides` — тогда Bootstrap будет применять их **до** роутера B, без LLM и без перебора алиасов.

### Структура manual_overrides

```json
{
  "manual_overrides": {
    "2026-01-28 15-10-00 Delivery Discovery - summary.md": {
      "route": "project",
      "slug": "ai-transformaciya"
    },
    "2026-05-18 07-30-00 Кирилл 1-1 - actions.md": {
      "route": "1on1",
      "contact": "kkrivorotov"
    },
    "2026-04-04 05-10-00 Fireflies Demo Meeting - summary.md": {
      "route": "skip",
      "reason": "trash"
    },
    "_log_meet.md": {
      "route": "skip",
      "reason": "system"
    }
  }
}
```

**Поддерживаемые маршруты:**
- `"route": "project"` + `"slug": "<slug>"` → Route.PROJECT с указанным проектом
- `"route": "1on1"` + `"contact": "<login>"` → Route.ONE_ON_ONE, contact_slug устанавливается
- `"route": "skip"` + `"reason": "adm|trash|system|manual"` → встреча пропускается (не попадает в unclear)

**Ключ в overrides = точное имя файла** (`mf.filename`, не путь). Это `2025-09-25 08-30-00 Daily Кирилл - summary.md`, не полный путь.

### Интеграция в bootstrap.py

```python
# Загрузка overrides из classification_memory.json
with open(class_path) as f:
    raw = json.load(f)
manual_overrides = raw.get("manual_overrides", {})

# В цикле per-file — ДО b_router.determine_route()
override = manual_overrides.get(mf.filename)
if override:
    ov_route = override.get("route")
    if ov_route == "skip":
        route_counter["skip"] += 1
        skipped_by_override.append({"filename": mf.filename, "reason": override.get("reason")})
        continue
    elif ov_route == "1on1":
        pkg = parse_or_empty(mf)
        pkg.contact_slug = override.get("contact")
        packages_with_routes.append((mf, pkg, Route.ONE_ON_ONE))
        continue
    elif ov_route == "project":
        pkg = parse_or_empty(mf)
        pkg.project_slugs = [override.get("slug")] if override.get("slug") else []
        packages_with_routes.append((mf, pkg, Route.PROJECT))
        continue
# иначе — обычный path через b_router
```

### Когда применять

После каждого раунда брифа:
1. Собрать решения PM → записать в `manual_overrides` в `classification_memory.json`
2. Перезапустить Bootstrap: `AGGREGATE_LLM_FALLBACK=1 python3 scripts/bootstrap.py`
3. Проверить: `[overrides] Загружено N manual overrides из брифа` в логе
4. Сравнить новый unclear с предыдущим

**Результат (22.06.2026):** после добавления 28 overrides Bootstrap разобрал 51 из 74 unclear через R10, итого unclear 29/504 = 5.7% (цель < 15% ✅).

### Питфолл: adm-маршрут не поддерживается напрямую

Bootstrap не имеет `Route.ADM` — административные встречи (Q1/Q2 планирование, SR, OKR) нужно маппить на `"route": "skip", "reason": "adm"`. В пайплайне Фазы 1 они будут обрабатываться отдельно.

### Питфолл: multisync не обрабатывался в manual_overrides (баг 22.06)

Первая реализация override-блока в bootstrap.py обрабатывала только `skip`, `1on1`, `project` — ветка `multisync` отсутствовала. Встречи с `"route": "multisync"` проваливались в обычный path и попадали в unclear.

**Симптом:** override добавлен в JSON, Bootstrap загружает «35 manual overrides», но встреча всё равно в unclear_queue.

**Фикс:** добавить ветку `elif ov_route == "multisync"`:
```python
elif ov_route == "multisync":
    try:
        pkg = a_sources.parse_meeting_file(Path(mf.summary_path))
    except Exception:
        pkg = MeetingPackage(filename=mf.filename, title=mf.filename, date=mf.date)
    pkg.sync_slug = override.get("slug")
    packages_with_routes.append((mf, pkg, Route.MULTISYNC))
    continue
```

**Правило:** при добавлении нового Route в систему — проверить что все три места его знают: models.py, b_router.py, и override-блок в bootstrap.py.

## Bootstrap GATE H5: закрытие unclear (паттерн 22.06)

### Алгоритм закрытия H5
1. Запустить `bootstrap.py` → получить `unclear_queue.md` (N встреч)
2. **Сверить с реестром решений** — сравнить каждую запись в unclear_queue с уже принятыми решениями брифа (Python-скрипт, не вручную). Выделить реально новые.
3. Провести бриф с PM по новым записям (brief-mode skill) — группировать по типу:
   - Группа 1: нет участников (reason: «нет реальных участников»)
   - Группа 2: нет алиаса проекта (reason: «ни один алиас не сматчился»)
   - Группа 3: участник без алиаса (reason: «1 участник без алиаса»)
   - Группа 4: daily/стендап с нестандартным числом участников
4. После брифа: обновить `classification_memory.json` новыми алиасами через Opus-крон
5. Добавить системные файлы (`_log_meet.md`, `_registry_meet.md`) в skip-секцию `unclear_registry.md`
6. Перезапустить Bootstrap и снова сверить через скрипт

### Ловушки GATE H5
- **«Action items» записи** — Bootstrap генерирует записи типа `Action items:` (не «Саммари:»). Парсер, ищущий `— Саммари:`, пропускает их, они появляются как `? | ?`. Это НЕ новые unclear — это уже решённые встречи в другом формате.
- **Число в файле ≠ реальный unclear** — заголовок `unclear_queue.md` (N встреч) включает и уже решённые. Реальный % = записи в секции unclear в `unclear_registry.md` / total_files.
- **Решения брифа не применяются при Bootstrap** — Bootstrap классифицирует заново по `classification_memory.json`, игнорируя `unclear_registry.md`. Gate пройден если алиасы добавлены В classification_memory.

### Правило сверки (Python)
```python
# Сравнить unclear_queue.md с solved_titles
decided = {"Кирилл 1-1", "Илья 1-1", ...}  # все решения брифа
new_entries = [e for e in entries if not any(d.lower() in e['title'].lower() for d in decided)]
# Только new_entries требуют нового брифа
```

## Bootstrap fan_out — архитектурный разрыв (питфолл H4, 2026-06-23)

### Проблема: Opus bootstrap vs инкрементальный пайплайн

Bootstrap Opus-агрегации работает **по проектам** (все 50+ встреч → 1 вызов Opus → `Signal[]` без привязки к встрече/человеку), тогда как `fan_out_signals()` ожидает `MeetingSignals` — объект per-встрече с `scope`, `slug`, `login`, `sync_slug` на каждом сигнале.

**Симптом:** `bootstrap.py --step opus` отработал, `run_opus_aggregate.py` записал `_sandbox/opus_signals/*.json`, но вызвать `fan_out → D/E/H` невозможно — нет mapping-слоя.

**Что отсутствует в коде (шаги 9.6–9.8 IMPLEMENTATION_PLAN):**
- `scripts/bootstrap_fan_out.py` — обёртка, читающая `_sandbox/opus_signals/*.json` и вызывающая `D.append_*` в `_sandbox/vault/`
- mapping `Signal[]` (агрегированные по проекту) → `MeetingSignals` (per-встречи с owner/login) — для E (People) нужен resolve login
- Инициализация пустых card.md перед `append_decision()` / `append_action_item()`

**Решение для bootstrap:** писать signals только в Project-карточки (D), без E/People и без H/Syncs — у Opus-агрегации нет привязки к конкретным людям. E/H будут заполняться только при инкрементальном режиме (реальные новые встречи).

**Правило при постановке задачи:** если Opus-джоб получает задание «запусти полный bootstrap D/E/H» без готового `bootstrap_fan_out.py` — он должен СТОП и запросить разработку скрипта у PM, а не пытаться вызывать `fan_out` напрямую.

**Шаблон bootstrap_fan_out.py (минимум):**
```python
# Читает _sandbox/opus_signals/*.json → пишет в _sandbox/vault/Projects/<slug>/ai/card.md
import json, glob
from pathlib import Path
from aggregate_from.modules.d_database import append_decision, append_action_item

SANDBOX_VAULT = Path("_sandbox/vault")
SIG_DIR = Path("_sandbox/opus_signals")

for sig_file in sorted(SIG_DIR.glob("*.json")):
    data = json.loads(sig_file.read_text())
    slug = data["slug"]
    card_dir = SANDBOX_VAULT / "Projects" / slug / "ai"
    card_dir.mkdir(parents=True, exist_ok=True)
    card_path = card_dir / "card.md"
    if not card_path.exists():
        card_path.write_text(f"# {slug}\n\n## Decisions\n\n## Action Items\n\n## Risks\n")

    for sig in data.get("signals", []):
        t = sig.get("type", "")
        text = sig.get("text", "")
        if t == "decision":
            append_decision(card_path, text, source_sync=None)
        elif t in ("action_item", "action"):
            append_action_item(card_path, text, owner=sig.get("owner","unknown"), due=sig.get("due"))
        elif t in ("risk", "blocker"):
            # записать в раздел рисков напрямую
            with card_path.open("a") as f:
                f.write(f"\n- ⚠️ {text}")
```

## Состав полного пакета для Cursor
```bash
cd ~/WorkVault/Tools/AggregateFromMeetings && zip -j /tmp/AggregateFromMeetings_TZ_vX.X.X.zip \
  TZ_aggregate_main.md IMPLEMENTATION_PLAN.md \
  modules/TZ_A_sources.md modules/TZ_B_classification.md \
  modules/TZ_C_extractors.md modules/TZ_D_projects.md \
  modules/TZ_E_1on1.md modules/TZ_F_orchestration.md \
  modules/TZ_G_snapshot.md modules/TZ_H_syncs.md \
  briefs/brief_round2_results.md briefs/audit_logic_2026-06-22.md \
  ~/WorkVault/Contacts/tutu-contacts.md README.md
```

## Версионирование Cursor-пакетов (правило единой нумерации)

**Проблема:** ТЗ-документы имеют свою версию (v1.5.7), а Cursor-пакеты — свою (v1.3). Это путает.

**Правило (закреплено 2026-06-22):** единая сквозная нумерация пакетов `v{N}`. ТЗ-документы (frontmatter `version:`) синхронизируются с номером пакета при каждой сборке.

```
CURSOR_FINAL_v14.zip         ← имя файла
CURSOR_VERIFICATION_PACKAGE_v14.md ← имя файла
TZ_aggregate_main.md: version: v14  ← frontmatter
TZ_B_classification.md: version: v14
... все модули: version: v14
```

**Процедура сборки пакета v{N}:**
1. Устранить все замечания верификатора (MAJOR обязательно, MINOR желательно)
2. Обновить `version: vN` и `date:` в frontmatter ВСЕХ TZ-файлов
3. Добавить запись в историю версий TZ_aggregate_main.md: `**vN** (дата) — список правок`
4. Собрать CURSOR_VERIFICATION_PACKAGE_vN.md (конкатенация всех 10 файлов + changelog)
5. Собрать CURSOR_FINAL_vN.zip
6. rclone sync в owncloud

**Changelog в пакете:** обязательно включать раздел «Changelog v{N-1} → v{N}» с кратким списком всех изменений.

## R10 LLM-fallback: три последовательных бага (отладочный путь 2026-06-22)

Все три бага давали `resolved: 0` при `enabled: true` — симптомы одинаковые, причины разные.

| # | Симптом | Причина | Фикс |
|---|---------|---------|------|
| 1 | `enabled: false, resolved: 0` | `get_llm_client()` не существует | Заменить на `AnthropicLLM()` |
| 2 | `enabled: true, resolved: 0` | `ANTHROPIC_API_KEY not found in env or ~/.env` | Ключ в `~/.config/hermes/.env`, передавать явно через `env` |
| 3 | `enabled: true, resolved: 0` | Неверное имя модели `"claude-3-haiku"` | Исправить на `"claude-haiku-4-5"` (актуальное имя модели) |
| 4 | `enabled: true, resolved: 0` | `pkg.summary_text` всегда пустой | FF-файлы не содержат секцию `## Summary` — читать `## Notes` + `## Bullet points` |

**Баг 4 — самый неочевидный:** после исправления API и модели Haiku получал пустой текст и не мог классифицировать. Нужно было расширить парсер FF-файлов чтобы он читал `notes` + `bullet_points` как `summary_text`. После этого 65 из 74 unclear получили тексты, Haiku разобрал 47 из них.

**Диагностика R10 (быстрая):**
```python
# Проверить что Haiku реально получает тексты:
from aggregate.models import MeetingPackage
pkgs = load_unclear_packages()
with_text = [p for p in pkgs if p.summary_text]
print(f"{len(with_text)}/{len(pkgs)} пакетов с summary_text")
# Если 0 — проблема в парсере FF-файлов
```

**Итог R10 (22.06):** 74 → 32 unclear (6.3% из 504 файлов). Haiku разобрал 47 встреч самостоятельно.

**Итог брифа R10 (22.06, 32 записи — раунд 2):**
- adm: 9 (Q1/Q2/SR/планирование)
- 1on1/kkrivorotov: 7 (Кирилл 1-1 action items + Daily Кирилл)
- 1on1/isereda: 1 (Илья 1-1)
- ai-transformaciya: 1 (Delivery Discovery)
- trash: 5 (gantt, Fireflies Demo, VPN, туристические встречи)
- unclear: 6 (передано в раунд 3)
- исключить из обработки: 2 (_log_meet.md, _registry_meet.md)

**Итог брифа R10 (22.06, 6 записей — раунд 3, финальный):**
- trash: 2 (Zoom Meeting Ткаченко 08:00, Daily 18.12.25 чужая команда)
- vestnik-aid: 1 (конструктор отчетов.mp4 — инструмент отчётности)
- multisync/sync-aid: 1 (планы Q1 2026 — синк АИД)
- project/parsing: 1 (Untitled ретроспектива 10.02.26 — жд ретроспектива)
- project/cu: 1 (Встреча с ИБ 20.03.26 — ПДН/доступы студентов ЦУ)

**Финальный результат после 3 раундов + R10 Haiku:**
74 unclear → 28 manual_overrides (skip/1on1/project) → Haiku разобрал 39 из 41 → **2/504 = 0.4% unclear** 🏆

**Расположение unclear_queue.md:** `USERTOOLS/AggregateFromMeetings/_sandbox/unclear_queue.md` — в репозитории, НЕ в WorkVault. `unclear_registry.md` (решения PM) — в `WorkVault/Tools/AggregateFromMeetings/unclear_registry.md`.

## Архитектурный принцип «B — чистый Python» (инвариант ТЗ)

**Правило (закреплено R10, 2026-06-22):** `B.determine_route()` — детерминированный Python без LLM-вызовов. Это инвариант, зафиксированный в §0.7 плана и TZ_B §ВП3/M3.

**LLM-fallback (R10) — пост-B шаг в оркестраторе:**
- После `B.determine_route()` → если `route=unclear` и summary доступен → оркестратор (`F.run_pipeline()` / `bootstrap.py`) вызывает `C.pre_classify(summary_text, title, known_projects, context="bootstrap")`
- При `confidence ≥ 0.7` → принять route + `source="llm_fallback"`
- При `confidence < 0.7` → оставить unclear, сохранить `llm_hint` для PM

**Ошибка которую НЕ надо повторять:** первая реализация R10 поместила LLM-вызов внутрь `determine_route` как «Шаг 7» — это нарушило инвариант «B без LLM» и потребовало 2 итерации верификации.

**Confidence маппинг:** `pre_classify` возвращает float. Маппинг для логов: ≥0.8 → high, 0.6–0.79 → medium, <0.6 → low.

**PreClassifyResult** (добавлен в models.py §0.2):
```python
PreClassifyResult(route: str, project_slug: str | None, confidence: float, reasoning: str)
```

## Цикл верификации Cursor (итерационный паттерн)

| Итерация | Действие | Ожидаемый результат |
|----------|----------|---------------------|
| 1 | Отправить пакет в Cursor | Отчёт с CRITICAL/MAJOR/MINOR |
| 2 | Устранить MAJOR, пересобрать | 0 MAJOR, остались MINOR |
| 3 | Устранить MINOR, пересобрать | APPROVED |

**Правило:** не реализовывать код пока есть MAJOR в верификации. MINOR не блокируют старт.

## История верификаций и ключевые инварианты
См. `references/verification-history.md` — история итераций, причины отказов, инварианты ТЗ которые надо проверять при каждой правке.
