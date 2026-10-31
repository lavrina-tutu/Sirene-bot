---
name: tutu-telegram-delivery
description: "Доставка в группы ТУТУ: топики, бот, restore маршрутизации a"
version: 1.3.1
last-section-added: "2026-09-16 — канон 8→7: Hermes DEV (:4) удалён из группы, исключён из канона"
author: agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [telegram, tutu, group, delivery, bot, errorbus]
    related_skills: [hermes-gateway-setup, hermes-feature]
---

# Tutu Telegram Delivery (группа «Сирень Workspace»)

## Восстановление маршрутизации топиков

Единая команда (канон id — `references/sirene-workspace-topics.yaml`):

```bash
bash ~/.hermes/skills/devops/tutu-telegram-delivery/scripts/restore_telegram_topics.sh apply|check|dry-run
```

`dry-run` — diff снимок vs диск, ничего не писать. `apply` — бэкап трёх файлов → allowlist **только** в YAML `telegram.allowed_chats` (НЕ пишет `TELEGRAM_ALLOWED_CHATS` в `.env` — политика доступа живёт в config.yaml, `.env` строго секреты) + `TELEGRAM_ADDITIONAL_STARTUP_CHANNELS` + unify YAML-токена с `TELEGRAM_BOT_TOKEN` + YAML extras. `check` — exit 0 только если диск = снимок; проверяет allowlist по YAML, а НЕ по `.env`. Скрипт gateway **не** рестартует: после `apply` ждать «поднимай». Не править `.env`/`config.yaml` руками.

**Питфолл — `apply`/правка `.env`/`config.yaml` на диске НЕ видна работающему gateway до рестарта.** Allowlist и токен адаптер читает **на старте**, а не из файла при каждом апдейте. Поэтому после `apply` «сообщения в топики уходят, а LLM не отвечает» — это нормально: `sirene_vm_bot` админ, исходящая доставка идёт, но входящие режутся старым allowlist из памяти процесса, стартовавшего до правки. Диагноз «топики молчат» не закрывают одним `check`/`dry-run` — проверь `ps -o lstart -p <gateway_pid>`/`systemctl --user show hermes-gateway -p ActiveEnterTimestamp`: стартовал ПОСЛЕ `apply`? Если нет — рестарт является обязательным шагом, а не опцией. Рестартgateway — только по явному «поднимай» от Саши.

Как доставлять сообщения в группу ТУТУ и её топики из собственных скриптов,
инструментов (USERTOOLS), шин ошибок (ErrorBus) и крон-обёрток.

## Бот и токен (после `apply`)

Poller gateway и `gateway.telegram.token` **должны** совпадать с `TELEGRAM_BOT_TOKEN` (`sirene_vm_bot`, bot id prefix `863022`). Скрипт `apply` копирует env → YAML. Бот с prefix `882117` в группе не состоит — не использовать для группы.

- `TELEGRAM_BOT_TOKEN` лежит в `~/.hermes/.env` **и** `~/.hermes/profiles/default/.env`.
- **Правило:** любой инструмент, который должен писать в ГРУППОВОЙ топик, берёт `TELEGRAM_BOT_TOKEN`.
  `gateway.telegram.token`, если разошёлся с env, для группы даёт `Bad Request: chat not found`.

## Проверка ПЕРЕД интеграцией (не верь выбору архитектора/self-report)

```bash
curl -s https://api.telegram.org/bot<TOKEN>/getMe          # кто бот (username)
curl -s -X POST "https://api.telegram.org/bot<TOKEN>/sendMessage" \
  -d 'chat_id=-1004300127777' -d 'message_thread_id=11112' -d 'text=smoke'
# ok:true  → этот бот реально доставляет в топик — можно использовать
# chat not found → НЕ тот бот (не состоит в группе)
```

`getMe` недостаточен (бот с токеном существует, но может не состоять в группе).
Единственное надёжное подтверждение — `ok:true` в ответе sendMessage в конкретный топик.
Исполнитель обязан прогнать live-smoke до сдачи; координатор — проверить реальную
доставку, а не верить финальному отчёту.

## Топики группы «Сирень Workspace» (chat=-1004300127777)

Канон id — `references/sirene-workspace-topics.yaml` (ровно 8 топиков; `:6556` Messages — ЖИВОЙ топик, не «только в jobs.json»).

| Топик | Thread ID | Deliver target |
|-------|-----------|----------------|
| General | 1 | `telegram:-1004300127777:1` |
| Tools | 3 | `telegram:-1004300127777:3` |
| WorkVault | 5 | `telegram:-1004300127777:5` |
| Backlog | 6 | `telegram:-1004300127777:6` |
| Monitoring | 7 | `telegram:-1004300127777:7` |
| Personal | 8 | `telegram:-1004300127777:8` |
| Messages | 6556 | `telegram:-1004300127777:6556` |
| Errors | 11112 | `telegram:-1004300127777:11112` |

