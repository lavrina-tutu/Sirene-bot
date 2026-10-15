---
name: Honcho Integration
version: 0.1.0
created: 2026-08-12
author: Архитектор (tz-dev)
status: draft
---

# ТЗ: Интеграция Honcho self-hosted для профиля default (Сирень)

## Цель

Установить и настроить self-hosted Honcho как memory provider для профиля default (Сирень), обеспечив кросс-сессионное моделирование пользователя с изоляцией от профиля tz-dev и остальных профилей.

## Связи с существующими инструментами

| Инструмент | Связь | Комментарий |
|---|---|---|
| hermes-multi-profile-skills | Изоляция профилей | Honcho активируется ТОЛЬКО в default; tz-dev остаётся на built-in памяти |
| hermes-ops | Диагностика | Проверка через docs как источник истины |
| DialogBacklog | Потенциальная синергия | Honcho строит модель пользователя, DialogBacklog собирает backlog — данные могут дополнять друг друга в будущем |

## Связи с инфраструктурой Hermes

- Профили: `default` (активация), `tz-dev` (без изменений), `anthropic`, `openai` (без изменений)
- Config: `memory.provider: honcho` только в default
- Honcho конфиг: profile-specific (`~/.hermes/profiles/default/honcho.json`) — tz-dev его не видит
- Gateway: identity mapping через `pinUserPeer` + `runtimePeerPrefix: "telegram_"`

---

## §1. Инфраструктура: установка Honcho self-hosted

### 1.1. Зависимости

Сервер: AlmaLinux 9.7, sudo NOPASSWD. Docker не установлен.

**Вариант установки:** Docker Engine + Compose plugin через dnf с `--allowerasing` (конфликт с buildah/podman).

**Компоненты Honcho (Docker Compose):**
- `api` — FastAPI сервер, порт 8000 (127.0.0.1)
- `deriver` — background worker (извлечение наблюдений, summaries, dream)
- `database` — PostgreSQL 15 + pgvector, порт 5432 (127.0.0.1)
- `redis` — кэш, порт 6379 (127.0.0.1)

### 1.2. Процедура установки

1. Установка Docker CE + Compose plugin:
   ```bash
   sudo dnf install -y ca-certificates curl
   sudo dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
   sudo dnf install -y --allowerasing docker-ce docker-ce-cli containerd.io docker-compose-plugin
   sudo systemctl enable --now docker
   sudo usermod -aG docker tkachenkoav
   ```
2. Clone Honcho:
   ```bash
   git clone https://github.com/plastic-labs/honcho.git ~/honcho
   cd ~/honcho
   cp .env.template .env
   cp docker-compose.yml.example docker-compose.yml
   ```

### 1.3. Верификация установки
```bash
docker --version
docker compose version
docker compose up -d --build   # первый запуск (~2 мин билд)
docker compose ps
curl http://localhost:8000/health
docker compose logs deriver --tail 20
```

---

## §2. Конфигурация LLM-моделей Honcho

### 2.1. Провайдер: OpenRouter

Все LLM-вызовы Honcho идут через OpenRouter (один API ключ).

### 2.2. Маппинг моделей по компонентам

| Компонент | Модель | Thinking | Обоснование |
|---|---|---|---|
| Deriver | `google/gemini-2.5-flash-lite` | без thinking | Каждый ход, extraction — простая задача |
| Summary | `google/gemini-2.5-flash-lite` | без thinking | Каждые 20-60 сообщений, сжатие текста |
| Dialectic minimal | `google/gemini-2.5-flash-lite` | без thinking | Простой recall |
| Dialectic low | `google/gemini-2.5-flash-lite` | без thinking | Стандартные запросы |
| Dialectic medium | `deepseek/deepseek-v4-pro` | 1024 tokens | Вопросы о паттернах |
| Dialectic high | `deepseek/deepseek-v4-pro` | 2048 tokens | Cross-session связи |
| Dialectic max | `deepseek/deepseek-v4-pro` | 4096 tokens | Глубокий анализ |
| Dream deduction | `deepseek/deepseek-v4-pro` | 2048 tokens | Консолидация памяти (раз в ~8ч) |
| Dream induction | `deepseek/deepseek-v4-pro` | 2048 tokens | Консолидация памяти (раз в ~8ч) |
| Embeddings | `google/text-embedding-004` | — | Семантический поиск |

