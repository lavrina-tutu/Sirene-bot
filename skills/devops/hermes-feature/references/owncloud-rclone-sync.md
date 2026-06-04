# ownCloud WorkVault синк — конфигурация и паттерны

> Установлено 02.06.2026 в ходе миграции Windows → VM
> Обновлено 03.06.2026: убрали --size-only, добавили триггеры после инструментов

## Конфигурация

- **Remote:** `owncloud` (rclone WebDAV)
- **URL:** `https://owncloud.tutu.ru/remote.php/webdav`
- **Путь на ownCloud:** `owncloud:WorkVault` (НЕ `Documents/WorkVault` — исправлено 02.06.2026)
- **Локальный путь:** `~/WorkVault`
- **Unit:** `~/.config/systemd/user/owncloud-sync.service`
- **Таймер:** `~/.config/systemd/user/owncloud-sync.timer` (каждые 10 мин)
- **Логи:** `~/.local/share/hermes/logs/owncloud-sync.log`
- **Исключения:** `~/.config/rclone/workvault-exclude.lst`

## Оптимизированный ExecStart (актуальный — без --size-only)

```bash
ExecStart=/usr/bin/rclone sync /home/tkachenkoav/WorkVault owncloud:WorkVault \
  --transfers 4 --checkers 8 \
  --retries 3 --low-level-retries 10 \
  --timeout 60s --contimeout 30s \
  --exclude-from=/home/tkachenkoav/.config/rclone/workvault-exclude.lst \
  --log-file=/home/tkachenkoav/.local/share/hermes/logs/owncloud-sync.log \
  --log-level INFO
```

**Почему НЕ `--size-only`:** изменения одного размера (правки md-строки, ре-шифрование contacts.enc) пропускаются незаметно. По умолчанию rclone сравнивает size+mtime — достаточно и надёжнее. `--checksum` точнее, но дорог для WebDAV.

## Таймер: оставить 10 минут

Не менять на 5 мин — при наличии триггеров после инструментов учащение бессмысленно и увеличивает нагрузку на ownCloud вдвое без пользы.

## Триггер синка после инструментов (паттерн)

MoveFromFF, MoveFromZulip, DialogBacklog — каждый в конце успешного выполнения запускает синк:

```python
import subprocess
try:
    subprocess.run(
        ["systemctl", "--user", "start", "--no-block", "owncloud-sync.service"],
        check=False, timeout=5,
    )
except Exception:
    pass  # синк не критичен для завершения инструмента
```

**Флаги обязательны:**
- `--no-block` — не блокировать инструмент ожиданием rclone
- `check=False` — не падать, если systemd недоступен

## Атомарная запись contacts.enc

Любой инструмент, пишущий contacts.enc, обязан использовать атомарный паттерн:

```python
import os
tmp = path.with_suffix(".enc.tmp")
tmp.write_bytes(data)
os.replace(tmp, path)   # atomic rename, не truncate+write
```

Без этого rclone может залить частично записанный бинарь в ownCloud.

## Принудительный запуск

```bash
systemctl --user start owncloud-sync.service
```

Безопасно при работающем таймере — `Type=oneshot`, конкурентный запуск systemd блокирует (ставит в очередь).

## Проверка статуса

```bash
# Последний запуск
systemctl --user status owncloud-sync.service --no-pager | tail -5

# Лог последних прогонов
tail -20 ~/.local/share/hermes/logs/owncloud-sync.log

# Файлы на ownCloud
rclone ls owncloud:WorkVault/Meetings/NewMeetings/ | wc -l
```

## Метрики нормального прогона (холостой)

- Elapsed time: **0.4–0.5с** (без изменений)
- Checks: ~973 файла
- Status: `There was nothing to transfer`

## Безопасность

- `~/.config/rclone/rclone.conf` — права 600 ✅
- Пароль в формате rclone obscure (base64-обфускация, не шифрование) — known limitation
- `RCLONE_CONFIG_PASS` (полное шифрование конфига) НЕ применять — ломает автозапуск из systemd без пароля
- Лог-файл: права 600
- `workvault-exclude.lst` исключает .env и токены из синка
- `TUTU_DOMAIN_PASSWORD` хранится в `~/.config/hermes/.env` — нужен для Keycloak SSO (Grafana и др.)

## Доступ к корпоративным SSO-системам (Grafana, Confluence)

Grafana (`grafana.monitoring.tutu.ru`) и Confluence защищены Keycloak SSO.
- VM доступна по VPN → curl доходит, но нужна авторизация
- `web_extract` блокирует внутренние адреса — использовать `curl` + сессионные куки
- Доменный пароль: `TUTU_DOMAIN_PASSWORD` в `.env`
- Логин: `tkachenkoav` (без домена для Keycloak)

## Питфоллы

- **`--size-only` — ОПАСНО:** пропускает изменения одного размера. Убрать из конфига.
- Путь `owncloud:Documents/WorkVault` — НЕВЕРНЫЙ. Верный: `owncloud:WorkVault`
- После правки unit-файла обязательно: `systemctl --user daemon-reload`
- `--fast-list` на ownCloud может давать непредсказуемые результаты — не использовать
- Симлинки в `~/.hermes/scripts/` не работают для `cronjob(script=...)` — нужна физическая копия файла
- contacts.enc без атомарной записи → риск залить битый бинарь при параллельном синке
