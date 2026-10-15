# Импл-план §18 PFS (Блок 1А) — единый LLM-конфиг + semantic dedup по исполнителю

**Дата:** 17.08.2026 · **Источник:** `ProtocolFromSummary_TZ.md` v1.9, §18 (строки 2462–2930)
**Статус:** план (read-only обследование), реализация НЕ выполнена, код не менялся.
**Режим:** этот документ — единственный артефакт; `config.py`/`pipeline.py`/`dedup.py` не тронуты.

## 0. Расхождение формулировки задачи vs точного текста ТЗ

В постановке задачи датакласс указан как `LlmConfig(model, base_url, api_key, reasoning_effort,
routing_provider)`. Точный код в §18.1 ТЗ (строки 2567–2573) — **4 поля**:
`LlmConfig(model, base_url, api_key, provider_name)`. `reasoning_effort`
(`DEDUP_LLM_REASONING_EFFORT`) и `routing_provider` (`DEDUP_LLM_ROUTING_PROVIDER`, бывший
`DEDUP_LLM_PROVIDER`) **не входят** в `LlmConfig` — это отдельные env-константы в `config.py`,
семантически не связанные с источником `model.default/model.provider/custom_providers` из
`config.yaml` (см. §18.0: «два разных смысла слова provider»). План ниже следует точному коду
ТЗ §18.1 как источнику истины. Если Саша хотел иначе (объединить всё в один датакласс) —
нужно отдельное решение перед реализацией; в текущем плане — 4-польный `LlmConfig` + 2
отдельные константы, как в тексте ТЗ.

## Часть A — единый LLM-конфиг

### A.1 — `protocolfromsummary/config.py`

**Что меняется:** блок строк 107–114 (текущие `DEDUP_LLM_MODEL`, `DEDUP_LLM_PROVIDER`,
`DEDUP_LLM_REASONING_EFFORT`) заменяется/дополняется.

Текущий код (для справки, `config.py:107-114`):
```python
DEDUP_LLM_MODEL = os.environ.get("DEDUP_LLM_MODEL", "deepseek/deepseek-v4-flash-0731")
DEDUP_LLM_PROVIDER = os.environ.get("DEDUP_LLM_PROVIDER", "default")
DEDUP_LLM_REASONING_EFFORT = os.environ.get("DEDUP_LLM_REASONING_EFFORT", "high")
```

Новый вид (точно по §18.1, строки 2567–2613 ТЗ):

1. Добавить импорты: `from dataclasses import dataclass` (в начало файла, рядом с
   существующими импортами `os`, `Path`), `import json as _json` уже есть (для другого блока) —
   не путать с `yaml`, который импортируется лениво внутри `_load_llm_config` (не на верхнем
   уровне модуля — избегаем жёсткой зависимости на этапе импорта, если `pyyaml` вдруг
   отсутствует; см. A.4 про `pyproject.toml`).
2. Добавить датакласс `LlmConfig(model: str, base_url: str, api_key: str | None,
   provider_name: str)`, `frozen=True` — как в ТЗ.
3. Добавить функцию `_load_llm_config() -> LlmConfig` — **буквально** по коду §18.1
   (строки 2575–2609 ТЗ), без изменений логики:
   - читает `Path.home() / ".hermes" / "config.yaml"` через `yaml.safe_load`;
   - `model.default` → `model`, `model.provider` → `provider_name`;
   - ищет `custom_providers[].name == provider_name` → `base_url`, `api_key`;
   - `try/except Exception` вокруг парсинга — `log.warning` при ошибке, поля остаются `None`;
   - env-override: `DEDUP_LLM_MODEL`, `DEDUP_LLM_BASE_URL` (новая переменная — ранее не
     существовала), `DEDUP_LLM_API_KEY` (новая) — каждая через `os.environ.get(VAR, <из
     config.yaml>)`, т.е. переопределяет только если явно установлена;
   - fallback-дефолты (safety net, если и `config.yaml`, и env пусты):
     `model = "deepseek/deepseek-v4-flash-0731"`,
     `base_url = "https://llm-gateway.tutu.ru/api/openrouter/v1"`, `api_key` — без
     дефолта (секрет, `None` если не найден);
   - `provider_name` fallback — `"tutu"`.
4. Module-level: `LLM_CONFIG = _load_llm_config()` — вызывается один раз при импорте
   `config.py`, как остальные module-level константы файла (`ROUTES` — тот же паттерн,
   строка 89).