### 2.3. Конфигурация .env

Через environment variables (приоритет выше config.toml):

```bash
# API ключ (единственный секрет)
LLM_OPENAI_API_KEY=sk-or-v1-...

# Deriver — light tier
DERIVER_MODEL_CONFIG__TRANSPORT=openai
DERIVER_MODEL_CONFIG__MODEL=google/gemini-2.5-flash-lite
DERIVER_MODEL_CONFIG__OVERRIDES__BASE_URL=https://openrouter.ai/api/v1

# Summary — light tier
SUMMARY_MODEL_CONFIG__TRANSPORT=openai
SUMMARY_MODEL_CONFIG__MODEL=google/gemini-2.5-flash-lite
SUMMARY_MODEL_CONFIG__OVERRIDES__BASE_URL=https://openrouter.ai/api/v1

# Dialectic — tiered
DIALECTIC_LEVELS__minimal__MODEL_CONFIG__TRANSPORT=openai
DIALECTIC_LEVELS__minimal__MODEL_CONFIG__MODEL=google/gemini-2.5-flash-lite
DIALECTIC_LEVELS__minimal__MODEL_CONFIG__OVERRIDES__BASE_URL=https://openrouter.ai/api/v1

DIALECTIC_LEVELS__low__MODEL_CONFIG__TRANSPORT=openai
DIALECTIC_LEVELS__low__MODEL_CONFIG__MODEL=google/gemini-2.5-flash-lite
DIALECTIC_LEVELS__low__MODEL_CONFIG__OVERRIDES__BASE_URL=https://openrouter.ai/api/v1

DIALECTIC_LEVELS__medium__MODEL_CONFIG__TRANSPORT=openai
DIALECTIC_LEVELS__medium__MODEL_CONFIG__MODEL=deepseek/deepseek-v4-pro
DIALECTIC_LEVELS__medium__MODEL_CONFIG__OVERRIDES__BASE_URL=https://openrouter.ai/api/v1

DIALECTIC_LEVELS__high__MODEL_CONFIG__TRANSPORT=openai
DIALECTIC_LEVELS__high__MODEL_CONFIG__MODEL=deepseek/deepseek-v4-pro
DIALECTIC_LEVELS__high__MODEL_CONFIG__OVERRIDES__BASE_URL=https://openrouter.ai/api/v1

DIALECTIC_LEVELS__max__MODEL_CONFIG__TRANSPORT=openai
DIALECTIC_LEVELS__max__MODEL_CONFIG__MODEL=deepseek/deepseek-v4-pro
DIALECTIC_LEVELS__max__MODEL_CONFIG__OVERRIDES__BASE_URL=https://openrouter.ai/api/v1

# Dream — heavy tier
DREAM_DEDUCTION_MODEL_CONFIG__TRANSPORT=openai
DREAM_DEDUCTION_MODEL_CONFIG__MODEL=deepseek/deepseek-v4-pro
DREAM_DEDUCTION_MODEL_CONFIG__OVERRIDES__BASE_URL=https://openrouter.ai/api/v1

DREAM_INDUCTION_MODEL_CONFIG__TRANSPORT=openai
DREAM_INDUCTION_MODEL_CONFIG__MODEL=deepseek/deepseek-v4-pro
DREAM_INDUCTION_MODEL_CONFIG__OVERRIDES__BASE_URL=https://openrouter.ai/api/v1

# Embeddings
LLM_EMBEDDING_API_KEY=${LLM_OPENAI_API_KEY}
LLM_EMBEDDING_BASE_URL=https://openrouter.ai/api/v1
LLM_EMBEDDING_MODEL=google/text-embedding-004

# Auth отключён (локальный доступ)
AUTH_USE_AUTH=false

# Database (локальный PostgreSQL в compose)
DB_CONNECTION_URI=postgresql+psycopg://postgres:postgres@database:5432/postgres
```

### 2.4. Thinking budget для DeepSeek

