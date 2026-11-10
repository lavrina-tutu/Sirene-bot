# Вызов Tutu deepseek из внешнего Python-инструмента (без агентной обёртки)

Паттерн перевода рабочих инструментов (~/USERTOOLS/*, deep-mine, digest-контуры) с агентной обёртки codex CLI (`invoke-role`) на **прямое обращение к Hermes-LLM** через публичный `call_llm()`. Проверено на deep-mine `cursor_jobs.py` (2026-09-09), 89/89 тестов зелёные.

## Когда применять
Задача «компрессор/экстракт/сжатие» (компрессор = роль оркестратора, НЕ архитектор/исполнитель). Штатные роли — через codex CLI / invoke-role: архитектор `gpt-6-astra`, исполнитель `gpt-6.1-sol`, компрессор `gpt-6.1-terra`. Ниже — **прямой вызов тул-эндпоинта** Tutu gateway через `call_llm()` без агентной обёртки ролей (суть про endpoint, не про штатные роли): агентная спавн-обёртка ради экстракта 3–5 КБ избыточна (~13 мин спавна, прецедент TaskRefresh).

## Рабочий механизм — `call_llm()`

Публичный API Hermes для одноразового text-completion (`agent/auxiliary_client.py`):
- `call_llm(task, model=..., messages=..., timeout=..., max_tokens=None, tools=None)` — резолв провайдера + chat.completions + retry/fail-soft. Автор: `auxiliary_client.py:8605`.
- Конфиг берётся сам из `~/.hermes/config.yaml`: `auxiliary.<task>` → provider+model; `custom_providers[name=tutu]` → base_url + api_key. **Ключ/базу в код и .env НЕ копировать** — `call_llm` читает сам.
- Пример готового контура: `auxiliary.compression = {provider: tutu, model: deepseek/deepseek-v4-flash-0731}` (задач `compression` уже есть в config).

Минимальный вызов:
```python
from agent.auxiliary_client import call_llm

response = call_llm(
    task="compression",
    model="deepseek/deepseek-v4-flash-0731",  # явный slug, не auto
    messages=[{"role": "user", "content": prompt}],
    timeout=300.0,
    max_tokens=None,  # НЕ резать digest (провайдер = max output)
    tools=None,
)
content = (response.choices[0].message.content or "").strip()
if not content:
    raise RuntimeError("LLM returned empty content")  # fail-loud, как ненулевой returncode
```

## Импорт из внешнего инструмента (venv)
- Скрипт должен стартовать из venv Hermes: `~/hermes-agent/.venv/bin/python3` (`openai` там есть).
- Ленивый импорт внутри функции + подкладывание пути:
```python
def _ensure_hermes_on_path():
    _h = Path.home() / "hermes-agent"
    if str(_h) not in sys.path:
        sys.path.insert(0, str(_h))

def compress_with_llm(prompt, overlay, *, timeout=300.0):
    _ensure_hermes_on_path()
    from agent.auxiliary_client import call_llm  # lazy
    ...
```
Проверка до коммита: `~/hermes-agent/.venv/bin/python3 -c "from agent.auxiliary_client import call_llm; print('ok')"`.

## КРИТИЧНЫЙ ПИТФОЛЛ — НЕ использовать `extract_content_or_reasoning`
У `deepseek-v4-flash-0731` reasoning может уехать в `reasoning_details`. Если взять его как «content», в digest попадёт scratchpad → валидатор `digest_validate.py` режет как журнал → `rejected`. **Бери только `message.content`**; если стабильно пусто — только тогда точечно `extract_content_or_reasoning` + сразу прогон валидатора.

## Запасной путь (codex CLI) — сохранить через env, не CLI-флаг
Если deepseek не даёт full-coverage на жирном входе → откат на codex CLI / invoke-role, но **обязательно `--mode ask`** (иначе снова tools → журнал в теле → rejected, прецедент Trisigma 45/66 rejected):
```python
if os.environ.get("DEEP_MINE_COMPRESSOR", "hermes") == "codex":
    result = run_agent(prompt, "gpt-6.1-sol", overlay, source_mode="l0_allowed", mode="ask")
    ...
```
`run_agent` расширяется опциональным `mode=` (добавляет `--mode` в argv), для архитектора/исполнителя `mode` не передаётся.

## Откат кода
Вернуть `run_agent(prompt, COMPRESSOR_MODEL, ...)` + константу модели. `AgentResult`/`extract_md_from_agent` не ломаются — обёртка `AgentResult(0, text, "", model)` сохраняет strip fences/frontmatter.

## Правки по скиллу tz-workflow (канон)
| Было | Стало |
|---|---|
| компрессор = gpt-6.1-terra + invoke-role (codex CLI) | компрессор = gpt-6.1-terra через codex CLI (invoke-role) |
| канон в GLOSSARY §3, tz-compressor-prompt, tz-workflow Шаг 0 | единый `core-compressor-prompt.md` (роль/модель/процесс), оба промпта — overlay (только вход/выход) |
| auxiliary.compression model='' | явный `gpt-6.1-terra` (защита от будущего дефолта) |