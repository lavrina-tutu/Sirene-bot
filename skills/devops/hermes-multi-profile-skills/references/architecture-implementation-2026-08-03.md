# Реализация архитектуры скиллов — 03.08.2026

> **Исторический снапшот 03.08.2026.** Описывает реализацию multi-profile архитектуры (workspace → default → tz-dev). Профиль tz-dev decommissioned 13.08.2026; актуальная схема — workspace → default.

## Контекст

После `hermes update` 03.08.2026 из профиля tz-dev пропали ~58 кастомных скиллов (было 132, стало 74). Бэкап куратора от 29.07 сохранил полную копию.

## Решение

### 1. Git-репозиторий как каноничный источник

`~/hermes-workspace` (GitHub: `ialextkachenko-byte/hermes-workspace.git`) содержит 150 кастомных скиллов. 18 недостающих скиллов были добавлены из `~/hermes-config`.

### 2. Симлинки вместо копирования

```
hermes-workspace/skills/ ──(symlink)──▶ default/skills/ ──(symlink)──▶ tz-dev/skills/
```

Почему симлинки, а не копирование:
- Изменение в git мгновенно видно во всех профилях
- Нет дублирования
- `hermes update` не затрагивает git-репо
- Bundled skills остаются независимыми в каждом профиле

### 3. Скрипты

| Скрипт | Назначение |
|--------|-----------|
| `sync-to-hermes.sh [profile]` | Симлинки workspace → профиль |
| `link-tzdev-to-default.sh` | Симлинки default → tz-dev |
| `restore-all-skills.sh` | Мастер: оба шага |

Все скрипты идемпотентны.

### 4. Крон-защита

| Job ID | Расписание | Действие |
|--------|-----------|----------|
| `restore-skills-daily` | 3:00 ежедневно | `restore-all-skills.sh` |
| `5d16b96a9ed5` | 2:00 ежедневно | автосинк GitHub (исправлен — больше не стирает скиллы) |

### 5. Исправление autosync_github.sh

**Было:**
```bash
rm -rf skills
cp -r ~/.hermes/skills/. skills/
```
Удаляло кастомные скиллы, заменяло bundled.

**Стало:**
```bash
bash "$WS/restore-all-skills.sh"
```
Восстанавливает симлинки. Скиллы в workspace не трогает.

## Результаты

| Компонент | Скиллов |
|-----------|---------|
| hermes-workspace (git) | 150 |
| default (bundled + symlink) | 145 |
| tz-dev (bundled + symlink → default) | 149 |

## Извлечённые уроки

1. **Никогда не копировать из `~/.hermes/skills/` в git-репо.** Git — источник, Hermes — потребитель.
2. **Симлинки переживают `hermes update` частично.** Bundled skills обновляются, симлинки могут быть потеряны. Нужен restore-скрипт + крон.
3. **Бэкапы куратора — последняя линия защиты.** Перед update убедиться что куратор сделал свежий бэкап.