DeepSeek V4 Pro поддерживает extended thinking. Thinking budget задаётся через `MODEL_CONFIG__THINKING_BUDGET_TOKENS`:
- medium: 1024
- high: 2048
- max: 4096
- dream: 2048

**Важно:** `MAX_OUTPUT_TOKENS` должен превышать `THINKING_BUDGET_TOKENS`. Проверить дефолты Honcho — если не заданы, установить:
- medium: output 2048
- high: output 4096
- max: output 8192
- dream: output 4096

---

## §3. Настройка профиля default (Сирень)

### 3.1. Активация Honcho как memory provider

```bash
hermes config set memory.provider honcho --profile default
```

### 3.2. honcho.json (profile-specific)

Файл: `~/.hermes/profiles/default/honcho.json`

```json
{
  "baseUrl": "http://localhost:8000",
  "workspace": "hermes",
  "peerName": "honchodb-sasha",
  "hosts": {
    "hermes": {
      "enabled": true,
      "aiPeer": "hermes",
      "peerName": "honchodb-sasha",
      "workspace": "hermes",
      "recallMode": "hybrid",
      "writeFrequency": "async",
      "sessionStrategy": "per-session",
      "observation": {
        "user": { "observeMe": true, "observeOthers": true },
        "ai": { "observeMe": true, "observeOthers": true }
      },
      "dialecticCadence": 2,
      "dialecticDepth": 1,
      "dialecticReasoningLevel": "low",
      "dialecticMaxChars": 600,
      "contextCadence": 1,
      "contextTokens": 1200,
      "messageMaxChars": 25000,
      "saveMessages": true
    }
  },
  "pinUserPeer": true,
  "runtimePeerPrefix": "telegram_"
}
```

### 3.3. Gateway identity mapping

Для Telegram-пользователя (Саша, UID 400307920):
- `pinUserPeer: true` — все пользователи gateway маппятся на `peerName`
- `runtimePeerPrefix: "telegram_"` — namespace для runtime IDs

**Рекомендация на будущее:** если появится ещё один пользователь Telegram, которому нужен свой peer — использовать `userPeerAliases` вместо `pinUserPeer`.

---

## §4. Изоляция остальных профилей

### 4.1. Профиль tz-dev

- `memory.provider` НЕ задан в `~/.hermes/profiles/tz-dev/config.yaml`
- honcho.json лежит в `~/.hermes/profiles/default/honcho.json` (profile-specific) — tz-dev его НЕ читает
- Встроенная память (MEMORY.md/USER.md) работает без изменений
- **Никаких изменений в tz-dev не производится**

### 4.2. Профили anthropic, openai

- Без изменений, built-in memory

---

## §5. Верификация и тестирование

### 5.1. Проверка Honcho server
```bash
docker compose ps                      # все сервисы up
curl http://localhost:8000/health       # 200 OK
docker compose logs deriver --tail 20   # polling/processing
```

### 5.2. Проверка Hermes integration
```bash
hermes memory status --profile default
# Ожидаемый результат: Honcho active, baseUrl=http://localhost:8000

hermes memory status --profile tz-dev
# Ожидаемый результат: built-in only (без Honcho)
```

### 5.3. End-to-end тест
1. Начать сессию в default профиле
2. Сообщить факт: «Мой любимый язык программирования — Rust»
3. Завершить сессию
4. Подождать 30 секунд (deriver processing)
5. Начать новую сессию в default
6. Спросить: «Какой мой любимый язык программирования?»
7. Ожидаемый результат: Сирень вспоминает Rust через Honcho recall

### 5.4. Проверка изоляции tz-dev
1. Начать сессию в tz-dev
2. Сообщить факт: «Мой любимый фреймворк — FastAPI»
3. Завершить сессию
4. Начать сессию в default
5. Спросить: «Какой мой любимый фреймворк?»
6. Ожидаемый результат: Сирень НЕ знает про FastAPI (tz-dev не пишет в Honcho)

---

## §6. Эксплуатация и обслуживание

