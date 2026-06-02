# Exchange 2019 Configuration (ТУТУ)

## Версия сервера

- **Server:** Exchange 2019 (on-premise)
- **Build:** 15.2.1544.14
- **URL:** https://cas.tutu.ru/EWS/Exchange.asmx

## Kritichny parametry dla exchangelib

### 1. Явная версия Build (ОБЯЗАТЕЛЕН)

```python
from exchangelib import Version, Build

ver = Version(build=Build(15, 2, 1544, 14))
```

**Почему:** без явной версии exchangelib отправляет `ConvertId` запрос для auto-discovery версии сервера. Этот запрос требует дополнительных прав и возвращает UnauthorizedError даже если Basic auth работает.

**История:** найдено при отладке в мае 2026. код exchange_client.py использовал Configuration без версии → ConvertId → UnauthorizedError без VPN.

### 2. ОБЯЗАТЕЛЕН access_type=DELEGATE

```python
from exchangelib import DELEGATE

account = Account(
    primary_smtp_address=user,
    config=config,
    autodiscover=False,
    access_type=DELEGATE,  # ← критично
)
```

**Почему:** без DELEGATE → ErrorImpersonateUserDenied при попытке доступа к почтовому ящику.

### 3. НЕ передавать timeout в Configuration

```python
# ❌ НЕПРАВИЛЬНО
config = Configuration(server=server, ..., timeout=15)  # TypeError

# ✅ ПРАВИЛЬНО
config = Configuration(server=server, ...)
```

**История:** в новых версиях exchangelib (>4.x) параметр `timeout` вызывает TypeError.

### 4. auth_type=BASIC

```python
from exchangelib import BASIC

config = Configuration(
    server=server,
    credentials=creds,
    auth_type=BASIC,  # не NTLM, не DIGEST
    version=ver,
)
```

**Почему:** NTLM/Negotiate работает только в интерактивной сессии Windows (Kerberos), но не работает в Python скриптах. Basic auth работает универсально.

## Полный рабочий шаблон

```python
from exchangelib import (
    Credentials, Account, Configuration,
    BASIC, DELEGATE,
    Version, Build,
)

def create_exchange_account(url: str, user: str, password: str):
    creds = Credentials(username=user, password=password)
    
    # Extract server hostname from URL
    server = url.split('://')[1].split('/')[0]
    
    # Явная версия Exchange 2019
    ver = Version(build=Build(15, 2, 1544, 14))
    
    # Configuration БЕЗ timeout
    config = Configuration(
        server=server,
        credentials=creds,
        auth_type=BASIC,
        version=ver,
    )
    
    # Account С access_type=DELEGATE
    account = Account(
        primary_smtp_address=user,
        config=config,
        autodiscover=False,
        access_type=DELEGATE,
    )
    
    return account

# Реальная проверка подключения (первый запрос вернёт ошибку если auth неверный)
try:
    count = account.inbox.all().count()
    print(f"✅ Connected. Inbox has {count} messages.")
except UnauthorizedError:
    print("❌ Authentication failed")
except Exception as e:
    print(f"❌ Connection error: {e}")
```

## Диагностика

- **Account() возвращает успешно, но account.inbox.all() fail** → Configuration неправильная, добавить версию
- **ErrorImpersonateUserDenied** → забыли `access_type=DELEGATE`
- **TypeError про timeout** → убрать `timeout=` из Configuration
- **401 при resolve_names** → VPN требуется для GAL access

## Ссылки

- Code: `/home/tkachenkoav/Documents/Cursor_projects/MoveFromExchange/movefromexchange/exchange_client.py` (lines 79-87)
- Tests: `tests/test_exchange_client.py` (mock mode checks, реальные тесты нужна VPN)
- TZ: `hermes-workspace/docs/tz/MoveFromExchange_TZ_contacts_v1.0.md`
