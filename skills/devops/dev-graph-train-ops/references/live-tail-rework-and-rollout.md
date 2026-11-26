# Живой хвост dev-графа: HF:test rework и ORCH rollout

Обязанности оркестратора на живой фазе DEV-задачи (после REV:plan APPROVE до GATE:done).

## HF:test FAIL → rework HF:impl

Одинаковая петля для REV и HF-хвоста:
1. Прочитать честный вердикт/blocking из `AC-report.md` и `evidence/HF-test.json` (исполнитель может вернуть FAIL — это рабочая итерация, не сбой).
2. Перемотать `write_state st event="repair"`: обе активные фазы (`HF:impl` и `HF:test`) → `todo`, снять pid/fail_class/role/session_id/awaiting_invoke/started_at.
3. `next` → снова активная фаза; затем ОДИН свежий `emit-prompt`.
4. Рework-диагнозы НЕ дописывать в emit-выход и не переписывать его: правка `/tmp/task.md` после emit ломает G2 (`pair is missing, changed, or stale`), а `--prompt-file` обязан быть ровно выход emit. Диагноз класть ОТДЕЛЬНЫМ файлом в workspace (напр. `S/evidence/HF-impl-rework-notes.md`: какие IAC-XX упали, оба регресса, требуемый git-proof) — роль читает весь workspace и увидит его. Без такой заметки исполнитель не знает, что чинить, и может молча переслать тот же неполный корпус.

## Имя события в write_state — только закрытое

Имя обязано быть из `CLOSED_EVENTS` (`repair`, `rev_request_changes_rewind`, `start`, `complete`, …).
Неизвестное имя НЕ вызывает исключения: молча откатывает ВСЮ запись, state остаётся прежним, в журнал пишется `Incomplete log event: unknown event ...`.
Признак — state не изменился при том, что скрипт «прошёл». Это rollback, а не no-op: после каждой перемотки проверять реально применённые фазовые поля.

## Два независимых критерия FAIL: сценарный корпус плана + чистый git-proof

Исполнитель часто сдаёт «ядра кода + свой фокусный тест-файл зелёным» (например 101 в `test_context_packet.py`), а FAIL лежит в двух невидимых по его self-report местах:

- Сценарный корпус плана §5 (169 записей матрицы, IAC-02..16) НЕ реализован — только несколько фокусов, `test_case_trace[T01..18]` отсутствует, publication/multipart/rollback/handoff-узлы — source-assertions, а не реальные CLI-трассы. Зелёный фокусный тест НЕ доказывает полноту матрицы: коллекция должна покрывать каждую запись матрицы, а не счётчик одинаковых сценариев. Перед приёмкой перегнать полный корпус из candidate и сверить IAC-вердикты построчно.
- git-proof нечист: `git status --porcelain` в candidate даёт много untracked (напр. 8 tracked / 91 untracked) при том, что `git diff HEAD` пуст. IAC-14 требует чистый porcelain только своих changed paths; untracked-мусор в candidate = FAIL, независимо от прошедших тестов.
- Приёмка — по `verdict=` в `AC-report.md` (PASS/FAIL), а не по rc=0 отдельных pytest и не по self-report «pass».

## Не доверять self-report исполнителя о тестах

Исполнитель пишет в evidence «340 passed», но полный корпус без обязательной env может давать «4 failed / 336 passed».
Перед `complete-phase` самому перегнать полный корпус из final P (или candidate) с правильным окружением и принять по фактическому rc.
Проверять вердикт по hash/фактическому прогону, не копируя цифры из self-report.

## Полный тест-корпус pipeline/tests требует B55_EVIDENCE_ROOT

Независимый ридер evidence (`test_b55_pilot_evidence.py`) поднимает `AssertionError: B55_EVIDENCE_ROOT is required`, если переменная не выставлена.
Экспортировать перед полным прогоном:
```bash
export B55_EVIDENCE_ROOT=$HOME/WorkVault/Hermes-Backlog/dev/<ведущий-слаг>/evidence/pilot/b55-run-<ts>
PYTHONPATH=. python -B -m pytest -q -p no:cacheprovider pipeline/tests
```
Фокусный новый `test_context_packet.py` этой переменной не требует.

## Candidate overlay обязан нести полный dependency surface

Корпус `pipeline/tests` импортирует всё дерево `pipeline/` (`paths.py`, `pipeline_gitproof.py`, …).
Candidate, содержащий только изменяемые targets, даёт 15 ImportError (IAC-13 rc=2) при том, что новый фокусный тест — зелёный.
Монтировать в `candidate/Registries` полное дерево в изоляции (`PYTHONPATH=.`), не тестируя production bytes в месте.

## Rollout (ORCH:shared-state) строго по write-set

1. Проверить backup/manifest, final→candidate mapping и ОТСУТСТВИЕ живых wrapper (скан всех `dev/*/_state.json` на pid; `ps -p`).
2. Cutover evidence `evidence/rollout.json` с `before_prod` hash у каждого файла.
3. Перенести ТОЛЬКО allowlist, у кого bytes отличаются тестовым манифестом (идентичные уже существующие — НЕ трогать). Сверять `bytes_match` после записи.
4. Штатный `~/.hermes/scripts/restore-all-skills.sh` (не менять сам скрипт), затем git-коммит скилла в hermes-workspace.
5. Импорт final модулей из production: проверить `__file__` = реальный Registries/pipeline плюс sha против expected (7 модулей).
6. `skill_view` загрузить SKILL/context/invoke — полученный content sha ОБЯЗАН совпадать с кандидатным (иначе загрузка в контекст не доказана). Проверять реальный realpath (skill_dir в HERMES_HOME может быть symlink на hermes-workspace), не верить «файл на диске есть» без совпадения hash.
7. Installed-smoke: полный корпус ИЗ FINAL P (не candidate) rc=0.
`GATE:done` — только после rollout evidence; `production_runtime` честно `NOT_RUN`, если платные вызовы не делались.