5. **Переименование `DEDUP_LLM_PROVIDER` → `DEDUP_LLM_ROUTING_PROVIDER`** (сохраняя дефолт
   `"default"` и смысл — OpenRouter routing hint, Q16.2): переменная модуля
   `DEDUP_LLM_ROUTING_PROVIDER = os.environ.get("DEDUP_LLM_ROUTING_PROVIDER", "default")`.
   `DEDUP_LLM_REASONING_EFFORT` — без изменений, остаётся отдельной константой.
6. **`DEDUP_LLM_MODEL` как module-level константа — решение: удалить.** Модель теперь
   доступна только через `LLM_CONFIG.model` (единая точка), отдельная константа
   `config.DEDUP_LLM_MODEL` создавала бы дублирующий, легко расходящийся источник (это и
   есть баг, который фиксирует §18 — см. находку §18.0 про случайное совпадение дефолтов).
   Имя `DEDUP_LLM_MODEL` **сохраняется только как env-var** (читается внутри
   `_load_llm_config`), не как атрибут модуля `config.py`. Любой код, который импортировал
   `config.DEDUP_LLM_MODEL` напрямую, переключается на `config.LLM_CONFIG.model`
   (единственный такой потребитель — `pipeline.py`, см. A.2).

Итоговый diff-эскиз (`config.py`, после строки 114, вместо текущего блока):

```python
DEDUP_LLM_ROUTING_PROVIDER = os.environ.get("DEDUP_LLM_ROUTING_PROVIDER", "default")
DEDUP_LLM_REASONING_EFFORT = os.environ.get("DEDUP_LLM_REASONING_EFFORT", "high")


@dataclass(frozen=True)
class LlmConfig:
    model: str
    base_url: str
    api_key: str | None
    provider_name: str


def _load_llm_config() -> LlmConfig:
    """Единый источник модели/endpoint/ключа для LLM-вызовов PFS (§18)."""
    cfg_path = Path.home() / ".hermes" / "config.yaml"
    model = provider_name = base_url = api_key = None
    if cfg_path.exists():
        try:
            import yaml
            data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
            model_block = data.get("model") or {}
            model = model_block.get("default")
            provider_name = model_block.get("provider")
            for prov in data.get("custom_providers") or []:
                if prov.get("name") == provider_name:
                    base_url = prov.get("base_url") or None
                    api_key = prov.get("api_key") or None
                    break
        except Exception as exc:  # noqa: BLE001
            log.warning("_load_llm_config: не удалось прочитать config.yaml: %s", exc)

    model = os.environ.get("DEDUP_LLM_MODEL", model) or "deepseek/deepseek-v4-flash-0731"
    base_url = os.environ.get("DEDUP_LLM_BASE_URL", base_url) or "https://llm-gateway.tutu.ru/api/openrouter/v1"
    api_key = os.environ.get("DEDUP_LLM_API_KEY", api_key)

    return LlmConfig(model=model, base_url=base_url, api_key=api_key, provider_name=provider_name or "tutu")


LLM_CONFIG = _load_llm_config()
```

**Нюанс:** `config.py` сейчас не импортирует `logging` (нет `log = logging.getLogger(...)` —
проверено, в файле такого нет). `_load_llm_config` использует `log.warning` — нужно добавить
`import logging` + `log = logging.getLogger("protocolfromsummary.config")` в начало файла
(рядом со строкой 4 `import os`). Это отсутствует в коде §18.1 ТЗ (там сниппет предполагает
`log` уже существующим, как в `dedup.py`/`pipeline.py`) — деталь реализации, добавить.

### A.2 — `protocolfromsummary/pipeline.py`

**Импорт (строки 11–23):** заменить

```python
from .config import (
    ...
    DEDUP_LLM_MODEL,
    DEDUP_LLM_PROVIDER,
    DEDUP_LLM_REASONING_EFFORT,
    ...
)
```

на

```python
from .config import (
    ...
    DEDUP_LLM_REASONING_EFFORT,
    DEDUP_LLM_ROUTING_PROVIDER,
    LLM_CONFIG,
    ...
)
```

(алфавитный порядок как в текущем стиле блока, `MEETINGS_DIR`/`REGISTRY_JSON`/`ROOMS_MD`
после — не трогать).

