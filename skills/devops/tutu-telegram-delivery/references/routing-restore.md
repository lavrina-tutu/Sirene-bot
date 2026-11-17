Source excerpt: verify effective env-over-YAML allowlist independently; check only compares disk snapshot. Gateway restart requires separate explicit authorization.

## Восстановление маршрутизации топиков

Единая команда (канон id — `references/sirene-workspace-topics.yaml`):

```bash
bash ~/.hermes/skills/devops/tutu-telegram-delivery/scripts/restore_telegram_topics.sh apply|check|dry-run
```

`dry-run` — diff снимок vs диск, ничего не писать. `apply` — бэкап трёх файлов → allowlist **только** в YAML `telegram.allowed_chats` (НЕ пишет `TELEGRAM_ALLOWED_CHATS` в `.env` — политика доступа живёт в config.yaml, `.env` строго секреты) + `TELEGRAM_ADDITIONAL_STARTUP_CHANNELS` + unify YAML-токена с `TELEGRAM_BOT_TOKEN` + YAML extras. `check` — exit 0 только если диск = снимок; проверяет allowlist по YAML, а НЕ по `.env`. Скрипт gateway **не** рестартует: после `apply` ждать «поднимай». Не править `.env`/`config.yaml` руками.

**Питфолл — `apply`/правка `.env`/`config.yaml` на диске НЕ видна работающему gateway до рестарта.** Allowlist и токен адаптер читает **на старте**, а не из файла при каждом апдейте. Поэтому после `apply` «сообщения в топики уходят, а LLM не отвечает» — это нормально: `sirene_vm_bot` админ, исходящая доставка идёт, но входящие режутся старым allowlist из памяти процесса, стартовавшего до правки. Диагноз «топики молчат» не закрывают одним `check`/`dry-run` — проверь `ps -o lstart -p <gateway_pid>`/`systemctl --user show hermes-gateway -p ActiveEnterTimestamp`: стартовал ПОСЛЕ `apply`? Если нет — рестарт является обязательным шагом, а не опцией. Рестартgateway — только по явному «поднимай» от Саши.

Как доставлять сообщения в группу ТУТУ и её топики из собственных скриптов,
инструментов (USERTOOLS), шин ошибок (ErrorBus) и крон-обёрток.

