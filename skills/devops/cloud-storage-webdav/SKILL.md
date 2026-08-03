---
name: cloud-storage-webdav
description: "Монтирование облачных дисков через WebDAV на Linux: Яндекс.Диск, Nextcloud, ownCloud. davfs2, credentials, fstab, диагностика 401."
version: 1.0.0
author: agent
tags: [linux, webdav, yandex-disk, davfs2, storage, mount]
platforms: [linux]
---

# cloud-storage-webdav

## Триггеры
- «подключи Яндекс.Диск на VM»
- «смонтировать WebDAV»
- «доступ к облачному диску с Linux»

## Яндекс.Диск — WebDAV

### Требования
- **Пароль приложения** (не пароль аккаунта): создать на [id.yandex.ru/security/app-passwords](https://id.yandex.ru/security/app-passwords)
- Выбрать тип: **Файлы · WebDAV**
- Логин: полный email (`user@yandex.ru`) или короткий логин — оба работают

### Установка davfs2
```bash
# AlmaLinux / RHEL / CentOS
sudo dnf install -y davfs2

# Ubuntu / Debian
sudo apt-get install -y davfs2
```

### Настройка
```bash
# Точка монтирования
mkdir -p ~/YandexDisk

# Credentials (пользовательский файл — предпочтительно)
mkdir -p ~/.davfs2
echo "https://webdav.yandex.ru LOGIN PASSWORD" > ~/.davfs2/secrets
chmod 600 ~/.davfs2/secrets

# Добавить пользователя в группу davfs2
sudo usermod -aG davfs2 $USER

# fstab для монтирования без sudo
echo "https://webdav.yandex.ru /home/$USER/YandexDisk davfs user,noauto,uid=$USER,gid=$USER,_netdev 0 0" | sudo tee -a /etc/fstab
```

### Монтирование
```bash
# Без sudo (после fstab)
mount ~/YandexDisk

# С sudo (сразу работает)
sudo mount ~/YandexDisk

# Проверка
ls ~/YandexDisk | head -20
```

### Автомонтирование при старте
```bash
# Через systemd (рекомендуется)
sudo systemctl enable remote-fs.target
# убедиться что в fstab стоит флаг _netdev
```

---

## Диагностика 401 Unauthorized

**Симптом:** `curl -u login:pass https://webdav.yandex.ru/ → 401`

**Чеклист:**
1. Используется **пароль приложения**, не пароль аккаунта
2. Тип пароля — **Файлы · WebDAV** (не «Другое приложение»)
3. Пробелы в пароле убраны (Яндекс показывает пароль с пробелами для читаемости — `dsehb ubju pqat dez` → `dsehbubjupqatdez`)
4. Проверить `Yandex-Uid` в ответе: если `0` — логин не распознан
5. Попробовать оба формата логина: `user` и `user@yandex.ru`

**Диагностика:**
```bash
# Проверить HTTP-код и Yandex-Uid
curl -v -u "LOGIN:PASSWORD" "https://webdav.yandex.ru/" 2>&1 | grep -E "< HTTP|Yandex-Uid|Location"

# Если 302 → help.yandex.ru/disk/webdav.xml — авторизация провалилась
# Если 207 (Multi-Status) — успех
```

**Решение если 302/401 при верном пароле:**
- Пересоздать пароль приложения
- Проверить что аккаунт Яндекса активен и не заблокирован
- Проверить IP VM (хотя Яндекс обычно не блокирует по IP внутри РФ)

---

## Питфоллы

- **`/etc/davfs2/secrets` требует sudo** — предпочтительно использовать `~/.davfs2/secrets` (пользовательский)
- **Группа davfs2** — нужен перелогин после `usermod -aG davfs2` чтобы группа применилась
- **Флаг `_netdev` в fstab** обязателен — иначе монтирование при старте падает до поднятия сети
- **`noauto`** — без него попытка mount при старте без сети будет вешать систему
- **Пароль с пробелами** — Яндекс отображает пароль приложения с пробелами для читаемости, их нужно убрать
- **`Yandex-Uid: 0`** в curl-ответе = логин не найден, не проблема пароля