**Удалить целиком** две функции (строки 104–126 и 129–161):
- `_load_tutu_api_key_from_hermes_config()` (104–126) — роль полностью покрыта
  `config._load_llm_config()`.
- `_load_llm_gateway_api_key()` (129–161) — цепочка
  `LLM_GATEWAY_API_KEY env → config.yaml tutu → ANTHROPIC_API_KEY → 3×.env` заменяется на
  `LLM_CONFIG.api_key` (только `config.yaml` + `DEDUP_LLM_API_KEY` override, без alias-цепочки
  — явное решение ТЗ, §18.1 «Fail-soft», не переносить старую цепочку).

**Переписать `_dedup_llm_fn`** (текущие строки 164–191) на:

```python
def _dedup_llm_fn(prompt: str) -> str:
    """Обёртка над OpenAI-совместимым клиентом для LLM-ступени дедупликации
    (§15/§16/§18). Модель/endpoint/ключ — из LLM_CONFIG (§18, единый источник
    из ~/.hermes/config.yaml + PFS env-override). Fail-soft: любая ошибка → "".
    """
    try:
        if not LLM_CONFIG.api_key:
            log.warning("dedup llm: ключ не найден (config.yaml + env-override) — LLM-ступень пропущена")
            return ""
        import openai  # ленивый импорт: тесты с mock llm_fn не требуют SDK

        client = openai.OpenAI(base_url=LLM_CONFIG.base_url, api_key=LLM_CONFIG.api_key)
        resp = client.chat.completions.create(
            model=LLM_CONFIG.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            extra_body={
                "provider": None if DEDUP_LLM_ROUTING_PROVIDER == "default" else {"order": [DEDUP_LLM_ROUTING_PROVIDER]},
                "reasoning": {"effort": DEDUP_LLM_REASONING_EFFORT},
            },
        )
        return resp.choices[0].message.content or ""
    except Exception as exc:  # noqa: BLE001
        log.warning("dedup llm: ошибка вызова API: %s", exc)
        return ""
```

Строка `_haiku_fn = _dedup_llm_fn` (текущая 194) — не трогать (обратная совместимость §16,
alias не зависит от внутренней реализации функции).

**Важный практический риск:** `LLM_CONFIG` вычисляется **один раз при импорте `config.py`**
(module-level). Существующие тесты `test_pipeline_dedup.py` используют
`monkeypatch.setenv("LLM_GATEWAY_API_KEY", ...)` **после** импорта модуля — с новым
механизмом `monkeypatch.setenv("DEDUP_LLM_API_KEY", ...)` тоже сработает только если
применить `importlib.reload(config)` / `reload(pipeline)`, либо тесты переключаются на
`monkeypatch.setattr("protocolfromsummary.pipeline.LLM_CONFIG", LlmConfig(...))` —
прямая замена объекта конфига, без reload. Это проще и надёжнее (см. B.6 план тестов A.5)
— зафиксировать как способ мокать конфиг в тестах, а не через env+reload.

### A.3 — Проверка `pyyaml`

`pyproject.toml` (`dependencies`, строки 10–16) **не содержит** `pyyaml`, при этом в venv PFS
(`~/USERTOOLS/ProtocolFromSummary/.venv`) `yaml` доступен (проверено: `yaml.__version__ ==
"6.0.3"`) — вероятно транзитивная зависимость другого пакета (уточнить на этапе реализации
командой `pip show pyyaml` в venv, чтобы понять, откуда пришёл, и не сломается ли при
переустановке venv). **Решение для реализации:** добавить `"pyyaml>=6"` явно в
`dependencies` `pyproject.toml`, чтобы не зависеть от случайной транзитивной зависимости
(риск, аналогичный найденному в §18.0 «совпадение временное, не гарантировано механизмом»).

### A.4 — Реальный `~/.hermes/config.yaml` (для сверки на этапе dry-run)

Подтверждено чтением (без вывода `api_key`):
```yaml
model:
  default: deepseek/deepseek-v4-flash-0731
  provider: tutu
custom_providers:
  - name: tutu
    base_url: https://llm-gateway.tutu.ru/api/openrouter/v1
    api_key: <64 симв.>
```
Совпадает с примером в §18.0 ТЗ. `_load_llm_config()` на этих данных должна вернуть
`LlmConfig(model="deepseek/deepseek-v4-flash-0731",
base_url="https://llm-gateway.tutu.ru/api/openrouter/v1", api_key=<64 симв.>,
provider_name="tutu")` — использовать как контрольный кейс в живой проверке (п. 9 ниже).

