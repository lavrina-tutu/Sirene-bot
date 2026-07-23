# Zoom API — Server-to-Server OAuth (23.07.2026)

## Статус
- Приложение создано: «Hermes Meeting Bot»
- Credentials прописаны в `~/.hermes/profiles/anthropic/.env`
- Токен получается ✅, создание встреч ❌ (нет scope `meeting:write`)

## Credentials
- `ZOOM_ACCOUNT_ID=KqCR_LU4SvODVaVYTu_BYQ`
- `ZOOM_CLIENT_ID=xbMKhrqHQU6zk5agAOlWbg`
- `ZOOM_CLIENT_SECRET=MKOAcR113M2okGzLrOR5y2F71RyGv8tM`
- User ID: `6fU9sTauSgeCx-x27gbikQ` (tkachenkoav@tutu.ru)

## Тест-скрипт
`/home/tkachenkoav/USERTOOLS/ZoomAPI/test_zoom.py`

## Блокер
Корпоративный аккаунт ТУТУ не даёт scope `meeting:write:meeting:admin` и `meeting:write:meeting`.
Нужно: обратиться к Zoom-администратору ТУТУ с запросом разрешить scope для app «Hermes Meeting Bot».

## Confluence pitfall (обнаружен 23.07.2026)
Страница 511559466 («Настройка ссылки Zoom») возвращает 404 через PAT — пространство под SSO.
Публикация инструкций через API невозможна для этого пространства. Решение: пользователь копирует текст вручную.

## Паттерн: пустая страница vs несуществующая
- 404 = нет прав или SSO-пространство
- 200 + `body.storage.value = ''` = страница существует как заглушка (пустая)
Не путать — в обоих случаях содержимое не публикуем через API.
