> Historical source, 2026; preserved as recorded, not current instructions. Verify against the current entrypoint and implementation.

## Роутинг по типу задачи (для пользователя tkachenkoav)

| Тип задачи | Модель |
|---|---|
| Терминальные / механические (ls, config set, статус) | claude-haiku-4-5 |
| Справочные вопросы по готовым инструментам/ТЗ/скиллам | claude-haiku-4-5 |
| Основной чат, координация, интерпретация запросов | claude-sonnet-4-6 |
| Разработка, **написание и правка ТЗ**, архитектура, дебаг | claude-opus-4-7 |

**Правило ТЗ:** ТЗ всегда пишет и правит Opus. После любой правки ТЗ — Opus проверяет все смежные ТЗ инструментов на непротиворечивость. Нарушение этого правила приводит к расхождениям между документами (как произошло в мае 2026: Haiku отредактировал ТЗ MoveFromExchange вместо Opus).

**Важно:** основной чат держать на Sonnet, не Haiku — Haiku теряет контекст длинных сессий и неточно формулирует задачи для субагентов. Sonnet дешевле Opus в ~5 раз при приемлемом качестве.

## 8. Справочные вопросы по готовым инструментам → Haiku

Когда пользователь задаёт вопрос вида «как работает X», «что делает функция Y», «объясни алгоритм Z» про уже написанный инструмент/ТЗ/скилл — этот вопрос можно делегировать Haiku. Haiku читает код/документ и объясняет — качество достаточное, стоимость в 20x меньше.

**Кандидаты для Haiku:**
- «Как MoveFromFF синхронизирует новые встречи?»
- «Что делает функция fetch_range?»
- «Какие поля в реестре v2.0?»
- «Как работает блокировка через portalocker?»
- «Что настроено в config.yaml?»

**Оставлять на Sonnet/Opus:**
- Вопросы с архитектурными решениями («как лучше сделать X»)
- Вопросы по нескольким файлам сразу с выводами
- Отладка — найти где баг в коде

## 9. Роутинг по типу задачи (рекомендуемая схема для tkachenkoav)

| Тип задачи | Модель | Способ |
|---|---|---|
| Лёгкие терминальные (ls, date, du) | `claude-haiku-4-5` | `model={"model": "claude-haiku-4-5", "provider": "anthropic"}` |
| Исследовательские (research, анализ) | `claude-opus-4-7` | `model={"model": "claude-opus-4-7", "provider": "anthropic"}` |
| Разработка, код, debugging | `claude-opus-4-7` | явно в каждом `delegate_task` |
| Настройки Hermes, конфиг | `claude-opus-4-7` | явно в каждом `delegate_task` |
| Основной чат с пользователем | `claude-sonnet-4-6` | `model.default` в config |

**Важно:** всегда передавай модель явно через параметр `model` в `delegate_task` — конфиг `delegation.model` ненадёжен (см. Pitfalls).

---

## 11. Стек моделей Hermes (tutu-роутинг, DeepSeek/Gemini/Qwen)

Альтернативная схема роутинга — через tutu-гейтвей с DeepSeek/Gemini/Qwen (не через anthropic-модели). Актуально для профилей/задач с основным провайдером tutu.

### Текущая конфигурация (06.08.2026)

| Роль | Модель | Провайдер | Цена |
|---|---|---|---|
| Основной чат | `deepseek/deepseek-v4-pro` | tutu | $0.435/M in, $0.0036/M cache_hit, $0.87/M out |
| Compression | `google/gemini-3-flash-preview` | tutu | $0.50/M in, $0.05/M cache_hit, $3.00/M out |
| Session search | `google/gemini-3-flash-preview` | tutu | То же что compression |
| Исследования/оркестрация | `qwen/qwen3.6-plus` | tutu | $0.325/M in, $1.95/M out |
| Delegation | `deepseek/deepseek-v4-pro` | tutu | Как основной |

### DevWorkflow роли (codex CLI / invoke-role)

| Роль | Модель |
|---|---|
| Архитектор (ТЗ, планы) | `gpt-6-astra` |
| Исполнитель (код, тесты) | `gpt-6.1-sol` |
| Координатор | `gpt-6-astra` |

### Кроны (free tier) — PITFALL

- `nvidia/nemotron-3-super-120b-a12b:free` — selfcheck, upstream, backlog
- `openai/gpt-oss-20b:free` — batch processing

**Pitfall (07.08.2026):** Free-tier модели на Tutu-гейтвее (`nemotron-3-super-120b:free`) нестабильны для критичных кронов. Причина: очереди на inference, низкий приоритет обработки, большие задержки. Результат — таймаут крона после 600s ожидания API-ответа (`TimeoutError: idle for 602s — waiting for non-streaming API response`).

**Правило:** Для критичных кронов (backlog-collector, pfs_batch и т.д.) использовать платные модели (Haiku-4-5, gpt-oss-20b:free допустим только для no_agent/скриптовых кронов). Экономия на free-tier не стоит потери надёжности.

### Исторические цены (Anthropic direct, июнь-июль 2026)

| Модель | $/1K in | $/1K cache_hit | $/1K out | Effective $/1K out |
|---|---|---|---|---|
| Sonnet-4-6 | $0.003 | $0.0003 | $0.015 | $0.1006 |
| Opus-4-7 | $0.005 | $0.0005 | $0.025 | $0.0699 |
| Sonnet-5 (intro ≤31.08) | $0.001 | $0.0001 | $0.005 | $0.0185 |
| Haiku-4-5 | $0.001 | $0.0001 | $0.005 | $0.0414 |

### Экономия

- API Hermes: $307/мес → $44/мес (**86%**)
- + Cursor Pro ($200/мес): $307 → $244/мес (**20%**)

## Earlier OpenRouter session matrix (date not recorded)

# Role matrix for Hermes model selection

This reference captures a practical model split for a Hermes setup when selecting among currently verified OpenRouter models.

## Verified set

- `x-ai/grok-4.20`
- `google/gemini-3-flash-preview`
- `deepseek/deepseek-v4-pro`

## Recommended split from this session

| Role | Model | Why |
|---|---|---|
| Main | `x-ai/grok-4.20` | Fast, strict, low hallucination, large context |
| Title generation | `google/gemini-3-flash-preview` | Cheap and fast |
| Approval | `google/gemini-3-flash-preview` | Cheap and fast for trivial decisions |
| Web extract / summarization | `google/gemini-3-flash-preview` | Good speed/quality balance |
| Compression | `deepseek/deepseek-v4-pro` | Cheap, long context, suitable for summarization/compression |
| Code/file-heavy fallback | `deepseek/deepseek-v4-pro` | Cheap and strong for code / file tasks |
| Extra long-context fallback | `x-ai/grok-4.20` | Large context and speed |

## Notes

- The user explicitly wanted a setup limited to models actually present in OpenRouter.
- Gemini 3 Pro and Sonnet were intentionally excluded in the final configuration.
- Grok 4.20 was chosen as main after comparison on speed, strictness, and hallucination behavior.


