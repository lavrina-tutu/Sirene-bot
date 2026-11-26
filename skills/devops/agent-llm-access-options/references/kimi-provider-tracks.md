# Kimi (Moonshot) — треки доступа, модели, цены (проверено 11.2026)

Два трека Moonshot, ключи и эндпоинты НЕ взаимозаменяемы (401 при смешивании).

## Трек A — Kimi Code (подписка kimi.ai membership)

- Потребительская/кодинг-агентная подписка: Plus $15/мес (annual), PRO $31/мес (annual $372), Max $79, Ultra $159.
- Эндпоинты: `api.kimi.com/coding/v1` (OpenAI), `api.kimi.com/coding` (Anthropic). Модели: `k3`, `k3-256k`, `kimi-for-coding`, `kimi-for-coding-highspeed`.
- **Gated по User-Agent**: `/coding/v1/chat/completions` с не-кодинг-агентом → **403 `access_terminated_error`** («only available for Coding Agents such as Kimi CLI, Claude Code, Roo Code...»). ToS: «personal interactive use only».
- Лимиты: ~30 concurrent, rolling 5-hour quota, общий месячный кредитный пул (прочие фичи ходят в тот же пул).
- Вердикт: для автоматического Hermes-контура (default/роли/кроны) НЕ годится — UA-gate + ToS. Пригоден только для интерактивного сессионного участия человека в кодинг-агенте.

## Трек B — Kimi Platform (Developer API, pay-as-you-go)

- Эндпоинт `api.moonshot.ai/v1`, OpenAI-compatible, ключ `MOONSHOT_API_KEY`. Единственный трек для агентного бэкенда.
- Запрос: `chat.completions.create(model=..., reasoning_effort=