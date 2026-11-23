---
name: llm-model-replacement-decisions
description: "Use when замена LLM-модели Hermes: DeepSeek, Luna, Gemini."
version: 1.0.0
author: agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [models, deepseek, gemini, luna, codex, cost, architecture]
    related_skills: [hermes-feature, hermes-cost-optimization]
---

# LLM-замены и дизайн-развилки по моделям

Как разбирать вопрос «заменить модель X на Y / где отказаться от DeepSeek» для Hermes tkachenkoav: собрать факты, прогнать вердикт через архитектора и ревизора, подать Саше. Включает стоящие правила Саши по замене моделей.

## When to Use

- Саша спрашивает «где можно заменить дипсик», «стоит ли перейти на X», «мнение архитектора по модели».
- Планируется смена основной/крон/вспомогательной модели Hermes.
- Оценка «скрипт вместо LLM» / no_agent для крона.

## Стоящие правила Саши (не пересматривать без него)

- **Замена LLM на скрипт / no_agent — ДА** там, где логика детерминирована: drift-check, проверки с порогами, детекторы тегов/версий. Решение принимает скрипт; LLM максимум для резюме/формулировки.
- **Замена на Gemini — НЕТ.** На OpenRouter (туту-гейтвей OpenRouter-совместим) Gemini ДОРОЖЕ DeepSeek: gemini-2.5-flash-lite $0.10/$0.40 за 1M против deepseek-v4-flash-0731 $0.0444/$0.1333 (~2.3x in, ~3x out). «Gemini дешевле» — ложная посылка; проверять цены API перед любой рекомендацией.
- **Luna (gpt-6-luna) — бесплатна по подписке Codex**, но это НЕ автоматический провайдер Hermes: отдельный `codex exec` на каждый вызов, 401 token_expired, квота с DevWorkflow, стартовый latency. Только вручную/черновики/некритичные вызовы и как LIGHT-исполнитель в DevWorkflow (≤3 файла).
- **Качество важнее мелкой экономии**: DeepSeek остаётся в ядре (основной агент, fallback, cron.model, компрессия, PFS-дедуп, координатор DevWorkflow). Не менять модель там, где теряется семантика (перефразы в дедупе, сжатие диалога, координация фаз).
- Исключения из правил — только после явного решения Саши.

## Процедура: дизайн-развилка по моделям

1. **Собрать факты с машины** (не по памяти): config.yaml (model.default, auxiliary.*, cron.model, x_search), jobs.json (агентные кроны и у кого свой model), коды инструментов (PFS DEDUP_LLM_MODEL и т.п.), и **реальные цены OpenRouter** для кандидатов:
   ```bash
   curl -s --max-time 20 https://openrouter.ai/api/v1/models | python3 -c '
   import json,sys
   for m in json.load(sys.stdin)["data"]:
       if any(x in m["id"] for x in ["deepseek-v4-flash-0731","gemini-2.5-flash-lite"]):
           p=m["pricing"]; print(m["id"], p["prompt"], p["completion"])'
   ```
2. **Промпт архитектору** (gpt-6.1-sol): по каждой позиции использования модели — вариант замены / эффект / риск / вердикт. Ограничения Саши включать дословно в промпт.
3. **Вывод архитектора — на согласование ревизору** (gpt-6-astra): полнота, соответствие ограничениям, риски, приоритет. Вердикт: согласовано / с замечаниями / не согласовано.
4. **Подать Саше**: сводная таблица «позиция → вердикт → эффект → риск» + порядок внедрения. Свои рекомендации не добавлять — только вердикты ролей.
5. **Внедрение по одобренной вырезке — по одному слагу, «по очереди».** Когда Саша отвечает «делаем только пункты N–M, остальное не трогаем, по очереди»: каждый одобренный пункт — отдельный DevWorkflow-слаг (CHANGE), запускается последовательно (следующий после `GATE:done` / отчёта предыдущего), не сливать в один граф. Отклонённые пункты не включать. Докладывать результат по каждому слагу перед стартом следующего.

## Механика вызова ролей ad-hoc (вне графа)

`pipeline invoke-role` без `--slug/--phase` возвращает молчаливый rc=0 без вывода — для разового вопроса роли вызывать codex exec напрямую:

```bash
cd <workspace> && timeout 590 codex exec -C <workspace> -m gpt-6.1-sol \
  -c 'model_reasoning_effort="high"' --skip-git-repo-check --json \
  --sandbox danger-full-access -- "$(cat /tmp/prompt.md)" > /tmp/out.json
```

