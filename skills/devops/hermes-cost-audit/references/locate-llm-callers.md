# Как найти, кто именно ходит в LLM-гейтвей (крон/инструмент/auxiliary) и каким ключом

Применять, когда пользователь говорит: «в биллинге админки вижу расход на модель X
(напр. `deepseek-v4-pro`) по ключу с хвостом …NNN — найди, кто это делает».
Внутренние логи Hermes (state.db, agent.log, крон output/*) НЕ показывают внешние
инструменты, поэтому нельзя отвечать «0 записей — значит никто». Нужен исчерпывающий
обход ВСЕХ сущностей, способных делать HTTP к гейтвею.

## Принцип
Ключ, по которому идёт расход, может жить НЕ в `~/.hermes/config.yaml`. Полное значение
ключа часто не находится тривиальным grep (секрет, зашифрован, на другой машине,
только в админке). Работай по **хвосту ключа** (последние 3–6 символов) и по **имени
модели**, никогда не раскрывая полное значение в выводе/промпте.

## Чеклист обхода — проверить каждый пункт, отметить [OK]/[PRO]/[KEY<хвост>]/[N/A]

1. **Кроны Hermes** — `~/.hermes/cron/jobs.json`. Для каждого job: id, имя, model,
   provider, base_url, script. Отдельно посмотреть `no_agent`-кроны со скриптами
   (`~/.hermes/scripts/*.sh`, `~/USERTOOLS/<tool>/*.py`) — не тянет ли скрипт
   LLM-ключ/модель из env.
2. **Auxiliary-модели** — секция `auxiliary` в `~/.hermes/config.yaml`
   (vision, session_search, compression и т.п.): какие модели и ключи.
3. **Инструменты `~/USERTOOLS/`** — перечислить все подпапки (MoveFromFF, MoveFromLoop,
   MoveFromJira, ProtocolFromSummary, ConfluenceSync, SRTool, AggregateFromMeetings,
   AnywhereContacts, MofsIndex, …). В каждой: свой `.env`, LLM-переменные
   (LLM_GATEWAY_API_KEY / OPENROUTER / ANTHROPIC / TUTU), base_url, дефолтный model,
   реально ли вызывает LLM (grep `openai|anthropic|llm-gateway|chat.completions|client.chat`)
   в `*.py`. Особо смотреть `config.py` и его бэкапы `*.bak-*` — там остаются старые дефолты.
4. **Скиллы Hermes** — `~/hermes-workspace/skills/`, `~/.hermes/skills/`: любой скилл с
   curl/HTTP к LLM или читающий LLM-ключ (cost-audit, llm_anomaly_scan, upstream-check, …).
5. **Все ключи по системе** — собрать строки-кандидаты (64-hex, `sk-`, `eyJ`, без префикса)
   из `~/.hermes/.env`, `~/.hermes/profiles/*/.env`, `~/USERTOOLS/*/.env`, `*.env.example`.
   Выводить ТОЛЬКО последние 6 символов каждого. Отметить, есть ли искомый хвост.
6. **Прочее окружение** — `~/.bashrc`, `~/.profile`, `~/.env`, `crontab -l` (user+system),
   systemd-юниты, `~/.hermes/logs/*`.

## Полезные сырые команды (read-only)

```bash
# Модель по всем конфигам/коду (отсечь .venv/venv pygments-шум):
grep -rniE "deepseek[-/]?v4[-_]?pro|v4-pro" ~/.hermes/config.yaml ~/.hermes/scripts ~/USERTOOLS ~/hermes-workspace \
  | grep -viE "\.pyc|node_modules|\.git/|site-packages|backup|_Archives"

# Дефолт модели в config.py инструмента (включая бэкапы):
grep -rn "DEDUP_LLM_MODEL\|SOME_LLM_MODEL\|os.environ.get(.*MODEL" ~/USERTOOLS/*/config.py* 2>/dev/null

# Найти значение ключа по хвосту (без раскрытия):
find ~/USERTOOLS -maxdepth 3 \( -name "*.env" -o -name "*.py" -o -name "*.sh" \) \
  | xargs grep -rEoh "[a-f0-9]{40,}|sk-[A-Za-z0-9_-]{30,}|eyJ[A-Za-z0-9_.-]{30,}" 2>/dev/null \
  | awk '{print substr($0, length($0)-5)}' | grep -i "<хвост>"
```

## Ключевые питфоллы
- **Ключ в админке ≠ ключ на ВМ.** Hermes-ключ туту-гейтвея — 64-hex из
  `custom_providers[0].api_key` в `~/.hermes/config.yaml`. Искомый хвост может быть
  ДРУГИМ ключом, которого на ВМ нет открыто (лаптоп Windows, отдельный сервис,
  другое значение в админке). Если не найден — честно сказать «на ВМ не лежит,
  источник — админка/лаптоп», а не выдумывать.
- **Списки моделей ≠ активные вызовы.** `models:` у провайдера в config.yaml — это
  просто доступные модели гейтвея, не факт использования. Не считать их потребителями.
- **Архитектор за один `--mode plan`-вызов останавливается на плане.** Для read-only
  ресёрча звать архитектора без `--mode plan` с жёстким запретом записи (см. cursor-cli).
- Если ресёрч передаётся курсору в фоне — не отчитываться «найдено X» до возврата
  результата; дождаться архитектора и проверить его вывод на диске самому
  (self-report ≠ факт, см. cursor-cli pitfall).

## Прецедент (авг 2026)
Расследование расхода `deepseek-v4-pro` по ключу …730: внутренние логи не показывали
pro-вызовов, PFS ранее имел `DEDUP_LLM_MODEL=deepseek-v4-pro` + invalid ANTHROPIC key
(fail-soft) и был переключён на flash. Полный обход по чеклисту выше — именно так
строится задача для Cursor-архитектора (см. агентский диалог 17.08).
