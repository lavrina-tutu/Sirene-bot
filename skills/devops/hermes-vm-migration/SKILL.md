---
name: hermes-vm-migration
description: "Миграция Hermes Agent с Windows на Linux VM (AlmaLinux/Ubuntu). Архитектура, блоки работ, SSH-доступ, systemd, ownCloud (WorkVault), адаптация USERTOOLS."
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
- **Отдельный Telegram-бот** для VM-инстанса: `Сирень-ВМ` / `@sirene_vm_bot`, токен: `8630226915:AAFoM3NFKCeddFYXfb_LZN-xRidE_-O-hbA`
- **Клон личности** с немного другим именем (переименовать позже если надо)
- **Windows работает** до полного переезда всего — не отключать раньше времени
- **Кроны дублирующие** — разносить по времени, не запускать параллельно одинаковые
- **Бэкапы** — на локале перед стартом каждого блока
- **WorkVault синхронизация** — ownCloud (корп. ТУТУ, `owncloud.tutu.ru`), rclone WebDAV + systemd timer каждые 10 мин. Syncthing и Yandex.Disk для WorkVault не используются. ✅ Выполнено 02.06.2026
- **USERTOOLS** — все переносим вручную, адаптируем под Linux (нет GUI, нет Windows API)
- **Memory/сессии** — переписываем всё что знаем на момент миграции, далее независимо
- **Всё ПО поднимаем сами** (Python, systemd и т.д.) — не через IT-заявки

## ТЗ миграции

Файл: `C:\Users\tkachenkoav\WorkVault\Hermes-Backlog\MigrationToVM\TZ.md`

Блоки:
- **Блок 0** — Подготовка VM (Python, git, структура директорий)
- **Блок 1** — MVP gateway (новый TG-бот, systemd unit, базовая работа)
- **Блок 2** — Личность Сирени (memory, skills, профиль)
- **Блок 3** — Кроны (адаптация путей, замена Windows-команд)
- **Блок 4** — USERTOOLS (перенос и адаптация всех инструментов)
- **Блок 5** — WorkVault синхронизация (ownCloud) ✅ ВЫПОЛНЕНО 02.06.2026
- **Блок 6** — Финальный переезд и верификация ✅ ВЫПОЛНЕНО 02.06.2026 (Windows gateway остановлен, VM основная)

**Принцип приёмки:** после каждого блока Саша сам проверяет как пользователь (без знаний программирования).

## Целевой layout на VM

