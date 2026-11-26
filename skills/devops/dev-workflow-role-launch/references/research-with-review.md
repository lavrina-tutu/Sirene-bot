# RESEARCH по контенту + согласование ревизором (каноническая цепочка)

Саша часто просит «исследуй X» / «подготовь план по X и согласуй с ревизором» — это НЕ CHANGE/DEV (там компрессорные фазы и master), а **RESEARCH-кейс с добавленной фазой `REV:report`**: план/анализ выдаёт архитектор (RS:collect → RS:analyze), согласование — отдельный ревизор (REV:report), без ТЗ-поезда и без master. Проверено 24.11.2026 на анализе скилла tutu-dev → плане внедрения.

## Полная рабочая последовательность

1. `suggest-slug --title '<формулировка>' --kind train` → свободный слаг.
2. `init --case RESEARCH --slug <slug> --title … --origin-chat <chat> --origin-thread <thread> --slug-source suggest-cli` — рецепт по умолчанию `RS:collect → RS:analyze → GATE:done`.
3. **До первого emit добавить ревизию:**
   ```bash
   F=<dir>/evidence/owner-directive-<date>.md   # сначала записать директиву владельца
   SHA=$(sha256sum "$F" | cut -d' ' -f1)
   python3 -m pipeline.cli recipe-add --slug <slug> --phase REV:report \
     --reason '<что согласуем>' --evidence "path=$F sha256=$SHA"
   ```
   `--evidence` обязан содержать ОБА токена `path=` и `sha256=` (одна причина → rc=2 `recipe-add requires --reason and evidence path= sha256=`). Проверить `next` → должен вернуть `WORK RS:collect` (рецепт увидел новую фазу).
4. **В handoff-contract brief занести `REV:report` и в `write_scope`, и в `inputs` (вход = RS-analyze.md), и в `outputs` (выход = REV-report.md) ДО emit этой фазы** — иначе ревизор отработает, запишет канон и получит rc=4 `output outside write_scope: …/REV-report.md` (тот же класс, что первая фаза без контракта).
5. Три ролевые фазы последовательно, каждая через emit-prompt → ОДИН фоновый invoke-role (background+notify+persist; foreground на крупной работе таймаутится) → complete-phase с реальным хешем:
   - `RS:collect` (architect) — факты; выход `RS-collect.md`;
   - `RS:analyze` (architect) — план/анализ; выход `RS-analyze.md`; в brief требовать ГОТОВЫЕ к вставке промпты-образцы (текст, не описание), каждый помеченный как авторское предложение (не цитата из исследуемого источника);
   - `REV:report` (reviewer) — APPROVE / REQUEST-CHANGES; выход `REV-report.md`.
   После каждого complete → `next`. Финальный `GATE:done` закрывает оркестратор сам.
6. Результат Саше = согласованный план с пометкой «внедрение — отдельный шаг после твоего решения»; в рамках RESEARCH никакие runtime/скиллы/конфиг не менять (prohibition в контракте).

## Как Саша называет этот класс задач

- «архитектор, подготовь план того, что … взять в наши промпты … результат согласуй с ревизором»
- «исследуй скилл X с архитектором и дай отчёт» (без ревизора — просто RESEARCH без recipe-add)
- «что из этого применимо к …», «инструкцию развёртывания …»

Первая формулировка (план + согласование) = RESEARCH с REV:report; вторая (только отчёт) = RESEARCH без ревизора.

## Питфоллы, уже в основной SKILL.md

- recipe-add требует `--reason` + evidence с обоими токенами.
- Добавленную фазу вносить в write_scope/inputs/outputs ДО emit.
- RESEARCH по контенту завершён, но пришло новое требование — вернуть фазу на активную в том же слаге, не заводить новый поезд (когда GATE:done ещё не закрыт).
- Неправить состояние вручную (JSON-write запрещён); первый next после правки контракта может вернуть прежнюю фазу — вызвать next ещё раз.