## Часть B — semantic dedup задач по исполнителю

### B.1 — `protocolfromsummary/dedup.py::PROMPT_TASK_DEDUP`

Заменить константу (текущие строки 40–50) на новую редакцию (буквально по §18.2 п.3 ТЗ,
строки 2755–2769):

```python
PROMPT_TASK_DEDUP = (
    "Ты помощник по дедупликации задач в протоколах встреч.\n"
    "Для каждой новой задачи в списке ниже сравнивай её ТОЛЬКО с опубликованными "
    "задачами из её собственного поля \"candidates\" (это уже отфильтрованный список "
    "задач ТОГО ЖЕ исполнителя — фильтр по исполнителю применён программно, тебе он "
    "не нужен).\n"
    "Определи, есть ли среди candidates семантический дубль — та же суть задачи, "
    "даже если текст сформулирован совершенно иначе (другие слова, другой порядок, "
    "другая степень детализации). Судим по смыслу, НЕ по текстовому сходству.\n\n"
    "Новые задачи с их кандидатами (JSON):\n{new_items_with_candidates}\n\n"
    "Ответь СТРОГО JSON-массивом, без пояснений вне JSON:\n"
    '[{{"new_index": N, "duplicate_of_published_index": M_or_null, "reasoning": "..."}}]\n'
    "N — индекс в новых задачах (0-based). M — индекс из поля candidates этой же "
    "задачи (не сквозной индекс по всем опубликованным!), null если не дубль."
)
```

`PROMPT_SECTION_DEDUP`/`PROMPT_RISK_DEDUP` (строки 52–77) — **не трогать** (§18.2 «Что НЕ
меняется»).

### B.2 — `protocolfromsummary/dedup.py::_llm_check_tasks` — новая логика пула

Текущая сигнатура (строка 357) не меняется: `_llm_check_tasks(self, candidates:
list[tuple[int, tuple]]) -> tuple[list[tuple], list[DuplicateInfo]]`. Меняется **тело**
(строки 360–441).

Заменить построение единого `all_published` (текущие строки 364–378) на построение
**per-candidate** пула. Ключевой алгоритм:

```python
def _llm_check_tasks(
    self, candidates: list[tuple[int, tuple]]
) -> tuple[list[tuple], list[DuplicateInfo]]:
    if not self._llm_fn:
        return [t for _, t in candidates], []

    # Резолвим userkey/raw для каждого кандидата (тот же способ, что в _check_tasks_impl,
    # строки 298-307).
    resolved_new = []  # (new_userkey, assignee_raw) параллельно candidates
    for _, (task, resolved, _deadline) in candidates:
        if isinstance(resolved, list):
            uk = next((r.userkey for r in resolved if r.resolved and r.userkey), None)
            raw = resolved[0].raw if resolved else ""
        else:
            uk = resolved.userkey if (resolved.resolved and resolved.userkey) else None
            raw = resolved.raw
        resolved_new.append((uk, raw))

    # Опубликованные задачи (incomplete) с исходной привязкой к дате строки.
    published_incomplete: list[tuple[PublishedTask, date]] = [
        (pub_task, pub_row.meeting_date)
        for pub_row in self._rows
        for pub_task in pub_row.tasks
        if pub_task.status == "incomplete"
    ]

    if not published_incomplete:
        return [t for _, t in candidates], []

    # Per-candidate пул: список candidates[i] содержит ТОЛЬКО задачи того же
    # assignee_userkey (Q18.3: если userkey нет — сравниваем по assignee_raw,
    # case-insensitive/strip, среди опубликованных с assignee_userkey is None).
    new_items_data = []
    per_candidate_pub: list[list[tuple[PublishedTask, date]]] = []
    for i, (_, (task, _resolved, _deadline)) in enumerate(candidates):
        new_uk, new_raw = resolved_new[i]
        if new_uk is not None:
            pool = [(pt, d) for pt, d in published_incomplete if pt.assignee_userkey == new_uk]
        else:
            norm_raw = (new_raw or "").strip().lower()
            pool = [
                (pt, d) for pt, d in published_incomplete
                if pt.assignee_userkey is None
                and (pt.assignee_raw_norm == norm_raw if hasattr(pt, "assignee_raw_norm") else False)
            ]
        per_candidate_pub.append(pool)
        new_items_data.append({
            "new_index": i,
            "text": task.text,
            "candidates": [
                {"idx": j, "text": pt.text, "meeting_date": d.isoformat()}
                for j, (pt, d) in enumerate(pool)
            ],
        })

    # Экономия (§18.2 п.4): кандидаты с пустым пулом — гарантированно unique,
    # не отправляем в LLM вовсе.
    llm_items = [item for item in new_items_data if item["candidates"]]
    if not llm_items:
        return [t for _, t in candidates], []

    prompt = PROMPT_TASK_DEDUP.format(
        new_items_with_candidates=json.dumps(llm_items, ensure_ascii=False),
    )

    try:
        raw = self._llm_fn(prompt)
        results = json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        log.warning("dedup llm_check_tasks: ошибка LLM: %s", exc)
        return [t for _, t in candidates], []

    unique: list[tuple] = []
    dups: list[DuplicateInfo] = []

    for i, (orig_idx, task_tuple) in enumerate(candidates):
        task, resolved, deadline = task_tuple
        assignee_raw = resolved_new[i][1]
        pool = per_candidate_pub[i]

        if not pool:
            unique.append(task_tuple)
            continue

        dup_pub_idx: int | None = None
        reasoning = None
        for r in results:
            if r.get("new_index") == i:
                dup_pub_idx = r.get("duplicate_of_published_index")
                reasoning = r.get("reasoning")
                break

        if dup_pub_idx is not None and 0 <= dup_pub_idx < len(pool):
            pub_task, matched_date = pool[dup_pub_idx]
            log.info(
                "dedup: дубль [%s] %r → %r (reasoning: %s)",
                "задача", task.text[:80], pub_task.text[:80], reasoning or "нет",
            )
            dups.append(DuplicateInfo(
                kind="task", text=task.text, assignee=assignee_raw,
                matched_meeting_date=matched_date, reason="llm",
            ))
        else:
            unique.append(task_tuple)

    return unique, dups
```

