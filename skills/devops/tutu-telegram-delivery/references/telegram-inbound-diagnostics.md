HISTORY: the getUpdates polling recipe below is obsolete and must not be used against a live poller. Use process/service/log evidence. The restore check does not detect env-over-YAML shadowing.

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