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

## Оптимизированный unit-файл (актуально 03.06.2026)

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
  --log-file=/home/tkachenkoav/.local/share/hermes/logs/owncloud-sync.log \
  --log-level INFO
```

> ⚠️ **`--size-only` УБРАН** (03.06.2026 по рекомендации Opus).
> Причина: пропускает изменения одного размера — правки строки в md одинаковой длины,
> ре-шифрование contacts.enc с тем же числом записей. Дефолт rclone (size+mtime) надёжнее.

## Объяснение флагов

| Флаг | Зачем |
|---|---|
| `--transfers 4` | Параллельные передачи файлов (ускорение) |
| `--checkers 8` | Параллельная проверка изменений |
| `--retries 3` | Повторные попытки при ошибке |
| `--low-level-retries 10` | Retry на уровне HTTP |
| `--timeout 60s` | Таймаут операции |
| `--contimeout 30s` | Таймаут установки соединения |

## Синк после инструментов (03.06.2026)

MoveFromFF, MoveFromZulip, DialogBacklog запускают синк по завершению:
```python
import subprocess
try:
    subprocess.run(
        ["systemctl", "--user", "start", "--no-block", "owncloud-sync.service"],
        check=False, timeout=5,
    )
except Exception:
    pass
```
Таймер оставить 10 мин — принудительный запуск + таймер = достаточно.

## Проверка синка

```bash
# Сравнить количество файлов локально и на ownCloud:
find ~/WorkVault -type f | wc -l
rclone ls owncloud:WorkVault/ | wc -l

# Свежие встречи (должны совпадать):
ls ~/WorkVault/Meetings/NewMeetings/ | tail -5
rclone ls owncloud:WorkVault/Meetings/NewMeetings/ | tail -5
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