`Hermes DEV` (:4) и `:2` в группе **удалены** — не включать их в канон и не искать в логах; отсутствие `group:-1004300127777:2`/`:4` это ожидаемо, а не признак поломки.

**Питфолл — отправка в несуществующий thread_id молча уходит в General (:1).** `sendMessage` с `message_thread_id`, которого нет в группе, возвращает `ok:true`, но текст ложится в общий чат General вместо топика — без ошибки. При массовой рассылке названий по топикам это даёт «лишние» сообщения в General. Перед рассылкой сверь каждый thread_id с каноном (реальный ли топик), а не доверяй `--list`/кэшу.

**Питфолл — human-readable названия топиков Bot API НЕ отдаёт.** У Telegram Bot API нет метода «список
топиков форума»: `getChat` возвращает только `is_forum: true` без названий, а `--list`/`send --list`
отдают голые `thread_id`. Названия бот видит лишь как события `forum_topic_created`/`forum_topic_edited`
в polling (редкие). Hermes названия топиков нигде не хранит (`state.db`/`sessions/` пусты: inbound без
@mention не пишется в сессию, тела сообщений не логируются PII-фиксом). Поэтому маппинг
«название ↔ thread_id» брать ТОЛЬКО из канона `references/sirene-workspace-topics.yaml` или от Саши
(назвать текстом), и не тратить ходы на «прочитать названия» из топиков/логов/getUpdates — это тупик.

Отправка: `POST api.telegram.org/bot<TOKEN>/sendMessage`, параметры
`chat_id=-1004300127777`, `message_thread_id=<thread>`, `text=...`.
**Без `parse_mode`** для технических сообщений/ошибок (трейсбеки с `_`,`*`,`\`` ломают
Markdown-валидацию Telegram → тихая недоставка). Для бизнес-уведомлений parse_mode можно.

## Два канала доставки: различай

- **Штатный `deliver` крона** (`telegram:-1004300127777:<thread>`) — для бизнес-потока инструмента.
  У `no_agent`-скриптов реальный адрес = только поле `deliver` в jobs.json (не docstring/комментарий).
