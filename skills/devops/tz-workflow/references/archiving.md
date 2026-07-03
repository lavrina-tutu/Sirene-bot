# Archiving reference — commands (no bash script wrapper)

Все операции выполняются через обычный `terminal`-тул. Скрипт-обёртка **не заводится** намеренно (проще, меньше поверхности отказа).

## Снапшот перед крупной правкой ТЗ

```
TS=$(date +%Y%m%d-%H%M)
TOOL=<Tool>
mkdir -p ~/WorkVault_backup/Hermes-Backlog/TZ/$TOOL/
tar czf ~/WorkVault_backup/Hermes-Backlog/TZ/$TOOL/${TOOL}_TZ_snapshots-$TS.tgz \
    -C ~/WorkVault/Hermes-Backlog/TZ $TOOL/
echo "[$(date +%H:%M:%S)] SNAPSHOT: ${TOOL}_TZ_snapshots-$TS.tgz" \
    >> ~/WorkVault_backup/_moved-$(date +%Y-%m-%d).log
```

Проверить, что архив создан и читается:

```
tar tzf ~/WorkVault_backup/Hermes-Backlog/TZ/$TOOL/${TOOL}_TZ_snapshots-$TS.tgz | head
```

## Ретеншн (5 последних tgz на инструмент)

```
cd ~/WorkVault_backup/Hermes-Backlog/TZ/<Tool>/
ls -1t *_TZ_snapshots-*.tgz | tail -n +6 | while read f; do
    echo "[$(date +%H:%M:%S)] RETENTION_DELETE: $f" \
        >> ~/WorkVault_backup/_moved-$(date +%Y-%m-%d).log
    rm -- "$f"
done
```

## `.bak` перед мелкой правкой (последний 1)

```
cp ~/WorkVault/Hermes-Backlog/TZ/<Tool>/<Tool>_TZ.md \
   ~/WorkVault_backup/Hermes-Backlog/TZ/<Tool>/<Tool>_TZ.md.bak
echo "[$(date +%H:%M:%S)] BAK: <Tool>_TZ.md.bak" \
    >> ~/WorkVault_backup/_moved-$(date +%Y-%m-%d).log
```

`.bak` **перезаписывается** — держим один последний.

## Перенос старой .md-версии в backup после ревизии

```
NEW_VER=2.2
OLD_VER=2.1
DATE=$(date +%Y%m%d)
mkdir -p ~/WorkVault_backup/Hermes-Backlog/TZ/<Tool>/
cp ~/WorkVault/Hermes-Backlog/TZ/<Tool>/<Tool>_TZ.md \
   ~/WorkVault_backup/Hermes-Backlog/TZ/<Tool>/<Tool>_TZ_v${OLD_VER}_${DATE}.md
echo "[$(date +%H:%M:%S)] ARCHIVED_VERSION: <Tool>_TZ_v${OLD_VER}_${DATE}.md" \
    >> ~/WorkVault_backup/_moved-$(date +%Y-%m-%d).log
# затем в master правится frontmatter version -> NEW_VER
```

## Архивация ТЗ инструмента (инструмент выведен из эксплуатации)

**Триггер только: явное решение Саши.** Не по календарю, не по завершению доработки.

```
TOOL=<Tool>
mkdir -p ~/WorkVault_backup/Hermes-Backlog/TZ/_archived/$TOOL/
mv ~/WorkVault/Hermes-Backlog/TZ/$TOOL/* ~/WorkVault_backup/Hermes-Backlog/TZ/_archived/$TOOL/
rmdir ~/WorkVault/Hermes-Backlog/TZ/$TOOL
echo "[$(date +%H:%M:%S)] TOOL_DECOMMISSIONED: $TOOL -> _archived/$TOOL/" \
    >> ~/WorkVault_backup/_moved-$(date +%Y-%m-%d).log
# Затем — обновить MAIN_TZ_INVENTORY.md: строка переезжает в "Завершённые/архивные", статус=archived.
```

## Логирование — единый формат строки

```
[HH:MM:SS] ACTION: <path or details>
```

Файл лога: `~/WorkVault_backup/_moved-YYYY-MM-DD.log`. По одному на дату, дозаписывается (`>>`).

## Что делать НЕЛЬЗЯ

- Хранить активные версии в имени файла (`_v2.md`, `_v3.md`) в `WorkVault/`.
- Переименовывать уже архивированные кириллические файлы в `WorkVault_backup/`.
- Ставить cron/автотаймер на архивацию ТЗ инструмента.
- Рестартовать gateway.
- Трогать `~/hermes-config*`, `~/hermes-workspace`, `WorkVault/Projects|People|Meetings|Contacts`.
