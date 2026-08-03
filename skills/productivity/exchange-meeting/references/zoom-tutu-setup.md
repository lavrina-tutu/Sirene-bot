# Zoom API — ТУТУ корпоративная конфигурация

## Статус (17.06.2026)
- `marketplace.zoom.us/develop/create` → **404**: developer privileges отключены администратором `tutu-ru.zoom.us`
- ZOOM_* переменных в `~/.config/hermes/.env` нет
- Код-заготовка: `/home/tkachenkoav/USERTOOLS/ZoomAPI/test_zoom.py` (ждёт credentials)
- README: `/home/tkachenkoav/USERTOOLS/ZoomAPI/README.md`

## Обходной путь (пока нет credentials)

Все МСК-переговорки имеют встроенный Zoom Room с **постоянным** join-URL.
Собрать маппинг один раз → хранить в `/home/tkachenkoav/USERTOOLS/ZoomAPI/rooms_map.yaml`:

```yaml
savanna-13floor.room@tutu.ru: https://tutu-ru.zoom.us/j/XXXXXXXXX
taiga-13floor.room@tutu.ru: https://tutu-ru.zoom.us/j/XXXXXXXXX
jungle-13floor.room@tutu.ru: https://tutu-ru.zoom.us/j/XXXXXXXXX
cloudy_land.room@tutu.ru: https://tutu-ru.zoom.us/j/XXXXXXXXX
# ... остальные 13floor комнаты
```

## Как получить credentials (требует IT)

Письмо в IT-отдел:
> Прошу выдать developer privileges на `tkachenkoav@tutu.ru` для создания Server-to-Server OAuth приложения (account-level, scopes: `meeting:write:meeting`, `meeting:read:meeting`, `user:read:user`). Либо создайте app от вашего имени и передайте Account ID / Client ID / Client Secret.

После получения → добавить в `~/.config/hermes/.env`:
```
ZOOM_ACCOUNT_ID=xxxxxxxxxxxxxxxxxxxxxx
ZOOM_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxx
ZOOM_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Затем проверить: `python3 /home/tkachenkoav/USERTOOLS/ZoomAPI/test_zoom.py`

## Ключевые ограничения

- **PAT (Personal Access Token) для Zoom REST API не существует** — только S2S OAuth или user-level OAuth
- **Zoom add-in Outlook** нельзя дёрнуть из exchangelib/EWS — только через UI
- **IsOnlineMeeting в EWS** относится к Microsoft Teams, не Zoom

## S2S OAuth flow (когда credentials будут)

```
POST https://zoom.us/oauth/token
  grant_type=account_credentials&account_id={ZOOM_ACCOUNT_ID}
  Authorization: Basic base64(CLIENT_ID:CLIENT_SECRET)
→ access_token (живёт 1 час, кэшировать)

POST https://api.zoom.us/v2/users/me/meetings
  Authorization: Bearer {access_token}
{
  "topic": "...",
  "type": 2,
  "start_time": "2026-06-18T15:00:00",
  "duration": 60,
  "timezone": "Europe/Moscow",
  "agenda": "...",
  "settings": {
    "join_before_host": true,
    "waiting_room": false,
    "mute_upon_entry": true,
    "auto_recording": "none"
  }
}
→ join_url (домен: tutu-ru.zoom.us)
```
