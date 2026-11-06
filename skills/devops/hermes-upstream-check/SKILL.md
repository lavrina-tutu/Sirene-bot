---
name: hermes-upstream-check
description: "Проанализировать диф между нашей текущей базой апстрима herm"
version: 2.2.1
author: agent
tags: [hermes, upstream, git, update, devops, cron]
platforms: [linux]
---

# Hermes Upstream Check

Структурированный анализ изменений апстрима `NousResearch/hermes-agent` между нашей базой и `origin/main`, плюс фиксированный автоматический паттерн для самого обновления. Цель — решение "обновляться/ждать/отложить" на фактах из git, а не пересказ "N коммитов, читай сам".

## Когда использовать

- Саша спрашивает "какая версия апстрима" / "что нового" / "стоит ли обновляться" / "обновляемся по плану"
- Еженедельный крон **"Upstream hermes-agent monitor"** (`upstream_monitor.sh` + этот скилл читает/интерпретирует вывод)
- Перед плановым обновлением `~/hermes-agent`

## Часть 1 — Анализ: 8 критериев + сбор данных

```bash
cd ~/hermes-agent
REPO_BASE=$(hermes --version | grep -oP 'upstream \K[a-f0-9]+')
git fetch origin main --quiet
HEAD_SHA=$(git rev-parse origin/main)
git log $REPO_BASE..$HEAD_SHA --format="%h %ai %s"
git diff --name-only $REPO_BASE $HEAD_SHA
```

Готовый скрипт `~/.hermes/scripts/upstream_monitor.sh` уже делает это + feat/fix/refactor-счётчики, находит "наши" компоненты, ведёт `watch_list` — предпочитай его, не пиши git-команды с нуля.