**Ключевые изменения индексации (п.5 задачи):**
- `dup_pub_idx` (JSON-поле `duplicate_of_published_index`) теперь резолвится через
  `pool[dup_pub_idx]` (пул конкретного кандидата `i`), НЕ через глобальный
  `all_published[dup_pub_idx]`, как было раньше (старые строки 416–437). Это ломающее
  изменение семантики ответа LLM (см. B.1: промпт явно говорит модели, что `M` — индекс в
  `candidates`, не сквозной).
- Итерация по `candidates` (внешний цикл `for i, (orig_idx, task_tuple) in
  enumerate(candidates)`) сохраняет тот же порядок, что и `new_items_data`/`llm_items` —
  но `llm_items` может быть **короче** `candidates` (кандидаты с пустым пулом не
  отправляются в LLM). Использую `new_index` из `results`, сопоставляемый с `i` (индекс в
  ПОЛНОМ `candidates`, не в отфильтрованном `llm_items`) — поэтому `new_items_data`
  должен нумероваться по полному индексу `i` **до** фильтрации в `llm_items`, что уже
  учтено в эскизе (`"new_index": i` присваивается на этапе построения `new_items_data`,
  фильтрация `llm_items = [item for item in new_items_data if item["candidates"]]`
  происходит после — индексы `new_index` внутри `llm_items` остаются оригинальными `i`,
  не переиндексируются). Это критично проверить в реализации — источник тонкой ошибки.

