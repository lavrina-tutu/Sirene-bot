---
name: zoom-api-integration
description: "zoom: создание конференции Server-to-Server API"
version: 1.0.1
author: agent
license: MIT
platforms: [linux]
tags: [zoom, api, oauth, meetings, exchange, tutu]
---

# Zoom API Integration

## Способ аутентификации: Server-to-Server OAuth

Единственный актуальный способ (JWT deprecated с сентября 2023). Не требует user consent / браузера / refresh-токенов.

**Три статичных значения из Zoom Marketplace:**
- `ZOOM_ACCOUNT_ID`
- `ZOOM_CLIENT_ID`
- `ZOOM_CLIENT_SECRET`

Хранятся в `~/.hermes/profiles/anthropic/.env`.

**Текущий статус (23.07.2026):** credentials получены, токен работает ✅. User ID Саши: `6fU9sTauSgeCx-x27gbikQ` (lavrina@tutu.ru). Создание встреч блокируется — корп. аккаунт ТУТУ не даёт scope `meeting:write:meeting`. Ожидает разрешения от Zoom-админа ТУТУ.

## Получение токена

```python
import base64, requests

creds = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
r = requests.post(
    "https://zoom.us/oauth/token",
    params={"grant_type": "account_credentials", "account_id": ACCOUNT_ID},
    headers={"Authorization": f"Basic {creds}"},
)
token = r.json().get("access_token")
```

## Создание встречи

```python
resp = requests.post(
    f"https://api.zoom.us/v2/users/{user_id}/meetings",
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    json={
        "topic": "Название встречи",
        "type": 2,  # scheduled
        "start_time": "2026-07-23T15:00:00Z",
        "duration": 30,
        "timezone": "Europe/Moscow",
        "agenda": "Повестка"
    }
)
join_url = resp.json()["join_url"]
```

## Настройка в Zoom Marketplace

1. https://marketplace.zoom.us/ → **Develop → Build App**
2. Тип: **Server-to-Server OAuth** → Create
3. Имя: `Hermes Meeting Bot`
4. Вкладка **App Credentials** → скопировать Account ID, Client ID, Client Secret
5. **Scopes → Add Scopes:**
   - `meeting:write:meeting:admin` — создание встреч (**может быть недоступен в корп. аккаунте**)
   - `meeting:read:meeting:admin`
   - `user:read:user:admin`
6. **Activation → Activate your app**

**Найти своё приложение:** Develop → **My Apps**

## Корпоративный аккаунт ТУТУ — ограничения

Scope `meeting:write:meeting:admin` может быть недоступен — корп. политика ограничивает. Симптом: scope не появляется при поиске в Add Scopes, или: API 400 `code:4711, does not contain scopes:[meeting:write:meeting]`.

**Решения:**
1. Обратиться к Zoom-админу ТУТУ с запросом разрешить `meeting:write:meeting:admin` для App ID приложения
2. PMI fallback: Personal Meeting Room — статическая ссылка `https://zoom.us/j/<PMI>` (узнать на zoom.us/profile → Personal Meeting ID). Не требует API, вставляется в Exchange встречу как `location`.

## Инфраструктура на VM

- Код: `~/USERTOOLS/ZoomAPI/test_zoom.py` — рабочий скрипт (получение токена + создание встречи)
- README: `~/USERTOOLS/ZoomAPI/README.md`
- Credentials: `~/.hermes/profiles/anthropic/.env` → `ZOOM_ACCOUNT_ID`, `ZOOM_CLIENT_ID`, `ZOOM_CLIENT_SECRET`

## Pitfalls

- **Scope недоступен в корп. аккаунте** — при поиске в Marketplace видны не все scopes, если аккаунт корпоративный с ограничениями. Не искать долго — спросить Zoom-админа.
- **Как найти scope в Marketplace UI** — в Add Scopes есть левый список разделов (Meetings, Users, AI Companion и др.) и поиск. Поиск по `write` или `Create a meeting` надёжнее чем `meeting:write:meeting:admin` — ищет по описанию. Если scope не находится ни так ни так — он недоступен для аккаунта (корп. ограничение).
- **Client Secret показывается один раз** — скопировать сразу при создании приложения, потом не восстановить.
- **Токен создаётся без сетевого запроса** — `Account()` (exchangelib) аналогично `requests.post(token_url)` — реальная проверка только при первом API-вызове.
- **Confluence страница с инструкцией** (pageId `511559466`) — недоступна через PAT для записи (SSO-protected space). Инструкцию передавать пользователю текстом в чат, не через API.
- **В Marketplace UI scope ищется по разделу, не по строке.** «Meetings» в левом sidebar → раскрывается полный список scope этого раздела. Поиск по тексту (`write`, `Create a meeting`) работает лучше чем ввод технического имени (`meeting:write:meeting:admin`). Если scope не появляется — он заблокирован корп. политикой, не ошибка UI.
- **`user:read:user:admin` и `meeting:read:meeting:admin`** — как правило доступны в корп. аккаунте даже когда `meeting:write` заблокирован. Приложение можно активировать с этими двумя scope и проверить токен, создание встреч не заработает но факт блокировки подтвердится кодом `4711`.