#!/usr/bin/env bash
# LLM-anomaly scan via Cursor architect (read-only) за последние 7 дней.
# Результат (JSON отчёта от архитектора) сохраняется в ~/WorkVault_backup/llm-anomaly-audits/
# Краткое резюме выводится на stdout для пайпа в отчёт self-check.
# Проверен 2026-08-16: без --mode plan + жёсткий read-only промпт возвращает полный отчёт.
# Вызов из cron vm_selfcheck (п.11) и вручную: bash ~/.hermes/scripts/llm_anomaly_scan.sh
set -uo pipefail

OUTDIR="$HOME/WorkVault_backup/llm-anomaly-audits"
STAMP=$(date +%Y%m%d-%H%M)
OUTFILE="${OUTDIR}/LLM-anomalies_${STAMP}.json"
mkdir -p "$OUTDIR"

# Промпт для Cursor-архитектора (окно = последние 7 дней). БЕЗ --mode plan!
cat > "/tmp/llm-anomaly-scan-${STAMP}.md" << 'PROMPTEOF'
Ты — архитектор (read-only). Проанализируй LLM-логи Hermes за ПОСЛЕДНИЕ 7 ДНЕЙ из ~/.hermes/state.db (таблица sessions). Только SELECT, режим mode=ro, БЕЗ изменений БД/конфигов/скриптов/файлов.

ЖЁСТКИЙ ЗАПРЕТ: ты НЕ можешь и НЕ будешь изменять или создавать никакие файлы, НЕ выполняешь никаких команд записи (write, mkdir, chmod, install, фиксы). Вся работа — только чтение: python3 -c/SELECT к state.db в mode=ro, чтение таблиц. Итог — текстовый отчёт в своём ответе.

Колонки: model, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, api_call_count, tool_call_count, estimated_cost_usd, message_count, source, chat_type, title, started_at, end_reason.

ВАЖНО — окно анализа: started_at >= (текущее время в unix) - 604800. Игнорируй сессии старше 7 дней. Окно можешь проверить сам.

Верни структурированный отчёт на русском, компактно, только значимое для мониторинга:
1. Краткий breakdown по моделям за 7 дней (модель, сессий, output токенов, cache_write, cost).
2. Топ-5 самых дорогих сессий за 7 дней (модель, источник, название, api_calls, cost).
3. Аномалии за 7 дней: session monster (api_call_count>500 или tool_call_count>1000); cache write bloat (cache_write>5M); terminal spam (terminal >50% tool-calls в дорогих сессиях); дублирующие/пустые сессии (model=NULL, 0 токенов, кластерами в одну секунду — ретраи/gateway); «вечные» сессии (end_reason=session_reset); cron на тяжёлых моделях для мониторинга/уведомлений.
4. Признаки ошибок: обрывы/нулевые токены при ненулевых api_calls; cost_status='unknown' (заниженный прайсинг, скрытые расходы).
5. Рекомендации применимые к текущей конфигурации + оценка экономии в $.
Если за период нет сессий или нет аномалий — прямо так и напиши.
PROMPTEOF

# Запуск Cursor-архитектора (read-only). БЕЗ --mode plan, иначе останавливается на плане
# и не выдаёт финальный отчёт. Запрет правок обеспечен жёстким промптом (только SELECT/mode=ro).
cd "$HOME" && agent -p "$(cat /tmp/llm-anomaly-scan-${STAMP}.md)" -f --model claude-sonnet-5-thinking-medium --output-format json > "$OUTFILE" 2>&1
RC=$?

# Краткое резюме на stdout
python3 - "$OUTFILE" "$RC" << 'PYEOF'
import sys, json
outfile, rc = sys.argv[1], sys.argv[2]
try:
    d = json.load(open(outfile))
    sub = d.get("subtype", "")
    if d.get("is_error") or sub != "success":
        print(f"LLM-аудит 7д: ⚠️ PROBLEM (subtype={sub}) — файл {outfile}")
        sys.exit(0)
    r = d.get("result", "")
    print(f"LLM-аудит 7д: ✅ OK (rc={rc}) — файл {outfile}")
    print((r + "…") if len(r) > 2500 else r)
except Exception as e:
    print(f"LLM-аудит 7д: ⚠️ PROBLEM (rc={rc}, не удалось прочитать отчёт: {e}) — файл {outfile}")
PYEOF