**Требуется вспомогательное поле в `PublishedTask`** для Q18.3 (сравнение по
`assignee_raw`, case-insensitive): текущий `PublishedTask` (строки 85–89) хранит только
`text`, `assignee_userkey`, `status` — **не хранит raw-имя исполнителя** (в
`parse_published_rows`/`_parse_task_userkey` парсится только `ri:userkey`, сырое имя
mention'а не извлекается отдельно, см. `_parse_task_text` строки 133–144 — убирает все теги,
включая mention). Чтобы реализовать Q18.3 буквально («совпадающий `assignee_raw`»), нужно
либо (а) добавить парсинг сырого имени из `<ac:link><ri:user>`/текста mention в
`_parse_task_userkey`/новую функцию `_parse_task_assignee_raw`, добавить поле
`PublishedTask.assignee_raw: str | None = None`, либо (б) признать, что raw-имя
опубликованных задач физически недоступно в текущем формате Confluence storage (mention
рендерится как `<ac:link><ri:user ri:userkey=".."/></ac:link>` без видимого текста имени —
Confluence сам подставляет отображаемое имя на клиенте, в storage XML текста имени нет) —
тогда Q18.3 в буквальной трактовке ТЗ (сравнение по `assignee_raw`) **невыполнимо для
опубликованных задач** технически, и нужно **уточнение у Саши перед реализацией**: либо
раскрыть исходный вопрос — при `new_userkey is None` пул `candidates` **всегда пуст**
(упрощённый, но реализуемый вариант, строже текущего кода — что уже даёт частичное
исправление проблемы), либо искать raw-имя в других полях `PublishedRow` (нет таких полей
сейчас). **Это блокирующий для реализации открытый вопрос, не решённый на уровне
кода в §18.2 — плейсхолдер поставлен, но данных для raw-имени в текущей архитектуре
парсинга нет.** Рекомендация плана: реализовывать вариант «`new_userkey is None` → пул
пуст, задача гарантированно unique» как первый шаг (не увеличивает риск ложных дублей,
строже нынешнего поведения), и завести Q18.3-уточнение к Саше отдельным пунктом перед
началом кода.

### B.3 — `_check_tasks_impl` (строки 287–355) — требуется ли правка

По коду выше правка **не требуется**: `_llm_check_tasks` получает `needs_llm` (уже собранный
`_check_tasks_impl`) без изменений формата — вся новая логика инкапсулирована внутри
`_llm_check_tasks`. Формулировка ТЗ §18.3.1 п.2 («доп. группировка `needs_llm` по
`new_userkey`/`assignee_raw` перед передачей в LLM») по факту реализуется **внутри**
`_llm_check_tasks` (группировка per-candidate пулов), а не отдельным шагом в
`_check_tasks_impl` — эквивалентно, но проще (один проход). План — не трогать
`_check_tasks_impl`, если ревью на этапе реализации не найдёт причин вынести группировку
выше по стеку.

## План тестирования

### Т1. Новые unit-тесты `_load_llm_config` — файл `tests/test_config_llm.py` (новый)

Кейсы (через `monkeypatch` + `tmp_path` с фейковым `config.yaml`, подмена
`Path.home()` через `monkeypatch.setattr(config, "_load_llm_config", ...)` — точнее:
подмена самого пути через параметризацию функции, либо `monkeypatch.setattr(Path, "home",
lambda: tmp_path)`, что безопаснее и не требует правки сигнатуры `_load_llm_config()`):

1. `test_reads_model_and_provider_from_config_yaml` — валидный `config.yaml` с
   `model.default`/`model.provider`/`custom_providers` → `LlmConfig` содержит ожидаемые
   `model`/`base_url`/`api_key`/`provider_name`.
2. `test_env_override_wins_over_config_yaml` — валидный `config.yaml` +
   `monkeypatch.setenv("DEDUP_LLM_MODEL", "other/model")` → `LlmConfig.model ==
   "other/model"`, остальные поля из `config.yaml`.
3. `test_env_override_each_field_independent` — `DEDUP_LLM_BASE_URL`/`DEDUP_LLM_API_KEY`
   переопределяются по отдельности, без переопределения остальных полей.
4. `test_missing_config_yaml_falls_back_to_defaults` — `cfg_path` не существует (нет файла
   в `tmp_path`) → `LlmConfig.model == "deepseek/deepseek-v4-flash-0731"`,
   `base_url == "https://llm-gateway.tutu.ru/api/openrouter/v1"`, `api_key is None`.
5. `test_broken_yaml_falls_back_no_exception` — файл с невалидным YAML (например,
   `"model: [unclosed"`) → не бросает исключение, `log.warning` вызван (проверить через
   `caplog`), fallback на дефолты.
6. `test_provider_not_found_in_custom_providers` — `model.provider: "ghost"`, но в
   `custom_providers` нет записи с этим `name` → `base_url`/`api_key` — из env/дефолтов
   (`None`/захардкоженный `base_url`), `provider_name == "ghost"` (не подставляется
   `"tutu"`, потому что `provider_name` в config.yaml был явно указан, просто ссылка
   не резолвилась — уточнить это поведение явно в тесте, т.к. в коде §18.1
   `provider_name or "tutu"` — fallback срабатывает только если `provider_name is None`,
   не если он не найден в списке).
7. `test_empty_custom_providers_list` — `custom_providers` отсутствует в YAML вовсе →
   `base_url`/`api_key` — дефолты.

