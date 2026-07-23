---
name: tutu-corporate-integrations
description: "Подключение к корпоративным сервисам ТУТУ: Confluence, Jira, Exchange EWS, Zulip — credentials, паттерны auth, особенности API."
version: 1.1.0
author: agent
tags: [tutu, confluence, jira, exchange, zulip, ews, ntlm, api, credentials]
platforms: [windows]
---

# ТУТУ — Корпоративные интеграции

Все credentials хранятся в `/home/tkachenkoav/Documents/Cursor_projects/MoveFromFF/.env`

## ⚠️ Правило: минимизация авторизаций

**Одна успешная проверка = достаточно.** Не перебирать форматы логина, методы auth, endpoint-ы в цикле — это блокирует учётку. При первом 401 → остановиться и сообщить пользователю. Не делать больше 2-3 запросов на один сервис за сессию.

Особенно критично для Exchange — Basic auth с неверными credentials быстро триггерит lock-out.

## Confluence + Jira (Atlassian)

- **URL:** `https://dom.tutu.ru`
- **Auth (браузер):** Keycloak SSO — в офисной сети работает без 2FA (Windows domain session), дома требует 2FA
- **Auth (API) — ⚠️ НЕ РАБОТАЕТ через Bearer PAT (май 2026):** ТУТУ перевёл `dom.tutu.ru` на **Keycloak + oauth2-proxy**. Все HTTP-запросы, включая `Authorization: Bearer <PAT>`, редиректятся на `keycloak.tutu.ru/realms/tutu/...`. Токен игнорируется.
- **Env:** `TUTU_ATLASSIAN_TOKEN` (устарел для API), `TUTU_CONFLUENCE_URL=https://dom.tutu.ru`, `TUTU_USERNAME=tkachenkoav@tutu.ru`
- **Версия:** Atlassian Confluence 8.9.4 (on-premise)
- **Срок действия токена:** до 21 февраля 2027 (но бесполезен пока не решён вопрос SSO)

**Вопрос к IT-администраторам ТУТУ:**
> Раньше мог обращаться к Confluence/Jira REST API через Personal Access Token (Bearer-заголовок). Сейчас все запросы к `dom.tutu.ru` через API редиректятся на Keycloak SSO, и токен не принимается. Есть ли способ делать API-запросы к Confluence/Jira программно (не через браузер)? Какой метод аутентификации сейчас поддерживается для REST API?

- **Домашняя страница Confluence:** `pageId=422705401`

## Exchange EWS

- **URL:** `https://cas.tutu.ru/EWS/Exchange.asmx`
- **Версия сервера:** Exchange 2019, build `15.2.1544.14`
- **Auth:** Basic или NTLM/Negotiate. Basic поддерживается (`www-authenticate: Basic` в заголовках). Negotiate — зависает из терминала (Kerberos требует Windows credential store).
- **Env (MoveFromExchange/.env):** `EXCHANGE_URL`, `EXCHANGE_USER=tkachenkoav@tutu.ru`, `EXCHANGE_PASSWORD`
- **Env (MoveFromFF/.env):** `TUTU_EXCHANGE_URL`, `TUTU_USERNAME`, `TUTU_PASSWORD` — те же данные, другие имена ключей
- **SSL:** самоподписанный сертификат — exchangelib обрабатывает сам

**Рабочий шаблон подключения (exchangelib, Kerberos):**
```python
from exchangelib import Credentials, Account, Configuration, BASIC, DELEGATE

creds = Credentials(username=user, password=password)
server = url.split('://')[1].split('/')[0]  # только хост
# НЕ указывать version= (мешает Kerberos negotiate в домене ТУТУ)
# НЕ передавать timeout= в Configuration (TypeError в новых версиях)
config = Configuration(server=server, credentials=creds, auth_type=BASIC)
# ОБЯЗАТЕЛЕН access_type=DELEGATE (иначе ErrorImpersonateUserDenied)
account = Account(primary_smtp_address=user, config=config,
                  autodiscover=False, access_type=DELEGATE)

# Реальная проверка подключения:
count = account.inbox.all().count()
```

**Детальная справка:** см. `movefrom-exchange-contacts` skill → `references/exchange-version-configuration.md`

**✅ Статус (май 2026, в домене):** Inbox ✅, Calendar ✅, GAL resolve_names ✅ — всё работает.
**Auth через Windows Kerberos** — пароль в .env НЕ используется и НЕ нужен (`TUTU_PASSWORD=***` — плейсхолдер). Авторизация через доменную сессию Windows автоматически. Работает ТОЛЬКО в домене (офис). Дома — не работает.
**Ключ**: НЕ указывать version= в Configuration (мешает Kerberos). НЕ передавать timeout=. `access_type=DELEGATE` — обязателен.

**Планируемые кейсы использования Exchange:**
1. Чтение/создание встреч в календаре
2. Анализ входящей почты (inbox)
3. Обогащение contacts.enc полями department/position из GAL

**⚠️ Диагностика:** если подключение "успешно" но данных нет — Account-объект создаётся без сетевого запроса. Реальный запрос только при `inbox.all().count()`, `resolve_names()` и т.д.

