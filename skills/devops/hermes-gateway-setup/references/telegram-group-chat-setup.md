# Telegram Group Chat Setup — Debug Notes

## Архитектура фильтрации групп (три уровня)

```
Telegram Bot API → polling → adapter.py
                                 ↓
                    [1] Bot Privacy Mode
                        can_read_all_group_messages
                        (настраивается в @BotFather)
                                 ↓
                    [2] _telegram_allowed_chats()
                        config.yaml: telegram.allowed_chats
                        .env: TELEGRAM_ALLOWED_CHATS
                        (пустое = нет ограничений для DM)
                                 ↓
                    [3] _telegram_group_allowed_chats()
                        .env: TELEGRAM_GROUP_ALLOWED_CHATS
                        (ОТДЕЛЬНЫЙ allowlist для групп!)
                                 ↓
                    Молчаливый drop (без лога!) если не прошёл
```

## Почему `getUpdates` всегда пустой

Gateway использует long polling. Он вычитывает все апдейты и выставляет `offset` так, что повторный `getUpdates` возвращает пустой массив.

**Следствие:** пока gateway запущен, нельзя перехватить апдейты вручную через curl/python — они уже вычитаны.

**Решение:** остановить gateway → написать в группу → вызвать getUpdates → поднять gateway.

## Почему групповые сообщения не попадают в gateway.log

Фильтрация происходит **до** записи в лог (`inbound message:` пишется уже после прохождения всех фильтров). Поэтому в логах видно только chat=400307920 (личка), а группа молчит — даже ошибок нет.

Строка в коде: `plugins/platforms/telegram/adapter.py` ~5884:
```python
if not allowed or chat_id_str not in allowed:
    return False  # silently dropped, no log
```

## Диагностика getMe — проверить Privacy

```bash
TOKEN=$(grep TELEGRAM_BOT_TOKEN ~/.config/hermes/.env | cut -d= -f2)
curl -s "https://api.telegram.org/bot${TOKEN}/getMe" | python3 -m json.tool
```

Ключевые поля:
- `"can_read_all_group_messages": true` — Privacy выключен ✅
- `"can_read_all_group_messages": false` — Privacy включён, бот видит только @mentions ❌

## Порядок отладки молчащего бота в группе

1. Проверить Privacy: `getMe` → `can_read_all_group_messages`
2. Проверить `.env`: `TELEGRAM_ALLOWED_CHATS` и `TELEGRAM_GROUP_ALLOWED_CHATS`
3. Проверить `config.yaml`: `telegram.allowed_chats` (должно быть `''`)
4. Найти ID группы: остановить gateway, написать в группу, `getUpdates`
5. Прописать ID в `TELEGRAM_GROUP_ALLOWED_CHATS` в `.env`
6. Рестарт gateway

## Конфигурация для группы "Сирень Workspace"

После того как ID будет найден (сессия завершилась до получения ID):
```env
TELEGRAM_GROUP_ALLOWED_CHATS=<group_id>
GATEWAY_ALLOW_ALL_USERS=false  # вернуть обратно после настройки
```