### Т2. `tests/test_pipeline_dedup.py` — обновление существующих + новые

- Тесты `test_dedup_llm_fn_calls_openai_with_expected_params`,
  `test_dedup_llm_fn_uses_model_from_config`, `test_dedup_llm_fn_fail_soft_no_key` (строки
  241–293) — **переписать**: мокать не `LLM_GATEWAY_API_KEY` env /
  `_load_llm_gateway_api_key`, а `monkeypatch.setattr("protocolfromsummary.pipeline.LLM_CONFIG",
  LlmConfig(model=..., base_url=..., api_key=..., provider_name="tutu"))` (см. A.2 про
  module-level кэширование — прямая замена объекта, не env+reload).
  `test_dedup_llm_fn_alias_backward_compat` — без изменений (не завязан на конфиг).
- Новый тест `test_dedup_llm_fn_uses_base_url_from_config` — `LLM_CONFIG.base_url ==
  "https://custom.example/v1"` → `openai.OpenAI` вызван с этим `base_url` (раньше это было
  невозможно протестировать — `base_url` был захардкожен в теле функции).
- Проверить остаётся зелёным: `test_dedup_filters_fuzzy_duplicate_decision`,
  `test_dedup_serializes_duplicates_into_registry`, `test_dedup_fail_soft_on_broken_llm`,
  `test_dedup_skipped_on_republish`, `test_notify_pending_appends_duplicates_block` — не
  зависят от `_dedup_llm_fn`/конфига (используют `llm_fn=` явно передаваемый в `run_pilot`),
  правка не требуется, но прогнать после изменений для регрессии.

### Т3. `tests/test_dedup.py` — обновление под новый `PROMPT_TASK_DEDUP`/пер-кандидатный пул

Существующий тест `test_no_userkey_skips_fuzzy_uses_haiku` (строки 186–205) — **требует
правки**: по решению B.2 (пул пуст при `new_userkey is None`, если нет raw-сравнения) этот
тест перестанет вызывать `haiku_called` (пул `candidates` для задачи без userkey — пуст,
`llm_items` пуст → LLM не вызывается вовсе). **Нужно решить** до реализации: либо (а)
обновить ожидание теста (`haiku_called == []`, `unique` содержит задачу без матча), приняв
что это осознанное ужесточение поведения (Q18.3, пункт из B.2), либо (б) реализовать
raw-сравнение (требует доработки `PublishedTask`, см. B.2 — блокер). **План — обновить тест
под вариант (а)**, задокументировать в самом тесте, что это сознательное изменение §18.

Новые тесты (по п.7 задачи, а–г):

- **(а) `test_llm_dedup_different_assignees_same_text_not_dup`** — два опубликованных
  задания с одинаковым текстом у РАЗНЫХ `assignee_userkey`; новая задача с тем же текстом
  и userkey одного из них. Мокаем `llm_fn` так, чтобы он **обязан быть вызван с пулом из
  1 элемента** (не 2) — проверка через анализ промпта, переданного в `fake_llm(prompt)`
  (`json.loads` части `candidates` внутри промпта, `len(candidates) == 1`). Это тест на
  структурную гарантию (`candidates` НЕ содержит задачу другого исполнителя), а не на
  решение LLM.
- **(б) `test_llm_dedup_same_assignee_different_wording_is_dup`** — один исполнитель,
  разный текст («Подготовить отчёт по продажам» vs «Собрать цифры выручки за месяц»,
  fuzzy `ratio` заведомо `< 0.80`), мок `llm_fn` возвращает
  `duplicate_of_published_index: 0` (индекс внутри `candidates`, один элемент в пуле) →
  дубль, `reason == "llm"`.
- **(в) `test_fuzzy_dup_same_assignee_same_text`** — уже покрыт существующим
  `test_fuzzy_match_same_userkey_incomplete_is_dup` (строка 146) — не создавать дубль
  теста, отметить в новом файле/секции как «уже покрыто, без изменений».
- **(г) `test_none_userkey_pool_is_empty_llm_not_called`** — `new_userkey is None` →
  пул `candidates` пуст → `llm_fn` НЕ вызывается (`haiku_called == []` — обновлённая версия
  бывшего `test_no_userkey_skips_fuzzy_uses_haiku`, см. выше), задача попадает в `unique`.

Все новые тесты — в классе `TestCheckTasks` (`tests/test_dedup.py`), рядом с существующими.