Вывод — JSONL, несколько объектов (не один JSON; `json.load` на весь файл падает `Extra data`). Вердикт роли лежит под объектами `item.completed` → `item` таблицей где `item.type == "agent_message"` → читать `item.text`. Тop-level события `type == "agent_message"` могут приходить пустыми (`item.text == ""`) — не считать их итогом. Надёжнее перебрать все `item.completed`, собрать text из всех agent_message-элементов и взять последний большой текст. Модели: архитектор gpt-6.1-sol, ревизор gpt-6-astra.

**`codex exec` требует залогиненного CLI.** `codex login status` = Not logged in → вызовы уходят в `401 Unauthorized: Missing bearer...`. Логин: `codex login --device-auth`, юзер вводит код https://auth.openai.com/codex/device. ВАЖНО: device-auth процесс должен ЖДАТЬ обратного вызова, пока юзер вводит код; `timeout N`ы а foreground или короткий таймаут убивают его раньше и логин не доезжает (повторный запуск выдаёт свежий код). Запускать с persist-on-release в фоне, дать юзеру ссылку+код, затем проверить `codex login status` = "Logged in using ChatGPT" и наличие `~/.codex/auth.json`.

Ким/Муншот как провайдер (Platform pay-as-you-go vs Kimi Code подписка, модели, ограничение подписки на автоматику, назначение ролей) — `references/kimi-moonshot.md`.

## Типовые вердикты по позициям (10.2026, архитектор + ревизор)

- model.default, fallback, cron.model, компрессия, PFS-дедуп, координатор DevWorkflow → **оставить DeepSeek**.
- Ecosystem drift-check (`render_manifest.py --check-drift`) → **no_agent полностью** (детерминирован, LLM не добавляет качества).
- vm_selfcheck → детерминированные проверки скриптом, LLM-резюме/Codex-аудит аномалий отдельным опциональным шагом.
- Upstream monitor / уведомление о версии → гибрид: скрипт-детектор + редкий LLM-вызов для интерпретации.
- Не путать контуры: компрессор ТЗ/координатор = Hermes default (DeepSeek); роли DevWorkflow уже Codex (gpt-6.1-sol/gpt-6-astra/gpt-5.6-terra/gpt-6-luna). Вспомогательные vision/session_search уже Gemini — это ранее принятое решение, не «замена DeepSeek на Gemini».

## Механика реализации вердикта (DevWorkflow-слаг, питфоллы воркера)

- **`TZ:compress`/`HF:compress` — роль `compressor` (= Hermes default, deepseek-flash), выполняется самой Сиренью, не invoke-role**: `invoke-role --role compressor` — заглушка `hermes-internal not runnable from CLI stub`. Пишешь `dev/<slug>/extract.md` (3–5 КБ) по мастер-ТЗ, дописываешь `context-used:` в journal.md, закрываешь complete-phase с `path=...extract.md`.
- **Sirene-фазы (TZ:stabilize) тоже требуют маркер `context-used:` в journal.md перед complete-phase** — G2 спит не только на invoke-ролях; дописать вручную, иначе `G2: context-used marker required`.
- **`TZ:patch`: канонный артефакт — `dev/<slug>/TZ-patch.md`.** Архитектор часто пишет пакет только в мастер-ТЗ и не создаёт канон → invoke-role падает rc=4 `canonical_artifact_fail` («пиши в TZ-patch.md, канон не обновлён»), фаза остаётся `doing`. Лечение: выцепить новую секцию пакета `sed -n '<первая_строка>,$p' TZ/<Tool>/<Tool>_TZ.md > dev/<slug>/TZ-patch.md`, через `pipeline_state.write_state` проставить `phases['TZ:patch']['role']='architect'` (+model, снять fail_class), дописать `context-used:` в journal.md, повторить complete-phase. Артефакт уже на диске в мастер-ТЗ — это не пустой результат роли, а недописанный канон; роль перезапускать не нужно.
- **invoke-role — только фон** (`background=true, notify=true, persist_on_release=true`, без пайпа). Если wrapper убит таймаутом foreground (exit 124) — фаза `doing` с pid без артефакта; повторный invoke-role легален только по факту мёртвого pid (`ps -p <pid>` пуст), не interrupt/recover.
- Перевод крона на no_agent меняет `jobs.json` (поле `no_agent`, `script`) — а он в списке «не трогать» мастер-ТЗ инструментов; правка легальна только по явному согласованию Саши («делаем по канону», «делаем пункты N–M»).
