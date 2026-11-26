# Консультативный invoke владельца и восстановление фазы

Когда владелец/оркестратор задаёт роли вопрос НЕ по рабочей фазе поезда (например «можно ли всегда так делать при возврате?»), вызывает обычную роль, но БЕЗ движения живого state.

## Консультативный invoke (вопрос владельца)

- Вызывать `invoke-role --role <architect|reviewer> --prompt-file <q.md> --workspace <ABS>` БЕЗ `--slug`/`--phase`: живой state, план, REV и рабочие фазы не трогаются; собственная фаза не открывается.
- Ответ роли НЕ приходит в stdout фонового процесса (bg-output пуст). Он лежит в новейшем `~/.codex/sessions/<date>/rollout-*.jsonl`: последний assistant-блок с `content[].type == "output_text"` (Для codex — payload/type=message/role=assistant/content). Извлечь python-разбором JSONL, записать во временный .md и прочитать; в свитке бывают и более старые пустые/тестовые rollout-файлы — брать по времени новейший.
- Запускать консультативный invoke ровно ОДИН раз и ждать завершения. Повторный запуск той же роли по тому же вопросу порождает параллельные codex-процессы и dead-дубликаты; лишние убивать по PID-цепочке (python `invoke-role` → node codex → codex exec), не класть оба в as-бытие.
- Консультативный ответ старшей роли может вернуться с отказом оболочки (например «пиши в HF-plan.md, канон не обновлён», exit 4) даже когда вердикт уже полностью записан в evidence/rollout: refuse-строку в stdout не читать как пустой результат — содержимое разбора искать в rollout/evidence.

## Сброс «мёртвого» PID и возврат фазы (штатный write_state)

Исполняемая роль завершается, но оставляет в `_state.json` непустой `pid` (wrapper мёртв) и фазу `doing`. Продолжение поезда требует штатного сброса без обхода лимитов:

- Правильный API — `from pipeline import pipeline_state`; читается `st = pipeline_state.read_state(slug)`, мутируется`st.phases[...]` и `st.phase`, сохраняется `pipeline_state.write_state(st, event={...})`. НЕТ функции `write_event` (частый ошибочный импорт); `write_state` принимает `event=`-словарь, а не отдельный объект.
- Событие `event='repair'`, `actor='sirene'`, `phase=<целевая>`; `reason` и `evidence` (словарь) обязательны. Для non-root события требуется `phase`; верхнеуровневый `st.status` не `idle` перед сохранением.
- Сброс PID и возврат фазы: очистить `st.pid`; целевую роль (HF:impl/HF:test) перевести `status='todo'`+`awaiting_invoke=True`; установить `st.phase`. Счётчики (`turn_count`, recover_counts, лимиты) НЕ трогать — смена модели/чистка по распоряжению, не повторный трей.
- После repair всегда перечитать `read_state` и сверить phase/status/awaiting_invoke перед следующим emit+invoke.

## Честный PARTIAL / FAIL — НЕ сигнал стоп-доклада

`PARTIAL_IMPLEMENTATION_PENDING_MATRIX` (регресс зелёный, матрица сценариев недовведена), `FAIL_MATRIX_INCOMPLETE` (HF:test собрал меньше узлов матрицы, чем требуется) — это штатные состояния незавершённости реализации, а НЕ эскалация исполнителя к архитектору. Правило «останови и доложи при следующей эскалации» срабатывает ТОЛЬКО на явном возврате исполнителя к архитектору (scope/запрет/новый product-path); честный красный тест или недовведённая матрица = точечное исправление на том же владельце-исполнителе.

При PARTIAL/FAIL продолжать на ТОТ ЖЕ кандидат и ТУ ЖЕ цель без сброса лимитов и без сокращения матрицы; возврат на владельца-архитектора только если исполнитель сам запросил (эскалация) или вердикт явно требует архитектурного решения.

## `complete-phase` обязательные reason и evidence

`complete-phase` молча возвращает `rc=2` (без stderr) при пропуске ЛЮБОГО из `--reason` / `--evidence` — пропущенный аргумент легко спутать с G2-блоком. Проверять оба флага и реальный `sha256sum <канон>` (вычисленный в той же команде) перед вызовом.

`--evidence` не принимает голый `verdict=... candidate=...`: требуется `path=<abs>` (или `sha256=`/`session_id=`) внутри. Без ключа `path=` команда молча отказывается с «evidence must include path= or sha256= or session_id=». Всегда указывать `path=<абсолютный путь к evidence-файлу>` + остальные ключи.

## rc=0 + пустой stdout — норма, не сбой

CLI `invoke-role` при успехе не обязан печатать JSON; пустой stdout не доказывает падение роли. SoT результата — exact `(slug, phase)` в state/journal и канон, проверенные после смерти именно того wrapper, а не механизм транспорта (notify/stdout). Перед dead-pid repair сверять state/journal/receipt по exact `(slug, phase)`; пустой stdout сам по себе никогда не `empty-result`. Внешний completion-путь, трактующий `rc=0`+пустой stdout как сбой без сверки state — корень ложных dead-pid ремонтов.

G2 `complete-phase` сверяет связку `context_prepare` → `context_result` → receipt и `output_snapshot(packet) == result.outputs`. Возможные состояния после смерти wrapper и восстановление:

| State после смерти wrapper | Действие |
|---|---|
| `role` записан, `context_result`+receipt совпадают с prepare, канон обновлён | Обычный `complete-phase` с evidence — без нового invoke и без ручной правки state |
| `context_result`/receipt стёрнут ранним reset | Восстановить `context_result` в точном формате `invoke_role` (packet_id + prepare_identity + outputs через `output_snapshot` + receipt) штатным writer-ом, затем обычный complete — НЕ второй/третий invoke |
| `rc=143` transport-termination при готовом каноне | Существующий `reconcile_invoke_result`, затем обычный complete |
| Канона/proof нет, исход неясен | Ожидание/диагноз; файл сам по себе не PASS и не основание слепого retry |

Повторный invoke при уже готовом каноне бесполезен: роль отказывается переписывать существующий артефакт → `canonical_artifact_fail` («пиши в <канон>, канон не обновлён» / `required output unchanged`). Это признак, что фазу надо закрыть complete-ом, а не гнать повторным invoke.

## G2 отказ по промпту после emit

`invoke-role` сверяет переданный prompt-файл с immutable packet pair (prompt_sha); правка файла после `emit-prompt` даёт `G2: emitted packet/prompt pair is missing, changed, or stale`. Доп. контекст роли передаётся через файлы workspace (роль читает их по плану/путям), а не правкой emit-выхода.

## Ревью блокера на executor-фазе — не прямой invoke архитектора

Архитектора нельзя вызывать на executor-фазе (HF:impl/HF:test) — G6. Для вердикта архитектора по блокеру (напр. `ARCHITECT_REVIEW_REQUIRED` от исполнителя) вернуть фазу владельцу-архитектору (HF:plan) штатным repair-writer-ом (event=repair, actor=sirene), затем emit+invoke architect. Тот же подход — при вердикте ревизора `REQUEST-CHANGES`: REV-факт зафиксирован, работа возвращается архитектору на доработку плана; ревизорские замечания читаются из канонного `REV-plan.md` в workspace.