### 6.1. Бэкап данных Honcho
```bash
# PostgreSQL backup
docker compose exec database pg_dump -U postgres postgres > ~/honcho-backup-$(date +%Y%m%d-%H%M%S).sql

# Restore
cat backup.sql | docker compose exec -T database psql -U postgres postgres
```

### 6.2. Обновление Honcho
```bash
cd ~/honcho
git pull
docker compose up -d --build
docker compose exec api uv run alembic upgrade head
```

### 6.3. Мониторинг
- `docker compose ps` — статус сервисов
- `docker compose logs -f api deriver` — логи
- Health check: `curl http://localhost:8000/health`

### 6.4. Cron для автозапуска Honcho (опционально)
Рекомендуется добавить `restart: unless-stopped` в docker-compose.yml для всех сервисов (уже есть в production compose).

---

## §7. Оценка стоимости

### 7.1. LLM-расходы (через OpenRouter)

| Компонент | Модель | Частота | Примерная стоимость/мес |
|---|---|---|---|
| Deriver | gemini-2.5-flash-lite | ~50 сообщ/день × 30 | ~$0.50 |
| Summary | gemini-2.5-flash-lite | ~2-3/день × 30 | ~$0.10 |
| Dialectic low | gemini-2.5-flash-lite | ~10/день × 30 | ~$0.30 |
| Dialectic med/high | deepseek-v4-pro | ~3/день × 30 | ~$0.50 |
| Dream | deepseek-v4-pro | 3/день × 30 | ~$0.30 |
| Embeddings | text-embedding-004 | ~50/день × 30 | ~$0.05 |

**Итого: ~$1.75/мес** (оценка, зависит от активности)

### 7.2. Инфраструктура
- Docker + PostgreSQL + Redis — на той же машине, что Hermes
- RAM: ~1.5 GB дополнительно (PostgreSQL ~500MB, Redis ~50MB, Honcho API+Deriver ~1GB)
- Disk: ~5 GB (PostgreSQL data + Docker images)

---

## §8. Риски и ограничения

### 8.1. Риски

| Риск | Вероятность | Влияние | Митигация |
|---|---|---|---|
| Docker конфликт с buildah/podman | Средняя | Блокировка установки | `--allowerasing` решает |
| DeepSeek V4 Pro не поддерживает tool calling в OpenRouter | Низкая | Dialectic не работает | Fallback на другой модель |
| Honcho AGPL лицензия | Низкая | Юридический риск для корп. использования | Проверить лицензию |
| Потеря данных при перезапуске | Низкая | Потеря наблюдений | PostgreSQL persists, Docker restart policy |
| Deriver queue backlog при высокой нагрузке | Средняя | Задержка обработки | Увеличить `DERIVER_WORKERS` |

### 8.2. Ограничения

- Honcho self-hosted не использует Neuromancer XR (модель Plastic Labs) — используется general-purpose LLM. Разница в качестве deductive reasoning компенсируется сильными моделями (GLM-5, DeepSeek V4 Pro).
- Модели должны поддерживать tool calling (function calling) — без этого Honcho не запустится.
- Нет E2EE — Honcho agents используют function calling, контент запросов виден провайдеру (OpenRouter), но данные хранения (sessions, observations, embeddings) — только на нашей машине.

---

## Что НЕ трогать

- Профиль tz-dev — НИКАКИХ изменений
- Профили anthropic, openai — НИКАКИХ изменений
- Built-in память Hermes (MEMORY.md/USER.md) — продолжает работать параллельно
- Конфиг tz-dev (`~/.hermes/profiles/tz-dev/config.yaml`) — не модифицировать
- Скиллы tz-dev — не модифицировать
- Gateway — НЕ рестартовать без явного императива

---

## Открытые вопросы

