---
name: hermes-vm-migration
description: "Миграция Hermes Agent с Windows на Linux VM (AlmaLinux/Ubuntu). Архитектура, блоки работ, SSH-доступ, systemd, Syncthing, адаптация USERTOOLS."
version: 1.0.0
author: Сирень
tags: [hermes, migration, linux, vm, almalinux, systemd, ssh]
platforms: [linux, windows]
---

# Hermes VM Migration

Перенос Hermes Agent с Windows 10 на удалённую Linux VM. Два агента живут независимо.

## Целевая VM (ТУТУ)

- Хост: `hermes-agents.devel.tutu.ru` / `10.2.24.163`
- OS: AlmaLinux 9.7
- RAM: 11Gi, CPU: 4, Disk: 195G free
- SSH: `tkachenkoav@hermes-agents.devel.tutu.ru` (ключевая авторизация)
- Доступ: только через корпоративный VPN
- sudo: есть (passwordless, группа `sudo_hermes-agents.devel.tutu.ru`)
- Firewall: api.telegram.org, api.anthropic.com, github.com, fireflies.ai — всё открыто

## Архитектурные решения (зафиксированы с Сашей)

- **Два независимых агента**: Windows-агент и VM-агент живут отдельными судьбами
- **Отдельный Telegram-бот** для VM-инстанса (новый токен через @BotFather)
- **Клон личности** с немного другим именем (переименовать позже если надо)
- **Windows работает** до полного переезда всего — не отключать раньше времени
- **Кроны дублирующие** — разносить по времени, не запускать параллельно одинаковые
- **Бэкапы** — на локале перед стартом каждого блока
- **WorkVault синхронизация** — Syncthing (realtime, ≤10 мин), Yandex.Disk как fallback
- **USERTOOLS** — все переносим вручную, адаптируем под Linux (нет GUI, нет Windows API)
- **Memory/сессии** — переписываем всё что знаем на момент миграции, далее независимо
- **Всё ПО поднимаем сами** (Python, systemd, Syncthing и т.д.) — не через IT-заявки

## ТЗ миграции

Файл: `C:\Users\tkachenkoav\WorkVault\Hermes-Backlog\MigrationToVM\TZ.md`

Блоки:
- **Блок 0** — Подготовка VM (Python, git, структура директорий)
- **Блок 1** — MVP gateway (новый TG-бот, systemd unit, базовая работа)
- **Блок 2** — Личность Сирени (memory, skills, профиль)
- **Блок 3** — Кроны (адаптация путей, замена Windows-команд)
- **Блок 4** — USERTOOLS (перенос и адаптация всех инструментов)
- **Блок 5** — WorkVault синхронизация (Syncthing)
- **Блок 6** — Финальный переезд и верификация

**Принцип приёмки:** после каждого блока Саша сам проверяет как пользователь (без знаний программирования).

## Целевой layout на VM

```
/home/tkachenkoav/
├── hermes-agent/          # код (git clone)
├── .config/hermes/        # config.yaml, .env, jobs.json
├── .local/share/hermes/   # sessions/, skills/, memory/, logs/
├── WorkVault/             # рабочие заметки (Syncthing ↔ ноут)
├── YandexDisk/            # личные заметки (если нужно)
└── USERTOOLS/             # инструменты Сирени
```

## SSH подключение

```bash
ssh tkachenkoav@hermes-agents.devel.tutu.ru
# или по IP:
ssh tkachenkoav@10.2.24.163
```

Проверка что VM жива и доступна:
```bash
ssh -o ConnectTimeout=10 tkachenkoav@10.2.24.163 "echo OK && hostname && uname -a"
```

## Проверка доступов с VM

```bash
ssh tkachenkoav@10.2.24.163 "
  curl -s --max-time 5 -o /dev/null -w '%{http_code}' https://api.telegram.org && echo telegram
  curl -s --max-time 5 -o /dev/null -w '%{http_code}' https://api.anthropic.com && echo anthropic
  curl -s --max-time 5 -o /dev/null -w '%{http_code}' https://api.github.com && echo github
  curl -s --max-time 5 -o /dev/null -w '%{http_code}' https://api.fireflies.ai && echo fireflies
"
```

## GUI на VM: XFCE + VNC + Obsidian (Блок 0.5)

Делается до Hermes gateway — даёт ранний визуальный результат.

**Проверено на AlmaLinux 9.7:** XFCE, TigerVNC 1.15.0, rclone 1.71.0 — всё есть в dnf.

```bash
# 1. Установка
sudo dnf groupinstall -y "Xfce"
sudo dnf install -y tigervnc-server rclone

# 2. xstartup
mkdir -p ~/.vnc
cat > ~/.vnc/xstartup << 'EOF'
#!/bin/bash
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
exec startxfce4
EOF
chmod +x ~/.vnc/xstartup

# 3. VNC пароль и запуск
vncpasswd   # ввести пароль
vncserver :1 -geometry 1280x800 -depth 24

# 4. Autostart
echo '@reboot /usr/bin/vncserver :1 -geometry 1280x800 -depth 24' | crontab -

# 5. Obsidian AppImage
VER=$(curl -s https://api.github.com/repos/obsidianmd/obsidian-releases/releases/latest | grep '"tag_name"' | cut -d'"' -f4 | tr -d v)
wget -O ~/obsidian.AppImage "https://github.com/obsidianmd/obsidian-releases/releases/latest/download/Obsidian-${VER}.AppImage"
chmod +x ~/obsidian.AppImage
# Запуск из VNC:
~/obsidian.AppImage --no-sandbox

# 6. Yandex.Disk через rclone WebDAV
# rclone config → new remote → WebDAV → https://webdav.yandex.ru → yandex → логин/пароль приложения
rclone mount yandex: ~/YandexDisk --daemon --vfs-cache-mode writes
```

