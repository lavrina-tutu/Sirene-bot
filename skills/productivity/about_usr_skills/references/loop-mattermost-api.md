# Loop (Mattermost) API — справочник

**Дата исследования:** 2026-05-29

## Что такое Loop

Loop (`loop.tutu.ru`) — корпоративный мессенджер ТУТУ на базе **Mattermost** (не Zulip!).
API: `/api/v4` (стандартный Mattermost REST API).

Проверка: `curl -s "https://loop.tutu.ru/api/v4/system/ping"` → `{"status":"OK","ActiveSearchBackend":"elasticsearch",...}`

**АКЦ остаётся в Zulip:** `zulip-outsource.tutu.ru` — отдельный инстанс для аутсорсингового контакт-центра.

## Аутентификация

### Personal Access Token (рекомендуется)
Loop → Профиль (правый верхний угол) → Настройки → Безопасность → Токены доступа → Создать.

```bash
curl -H "Authorization: Bearer <TOKEN>" "https://loop.tutu.ru/api/v4/users/me"
```

### Логин/пароль (для получения токена)
```bash
curl -X POST "https://loop.tutu.ru/api/v4/users/login" \
  -H "Content-Type: application/json" \
  -d '{"login_id":"tkachenkoav@tutu.ru","password":"<доменный_пароль>"}'
# Ответ: заголовок Token + тело пользователя
```

## Ключевые эндпоинты

### Пользователи (для MoveFromLoop)
```bash
# Все пользователи (постранично)
GET /api/v4/users?page=0&per_page=200

# Один пользователь
GET /api/v4/users/<user_id>

# Пользователи команды
GET /api/v4/teams/<team_id>/members
```

### Структура пользователя
```json
{
  "id": "abc123",
  "username": "tkachenkoav",
  "email": "tkachenkoav@tutu.ru",
  "first_name": "Александр",
  "last_name": "Ткаченко",
  "nickname": "",
  "position": "PM",
  "roles": "system_user",
  "delete_at": 0,
  "is_bot": false
}
```

`delete_at > 0` → уволен/деактивирован. Фильтровать.

### Каналы и сообщения
```bash
# Список команд (workspaces)
GET /api/v4/teams

# Каналы команды
GET /api/v4/teams/<team_id>/channels?page=0&per_page=200

# Сообщения канала (для будущего MoveFromLoop messages)
GET /api/v4/channels/<channel_id>/posts?page=0&per_page=60
```

## Структура Loop (Mattermost-терминология)
| Термин Loop | Термин Mattermost | Описание |
|---|---|---|
| Канал (stream) | Channel | Объединение пользователей |
| Тема (topic) | Thread / Post topic | Группа сообщений внутри канала |
| Тред | Thread | Цепочка ответов под сообщением |

## Для MoveFromLoop (будущая разработка)

**Цель:** синк контактов Loop → contacts.enc (аналогично MoveFromZulip).

**Минимальный запрос:** `GET /api/v4/users?page=0&per_page=200` с пагинацией.

**Поля маппинга:**
- `username` → `login`
- `email` → `email`
- `first_name + last_name` → `fio`
- `position` → `position`
- `delete_at > 0` → `active: false`
- `is_bot: true` → пропускать

**Credentials в .env:**
```
LOOP_URL=https://loop.tutu.ru
LOOP_TOKEN=<personal_access_token>
```

## Питфолл
- `loop.tutu.ru/api/v1/...` — НЕ работает (это Zulip API). Использовать только `/api/v4/`.
- Аутентификация через `Authorization: Bearer <TOKEN>`, не Basic Auth.