## Zulip

- **URL:** `https://zulip.tutu.ru`
- **Auth:** HTTP Basic (`username:api_key`)
- **Env:** `TUTU_ZULIP_URL`, `TUTU_ZULIP_API_KEY`, `TUTU_USERNAME`
- **SSL:** самоподписанный сертификат → `verify=False`
- **✅ Работает из терминала/кода без VPN** — проверено в офисной сети (май 2026)
- **Объём:** 2209 пользователей, 1167 активных людей (май 2026)
- **Получить API key:** `zulip.tutu.ru/#settings/account-and-privacy` → «Управление API-ключом»

```python
import requests, warnings
warnings.filterwarnings('ignore')  # suppress SSL warning

url = os.getenv('TUTU_ZULIP_URL')
api_key = os.getenv('TUTU_ZULIP_API_KEY')
user = os.getenv('TUTU_USERNAME')

# Проверка подключения (один запрос)
r = requests.get(f'{url}/api/v1/users/me', auth=(user, api_key), verify=False, timeout=10)
# r.json() → {'full_name': 'Ткаченко Александр Владимирович', 'email': '...', ...}

# Все пользователи
r = requests.get(f'{url}/api/v1/users', auth=(user, api_key), verify=False, timeout=15)
members = r.json().get('members', [])
active_humans = [m for m in members if m.get('is_active') and not m.get('is_bot')]
# Поля: email, user_id, full_name, is_active, is_bot, is_admin, role
```

**Zulip → contacts.enc bootstrap:** Zulip — основной источник для первичного заполнения справочника контактов (см. `movefrom-exchange-contacts`). Выгружает email + ФИО + zulip_id. Department/position недоступны (не хранятся в Zulip) — обогащать через Exchange когда заработает.

## Zoom API

- **Путь:** `~/USERTOOLS/ZoomAPI/` — задел готов (README.md + test_zoom.py)
- **Auth:** Server-to-Server OAuth (JWT deprecated с сентября 2023)
- **Env:** `ZOOM_ACCOUNT_ID=KqCR_LU4SvODVaVYTu_BYQ`, `ZOOM_CLIENT_ID=xbMKhrqHQU6zk5agAOlWbg`, `ZOOM_CLIENT_SECRET` — **прописаны в `~/.hermes/profiles/anthropic/.env`** (23.07.2026)
- **Приложение:** «Hermes Meeting Bot», Account ID: `KqCR_LU4SvODVaVYTu_BYQ`
- **Статус (23.07.2026):** токен получается ✅, userId `6fU9sTauSgeCx-x27gbikQ` (tkachenkoav@tutu.ru) ✅. Создание встречи ❌ — корпоративный аккаунт ТУТУ не выдаёт scope `meeting:write:meeting`.
- **Ожидает:** разрешения Zoom-админа ТУТУ на scope `meeting:write:meeting` для приложения
- **Fallback:** PMI (Personal Meeting Room) — статическая ссылка `https://zoom.us/j/<PMI>` из профиля zoom.us/profile. Вставляется в `location` Exchange-встречи без API.
- **Создать/найти credentials:** https://marketplace.zoom.us/ → Develop → Build App → Server-to-Server OAuth
- **Scopes:** `meeting:write:meeting` (обязателен), `meeting:read:meeting`, `user:read:user`
- **⚠️ Питфолл scope в UI Marketplace:** поиск по `write` не находит нужный scope. Нужно: перейти в раздел **Meetings** в левом меню → прокрутить список или искать `Create a meeting`. В корпоративном аккаунте ТУТУ admin-версии scopes (`:admin` суффикс) недоступны для выбора.
- **Проверка:** `python3 ~/USERTOOLS/ZoomAPI/test_zoom.py` → должен печатать `join_url`
- **Назначение:** будущий инструмент «назначить встречу» (Exchange + Zoom + Fireflies)

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
- **Zulip API timeout** из терминала — УСТАРЕВШИЙ ПИТФОЛЛ, фактически API работает из офисной сети без проблем (проверено май 2026).
- **Confluence/Jira PAT** — устарел: oauth2-proxy перехватывает все запросы и редиректит на Keycloak. Workaround пока не найден.
- **Exchange Basic auth** — не используется. Аутентификация через Windows Kerberos (доменная сессия). EXCHANGE_PASSWORD в .env = `***` плейсхолдер, реальный пароль не нужен. Не пытаться подобрать или «восстановить».
- **GitHub fine-grained PAT** без `Administration: Read & Write` не может создавать репозитории — добавить через Edit токена на github.com/settings/personal-access-tokens
- **sed** не работает на активных файлах Windows (Device or resource busy) — использовать Python `str.replace()`
- **exchangelib Account() не делает реальный запрос** — объект создаётся без сетевого вызова. `connect()` может вернуть `True` даже без VPN. Реальный запрос происходит только при `resolve_names()`, `account.inbox.all()` и т.д.
- **EXCHANGE_PASSWORD = TUTU_PASSWORD** — один и тот же пароль доменной учётки