| № | Вопрос | Решение |
|---|---|---|
| 1 | Docker установка — есть ли ограничения от Tutu infra? | Ограничений нет. Установить Docker (единственный новый инструмент). Приоритет — обходиться имеющимся, Docker необходим (Honcho требует контейнеризацию). |
| 2 | OpenRouter API ключ — какой именно? | Отдельный OpenRouter НЕ нужен. Используем Tutu gateway: `https://llm-gateway.tutu.ru/api/openrouter/v1` с ключом из профиля (`custom_providers.tutu.api_key`). |
| 3 | DeepSeek V4 Pro extended thinking через Tutu gateway? | Требует проверки. Если не поддерживает — fallback на `deepseek/deepseek-v4-pro` без thinking или другой модели. |
| 4 | AGPL лицензия Honcho — допустимо для Tutu? | Допустимо. |
| 5 | Session strategy — per-session или per-directory? | Выбрано: `global`. Все сессии default профиля (все топики Telegram) → одна Honcho session. Сирень накапливает единую модель пользователя без фрагментации. |

---

## Приложения к ТЗ

| Приложение | Описание | Дата |
|---|---|---|
| `appendix_research_honcho_setup_12082026.md` | Результаты исследования self-hosted Honcho, docs, конфигурация | 2026-08-12 |
| `appendix_llm_cost_analysis_12082026.md` | Анализ стоимости LLM-моделей для Honcho компонентов | 2026-08-12 |

---

## §9. Фактические отклонения при реализации (зафиксировано 2026-08-13)

| № | По плану/ТЗ | По факту | Раздел/Причина |
|---|---|---|---|
| 1 | Embeddings: `google/text-embedding-004` через Tutu gateway | Локальный TEI `ghcr.io/huggingface/text-embeddings-inference:cpu-1.9`, модель `intfloat/multilingual-e5-small`, 384 dim, порт 8081 | §2.3, 0.1 (план). **Причина:** Tutu gateway не поддерживает embedding-модели (`model_not_allowed`, 400) |
| 2 | 4 контейнера (api, deriver, database, redis) | 5 контейнеров (добавлен `embeddings`) | §1.1. **Следствие отклонения №1** |
| 3 | OpenRouter: `https://openrouter.ai/api/v1` | Tutu gateway: `https://llm-gateway.tutu.ru/api/openrouter/v1` | §2.3. **Причина:** используем имеющийся ключ Tutu, отдельный OpenRouter не нужен |
| 4 | healthcheck embeddings: `wget -qO- http://localhost:80/health` | `curl -sf http://localhost:80/health > /dev/null` | docker-compose.yml. **Причина:** `wget` отсутствует в образе TEI |
| 5 | sessionStrategy: `per-session` | `global` | §3.2 / honcho.json. **Решение Саши:** все сессии → одна Honcho session |
| 6 | honcho.json: плоские поля + host block | Упрощённая структура (dialecticCadence, contextTokens и т.д. внутри `hosts.hermes`, `peerName` только в корне) | §3.2. **Причина:** упрощение конфига при настройке |
| 7 | `uv run python` в контейнере | `/app/.venv/bin/python` | **Причина:** `uv run` падает — `honcho-ai` в `[dependency-groups].dev` но не в workspace members |
| 8 | pgvector dim по умолчанию 1536 | ALTER на 384 через `configure_embeddings.py --yes` | **Причина:** alembic создаёт vector(1536), но TEI отдаёт 384 |

### §9.1. Обновлённые команды (фактические)

**Запуск Honcho (с embeddings):**
```bash
cd ~/honcho && sudo docker compose up -d --build
```

**Проверка embeddings (TEI, не Tutu):**
```bash
curl -s -m 10 http://127.0.0.1:8081/health
curl -s -m 30 http://127.0.0.1:8081/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"input":"тестовая фраза","model":"intfloat/multilingual-e5-small"}' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print('dims:', len(d['data'][0]['embedding']))"
# Ожидание: dims: 384
```

**Honcho config (упрощённый honcho.json):**
```json
{
  "baseUrl": "http://localhost:8000",
  "workspace": "hermes",
  "peerName": "honchodb-sasha",
  "sessionStrategy": "global",
  "hosts": {
    "hermes": {
      "enabled": true,
      "aiPeer": "hermes",
      "workspace": "hermes",
      "recallMode": "hybrid",
      "observation": {
        "user": {"observeMe": true, "observeOthers": true},
        "ai": {"observeMe": true, "observeOthers": true}
      }
    }
  },
  "pinUserPeer": true,
  "runtimePeerPrefix": "telegram_"
}
```
