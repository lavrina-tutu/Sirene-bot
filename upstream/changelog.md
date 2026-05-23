# Upstream changelog (NousResearch/hermes-agent)

Ручные заметки по релевантным изменениям upstream. Дополняется при каждом `upstream_update.sh`.

## 2026-05-23 — initial pin

- Зафиксирован commit `127b56a61aa84c26f52feb8b672c89112f607a1a` (tag `v2026.5.16`) — это HEAD локального клона `~/Documents/Cursor_projects/hermes-agent` на момент консолидации репозиториев.
- prev: нет (первый pin)
- Клон на этом коммите работает; cli, cron, gateway функционируют.
- TODO до следующего апдейта: проверить security-фикс API-key leakage в upstream/main и Telegram allowed_chats observation behavior.
- Затронуты ли скиллы: нет.
- Затронут ли config.yaml: проверить блок `gateway.telegram` при следующем апдейте.