| # | Критерий | Что искать |
|---|---|---|
| 1 | Донастройка/конфликт | Пересечение диффа с нашими файлами (`cron/`, `gateway/platforms`, `agent/prompt_builder.py`); `config.*schema\|DEFAULT_CONFIG` → возможна миграция конфига. Плюс `extra_or_secret\|TELEGRAM_ALLOWED\|allowed_chats\|env.*YAML` — сверка с **нашим `.env`**, не только YAML (Pitfall #6) |
| 2 | Экономия токенов | `token\|cost\|cach\|compress` |
| 3 | Фиксы нашего функционала | `telegram\|gateway\|cron\|delegat\|subagent\|heartbeat\|stale` — с человеческим объяснением "что чинит" |
| 4 | Устойчивость/надёжность | `crash\|corrupt\|WAL\|deadlock\|race\|leak\|drain\|SIGTERM` — самая весомая категория для VM |
| 5 | Выдержка стабильности | Коммит revert-нут в том же диапазоне, ИЛИ fix без теста в критичной зоне → карантин 2 цикла (см. watch_list) |
| 6 | 🚨 Security вне очереди | `security\|CVE\|vulnerab\|auth.*bypass\|credential leak\|privilege escalation` — рассмотреть немедленно |
| 7 | 🔇 Платформенный шум | `windows\|win32\|macos\|darwin\|schtasks\|powershell` — не в фокусе (Linux VM), не путать объём с релевантностью |
| 8 | Новые фичи | `feat(...)` в интересных зонах (провайдеры, toolset'ы, delegation/cron API) — апсайд, не только риск |

**watch_list** (`~/.hermes/upstream-monitor.json`, рядом с `last_sha`): коммит из критерия 5 → добавляется с `cycles_pending: 1`; на следующем еженедельном цикле, если всё ещё в диапазоне → `+1`; при `cycles_pending >= 2` — "выдержал срок", учитывается в обычной категоризации. Если `last_sha` продвинулся дальше коммита — запись удаляется.

**Правило продвижения `last_sha`** (чинили 15.07.2026): продвигается ТОЛЬКО когда `~/hermes-agent` реально обновлён (`git merge-base --is-ancestor $LAST_SHA $LOCAL_HEAD` подтверждает HEAD ушёл вперёд). Если репозиторий не менялся — `last_sha` остаётся прежним, диапазон анализа накапливается неделя за неделей до реального апдейта. Иначе "выдержка" технически не работает (коммит выпадает из диапазона до срока).

**Сверять `last_sha` с `origin/main` ПЕРЕД риск-анализом, база == merge-base, не last_sha:** `last_sha` в `upstream-monitor.json` может выпасть из истории `origin/main` (напр. монитор однажды считал диф от форк-ветки другого происхождения) — тогда диапазон `last_sha..origin/main` даёт ложный гигантский коммит-счёт (тысячи вместо сотен) и риск-анализ гоняется по неверной базе. Перед расчётом диффа проверить: `git merge-base --is-ancestor $LAST_SHA origin/main && echo ok || echo DRIFT`. При DRIFT базой брать локальный HEAD, реально смерженный в `origin/main` (`git merge-base HEAD origin/main` = `a938f00f...`), а не `last_sha` — иначе запущенный архитектор проанализирует не тот диф. Само расхождение — дефект монитора, завести на исправление.

**Формат отчёта:**
```
🔔 Upstream hermes-agent: N новых коммитов
## По категориям (только непустые): 1/2/3/4/6🚨/8
⏳ На выдержке: N коммитов, M ждут ещё 1 цикл
🔇 Не касается нас: N коммитов
## Итог: 🟢/🟡/🔴 + обоснование в 3-5 пунктов
```

## Часть 2 — Паттерн обновления (после решения 🟢/🟡)

Установлен 15.07.2026, обязателен для ЛЮБОГО апстрим-апдейта этого репозитория, не только текущего случая — не переспрашивать/не придумывать заново.

### Цикл: план архитектора → исполнение → эскалация

| Шаг | Роль | Модель |
|---|---|---|
| Risk-анализ | архитектор | cursor-grok-4.6-high |
| План vN | архитектор | cursor-grok-4.6-high |
| Исполнение (поэтапный merge) | исполнитель | composer-2.5 |
| Эскалация / доп.план vN+1 / откат | архитектор | cursor-grok-4.6-high |

В паттерне ЗАПРЕЩЕНО использовать Anthropic Opus, Claude Sonnet, claude-sonnet-5-thinking-* — только наши модели выше.

1. **Risk-анализ (архитектор cursor-grok-4.6-high, read-only)** — реальные `git diff`/`git show` по каждому потенциально конфликтному файлу (не заголовки), вердикт по security/breaking changes/config-миграции применительно к НАШЕЙ конфигурации. Ноль side-effects: чтение, либо `git worktree add /tmp/<name> origin/main` для исследования. **Обязателен directory-tree diff, не только content-diff** (см. Pitfall #1). **Обязателен аудит live-конфига платформ: YAML + `.env`, не YAML отдельно** (см. «После FF» и Pitfall #6) — precedence `env → YAML extra → default` (`extra_or_secret`) ломает доставку, если в `.env` лежит узкий allowlist/другой токен, а в YAML «всё правильно». Сохраняется в `~/WorkVault/Hermes-Backlog/upstream-update-analysis-<date>.md`.
2. **План (архитектор cursor-grok-4.6-high)** — читает анализ, пишет `~/WorkVault/Hermes-Backlog/upstream-update-PLAN-<date>-v<N>.md`:
   - (а) git safety net первым шагом — backup-ветка `backup/pre-upstream-<date>` + бэкап `~/.hermes/config.yaml` **и обеих** `.env` (создаются один раз за попытку, переиспользуются во всех циклах)
   - (б) **ветка прогресса** `upstream-merge-in-progress` — реальный merge коммитится СЮДА, не в рабочую ветку напрямую; НЕ откатывается автоматически при отклонениях
   - (в) поэтапный merge с критерием успеха на каждом шаге
   - (г) МОДУЛЬНОЕ тестирование (cron/scheduler, gateway/platforms, auxiliary, config migration, MCP, base smoke) — от дешёвого к дорогому. Config migrate: бэкап `config.yaml` **и обеих** `.env` (`~/.hermes/.env`, `~/.hermes/profiles/default/.env`); после migrate — diff токена/allowlist/multiplex (см. «Миграция конфига без потери мульти-токен связки»). Юнит-тесты **не** заменяют post-FF доставку в группу.
   - (д) **самодостаточный whitelist** уже разобранных проблем — см. правило передачи контекста ниже
   - (е) явный запрет исполнителю: не импровизировать, не чинить самостоятельно, не расширять скоуп, не откатывать без указания
   - (ж) в финальный план — чеклист «После FF» (группа + DM). `hermes doctor` / `cron list` / одно сообщение в DM **недостаточны**.
3. **Исполнение (исполнитель composer-2.5)** — план как ТЗ, пункт за пунктом, в ветке прогресса, коммитит каждый пройденный этап, ведёт чеклист прогресса в файле плана. При ЛЮБОМ отклонении вне whitelist — **не чинит, не импровизирует, не откатывает**: фиксирует точное состояние (текст ошибки, SHA, пройденные шаги) и эскалирует к архитектору. Ветка прогресса не трогается.
4. **Эскалация к архитектору** — разбирает причину (регрессия апстрима / flaky / архитектурный рефакторинг / наша несовместимость) С УЧЁТОМ прогресса в ветке — не с нуля. Переделывает план (`-v<N+1>.md`): либо шаг обхода/фикса (работа продолжается в той же ветке, без отката), либо явное "откатываемся" с указанием точки. **Откат — только осознанное решение архитектора в новом плане, никогда автоматическая реакция исполнителя.**
5. Финализация (успех) — fast-forward merge `upstream-merge-in-progress` → исходная рабочая ветка. Рестарт gateway — НЕ автоматический шаг; отдельное решение Саши после завершения git-части. **Git-FF + зелёные тесты ≠ апдейт закрыт.** Закрытие попытки — только после чеклиста «После FF» (аудит на диске сразу; живой smoke группы+DM — после рестарта, если Саша его дал).

### Правило передачи контекста (обязательно на каждой эскалации)

Каждый крон/agent -p к архитектору (cursor-grok-4.6-high) для разбора отклонения ОБЯЗАН включать текстом (не просто ссылку на файл):
- Полную хронологию всех версий плана этой попытки и что в каждой произошло
- Полный список уже разобранных/whitelisted проблем с обоснованием
- Точный whitelist, сформированный в предыдущей эскалации

**Правило форматирования whitelist:** любое исключение теста/файла в диагностике архитектора (`--deselect`, ручной вычет) ОБЯЗАНО быть перенесено явным пунктом в whitelist следующей версии плана — не должно оставаться только в командах диагностики. Whitelist обязан быть самодостаточным: исполнитель сверяется ТОЛЬКО с ним, не реконструируя логику из истории.

Причина: кроны не имеют памяти между сессиями — каждый запуск видит только то, что явно написано в промпте или лежит в указанных файлах. Пропуск факта — это «планировщик этого факта не видел», не «забыл» (прецедент 16.07, тогдашние роли Opus/Sonnet — тест `test_honcho_cache_busting_config_memoized_by_mtime` был признан flaky в диагностике к v4, но не попал в explicit-whitelist плана v4 → исполнитель остановился на уже разобранном кейсе повторно).

### Автоматический режим и лимит циклов

Весь цикл идёт **автоматически, без остановки на подтверждение между итерациями** — Сирень создаёт следующий cronjob сразу по получении отчёта, не дожидаясь команды "продолжаем".

- **Счётчик обязателен**: каждая версия плана = один цикл. Номер цикла явно проговаривается в промпте каждого нового крона ("цикл 4 из 5").
- **Жёсткий лимит — 5 циклов.** После 5-го (успех или новая эскалация) — Сирень останавливается, НЕ создаёт 6-й цикл сама. Заказывает/собирает сводный анализ всех 5 циклов, докладывает Саше (статус, история решений, явный вопрос продолжать/закрыть).
- Если обновление завершилось успехом раньше лимита — тоже стоп и доклад: git-часть готова; рестарт gateway — отдельное решение Саши; **после рестарта обязателен чеклист «После FF»** (группа + DM, не только doctor/cron).
- **Решение Саши после отчёта:**
  - *"Прекращаем"* — попытка закрывается; ветка прогресса/backup/config.bak НЕ удаляются автоматически.
  - *"Продолжаем"* — новый пайплайн, но не с нуля: следующий архитектор (cursor-grok-4.6-high) получает полную сводку прошлых циклов (см. правило передачи контекста). Счётчик сбрасывается на 1, наработки переиспользуются. Новый лимит — снова 5.

### Разовая чистка перед первым циклом новой попытки

Перед самым первым risk-анализом новой попытки: просмотреть MEMORY на предмет питфоллов/заметок по апстрим-обновлениям этого репозитория и перенести их сюда (в Pitfalls ниже), удалив из MEMORY после подтверждения переноса (не дублировать факт в двух местах). Процедурные детали живут в скилле, не в общей памяти.

## После FF: проверка мульти-платформенной доставки (обязательна)

Прецедент 16.09.2026: git-FF `v2026.9.14` + тесты зелёные + рестарт gateway → **DM жив, топики группы молчат**. Паттерн счёл апдейт успешным. Реальный inbound группы умер на allowlist-гейте (env-over-YAML); это увидели только живым сообщением в группе.

**Вердикт попытки = git-FF + (если был рестарт) PASS этого чеклиста.** DM-only / `hermes doctor` / cron outbound в топик — не доказательство, что gateway видит группу.

Шаг 7 в `references/upstream-merge-steps.md` (`hermes doctor` / `status` / `cron list`) — import/health, **не** этот чеклист. Не закрывать попытку по шагу 7.

### Когда рестарт допустим и что за ним

- Рестарт **не** часть git-исполнения (Pitfall #2). FF оставляет в памяти старый байткод — это нормально до явного «рестартуй» Саши с окном.
- Рестарт — момент, когда новый код **и** новый конфиг с диска входят в процесс. Правка `.env`/`config.yaml` без рестарта = диск ≠ runtime; не объявлять «починено».
- После разрешённого рестарта агент **сам** гоняет чеклист ниже (не «Саша напиши в DM и скажи ок»). Живой getUpdates/smoke в Telegram — только если Саша явно разрешил рестарт+проверку; иначе ограничиться аудитом на диске + логам уже существующих inbound.
- Конкурирующий `getUpdates` на боевом токене **запрещён**, пока gateway в polling: это 409 → `_handle_polling_conflict` + `drop_pending_updates=True` (теряется очередь). Кто поллит — смотреть по `gateway.log` / `gateway_state.json`, не перехватом long-poll.

### Аудит на диске (сразу после FF, до рестарта)

Сверять **эффективные** значения, не «что написано в YAML».

| Проверка | Как | PASS |
|---|---|---|
| Код vs процесс | `gateway_state.json` `code_sha` vs `git rev-parse HEAD` | до рестарта SHA **разъедутся** (ожидаемо); после — совпадают |
| Токен-аудит | bot-id prefix `TELEGRAM_BOT_TOKEN` в `~/.hermes/.env` **и** `profiles/default/.env` vs `gateway.telegram.token` в YAML | один и тот же бот; это админ группы «Сирень Workspace» (`863022…` / `sirene_vm_bot`). YAML `882117…` (AlexHermesLocal1) — мина: `_Cred` в runtime берёт env, но если env пропадёт, poller уйдёт на бота вне группы |
| Allowlist | `TELEGRAM_ALLOWED_CHATS` в обеих `.env` vs `telegram.allowed_chats` в YAML | в **эффективном** сете есть DM `400307920` **и** группа `-1004300127777`. Env, если задан, **побеждает** YAML (`extra_or_secret`, `gateway/platforms/_shared.py`) |
| Не путать ключи | `TELEGRAM_ADDITIONAL_STARTUP_CHANNELS` / `TELEGRAM_HOME_CHANNEL` | это не inbound-allowlist |
| Снимок топиков | `bash ~/.hermes/skills/devops/tutu-telegram-delivery/scripts/restore_telegram_topics.sh check` | exit 0; при расхождении — `dry-run`, `apply` только с явного решения |
| Multiplex | `gateway.multiplex_profiles` + какие профили имеют свой telegram `.env` | второй poller на тот же токен = 409. Скелеты без `.env` telegram не поднимают |

Греп апстрим-диффа в risk-анализе (критерий 1), если трогались адаптеры/platforms: `extra_or_secret`, `TELEGRAM_ALLOWED_`, `allowed_chats`, `env → YAML`, `get_scoped_secret`. Сверять с **нашим** `.env`, не только с YAML. Коммит-класс `3dedb71f2f` (13.09.2026, env-first) на нашей базе `d01cc627` отсутствовал и пришёл мерджем 16.09 — YAML-only ревью это пропустило.

### Живой smoke после рестарта (если рестарт был)

Минимум **два канала**, иначе регрессия 16.09 повторится:

1. **DM** `400307920` — ответ пришёл. Сам по себе **недостаточен**: `_should_process_message` для private сразу `True`, allowlist групп не трогает.
2. **Группа** «Сирень Workspace» `-1004300127777` — сообщение в любом живом топике канона (каталог в `tutu-telegram-delivery/references/sirene-workspace-topics.yaml`). В `gateway.log` после рестарта: `inbound` с `chat=-1004300127777` **и** ответ в тот же `message_thread_id`.
3. Cron/уведомление в топик **не** считается: исходящая доставка идёт Bot API напрямую, минуя inbound-гейт gateway.
4. Если группа тихая при живом DM: **сначала** эффективный allowlist и токен poller, не forum-роутинг / prune sessions / multiplex. WARNING `Dropped inbound` в адаптере — искомый лог (если патч влит).

Канон топиков — 7 (без удалённого `Hermes DEV :4`, без `:6556`). Отсутствие inbound `:4` — ожидаемо, не поломка.

### Миграция конфига без потери мульти-токен связки

`hermes config migrate` (у нас 16.09: 33→44) **не пишет `.env`**. Узкий `TELEGRAM_ALLOWED_CHATS` в `.env` с ≥14.08 пережил migrate нетронутым и после рестарта накрыл правильный YAML. Токен в YAML 16.09 тоже не подменился migrate'ом (бэкап 11:56 = `882117…`); «restore our defaults» вернуло display/delegation/curator (`all/50/3/30/90`), не telegram.

Перед migrate:

```bash
cp -a ~/.hermes/config.yaml ~/.hermes/config.yaml.bak-<date>
cp -a ~/.hermes/.env ~/.hermes/.env.bak-<date>
cp -a ~/.hermes/profiles/default/.env ~/.hermes/profiles/default/.env.bak-<date>
```

После migrate, **до** рестарта gateway — diff bak↔live (только id, не полный секрет):

```bash
python3 - <<'PY'
import yaml
from pathlib import Path
def bot_id(s):
    s = (s or "").strip(); return s.split(":",1)[0] if s else ""
live = yaml.safe_load(Path.home().joinpath(".hermes/config.yaml").read_text())
print("version", live.get("_config_version"))
print("yaml_token_id", bot_id((live.get("gateway") or {}).get("telegram", {}).get("token")))
print("yaml_allowed", (live.get("telegram") or {}).get("allowed_chats"))
print("multiplex", (live.get("gateway") or {}).get("multiplex_profiles"))
PY
# плюс: grep -E '^TELEGRAM_(BOT_TOKEN|ALLOWED_CHATS)=' обеих .env — сравнить bot-id prefix и csv с YAML
```

Правила восстановления после migrate:

- Poller = бот-админ группы (`TELEGRAM_BOT_TOKEN` / `863022…`). YAML `gateway.telegram.token` привести к тому же id, не оставлять второй бот «на всякий».
- Эффективный `allowed_chats` должен содержать группу. Предпочтительно: политика в YAML, ключ `TELEGRAM_ALLOWED_CHATS` **убрать** из `.env` (`.env` = секреты). Если ключ оставляем — csv обязан включать группу, иначе env-over-YAML снова отрежет inbound.
- Не считать «restore defaults» покрытием telegram-связки. Канон топиков возвращать модулем `restore_telegram_topics.sh apply`, не руками.

## Pitfalls

1. **Content-diff недостаточен — нужен structural/path diff.** Прецедент 15.07.2026: `git diff`/`git merge-tree` показали 0 конфликтов, но модульный тест упал с `ModuleNotFoundError: No module named 'gateway.platforms.telegram'` — апстрим переместил telegram-адаптер в `plugins/platforms/telegram/adapter.py`. Content-diff этого не видит (файл просто отсутствует по старому пути). **Risk-анализ обязан включать** `git ls-tree -r <base> -- <dir>` vs `git ls-tree -r origin/main -- <dir>` (или `--find-renames`) по каждой затронутой директории — особенно `gateway/platforms/`, `plugins/`, `agent/`, где апстрим практикует периодические архитектурные рефакторинги.
2. **Рестарт gateway без подтверждения** допустим ТОЛЬКО если Саша явно разово разрешил на конкретное окно времени ("в течение 2 часов от начала задачи") — разрешение НЕ переносится на следующую попытку/цикл, каждый раз новое явное разрешение с окном. После разрешённого рестарта чеклист «После FF» обязателен **до** закрытия попытки: группа + DM, токен-аудит, эффективный allowlist. Рестарт без этого чеклиста — дыра 16.09.
3. **Тестирование правок `upstream_monitor.sh` без риска для боевого state** — скрипт хардкодит `STATE=~/.hermes/upstream-monitor.json` и `REPO=~/hermes-agent`, нельзя гонять "для проверки" напрямую:
   ```bash
   rm -rf /tmp/hermes-agent-test && cp -r ~/hermes-agent /tmp/hermes-agent-test
   cd /tmp/hermes-agent-test && git checkout <some-sha-ahead> --quiet
   cp ~/.hermes/upstream-monitor.json /tmp/test-state.json
   sed "s|STATE=\"\$HOME/.hermes/upstream-monitor.json\"|STATE=\"/tmp/test-state.json\"|; \
        s|REPO=\"\$HOME/hermes-agent\"|REPO=\"/tmp/hermes-agent-test\"|" \
        ~/.hermes/scripts/upstream_monitor.sh > /tmp/test_monitor.sh
   bash /tmp/test_monitor.sh
   rm -rf /tmp/hermes-agent-test /tmp/test-state.json /tmp/test_monitor.sh
   ```
   Прогнать минимум 2 сценария: без апдейта (`last_sha` не двигается) и с симулированным апдейтом (`last_sha` подтягивается). Проверить боевой `upstream-monitor.json` не изменился.
4. **Не путать со скиллом `hermes-skills-discovery`** — тот мониторит сторонние скиллы в экосистеме (skills.sh/GitHub/clawhub), не апдейты этого репозитория.
5. **`hermes --version` "+N carried commits" ≠ N кастомных патчей — не отвечать на вопрос "актуальны ли наши коммиты" без проверки.** Прецедент 16.07.2026: версия показала "+13271 carried commits" (upstream `5f171e36`, local `03f8f5fe`), Саша спросил, нужны ли эти коммиты или уже неактуальны — предполагая большой слой самописной кастомизации для ревью. Реальность: это была история только что влитого (15-16.07) крупного апстрим-апдейта; собственно нашего авторства среди них — единицы (progress-маркеры того же мерджа), не функциональный код. **Перед ответом на такой вопрос — сначала измерить, а не пересказывать счётчик из `hermes --version`:**
   ```bash
   cd ~/hermes-agent
   git log <local_branch> --not origin/main --author="<наш agent author name>" --oneline | wc -l   # реально наше
   git log <local_branch> --not origin/main --oneline | wc -l                                        # весь "carried commits" счётчик
   git merge-base --is-ancestor <REPO_BASE_from_version> <local_branch> && echo YES || echo NO       # база апстрима реально смержена?
   bash ~/.hermes/scripts/upstream_monitor.sh   # актуальный диф от last_sha — обычно на порядки меньше "carried commits"
   ```
   Если "carried commits" ≈ история недавно влитого апстрима, а не кастомный слой — прямо сказать это Саше вместо "анализирую N коммитов на актуальность"; настоящий открытый вопрос обычно сводится к 1-2 висящим коммитам поверх `last_sha` в `upstream-monitor.json`.
6. **Env-over-YAML молча режет группу, DM остаётся живым.** Прецедент 16.09.2026: после FF + рестарта `TELEGRAM_ALLOWED_CHATS=400307920` в `.env` (с ≥14.08) победил YAML `400307920,-1004300127777`. Контракт `extra_or_secret` — env → YAML extra → default (`3dedb71f2f`, 13.09). До рестарта процесс жил на старом коде (YAML extra первым) — группа отвечала. После — inbound группы дропался без лога; `_should_process_message` для DM сразу True. **Risk-анализ, смотрящий только YAML `allowed_chats`, эту регрессию не видит.** Не чинить forum/prune/multiplex, пока не сверен эффективный allowlist.
7. **Два бота на один `Platform.TELEGRAM` — мина, не всегда primary.** YAML `gateway.telegram.token` last-wins среди блоков; runtime `_Cred` перезаписывает токен из `TELEGRAM_BOT_TOKEN`, если env непустой. 16.09 poller был правильный (`863022`, админ группы), YAML держал `882117` (бота нет в группе). Симптом «слушает не того бота» — соседний отказ, если env токена когда-нибудь пропадёт. После migrate сверять **оба** источника по bot-id prefix.
8. **409 getUpdates во время диагностики — часто self-conflict.** Ручной `getUpdates` на токене живого poller даёт 409; адаптер рестартит polling с `drop_pending_updates=True` и теряет очередь. Не использовать конфликт как датчик «кто поллит». `TELEGRAM_ADDITIONAL_STARTUP_CHANNELS` — не allowlist. Cron outbound в топик ≠ inbound gateway.
9. **`references/upstream-merge-steps.md` шаг 7 (`hermes doctor` / `status` / `cron list`) недостаточен как post-FF smoke.** Это import/health, не доставка. Живой критерий — чеклист «После FF» в этом файле. План апдейта, где §9.2 = «Саша напиши в DM», закрывает только канал, который allowlist не фильтрует.

## Связанные материалы

- `~/.hermes/scripts/upstream_monitor.sh` — сбор данных + watch_list, no_agent-safe
- Крон "Upstream hermes-agent monitor" (искать через `cronjob(action='list')` по имени) — еженедельно, `0 4 * * 6`
- Скилл `hermes-agent` — команды `hermes update`/`config migrate`/`doctor`
- Скилл `tutu-telegram-delivery` — снимок топиков + `scripts/restore_telegram_topics.sh` (`check`/`dry-run`/`apply`)
- `~/WorkVault/Hermes-Backlog/upstream-update-analysis-<date>[-vN].md` / `upstream-update-PLAN-<date>[-vN].md` — документы каждой попытки
- `~/WorkVault/Hermes-Backlog/upstream-postmortem-2026-09-16.md` — разбор сбоя группы после FF v2026.9.14
- `~/WorkVault/Hermes-Backlog/TZ/TelegramGroupTopics/appendix_upstream_context_20260916.md` — выжимка для топика upstream

## Verification Checklist

- [ ] Risk-анализ включает directory-tree diff (не только content-diff) для всех затронутых директорий
- [ ] Risk-анализ сверил live YAML **и** `.env` платформ (токен bot-id, `TELEGRAM_ALLOWED_CHATS`, multiplex), не YAML отдельно
- [ ] Backup-ветка + бэкап `config.yaml` **и обеих** `.env` созданы один раз за попытку, не пересоздаются на каждом цикле
- [ ] После `config migrate` — diff bak↔live: token id, `allowed_chats`, multiplex; `.env` не «пропал» и не уже YAML
- [ ] Ветка прогресса `upstream-merge-in-progress` не откатывается автоматически при отклонении
- [ ] Whitelist в каждом плане самодостаточен — переносит все исключения из предыдущих диагностик явным текстом
- [ ] Эскалация к архитектору включает полную хронологию попытки, не только последнее отклонение
- [ ] Счётчик циклов ведётся, лимит 5 соблюдается, на 5-м — обязательный стоп и отчёт Саше
- [ ] Рестарт gateway не выполняется без свежего явного разрешения с указанным окном времени
- [ ] После FF (и после рестарта, если был): чеклист «После FF» — токен-аудит, эффективный allowlist, smoke **группы и DM**, без диагностического getUpdates
- [ ] Вердикт попытки не ставится по doctor/cron/DM-only
- [ ] Перед первым циклом новой попытки — MEMORY проверена на питфоллы по теме, перенесены сюда при находке