```
/home/tkachenkoav/
├── hermes-agent/          # код (git clone)
├── .config/hermes/        # config.yaml, .env, jobs.json
├── .local/share/hermes/   # sessions/, skills/, memory/, logs/
├── WorkVault/             # рабочие заметки (ownCloud ↔ ноут, /WorkVault/ в корне)
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

## ownCloud для WorkVault (актуально с 02.06.2026)

**Решение Саши:** синхронизация WorkVault через корпоративный ownCloud ТУТУ вместо Syncthing.

**Факты:**
- URL: `https://owncloud.tutu.ru/` (302 → `/index.php/login`)
- Пользователь: `tkachenkoav`
- WebDAV root: `https://owncloud.tutu.ru/remote.php/webdav/`
- ownCloud Desktop Client 6.0.0 установлен на Windows (`C:\Program Files\ownCloud\`)
- Конфиг Windows: `%APPDATA%\ownCloud\owncloud.cfg`
- **App Token** (не пароль!) — создаётся в ownCloud → Settings → Security → App passwords. Хранится в `.env` как `OWNCLOUD_APP_TOKEN`. Реальный пароль никуда не передаём.
- **WorkVault папка** — `/WorkVault/` в **корне** ownCloud (персональная, создана 02.06.2026). НЕ внутри Documents.
- Windows-сторона настроена: Documents и WorkVault синкаются как отдельные папки через Desktop Client.

**Проверить корень ownCloud (что там есть):**
```bash
curl -sk -u 'tkachenkoav:<APP_TOKEN>' \
  -X PROPFIND -H 'Depth: 1' \
  'https://owncloud.tutu.ru/remote.php/webdav/' \
  | grep -oP '(?<=<d:href>)[^<]+' | grep -v '^/remote.php/webdav/$'
```

**Создать папку в ownCloud:**
```bash
curl -sk -u 'tkachenkoav:<APP_TOKEN>' \
  -X MKCOL 'https://owncloud.tutu.ru/remote.php/webdav/WorkVault/'
# 201 = создана, 405 = уже существует
```

**На VM (AlmaLinux) — rclone + WebDAV + systemd timer:**
```bash
# 1. Установить rclone
sudo dnf install -y rclone

# 2. Записать конфиг напрямую (без интерактивного rclone config)
mkdir -p ~/.config/rclone
cat > ~/.config/rclone/rclone.conf << 'EOF'
[owncloud]
type = webdav
url = https://owncloud.tutu.ru/remote.php/webdav
vendor = owncloud
user = tkachenkoav
pass = ENCODED_TOKEN
EOF
# Закодировать app token:
ENCODED=$(rclone obscure "<APP_TOKEN>")
sed -i "s|ENCODED_TOKEN|${ENCODED}|g" ~/.config/rclone/rclone.conf
chmod 600 ~/.config/rclone/rclone.conf

# 3. Проверить подключение
rclone lsd owncloud:

# 4. Первичный pull из ownCloud → VM
rclone sync owncloud:WorkVault ~/WorkVault --progress

# 5. Готовый скрипт настройки:
# C:\Users\tkachenkoav\WorkVault\Hermes-Backlog\MigrationToVM\setup_owncloud_vm.sh
```

**Systemd timer для периодического синка (каждые 10 мин):**
```ini
# ~/.config/systemd/user/owncloud-sync.service
[Unit]
Description=ownCloud WorkVault sync
After=network-online.target
[Service]
Type=oneshot
ExecStart=/usr/bin/rclone sync /home/tkachenkoav/WorkVault owncloud:WorkVault \
  --log-file=/home/tkachenkoav/.local/share/hermes/logs/owncloud-sync.log \
  --log-level INFO
```
```ini
# ~/.config/systemd/user/owncloud-sync.timer
[Unit]
Description=ownCloud WorkVault sync every 10 min
[Timer]
OnBootSec=2min
OnUnitActiveSec=10min
[Install]
WantedBy=timers.target
```
```bash
systemctl --user daemon-reload
systemctl --user enable --now owncloud-sync.timer
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

## SSH с Windows — критические питфоллы

### ControlMaster НЕ работает на Windows OpenSSH
Windows OpenSSH (даже 10.x) не поддерживает Unix-сокеты → `ControlMaster`/`ControlPath` в `~/.ssh/config` создаёт сокет-файл которого нет → `getsockname failed: Not a socket` в cmd.exe.

**Правильное решение — Windows SSH Agent:**
1. Убедиться что сервис `ssh-agent` запущен: `sc query ssh-agent` → STATE: RUNNING
2. Добавить ключ один раз: в **Git Bash** выполнить `ssh-add ~/.ssh/id_ed25519` → ввести пароль
3. После этого все SSH-команды из любого процесса идут без пароля до перезагрузки

**Добавлять в ~/.ssh/config** (работает и без ControlMaster):
```
Host hermes-vm
  HostName hermes-agents.devel.tutu.ru
  User tkachenkoav
  IdentityFile ~/.ssh/id_ed25519
  ServerAliveInterval 60
  ServerAliveCountMax 10
  StrictHostKeyChecking no
```

### cmd.exe vs Git Bash
- `ssh hermes-vm` из **cmd.exe** — ошибка `getsockname failed: Not a socket` (Windows system SSH, нет агента)
- `ssh hermes-vm` из **Git Bash** — работает, подхватывает агент
- Пользователь привык к команде `ssh -L 5901:localhost:5901 tkachenkoav@hermes-agents.devel.tutu.ru` — это тоже рабочий вариант для первичного подключения

### Ключ с passphrase — пользователь не успевает вводить пароль
Если пользователь говорит «не успеваю вводить пароль» / «поставьте таймаут» — нужно добавить ключ в SSH Agent, а не увеличивать таймауты. После `ssh-add` пароль больше не запрашивается.

### Паттерн выполнения скриптов на VM (агент не имеет доступа к SSH-агенту git-bash)

Hermes `terminal`/`execute_code` не имеет доступа к SSH-агенту пользователя. Поэтому SSH-команды из агента не работают если ключ с паролём.

**Правильный паттерн:**
1. Агент пишет скрипт в файл (`write_file`)
2. Пользователь запускает скрипт из **Git Bash** (где агент активен после `ssh-add`): `bash /c/путь/к/скрипту.sh`
3. Скрипт сам подключается к VM через SSH без пароля
4. Результат — пользователь показывает скриншот или копирует вывод

**Скрипты для переноса данных через SSH (из git-bash, без интерактива):**
```bash
# Передать файл через stdin (не через scp — scp тоже попросит агента):
cat /c/Users/tkachenkoav/.local/share/hermes/config.yaml | \
  ssh tkachenkoav@hermes-agents.devel.tutu.ru 'cat > ~/.config/hermes/config.yaml'

# Выполнить блок команд на VM:
ssh tkachenkoav@hermes-agents.devel.tutu.ru 'bash -s' << 'EOF'
  echo "hello from VM"
EOF
```

### git clone на VM — только SSH, не HTTPS

HTTPS-клонирование GitHub с VM падает: `gnome-ssh-askpass` не может открыть дисплей (нет X11), fatal: Could not read Username.

**Правильный путь:**
```bash
# 1. Сгенерировать SSH ключ на VM (без пароля — VM в корп. сети, VPN обязателен):
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N "" -C "hermes-vm"
cat ~/.ssh/id_ed25519.pub   # скопировать вывод

# 2. Добавить публичный ключ в GitHub: https://github.com/settings/keys → New SSH key

# 3. Клонировать через SSH:
git clone git@github.com:ialextkachenko-byte/hermes-agent.git ~/hermes-agent
```

## SSH без пароля (ControlMaster не работает на Windows)

Windows OpenSSH **не поддерживает Unix-сокеты** → ControlMaster/ControlPath не работает.
Единственный рабочий способ — запустить `ssh-agent` внутри самого скрипта:

```bash
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519   # пароль вводится ОДИН раз здесь
# дальше все SSH/SCP команды идут без пароля
# в конце скрипта:
eval "$(ssh-agent -k)"
```

**Важно:** агент живёт только в рамках текущего bash-процесса. Новое окно git-bash = новый агент = снова пароль.

## ownCloud WebDAV (вместо Syncthing/Yandex.Disk)

WorkVault синхронизируется через **ownCloud** (`owncloud.tutu.ru`), не Syncthing.

**App Token** (не пароль!): создаётся на `owncloud.tutu.ru` → Settings → Security → App passwords.
Формат токена: `XXXXX-XXXXX-XXXXX-XXXXX` (5 групп по 5 символов).

**rclone конфиг на VM:**
```ini
[owncloud]
type = webdav
url = https://owncloud.tutu.ru/remote.php/webdav
vendor = owncloud
user = tkachenkoav
pass = <rclone obscure TOKEN>
```

**systemd timer** (каждые 10 мин):
```bash
systemctl --user enable --now owncloud-sync.timer
systemctl --user status owncloud-sync.timer
```

Скрипт первичной настройки: `USERTOOLS/MigrationToVM/setup_owncloud_vm.sh`

## Клонирование hermes-agent на VM

**Не использовать** `tar` с Windows git-bash для копирования больших папок (>100 МБ) — зависает на сканировании `.venv` и `node_modules` даже с `--exclude`. Это не баг exclude, это особенность MSYS tar. Зависание происходит молча, без вывода — пользователь видит просто висящий терминал.

### python3 vs python в git-bash скриптах

В git-bash на Windows нет `python3` — только `python`. Скрипты должны определять команду динамически:
```bash
PYTHON=$(which python3 2>/dev/null || which python 2>/dev/null)
$PYTHON - << 'PYEOF'
# ... Python код
PYEOF
```

**Правильный порядок:**
1. Сгенерировать SSH-ключ прямо на VM: `ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N "" -C "hermes-vm"`
2. Добавить публичный ключ в GitHub: `https://github.com/settings/keys`
3. Клонировать на VM: `GIT_SSH_COMMAND="ssh -o StrictHostKeyChecking=no" git clone git@github.com:<repo>.git ~/hermes-agent`

Мелкие файлы (config.yaml, .env) — передавать через stdin: `cat file | ssh vm "cat > remote_path"` — мгновенно, без зависаний.

## Telegram паринг нового бота

После первого запуска gateway новый пользователь получает код паринга:
```
Hi~ I don't recognize you yet!
Here's your pairing code: XXXXXXXX
Ask the bot owner to run: hermes pairing approve telegram XXXXXXXX
```

Утвердить на VM (правильная команда):
```bash
source ~/hermes-agent/.venv/bin/activate
# Правильно — через CLI:
python -m hermes_cli.main pairing approve telegram XXXXXXXX
# ИЛИ если hermes в PATH:
hermes pairing approve telegram XXXXXXXX
```

**Неправильно** (команды `hermes_pairing_approve_telegram` не существует как бинарника):
```bash
hermes_pairing_approve_telegram XXXXXXXX  # → command not found
```

Найти правильные подкоманды pairing:
```bash
grep -n "def\|approve\|@click" ~/hermes-agent/hermes_cli/pairing.py | head -20
# Формат: hermes pairing {list|approve|revoke|clear-pending}
# Approve: hermes pairing approve <platform> <code>
```

## GATEWAY_ALLOW_ALL_USERS — обязательно выключить

По умолчанию в `.env` стоит `GATEWAY_ALLOW_ALL_USERS=true`. Это открывает бота всем.
Для личного использования обязательно:
```
GATEWAY_ALLOW_ALL_USERS=false
TELEGRAM_ALLOWED_CHAT_IDS=400307920
```

## Скрипты и статус блоков

Подробности и паттерны скриптов: `references/migration-scripts.md`

Оптимизация и эксплуатация ownCloud WebDAV синка: `references/owncloud-sync-optimization.md`

## Питфоллы

1. **Два Telegram-бота** — два разных токена, один в Windows `.env`, другой в VM `.env`. НЕ путать.
2. **loginctl enable-linger** — без этого systemd --user сервисы умирают при logout из SSH.
3. **CRLF в скриптах** — скопированные с Windows файлы могут иметь `\r\n`. Фикс: `dos2unix <file>`.
4. **Часовой пояс** — по умолчанию UTC, кроны поедут не в то время. `sudo timedatectl set-timezone Europe/Moscow`.
5. **Синхронизация кронов** — если один и тот же крон работает на обеих машинах одновременно (GitHub push, Dialog Backlog) → конфликты и дубли. Разносить по времени или отключать на Windows при запуске на VM.
6. **MoveFromExchange** — не переносить, архив (bk-013, VPN до Exchange с VM скорее всего недоступен).
7. **Yandex.Disk CLI** — официально для Ubuntu/Debian, на AlmaLinux может не работать. Это не проблема — Yandex.Disk нужен только для личных Obsidian-заметок (не WorkVault). Fallback: rclone WebDAV.
8. **Yandex.Disk — только личные Obsidian-заметки**, НЕ WorkVault. WorkVault синкается через ownCloud `/WorkVault/`. Не путать два контура.
9. **ownCloud: app token, не пароль** — использовать только App Token (Settings → Security → App passwords). Реальный корп. пароль никуда не передаём.
10. **ownCloud конфиг на Windows** — `%APPDATA%\ownCloud\owncloud.cfg`. Там видны все sync-папки и DAV-пользователь.
11. **Память двух агентов** — после переноса VM и Windows пишут независимо. При финальном cutover память Windows замораживается.
12. **hermes-workspace репозиторий НЕ переносится автоматически** — при миграции USERTOOLS переносятся через rsync, но репозиторий `hermes-workspace` (GitHub autosync) на VM отсутствует. Нужно клонировать отдельно через SSH после настройки GitHub ключей. `GITHUB_TOKEN` на VM не нужен — используем SSH-аутентификацию (питфолл 15). Полный паттерн настройки autosync на VM:
   ```bash
   # 1. Клонировать
   git clone git@github.com:ialextkachenko-byte/hermes-workspace.git ~/hermes-workspace
   # 2. Адаптировать скрипт (пути Windows → Linux, токен → SSH)
   # WS="$HOME/hermes-workspace"; HERMES_HOME="$HOME/.hermes"; VAULT="$HOME/WorkVault/Hermes-Backlog"
   # git remote set-url origin git@github.com:ialextkachenko-byte/hermes-workspace.git
   # 3. Скопировать в ~/.hermes/scripts/ (не симлинк!)
   cat ~/hermes-workspace/scripts/autosync.sh > ~/.hermes/scripts/autosync_github.sh
   chmod +x ~/.hermes/scripts/autosync_github.sh
   # 4. Создать cron-job
   hermes cron create --name "GitHub автосинк [VM]" --schedule "0 2 * * *" --no-agent --script autosync_github.sh --deliver local
   ```
13. **SSH ключ VM добавлен не к тому GitHub-аккаунту** — частая ошибка: ключ `hermes-vm` добавляется в основной корпоративный аккаунт вместо личного `ialextkachenko-byte`. Симптом: `ssh -T git@github.com` → `Permission denied (publickey)` даже после добавления ключа. Диагностика: убедиться что ты залогинен в `ialextkachenko-byte` при открытии https://github.com/settings/keys.
14. **`cronjob(create, script=...)` не принимает симлинки и абсолютные пути** — скрипт должен физически лежать в `~/.hermes/scripts/`. Симлинк через `ln -sf` резолвится в абсолютный путь и блокируется с ошибкой `Script path escapes the scripts directory`. Решение: `cat source.sh > ~/.hermes/scripts/target.sh` (физическая копия, не симлинк).
15. **autosync.sh на VM — использовать SSH, не HTTPS-токен** — оригинальный скрипт Windows использовал `GITHUB_TOKEN` для HTTPS-пуша. На VM SSH-ключ уже настроен, поэтому `git remote set-url origin git@github.com:...` — правильный подход, не искать токен в `.env`. Это упрощает обслуживание и убирает зависимость от токена.
16. **git config identity на VM** — после первого коммита git предупреждает об автоматически определённом имени/email. Настроить явно: `git config --global user.name "Сирень (hermes-vm)"` + `git config --global user.email "tkachenkoav@tutu.ru"`. Без этого commits выглядят как `tkachenkoav@hermes-agents.devel.tutu.ru`.
17. **CRLF warnings при первом git add на VM** — файлы перенесённые с Windows имеют `\\r\\n`. Git предупреждает `CRLF will be replaced by LF` — это косметика, не ошибка. Push проходит успешно. При следующих синках файлы уже будут в LF.
18. **ownCloud: путь WorkVault без Documents** — верный удалённый путь `owncloud:WorkVault` (в корне ownCloud-аккаунта). Вложенности типа `owncloud:Documents/WorkVault` быть не должно. Проверять через `rclone ls owncloud:WorkVault/ | head -5`. Ссылка на веб-интерфейс папки: `https://owncloud.tutu.ru/index.php/f/6966632`.
19. **Принудительный запуск синка** — `systemctl --user start owncloud-sync.service`. Безопасно: `Type=oneshot`, systemd не позволит конкурентный запуск. Для проверки результата: `rclone ls owncloud:WorkVault/Meetings/NewMeetings/ | wc -l`.
20. **Оптимизированные флаги rclone для WebDAV ownCloud** — добавить в `owncloud-sync.service` для ускорения и надёжности:
    ```
    --transfers 4 --checkers 8
    --retries 3 --low-level-retries 10
    --timeout 60s --contimeout 30s
    --size-only
    ```
    `--size-only` особенно важен: WebDAV плохо поддерживает чексуммы, без флага rclone делает лишние roundtrip-запросы. `--fast-list` тоже можно добавить если ownCloud поддерживает PROPFIND с Depth:infinity.
