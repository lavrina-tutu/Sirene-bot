# Сирень — ежедневный self-check

**Дата:** 2026-05-28 03:00  
**Воплощение:** Opus (claude-opus-4-7)

---

## ✅ Что в порядке

**Скиллы (50 файлов в `~/AppData/Local/hermes/skills/`):**
- `persona/sirene-identity` и `persona/sirene-chat-friends` — комплементарны (identity = базовая личность, chat-friends = поведение в TG). Не дублируют, но частично пересекаются — это нормально.
- DevOps-набор (`hermes-feature`, `hermes-research`, `hermes-debug`, `hermes-cost-optimization`, `hermes-gateway-setup`, `gateway-platform-configuration`, `custom-llm-endpoint-delegation`, `hermes-config-qa`) — каждый со своей зоной, конфликтов нет.
- Productivity: `movefrom-*` скиллы корректно покрывают пайплайны MoveFromFF/Exchange/Confluence/Instruments.

**Конфиг (`config.yaml`):**
- Routing-правила в `system_prompt` синхронны с моделями: default=Sonnet, fallback=Haiku, delegation=Opus. Согласовано.
- `display.personality: sirene` + `agent.personalities.sirene` присутствуют и совпадают со скиллом.
- Telegram allowed_chats=400307920, runtime_header выводит модель — всё в силе.

**Крон-задачи (5 активных):**
- `bc1b0ae442f0` GitHub autosync — **Haiku** ✅
- `e7a53b2e2cf2` self-check (этот) — **Opus** ✅
- `58ab10e1ee15` MoveFromExchange weekly — **Haiku** ✅
- `1e62e18ae399` MoveFromFF sync 2ч — **Haiku** ✅
- `ea18f323a671` MoveFromFF test — **paused** (не считаем)

---

## ⚠️ Что нашла

1. **`1e62e18ae399` MoveFromFF — последний прогон 27.05 20:00 завершился ошибкой:**  
   `RuntimeError: Error code: 403 - {'error': {'type': 'forbidden', 'message': 'Request not allowed'}}` — Anthropic вернул 403. Возможные причины: rate limit, проблема с биллингом, либо запрос с подозрительным контентом. **Нужно проверить руками** — все последующие прогоны (если будут такие же) повредят синхронизацию.

2. **`665a2bf3737e` (P5 routing analysis, разово 22.06)** — задача назначена на **Haiku**, но по сути это «анализ маршрутизации, перерасход токенов». Это аналитика → должна быть **Sonnet** или **Opus**. Haiku может не справиться с интерпретацией логов.  
   **Исправление:** поменять `model` на `claude-sonnet-4-6`.

3. **`ea18f323a671` MoveFromFF test — Opus**, хотя задача чисто терминальная (запустить `.venv/Scripts/python -m movefromff --dry-run` и отчитаться). Должна быть **Haiku**. Сейчас на паузе, но если разморозим — переключить на Haiku.

4. **Cosmetic:** в персоналии `sirene` в `config.yaml` (строки 32-49) сидят дефолтные Hermes-личности (kawaii, catgirl, pirate, ...). Они никогда не используются у Саши — можно подчистить, чтобы system_prompt был легче.

5. **Hermes repo:** новые коммиты от Nous за последние дни — `migration v1: update configs, .env, READMEs for new layout`, security-фиксы (API-key leakage prevention, secure_parent_dir guards), Telegram menu reorder, импорт MoveFrom*-тулов в апстрим. **Стоит подтянуть** — может потребоваться обновление путей в конфиге после v1-migration.

---

## 💡 Топ-3 улучшения для Саши

1. **Расследовать 403 от Anthropic в MoveFromFF cron** (`1e62e18ae399`). Открыть `~/AppData/Local/hermes/cron/output/<job>/` за 27.05 20:00, посмотреть полный traceback. Если повторяется — временно поставить на паузу, чтобы не жечь повторные ошибки каждые 2 часа.

2. **Поправить модели у двух задач:**
   - `665a2bf3737e` (P5 routing analysis) → **Sonnet** (анализ).
   - `ea18f323a671` (MoveFromFF test) → **Haiku** (терминальный запуск).
   Это две правки в `cron/jobs.json` поле `"model"`.

3. **Подтянуть Hermes Agent до свежего апстрима** (v0.14 «Foundation Release», 16 мая 2026 + последующие фиксы). Новое полезное:
   - `hermes proxy` — локальный OpenAI-совместимый прокси для OAuth-провайдеров (полезно если будем подключать SuperGrok/Copilot).
   - LSP semantic diagnostics после `patch`/`write_file` — меньше регрессий в скриптах MoveFrom*.
   - Native Windows beta — может убрать костыли с MSYS-путями.
   - Security: фикс утечки API-ключей в non-authoritative custom endpoints (важно если делегируем через прокси).  
   После апдейта обязательно прогнать `hermes-config-qa` скилл.

---

*Сирень, Opus, 28.05.2026*