- **Прямой HTTP из скрипта/шины** — когда нужно писать в топик мимо `deliver` (напр. ошибки → Errors,
  т.к. на успехе крона stderr стирается scheduler'ом). Использует `TELEGRAM_BOT_TOKEN`.

## Питфолл: фоновый исполнитель + `/new` → потеря контекста отчёта

Когда большой цикл (ТЗ→архитектор→исполнитель) запущен как фоновый процесс
(`agent -p ...` + `notify_on_complete=true`), а Саша делает `/new` до завершения:
результат `notify_on_complete` придёт в НОВУЮ сессию — она не помнит контекст задачи.
- Держать исполнителя в текущей сессии до конца, собрать связный отчёт, потом `/new`.
- Если сброс неизбежен — перед `/new` записать контекст-маркер (задача, пути, что дальше)
  в файл (ТЗ / `/tmp/<tool>-*.md`), чтобы новая сессия восстановила картину чтением диска.

## Проверка статуса крон-задачи

Никогда не угадывать статус по памяти: `hermes cron list` + `ls -t cron/output/<job_id>/` +
хвост `agent.log`. В большинстве случаев задача уже завершена к моменту разговора.

## Диагностика «топики группы перестали отвечать» (после рестарта gateway)

Симптом: DM отвечает, а групповые топики молчат. Три причины, от самой частой:

### (1) Allowlist-гейт: `.env` `TELEGRAM_ALLOWED_CHATS` тенью накрывает YAML (env-over-YAML)

**Самая вероятная после рестарта gateway с новым кодом.**

Механизм: gateway принимает входящие только из списка, собранного `extra_or_secret` — **сначала
env, потом YAML extra**. Если в `~/.hermes/.env` (и `profiles/default/.env`) задан
`TELEGRAM_ALLOWED_CHATS=400307920` (только DM, без группы), он накрывает
`config.yaml` `telegram.allowed_chats: 400307920,-1004300127777`, и группа молча отбрасывается
на allowlist-гейте (`_should_process_message` → False) **без лога**. DM жив именно потому, что
private chat не проходит этот гейт; бот может быть админом группы и штатно поллить — тишина всё
равно будет.

ЭТО наблюдается после апдейта ядра: до рестарта старый код не перечитывал env-гейт, после
рестарта новый подхватил узкий `.env`. Узкий `TELEGRAM_ALLOWED_CHATS` может лежать в `.env`
месяцами, не мешая — пока процесс не перезапустят на env-over-YAML.

**Проверка (быстрая, до токена):** `bash ~/.hermes/skills/devops/tutu-telegram-delivery/scripts/restore_telegram_topics.sh check` или `dry-run`. Если drift по allowlist — `apply` + рестарт gateway. **Не** добавлять группу
через новый ключ / `guest_mode` / второй адаптер и **не** делать UNION yaml∪env (сломает
«env = сузить список»).

### (2) Не тот бот-токен

gateway поллит `gateway.telegram.token` (DM-only, не в группе) вместо `TELEGRAM_BOT_TOKEN`
(sirene, админ группы).

### (3) Двойной поллер → 409 → потеря апдейтов

`multiplex_profiles:true` поднимает 2-й адаптер на тот же токен, или зависший pre-restart socket.

Порядок дифференциальной проверки (отличает (1) от (2)/(3)):

1. **Боты живы** — `getMe` на ОБА токена: ok ≠ бот в группе.
2. **Бот в группе?** — `getChatMember` (sirene→administrator) или `sendMessage` в топик:
   `ok:true` = доставляет; `chat not found` = того бота в группе нет → физически не может
   ни услышать, ни ответить этим токеном (причина (2)).
3. **Кто реально поллит?** — `getUpdates?limit=1&timeout=<N>` на каждый токен:
   `409 Conflict: terminated by other getUpdates request` = этот токен **активно поллит** другой
   процесс (причина (3)); `ok:[]` = никто не держит поллинг в этот миг. Отрицательный результат
   слабый: поллинг ходит с окнами; 409 — сильный положительный.
4. **Бот в группе И поллит штатно, а группа всё равно молчит → причина (1): allowlist.**
   Проверь `TELEGRAM_ALLOWED_CHATS` в .env (обе копии) первым делом — не трать время на токен
   и поллинг, если бот-тот-что-надо и 409 нет.
5. **Лог gateway** (`~/.hermes/logs/gateway.log`) около рестарта для (1)/(3):
   - `pruning stale sessions ... telegram:group:-1004300127777:<thread> (session_reset)`
     = топики были забыты при рестарте; до рестарта были `inbound ... chat=-1004300127777`.
   - `Telegram polling conflict ... only one bot instance` = (3): два поллера на токен.
   - отсутствие `inbound ... chat=-1004300127777` при живых DM при (1) — allowlist-гейт молчит.
6. **Сверь cfg**: `hermes config get gateway.telegram.token` (DM бот) vs `TELEGRAM_BOT_TOKEN`.
   При апдейте ядра возможен дрейф/миграция токена в `config.yaml` (mtime изменился), хотя `.env`
   не трогали — сравни с **бэкапом** config (`~/.hermes/config.yaml.bak-*`), не только с текущим
   (причина (2); сопутствующая мина — держать один бот-токен на `Platform.TELEGRAM`, второй бот
   двойного-членства не нужен).

**Проверь, что поллит именно gateway, а не dashboard-serve.** На ВМ живут ДВА hermes-процесса:
`hermes-gateway.service` (`gateway run` = telegram-поллер, пишет `~/.hermes/logs/gateway.log`,
отвечает в топики/DM) и `hermes-serve.service` (`hermes serve --port 9119` = dashboard/remote
backend для Hermes Desktop, HTTP-API, НЕ поллит telegram). Дифференцировать:
`ps -eo pid,ppid,lstart,cmd | grep -E "hermes (serve|gateway)"`, затем
`ls -la /proc/<pid>/fd | grep gateway.log` — gateway держит fd на gateway.log, serve нет.
Не читай allowlist/токен из `/proc/<serve_pid>/environ`: serve стартовал раньше (до фикса) и
держит устаревший узкий `TELEGRAM_ALLOWED_CHATS` в памяти, но топики НЕ режет — он не поллит.
Актуальный поллер всегда 2135122-style (недавний рестарт), у него env telegram может быть пуст
в process-environ — секреты он читает из `.env`-файлов/профилей через `gateway/config_env.py`,
не из process env. Если сомневаешься, кто поллит — `ss -tnp | grep api.telegram` (кто в сетевом
поллинге).

Помни: исходящая доставка (`sendMessage`) и входящий поллинг — **разные** каналы. `sendMessage`
smoke подтверждает лишь, что бот в группе, а не что gateway слушает её. А **allowlist-гейт** —
третий, самый тихий слой: он срабатывает после поллинга и режет группу до `inbound`-лога, поэтому
«бот в группе + поллит живой + тишина» почти всегда = `.env` `TELEGRAM_ALLOWED_CHATS`.