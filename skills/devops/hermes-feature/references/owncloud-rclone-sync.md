# ownCloud WorkVault синк — конфигурация и паттерны

> Установлено 02.06.2026 в ходе миграции Windows → VM

## Конфигурация

- **Remote:** `owncloud` (rclone WebDAV)
- **URL:** `https://owncloud.tutu.ru/remote.php/webdav`
- **Путь на ownCloud:** `owncloud:WorkVault` (НЕ `Documents/WorkVault` — исправлено 02.06.2026)
- **Локальный путь:** `~/WorkVault`
- **Unit:** `~/.config/systemd/user/owncloud-sync.service`
- **Таймер:** `~/.config/systemd/user/owncloud-sync.timer` (каждые 10 мин)
- **Логи:** `~/.local/share/hermes/logs/owncloud-sync.log`
- **Исключения:** `~/.config/rclone/workvault-exclude.lst`

## Оптимизированный ExecStart (применён 02.06.2026)

```bash
ExecStart=/usr/bin/rclone sync /home/tkachenkoav/WorkVault owncloud:WorkVault \
  --transfers 4 --checkers 8 \
  --retries 3 --low-level-retries 10 \
  --timeout 60s --contimeout 30s \
  --size-only \
  --exclude-from=/home/tkachenkoav/.config/rclone/workvault-exclude.lst \
  --log-file=/home/tkachenkoav/.local/share/hermes/logs/owncloud-sync.log \
  --log-level INFO
```

**Почему `--size-only`:** WebDAV плохо поддерживает чексуммы → сравниваем по размеру. Даёт ускорение в 5-10x на холостых прогонах.

## Принудительный запуск

```bash
systemctl --user start owncloud-sync.service
```

Безопасно при работающем таймере — `Type=oneshot`, конкурентный запуск systemd блокирует.

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

## Питфоллы

- Путь `owncloud:Documents/WorkVault` — НЕВЕРНЫЙ, файлы идут не туда. Верный: `owncloud:WorkVault`
- После правки unit-файла обязательно: `systemctl --user daemon-reload`
- `--fast-list` на ownCloud может давать непредсказуемые результаты — не использовать
- Симлинки в `~/.hermes/scripts/` не работают для `cronjob(script=...)` — нужна физическая копия файла
