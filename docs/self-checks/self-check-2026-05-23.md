# Сирень — Self-check 2026-05-23

## ✅ Что в порядке

- **Скиллы** (~16 SKILL.md в `~/AppData/Local/hermes/skills/`) загружаются, фронт-маттер валиден.
- `persona/sirene-identity` и `persona/sirene-chat-friends` — НЕ дубли: первый описывает идентичность, второй — поведение в групповых чатах. Разделение оправдано.
- `productivity/movefrom-instruments` и `productivity/movefromff` — тоже не дубли: первый — зонтичная архитектура семейства MoveFrom*, второй — runner для FF. ОК.
- Крон-задача `bc1b0ae442f0` (GitHub автосинк) штатно отработала ночью 02:00, `last_status=ok`.
- `config.yaml`: default = `claude-sonnet-4-6`, fallback = `claude-haiku-4-5`, delegation = `claude-haiku-4-5` — иерархия Opus/Sonnet/Haiku соблюдена.
- Auxiliary (vision/compression/session_search) на Haiku — экономично, корректно.

## ⚠️ Что нашла

### Распределение моделей в крон-задачах

| Задача | Сейчас | Правильно | Комментарий |
|---|---|---|---|
| `bc1b0ae442f0` GitHub автосинк | `null` → Sonnet (default) | **Haiku** | Чистый bash: `cp -r`, `git add/commit/push`. Sonnet здесь избыточен и дороже. |
| `ea18f323a671` MoveFromFF — тест с FF API | **Opus** | **Haiku** | Запуск одной команды + проверка кода ошибки. Анализа нет, только выполнение. |
| `dab9865d259e` Opus — план реорганизации GitHub | Opus | Opus ✅ | Правильно: планирование, глубокий анализ. |
| `e7a53b2e2cf2` Сирень self-check (этот!) | Opus | Sonnet | Self-check — это рутинная сверка по чек-листу. Opus переплата. Sonnet справится. |

### Конфиг

- `display.personality: kawaii` ↔ system_prompt требует «Модель: …» и persona = Сирень. **Конфликт**: kawaii-personality перетягивает стиль (звёздочки, desu~), что не соответствует Сирени. Рекомендую `display.personality: helpful` или убрать.
- `display.language: en` при общении на русском с Сашей — стоит сменить на `ru`.
- `display.show_cost: false` — учитывая фокус на бюджет (Haiku-делегация, мониторинг), полезнее `true`.
- `checkpoints.enabled: false` — при активном разработческом потоке (MoveFromFF, hermes-config) checkpoint'ы могли бы спасать сессии. Стоит включить.

### Hermes-репозиторий (upstream)

Последний локальный коммит: **20 May 2026**. С тех пор пришли:
- `fix(security)`: защита от утечки API-ключей в неаутентичные custom endpoints — **важно**.
- `Observe unmentioned Telegram group messages` — новое поведение, может затронуть чат с друзьями.
- `fix(gateway)`: переупорядочивание Telegram-меню (everyday commands first).
- `fix(skills-hub)`: дедупликация по identifier.

**Локальный hermes-agent отстаёт на 3+ дня от upstream — нужно `git pull` + проверить changelog.**

## 💡 Топ-3 улучшения для Саши

1. **Переназначить модели в крон-задачах** (экономия ~70% токенов на ночных задачах):
   - `bc1b0ae442f0` (GitHub автосинк) → `claude-haiku-4-5`
   - `ea18f323a671` (MoveFromFF test) → `claude-haiku-4-5`
   - `e7a53b2e2cf2` (self-check, эта задача) → `claude-sonnet-4-6`
   Команда: `hermes cron edit <id> --model claude-haiku-4-5`.

2. **Обновить hermes-agent**: `cd ~/Documents/Cursor_projects/hermes-agent && git pull` — забрать security-фиксы (особенно про API-key leakage) и новое поведение Telegram group observation. После pull — пересмотреть `gateway.telegram` и `telegram.allowed_chats`.

3. **Привести `display` в соответствие с Сиренью**: `display.personality: helpful` (отключить kawaii), `display.language: ru`, `display.show_cost: true`, `checkpoints.enabled: true`. Это уберёт стилистический конфликт и даст видимость расходов + бэкап сессий.

---
*Сгенерировано Opus-воплощением Сирени, 2026-05-23.*
