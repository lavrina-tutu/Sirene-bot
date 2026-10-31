# Profile Isolation for External Memory Providers (Honcho)

## Проблема

При подключении external memory provider (например, Honcho) к одному профилю Hermes нужно гарантировать, что остальные профили продолжают использовать built-in память без изменений.

## Решение: profile-specific honcho.json

Honcho загружает конфиг в порядке приоритета:
1. `$HERMES_HOME/honcho.json` (profile-specific)
2. `~/.hermes/honcho.json` (shared)
3. `~/.honcho/config.json` (global)

**Ключевой принцип:** класть `honcho.json` в `$HERMES_HOME` конкретного профиля — тогда другие профили его НЕ видят.

### Пример структуры

```
~/.hermes/profiles/default/honcho.json   ← Honcho активен ТОЛЬКО для default
~/.hermes/profiles/tz-dev/               ← нет honcho.json → built-in память
```

### Конфигурация

**default profile** (`~/.hermes/profiles/default/config.yaml`):
```yaml
memory:
  provider: honcho
```

**tz-dev profile** — НЕ добавлять `memory.provider`. Встроенная память работает автоматически.

### honcho.json для self-hosted

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
      "workspace": "hermes"
    }
  }
}
```

### Multi-peer изоляция

Honcho моделирует каждый Hermes-профиль как отдельный AI peer:
- `hermes` → default profile AI peer
- `hermes.tz-dev` → tz-dev AI peer (если бы Honcho был активен)

AI peers строят независимые representations из своих наблюдений. Даже если два профиля подключены к одному Honcho серверу, их карточки не пересекаются.

### Gateway identity mapping

Для Telegram-пользователей:
```json
{
  "pinUserPeer": true,
  "runtimePeerPrefix": "telegram_"
}
```
- `pinUserPeer: true` — все gateway-пользователи маппятся на `peerName`
- `runtimePeerPrefix` — namespace для runtime IDs (`telegram_400307920`)

### Верификация изоляции

```bash
hermes memory status --profile default
# Должно показать: Honcho active, baseUrl=http://localhost:8000

hermes memory status --profile tz-dev
# Должно показать: built-in only (без Honcho)
```

## Питфоллы

1. **Global honcho.json** — если положить в `~/.honcho/config.json`, ВСЕ профили его увидят. Всегда используйте profile-specific путь.
2. **`memory.provider` в неправильном профиле** — даже если honcho.json отсутствует, установка `memory.provider: honcho` в config.yaml профиля заставит Hermes искать Honcho конфиг. Не задавайте `memory.provider` в профилях, где Honcho не нужен.
3. **Shared workspace** — все профили в одном workspace видят один user peer. Это фича (единая модель пользователя), но если нужна полная изоляция — используйте разные workspace.
