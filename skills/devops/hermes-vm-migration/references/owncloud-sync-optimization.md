# ownCloud WebDAV синк — оптимизация и эксплуатация

## Верный путь
- Удалённая папка: `owncloud:WorkVault` (в корне, БЕЗ Documents)
- Веб-интерфейс: https://owncloud.tutu.ru/index.php/f/6966632
- Проверка: `rclone ls owncloud:WorkVault/ | head -5`

## Принудительный запуск

```bash
systemctl --user start owncloud-sync.service
# Проверить статус:
systemctl --user status owncloud-sync.service
# Проверить файлы на ownCloud:
rclone ls owncloud:WorkVault/Meetings/NewMeetings/ | wc -l
```

`Type=oneshot` — systemd не допустит конкурентный запуск, безопасно.

## Оптимизированный unit-файл

```ini
[Unit]
Description=ownCloud WorkVault sync
After=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/rclone sync /home/tkachenkoav/WorkVault owncloud:WorkVault \
  --transfers 4 --checkers 8 \
  --retries 3 --low-level-retries 10 \
  --timeout 60s --contimeout 30s \
  --size-only \
  --log-file=/home/tkachenkoav/.local/share/hermes/logs/owncloud-sync.log \
  --log-level INFO
```

## Объяснение флагов

| Флаг | Зачем |
|---|---|
| `--transfers 4` | Параллельные передачи файлов (ускорение) |
| `--checkers 8` | Параллельная проверка изменений |
| `--size-only` | Не считать чексуммы (WebDAV их плохо поддерживает, ускоряет) |
| `--retries 3` | Повторные попытки при ошибке |
| `--low-level-retries 10` | Retry на уровне HTTP |
| `--timeout 60s` | Таймаут операции |
| `--contimeout 30s` | Таймаут установки соединения |

## Проверка синка

```bash
# Сравнить количество файлов локально и на ownCloud:
find ~/WorkVault -type f | wc -l
rclone ls owncloud:WorkVault/ | wc -l

# Свежие встречи (должны совпадать):
ls ~/WorkVault/Meetings/NewMeetings/ | tail -5
rclone ls owncloud:WorkVault/Meetings/NewMeetings/ | tail -5
```

## Очистка мусорных бэкапов unit-файлов

После правок накапливаются `.bak-*` файлы:
```bash
ls ~/.config/systemd/user/*.bak-*
# Удалить после проверки что активный unit верный:
rm ~/.config/systemd/user/*.bak-*
systemctl --user status owncloud-sync.timer  # убедиться что не сломали
```

## Диагностика проблем

```bash
# Последние строки лога:
tail -30 ~/.local/share/hermes/logs/owncloud-sync.log

# Проверка rclone конфига:
rclone config show owncloud

# Тест соединения:
rclone lsd owncloud:
```