**Подключение Саши (SSH-туннель — порт наружу НЕ открывать!):**
```bash
# На ноуте Windows:
ssh -L 5901:localhost:5901 tkachenkoav@hermes-agents.devel.tutu.ru
# Затем VNC-клиент → localhost:5901
```

**Pitfalls GUI:**
- Obsidian требует `--no-sandbox` (нет user namespace на серверном Linux)
- Yandex WebDAV требует пароль приложения если включена 2FA (не обычный пароль)
- VNC порт 5901 открывать наружу нельзя — только через SSH-туннель

## Systemd unit для gateway

```ini
[Unit]
Description=Hermes Agent Gateway (VM instance)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/tkachenkoav/hermes-agent
Environment=HERMES_CONFIG=/home/tkachenkoav/.config/hermes/config.yaml
EnvironmentFile=/home/tkachenkoav/.config/hermes/.env
ExecStart=/home/tkachenkoav/hermes-agent/.venv/bin/python -m hermes_cli.main gateway run
Restart=on-failure
RestartSec=10
StandardOutput=append:/home/tkachenkoav/.local/share/hermes/logs/gateway.log
StandardError=append:/home/tkachenkoav/.local/share/hermes/logs/gateway.err

[Install]
WantedBy=default.target
```

Управление:
```bash
systemctl --user daemon-reload
systemctl --user enable --now hermes-gateway
systemctl --user status hermes-gateway
journalctl --user -u hermes-gateway -f
```

**Обязательно:** `loginctl enable-linger tkachenkoav` — gateway работает без активной SSH-сессии.

## Адаптация Windows → Linux (чеклист)

При переносе кода и конфигов искать и заменять:

| Windows | Linux |
|---|---|
| `C:\Users\tkachenkoav\...` | `/home/tkachenkoav/...` |
| `AppData\Local\hermes\` | `~/.config/hermes/` или `~/.local/share/hermes/` |
| `taskkill /PID /F` | `kill -9 <pid>` |
| `schtasks /...` | `systemctl --user ...` |
| `wscript.exe`, `*.vbs`, `*.bat` | `bash -c "..."` |
| `python.exe` | `~/hermes-agent/.venv/bin/python` |
| `/c/Users/...` (MSYS) | нативные Linux пути |
| `cmd /c ...` | прямой shell-вызов |
| `os.sep = '\\'` | `os.sep = '/'` |
| `pathlib.WindowsPath` | `pathlib.PurePosixPath` |
| `winreg`, `pywin32`, `winsound` | убрать/заглушить |

Поиск Windows-специфики в коде:
```bash
grep -rn 'C:\\\\' hermes_cli/ USERTOOLS/ --include="*.py"
grep -rn 'taskkill\|schtasks\|wscript\|winreg\|pywin32' . --include="*.py"
```

## Syncthing для WorkVault

```bash
# Установка на VM
sudo dnf install syncthing   # или из официального RPM
systemctl --user enable --now syncthing

# Установить на ноут Windows если ещё нет
# Настроить общую папку WorkVault между устройствами
# Игнорировать: .obsidian/workspace.json, .trash/
```

Целевой SLA: изменение видно на другой машине за ≤10 минут.

## Перенос WorkVault с Windows на VM (без rsync)

На Windows нет нативного rsync — используем tar через SSH pipe:

```bash
# На Windows (git-bash):
cd /c/Users/tkachenkoav
tar czf /tmp/workvault.tar.gz WorkVault/
cat /tmp/workvault.tar.gz | ssh tkachenkoav@10.2.24.163 "cd ~ && tar xzf - && echo Готово"
# Проверка:
ssh tkachenkoav@10.2.24.163 "find ~/WorkVault -type f | wc -l && du -sh ~/WorkVault"
```

## Yandex.Disk — rclone WebDAV конфиг (проверено)

```
remote name: yandex
type: webdav
url: https://webdav.yandex.ru
vendor: other
user: i.alex.tkachenko@yandex.ru
pass: пароль приложения (не обычный пароль!)
```

Пароль приложения для Yandex.Disk WebDAV: создаётся на id.yandex.ru/security/app-passwords.
Формат: 16 символов, например `tpqasyxapzybjfad` (SHU-Obsidian).

Монтирование:
```bash
mkdir -p ~/YandexDisk
rclone mount yandex: ~/YandexDisk --daemon --vfs-cache-mode writes --dir-cache-time 5m
```

Проверка: `rclone lsd yandex:` должна показать папки (Obsidian Vault, Personal, Garmin, tmp).

## Pitfalls

1. **Два Telegram-бота** — два разных токена, один в Windows `.env`, другой в VM `.env`. НЕ путать.
2. **loginctl enable-linger** — без этого systemd --user сервисы умирают при logout из SSH.
3. **CRLF в скриптах** — скопированные с Windows файлы могут иметь `\r\n`. Фикс: `dos2unix <file>`.
4. **Часовой пояс** — по умолчанию UTC, кроны поедут не в то время. `sudo timedatectl set-timezone Europe/Moscow`.
5. **Синхронизация кронов** — если один и тот же крон работает на обеих машинах одновременно (GitHub push, Dialog Backlog) → конфликты и дубли. Разносить по времени или отключать на Windows при запуске на VM.
6. **MoveFromExchange** — не переносить, архив (bk-013, VPN до Exchange с VM скорее всего недоступен).
7. **Yandex.Disk CLI** — официально для Ubuntu/Debian, на AlmaLinux может не работать. Готовить fallback: rclone или Syncthing.
8. **Память двух агентов** — после переноса VM и Windows пишут независимо. При финальном cutover память Windows замораживается.
