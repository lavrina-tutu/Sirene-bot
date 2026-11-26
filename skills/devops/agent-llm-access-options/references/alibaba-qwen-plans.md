# Alibaba Cloud (Qwen) — планы, модели, квоты (проверено 10.2026)

Единая платформа: Alibaba Cloud **Model Studio** (он же Bailian/DashScope) — Qwen + сторонние (Kimi, GLM, MiniMax, DeepSeek). Всё ниже — международный (intl) регион, цены Global.

## Планы

### 1. Coding Plan Pro — рекомендован для агентного dev-контура
- **$50/мес** фикс; квота в **запросах** (вызов модели): 6 000/5ч · 45 000/нед · 90 000/мес. Три лимита действуют одновременно (первый сработавший паузит), не суммируются.
- Модели (закрытый список): рекомендуемые — `qwen3.7-plus` (vision), `qwen3.6-plus` (vision), `kimi-k2.5` (vision), `glm-5`, `MiniMax-M2.5`; ещё — `qwen3.5-plus`, `qwen3-max-2026-01-23`, `qwen3-coder-next`, `qwen3-coder-plus`, `glm-4.7`. **flash-семейство и qwen3.8-max в плане НЕТ.**
- Ключ плана: `sk-sp-…` (отдельно от обычного `sk-…` pay-as-you-go — их нельзя смешивать, иначе биллинг уйдёт в PAYG).
- Эндпоинты: `https://coding-intl.dashscope.aliyuncs.com/v1` (OpenAI-совместимый) и `https://coding-intl.dashscope.aliyuncs.com/apps/anthropic` (Anthropic-совместимый, для Claude Code-подобных).
- Официальные интеграции: Hermes Agent, Codex, Claude Code, Qwen Code, OpenCode, Cursor, Cline, OpenClaw, Qoder и др.
- Lite: закрыт для новых с марта 2026 (продления до 13.04.2026); новые — только Pro.
- Слоты ограничены (пополнение ежедневно 00:00 UTC+8), подписка невозвратная.
- Оценка расхода: «запрос» = 1 вызов модели; простая агентная задача 5–10 вызовов, сложная 10–30+.

### 2. Token Plan (новая, июль 2026)
- Отдельная подписка со своими `sk-sp-` ключами и эндпоинтами (China/Intl раздельно); туда эксклюзивно выходили превью флагманов (qwen3.8-max-preview). Цены — на консоли, детали менять.

### 3. Pay-as-you-go (Model Studio, обычный API)
- Все модели, оплата за токены (Global, 10.2026):
  - `qwen3.8-max` $2.00 / $6.00
  - `qwen3.7-plus` $0.80 / $2.00 (по другим источникам $0.32–0.96 / $1.28–3.84 tiered by context)
  - `qwen3.7-flash` $0.10 / $0.30 (≤256K), $0.40 / $1.20 (256K–1M)
  - `qwen3.6-flash` $0.165 / $0.99; `qwen3.5-flash` $0.029 / $0.287
  - прочие: `deepseek-v4-pro-0813`, `deepseek-v4.1-flash`, `glm-5.2`, `kimi-k3`, `qwen3-coder`
- Триал новым аккаунтам: ~70M токенов / 90 дней (Singapore endpoint). Цены всегда сверять с alibabacloud.com/help/en/model-studio/model-pricing.

### 4. QwenCloud Personal/Team — кредитная модель (Credits, не вызовы)
- Personal: Lite $6 promo/11,500 · Essential $10 promo/25,500 · Standard $18 promo/45,000 · Pro $68 promo/180,000 (строки «1–8 агентов»)
- Team: Standard $20/seat/25,000 · Pro $75/seat/100,000 · Max $200/seat/250,000
- Qwen OAuth free tier прекращён (15.04.2026).

## Маппинг на роли (архитектор / ревизор / исполнитель / оркестрация)

| Роль | Модель | Почему |
|---|---|---|
| Архитектор | `qwen3.7-plus` или `qwen3-max` | флагман, agentic reasoning, 1M контекст |
| Ревизор | `kimi-k2.5` или `glm-5` | другое семейство — независимость от автора в той же квоте |
| Исполнитель | `qwen3-coder-next` / `qwen3-coder-plus` / `qwen3.6-plus` | кодинговые специализированные |
| Оркестрация | flash-модели (только PAYG!) или `qwen3.7-plus` в квоте плана | flash-модели в Coding Plan недоступны |

Агентные возможности: Function Calling, MCP, Code Interpreter (Qwen-Agent), vision на plus-моделях. Hermes подключается как OpenAI-совместимый провайдер (base_url `/v1`, ключ `sk-sp-`).

## Правила и подводные камни
- **Проверять квоты до миграции**: квота в запросах, не токенах — выгодна при контекстно-тяжёлых задачах (мало вызовов, большие пейлоады), невыгодна при множестве мелких вызовов.
- Считать реальную нагрузку по логам (см. `hermes-cost-audit`: capacity check по `session_model_usage` + codex rollout-счётчики). Держать ≥2× запас по месячной квоте; самое узкое место — окно 6k/5ч в пиковые дни агентных батчей (5–8k вызовов/день — впритык).
- Не ставить keepalive/healthcheck-пинги в квоту — они платные и накручивают запросы.
- Урок OpenAI-бана: consumer/Business-подписку ChatGPT нельзя эксплуатировать как API-бэкенд автономных агентов; Coding Plan — явно агентный план, автоматизация легальна.