### Т4. Контрольные точки регрессии

- После Части A: `pytest tests/test_pipeline_dedup.py tests/test_config_llm.py -q` —
  зелёный, ноль сетевых вызовов.
- После Части B: `pytest tests/test_dedup.py tests/test_pipeline_dedup.py -q` — зелёный,
  включая новые (а)-(г); проверить итоговое число тестов (было 36 passed в
  `test_dedup.py`+`test_pipeline_dedup.py`, после правок ожидается 36 − 1 (обновлён, не
  удалён) + 4 новых (а-г, кроме (в) которое не дублируется) + новые тесты `_load_llm_fn` (Т2)
  ≈ 36 + 3 (Т3, новых) + Т2 (1 новый) = не менее 40, точное число зафиксировать в PR-описании
  реализации, не в этом плане).
- Полный offline-suite: `python -m pytest -q -m "not live_confluence"` (из корня
  `~/USERTOOLS/ProtocolFromSummary`, venv активирован) — весь набор (было 151), зелёный,
  без сетевых вызовов (`live_confluence`-тесты остаются деселектированы).

### Т5. Живая проверка (после регрессии, не dry в смысле «без сети» — реальный конфиг, без Confluence-публикации)

`run-pending --dry-run` (или прямой вызов `_dedup_llm_fn("тест")`/проверка `LLM_CONFIG` в
Python REPL внутри venv) на тестовой встрече:
- в логе `dedup llm: ...` **нет** warning «ключ не найден»;
- `LLM_CONFIG.model == "deepseek/deepseek-v4-flash-0731"`, `LLM_CONFIG.base_url ==
  "https://llm-gateway.tutu.ru/api/openrouter/v1"` (сверка с A.4 — совпадает с текущим
  `~/.hermes/config.yaml`);
- (опционально, отдельно от §18, но полезно для B) — встреча с известной семантической
  переформулировкой задачи одного исполнителя за 3 недели → дубль пойман (был бы пропущен
  до §18 при `ratio < 0.80`).

## Порядок реализации (§18.3.1, с критериями перехода)

1. **Часть A изолированно.** `config.py` (A.1) → `pipeline.py` (A.2) → `pyproject.toml`
   (A.3, добавить `pyyaml`). **Критерий перехода к шагу 2:** `pytest
   tests/test_pipeline_dedup.py tests/test_config_llm.py -q` зелёный (Т1+Т2 первая часть),
   вручную сверен `LLM_CONFIG` с реальным `config.yaml` (Т5 первая часть, без сети — просто
   проверка полей).
2. **Часть B, после стабилизации A.** Сначала решить блокер Q18.3 (raw-имя недоступно в
   `PublishedTask`, см. B.2) — зафиксировать выбор (пул пуст при `None` userkey, рекомендуемый
   вариант, либо доработка парсера). Затем `dedup.py`: промпт (B.1) → `_llm_check_tasks`
   (B.2) → обновление `test_dedup.py` (Т3). **Критерий перехода к шагу 3:** `pytest
   tests/test_dedup.py -q` зелёный, включая тесты (а)-(г).
3. **Регрессия.** `python -m pytest -q -m "not live_confluence"` — 0 failed. **Критерий
   перехода к шагу 4:** полностью зелёный офлайн-сьют, число тестов не меньше исходных 151
   (минус изменённые, плюс новые).
4. **Живая проверка (Т5).** Только после зелёной регрессии. **Финальный критерий:** лог
   `dedup llm` без warning «ключ не найден», модель/endpoint в логе совпадают с
   `model.default`/`custom_providers[tutu]` реального `config.yaml`.

## Открытые вопросы, требующие решения ДО начала кода

- **Q18.3-блокер (см. B.2):** `PublishedTask` не хранит raw-имя исполнителя — буквальная
  реализация «сравнение по `assignee_raw` при `userkey is None`» из §18.2/Q18.3 ТЗ физически
  невозможна без доработки парсера `dedup.py::_parse_task_userkey`/`PublishedTask`.
  Рекомендация: на первой итерации — пул пуст при `None` userkey (строже текущего кода,
  реализуемо без правки парсера); опция «доработать парсер» — отдельным пунктом, если
  Саша считает это критичным.
- **A.3:** уточнить происхождение `pyyaml` в venv (транзитивная зависимость какого пакета) —
  не blocker, но добавить в `pyproject.toml` явно перед реализацией.
