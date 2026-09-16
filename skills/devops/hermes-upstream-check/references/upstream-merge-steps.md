# Upstream merge — справочник команд (шаги 0–8)

## Процесс

### Шаг 0: Pre-flight
```bash
cd /home/tkachenkoav/hermes-agent
git status --porcelain | grep -E '^(UU|AA|DD)'   # пусто
test -f .git/MERGE_HEAD && echo "MERGE IN PROGRESS" || echo "CLEAN"
test -f .git/index.lock && rm .git/index.lock      # убрать лок если есть
git log -1 --oneline                                 # подтвердить HEAD
```

### Шаг 1: Baseline тестов
```bash
# Таргетный прогон (быстрее, наши зоны риска):
bash scripts/run_tests.sh -q tests/cron/ tests/gateway/ tests/agent/test_prompt_builder.py

# Полный прогон (1-2 часа, фон):
bash scripts/run_tests.sh -q 2>&1 | tee /tmp/baseline_full_tests.log
```

**ВАЖНО:** `python -m pytest -q` НЕ годится — 9 collection errors на `tests/acp*`. Всегда `scripts/run_tests.sh`.

### Шаг 2: Сухой merge
```bash
git merge --no-commit --no-ff origin/main
git diff --name-only --diff-filter=U   # список конфликтных файлов
```

### Шаг 3: Разрешение тривиальных конфликтов
Для конфликтов где апстрим заменил наш код общим решением:
```bash
git checkout --theirs <файл1> <файл2>
git add <файл1> <файл2>
```

### Шаг 4: Разрешение сложных конфликтов (Cursor CLI)
```bash
cd /home/tkachenkoav/hermes-agent && agent -p "Разреши конфликты в <файлы>. Контекст: [описание]. NE меняй другие файлы." -f --model composer-2.5 --output-format json
```

### Шаг 5: Обновление тестов (если затронуты)
Если конфликт затронул код, на который ссылаются тесты — обновить тесты через Cursor CLI:
```bash
agent -p "Обнови тесты <файл>. Функция X удалена, логика перенесена в Y." -f --model composer-2.5 --output-format json
```

### Шаг 6: Полный прогон тестов
```bash
bash scripts/run_tests.sh -q 2>&1 | tee /tmp/postmerge_tests.log
# Сравнить с baseline: фейлов НЕ больше, чем было до
```

### Шаг 7: Smoke-проверки (import/health, НЕ доставка)
```bash
hermes -p default doctor
hermes -p default status
hermes -p default cron list
```

Это **не** закрытие попытки. После FF (и после рестарта gateway, если Саша его дал) обязателен чеклист «После FF» в `SKILL.md`: токен-аудит, эффективный allowlist, smoke **группы и DM**. `doctor` / `status` / одно сообщение в DM / cron outbound в топик — недостаточны (прецедент 16.09.2026). Не делать диагностический `getUpdates` на боевом токене.

### Шаг 8: Commit
```bash
git commit --no-edit
git log -1 --oneline
```

## Стратегия: merge (НЕ rebase, НЕ squash)

- Сохраняет идентичность локальных коммитов (`hermes --version` показывает `+N carried commits`)
- Precedent: предыдущие апгрейды использовали merge-коммиты
- Rebase переписал бы хэши, на которые ссылаются внутренние файлы

## Питфоллы

1. **thinking-high таймаутится на больших задачах.** Анализ/план на 5000+ коммитов — архитектор `cursor-grok-4.6-high`; `claude-sonnet-5-thinking-*` из паттерна убрать; историческую заметку 07.08 оставить как прецедент; при нехватке объёма резать анализ по директориям (cron/gateway/plugins/agent), не откатываться на Claude.
2. **.git/index.lock** — может остаться от предыдущих сессий/Cursor. `rm .git/index.lock` перед git-операциями.
3. **`python -m pytest` не годится** — collection errors на `tests/acp*`. Всегда `scripts/run_tests.sh` (per-file subprocess isolation).
4. **Фоновые тесты убивает `pkill`** — не использовать `pkill -f` для остановки процессов, использовать `process(action='kill')` по session_id.
5. **Composer-2.5 таймаутится на промптах >4K токенов / 12+ файлов** — делить на 2-3 промпта по 4-6 файлов.
6. **Удалённые функции → сломанные тесты** — после удаления/перемещения функции ВСЕГДА grep'нуть по тестам: `grep -rn "<func_name>" tests/`.

## Откат

| Сценарий | Действие |
|---|---|
| Сухой merge пошёл не так | `git merge --abort` |
| Коммит сделан, но тесты упали | `git reset --hard <pre-merge-hash>` |
| Повреждено рантайм-состояние | Восстановить из `~/.hermes/_Archives/hermes-backup-YYYYMMDD-HHMMSS.tar.gz` |
