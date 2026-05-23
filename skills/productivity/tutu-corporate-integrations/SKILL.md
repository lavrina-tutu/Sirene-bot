---
name: tutu-corporate-integrations
description: "Подключение к корпоративным сервисам ТУТУ: Confluence, Jira, Exchange EWS, Zulip — credentials, паттерны auth, особенности API."
version: 1.1.0
author: agent
tags: [tutu, confluence, jira, exchange, zulip, ews, ntlm, api, credentials]
platforms: [windows]
---

# ТУТУ — Корпоративные интеграции

Все credentials хранятся в `C:/Users/tkachenkoav/Documents/Cursor_projects/MoveFromFF/.env`

## Confluence + Jira (Atlassian)

- **URL:** `https://dom.tutu.ru`
- **Auth:** Personal Access Token (Bearer)
- **Env:** `TUTU_ATLASSIAN_TOKEN`, `TUTU_CONFLUENCE_URL=https://dom.tutu.ru`, `TUTU_USERNAME=tkachenkoav@tutu.ru`
- **Версия:** Atlassian Confluence 8.9.4 (on-premise)
- **Получить токен:** `dom.tutu.ru` → профиль → Настройки → Личные маркеры доступа → Создать маркер
- **Один токен работает для Confluence и Jira** (один инстанс Atlassian)
- **Домашняя страница Confluence:** `pageId=422705401` — тестовые страницы создавать там же
- **Срок действия токена:** до 21 февраля 2027

```python
import requests
headers = {'Authorization': f'Bearer {token}'}
r = requests.get('https://dom.tutu.ru/rest/api/content', headers=headers)
```

## Exchange EWS

- **URL:** `https://cas.tutu.ru/EWS/Exchange.asmx`
- **Auth:** NTLM (`requests_ntlm.HttpNtlmAuth`)
- **Env:** `TUTU_EXCHANGE_URL`, `TUTU_USERNAME`, `TUTU_PASSWORD`
- **SSL:** самоподписанный сертификат → `verify=False`
- **OWA:** `https://cas.tutu.ru/owa/`
- **Проверка доступности:** `curl -o /dev/null -w "%{http_code}" https://cas.tutu.ru/EWS/Exchange.asmx` → 401 = сервер есть
- **Библиотеки:** `requests`, `requests-ntlm`

```python
from requests_ntlm import HttpNtlmAuth
r = requests.get(url, auth=HttpNtlmAuth(user, password), verify=False)
```

**⚠️ Ubuntu:** при переносе заменить хранение пароля — в `.env` с правами `chmod 600`.

## Zulip

- **URL:** `https://zulip.tutu.ru`
- **Auth:** HTTP Basic (`username:api_key`)
- **Env:** `TUTU_ZULIP_URL`, `TUTU_ZULIP_API_KEY`, `TUTU_USERNAME`
- **SSL:** самоподписанный сертификат → `verify=False`
- **API недоступен напрямую из терминала** — только через браузер или корпоративную сеть/VPN
- **Получить API key:** `zulip.tutu.ru/#settings/account-and-privacy` → «Управление API-ключом» (требует ввод пароля в браузере)

```python
r = requests.get(f'{url}/api/v1/users/me',
    auth=('tkachenkoav@tutu.ru', api_key), verify=False)
```

## GitHub

- **Пользователь:** `ialextkachenko-byte`
- **Токен:** Fine-grained PAT, env: `GITHUB_TOKEN`
- **Нужные права:** Contents R/W + Metadata R (auto) + Administration R/W (для создания репо)
- **Репозитории:**
  - `workvault-tools` — код инструментов MoveFrom*
  - `hermes-config` — конфиг Hermes, скиллы, бэклог
- **Автосинк:** cron каждую ночь в 02:00 МСК

## Pitfalls

- **requests_ntlm** нужно устанавливать отдельно: `pip install requests-ntlm`
- **keyring** (Windows Credential Manager) и `cmdkey` — разные хранилища, `keyring` не видит `cmdkey` записи. Проще хранить в `.env` локально.
- **Zulip API timeout** из терминала — не ошибка кода, сеть не пропускает прямые запросы. Для теста — только через браузер.
- **GitHub fine-grained PAT** без `Administration: Read & Write` не может создавать репозитории — добавить через Edit токена на github.com/settings/personal-access-tokens
- **sed** не работает на активных файлах Windows (Device or resource busy) — использовать Python `str.replace()`
