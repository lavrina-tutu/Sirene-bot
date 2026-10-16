# Выжимка починки бага — 2026-09-16 (топики группы «Сирень Workspace»)

**Формат:** компактный контекст для передачи в топик upstream (проработка upstream до сбоя).
**Составила:** Сирень. **Дата:** 16.09.2026.

---

## 1. Симптом
- Группа TG «Сирень Workspace» (`-1004300127777`, forum) перестала отвечать в топиках. DM (`400307920`) отвечал штатно.
- Произошло после: апдейт ядра 12:04 (config migrate 33→44) + systemd planned-restart gateway 13:11.
- До рестарта (13:03–13:09) gateway обрабатывал топик `:6` и отвечал. После — inbound группы = ноль.

## 2. Root cause (подтверждён BUG:diagnose + REV:plan)
- `.env` (`~/.hermes/.env` и `profiles/default/.env`) содержали `TELEGRAM_ALLOWED_CHATS=400307920` — ТОЛЬКО DM, без группы.
- Контракт **env-over-YAML** (`extra_or_secret`, `gateway/platforms/_shared.py`) — env побеждает YAML.
- `config.yaml` `telegram.allowed_chats` имел группу (`400307920,-1004300127777`), но **env тенью накрывал YAML**.
- Gateway дропал group inbound на allowlist-гейте МОЛЧА (без лога) → топики молчат, DM жив (private не проходит гейт).
- Forum-роутинг / prune sessions / multiplex / 409 — **НЕ причина** (опровергнуто).

## 3. Связанный факт — UPSTREAM (ключевое для другого топика)
- Сбой спровоцирован **апдейтом ядра** (config migrate 33→44, ~12:04) + рестартом: старый процесс работал на старом коде, рестарт подхватил новый код → проявился существовавший с ≥14.08 узкий env-allowlist.
- Память (16.09): **Upstream 16.09: kanban-слой НЕ надстройка, апстрим разрезал run.py/kanban_db/cli — merge НЕбезопасен; реальная база=merge-base** (`hermes --version` SHA не предок HEAD).
- Апдейт ядра сегодня: `hermes-agent` local `52ecd71cce` / upstream `7b6e0d38`, +17 carried commits. Коммит апдейта: `c06407e90e "step 7 config migrate 33->44 + restore our defaults"`.
- **Вывод для upstream:** правки ядра идут с ревизором; merge апстрима — через `hermes-upgrade-pattern.md` (риск-зоны: config migration, kanban split). До мержа сверить merge-base.

## 4. Что сделано (фикс)
**Кейс BUGFIX → CHANGE (единый модуль восстановления топиков).** Всё через Cursor (архитектор cursor-grok-4.6-high, исполнитель composer-2.5).

**Фикс inbound (П.1-П.3):**
- allowlist .env → `TELEGRAM_ALLOWED_CHATS=400307920,-1004300127777` (обе копии).
- unify bot token: `config.yaml gateway.telegram.token` `882117`→`8630226915` (= sirene_vm_bot, админ группы). Два бота на один Platform.TELEGRAM = мина (устранена).
- `adapter.py` (line ~5843): WARNING при drop по `TELEGRAM_ALLOWED_CHATS` (патч в `_should_process_message`, закрывает text+command+media).
- Рестарт gateway (16:29) → топики ожили: inbound+ответы по Backlog:6, WorkVault:5, Errors:11112, Tools:3, Personal:8, Monitoring:7, General:1. WARNING Dropped=0.

**Единый модуль восстановления (твоя вводная):**
- Снимок: `~/.hermes/skills/devops/tutu-telegram-delivery/references/sirene-workspace-topics.yaml` (без секретов).
- Скрипт: `~/.hermes/skills/devops/tutu-telegram-delivery/scripts/restore_telegram_topics.sh` (apply|check|dry-run).
- SKILL.md tutu-telegram-delivery v1.2.0 (секция восстановления); указатель в hermes-gateway-setup.
- При крахе: `restore_telegram_topics.sh apply` → маршрутизация восстанавливается «как была». check=exit 0.

## 5. Канон топиков (после сегодняшних правок)
**7 топиков** (было 8): General=1, Tools=3, WorkVault=5, Backlog=6, Monitoring=7, Errors=11112, Personal=8.
- `Hermes DEV` (:4) — **давно удалён, исключён из канона** (ТЗ v0.3.0; yaml/скрипт — в HF:impl, диспетчер).
- `:6556` (Messages) — НЕ в каноне, только jobs.json (Q1, вариант 1).

## 6. Артефакты/пути
- ТЗ: `TZ/TelegramGroupTopics/TelegramGroupTopics_TZ.md` (v0.3.0, approved)
- Диагноз: `~/hermes-agent/_fix_plan_20260916.md`
- План: `~/hermes-agent/HF-plan_20260916.md`
- Бэкап: `~/.hermes/_Archives/hermes-backup-20260916-155704-tg-topics/`
- Снимок+скрипт: `~/.hermes/skills/devops/tutu-telegram-delivery/`

## 7. Полезные команды
- Проверить статус: `bash ~/.hermes/skills/devops/tutu-telegram-delivery/scripts/restore_telegram_topics.sh check`
- Восстановить: `... apply` (dry-run сначала)
- Тесты: `~/hermes-agent/scripts/run_tests.sh tests/plugins/platforms/telegram/test_allowlist_env_over_yaml.py` (2/2); `test_restore_telegram_topics.py` (1/1)
