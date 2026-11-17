# Тесты и приёмка

Единственный контур S — существующий pytest/conftest.py. Каталоги каждого
прогона: `~/.cache/edit-plan-confluence-acceptance/<run-id>/stage-12/`
с state/index.sqlite, WorkVault, cache, fixtures, reports.
Production пути и symlink на них запрещены, в продуктовых вызовах глобальные
пути стоят перед подкомандой. Production A–D/AB не цели приёмки.

| Группа | Граница |
|---|---|
| unit | Сеть запрещена; parser и чистая логика, подменённые зависимости |
| archive_integration | Изолированный SQL/архив, ConfluenceClient запрещён |
| mpp_fixtures | Реальные бинарные MPP, настоящий reader/JVM |
| confluence_live | Только перечисленные выделенные тестовые страницы |

Группы сортируются unit → archive_integration → mpp_fixtures → confluence_live.
Маркер не заменяет обязательную карту test IDs. Пустая выборка или непройденный
обязательный тест не PASS. Переименование/перемещение обязательного теста требует
одновременного переименования его записи в обязательной карте (`ac-matrix.json` и
любых stage-специфичных картах): иначе весь запуск падает до исполнения
`ERROR: mandatory stage-13 tests not selected: <старое имя>` → RC=4 «no tests ran».
Искать имя теста по точному SYMBOL в картах и директивах обязательности, а не только
в самом файле теста — карта ссылается на имя, а не на код. Ступени 01–11 сохраняют собственные карты/hooks.
Этап 12 выбирает unit/archive_integration, включая уже существующие архивные
E/F и bootstrap тесты; живой профиль не проверяется этим запуском повторно.
M/R запускаются отдельными последовательными pytest-процессами, не совместным
сбором разных conftest. Docs-only изменение M/R всё равно фиксируется комплектом
before/after/patch/manifest и проверкой восстановления в двух временных деревьях.

```bash
S=/home/tkachenkoav/hermes-workspace/skills/productivity/edit-plan-confluence
PY=/usr/bin/python3.9
T=/home/tkachenkoav/.cache/edit-plan-confluence-acceptance/UNIQUE-RUN
export PYTHONPATH=/home/tkachenkoav/.local/lib/python3.9/site-packages
"$PY" -m pytest -c "$S/tests/pytest.ini" "$S/tests" \
  --acceptance-stage 12 --test-root "$T/stage-12" \
  -m "unit or archive_integration" \
  --junitxml="$T/stage-12/reports/junit.xml"
```

Stage-12 проверяет реальную загрузку двух имён из A через установленный
skills_tool.skill_view без изменения loader; пути и SHA возвращённого текста
должны совпадать с workspace. Короткая обёртка не содержит своего алгоритма.
Все исполнимые блоки cli-example в документации проходят реальный parser;
проверяются globals и полнота команд/опций. Проверки маршрутов сопоставляют
заявленные publish/save/Inbox/history/compare с наблюдаемым dispatch CLI,
а не только с формулировками SKILL.md. Успешный save stdout — один краткий JSON,
без полного export/traceback/credentials; canary secrets не попадают в receipt.

`_stage12_report` строит JSON/Markdown из pytest results и внешних evidence:
master/version/hash и §20 hash, план/inventory, tree/config hash, изменения по
файлам, загрузки, команды/rc, сохранность этапов 01–11, внешние docs/restore,
счётчики (неизмеренное — null), ограничения и gate passed/failed.
JUnit/stdout/stderr и очищенные evidence из T/reports копируются в
`references/implementation/20261116/stage-12/`. Завершающий коммит H
`edit-plan-confluence: stage 12` включает только файлы этапа и evidence;
его SHA записывается затем в журнал канонического плана. Чужой canon.md вне коммита.

Покрытие §20.7.3 и пользовательских AC-04/17/19/23/24/25 ограничено этапом 12:
интеграция, документация, parser/dispatch и выбранная регрессия. Статусы прежних
этапов не переписываются. Полная матрица AC-01…27, отдельные A–F/live A–D и
комплексный G относятся к этапу 13 и не объявляются пройденными здесь.
Изолированные проверки не заменяют пилот ZD/W5/Q1–Q7/AC-101…144 §19.
Gateway не меняется/не рестартует, cron/наблюдатели/расписания не создаются;
изолированный subprocess skill_view не означает прогон сообщения через Gateway.

## Корректирующий цикл 2 — полный этап 13

Новые обязательные test IDs добавлены к прежней AC-матрице: независимый от Confluence
первичный архив, точный round-trip actuals, view/edit-колонки, 21/47/76/100 и дробный
процент, source summary, отдельный actual finish, field/method/wrapper binding,
видимый текст и повторное открытие. Полная замена проверяет исчезновение старых задач
и связей, сохранение macro-id/id/hash и отсутствие новых версий при повторе.
Прежние conflict/resume/recovery и все реальные A–D остаются обязательными.

`test_source_values_live` проверяет отдельный контроль и браузерный наблюдатель,
используемый A–D. Контроль на синтетическом примере не заменяет успешные публикации,
даты, видимые значения и unchanged-повтор самих A–D. Отрицательные native controls
могут пройти как защитные тесты, сохраняя capability:not_verified и failed-приёмку.

Полный запуск на окончательном дереве, с новым изолированным T:

```bash
EDITPLAN_LIVE=1 PYTHONPATH=/home/tkachenkoav/.local/lib/python3.9/site-packages \
/usr/bin/python3.9 -m pytest -c "$S/tests/pytest.ini" "$S/tests" \
  --acceptance-stage 13 --test-root "$T/final" \
  -m 'unit or archive_integration or mpp_fixtures or confluence_live' \
  --junitxml="$T/final/reports/junit.xml" -q
```

Отчёт и blocker-ledger цикла — references/implementation/20261116/stage-13-fix2/;
история предыдущих failed-прогонов сохраняется. Условия §20/AC и числа A–D неизменны;
passed с ограничениями не используется. Production-БД, страницы A–D/AB и расписания
не являются целями записи.

Перед полной командой внешний этап подготовки сохраняет `reports/initial-state.json`
(реальные hashes защищённых файлов, canon, production DB, base commit) и
`reports/external-checks.json` (отдельные последовательные pytest R/M, JUnit/rc,
проверку прежних коммитов и восстановления after-копий USERTOOLS). Это входы
существующего pytest report hook; отсутствующие файлы оставляют соответствующие
gate checks непроверенными. Команды и точные manifests сохраняются в external-checks,
никаких старых флагов passed без проверки текущих hashes не переносится.

Живой этап 13 (confluence_live) длится ~29 мин: запускать в фоне с единым
junitxml и новым изолированным T, не переиспускать частично. Live-наблюдатель для
A–D сверяет даты задач с источником с допуском ≤60 сек — итеративно, т.к. плагин
реально пересчитывает интервалы. Разновременные падения одного и того же live-теста
на другом прогоне («1 проход ok, другой — failed/error») при том же коде — сигнал
транзиентного сбоя Confluence (404 «No content found» на parent, 403 «Could not
create content»/storage_verify), а не регрессии: перед диагнозом прогнать тот же
комплект ещё раз целиком. Нулевая веха (duration=0, start≠finish) рисуется плагином
точкой на одну дату, finish схлопывается к start: live-сверку дат вехи вести с допуском
схлопывания (materially different collapsed milestones), а не требовать точного
совпадения finish с источником — обе исходные даты уже в архиве.

Д3 / master 0.5.3 повторяет эту же полную команду и весь gate. Классификация факта:
`display-only` допускает публикацию с видимыми точными колонками; `schedule-affecting`
сохраняет блокировку. Обязательны маркировка «по плану; факт — в колонках», наблюдение
всех плановых дат A–D, фактов в обычном просмотре и после повторного открытия,
unchanged без роста версий и полная замена без смены макроса. Новые отрицательные
проверки блокируют потерю факта, скрытую колонку, нативную подстановку и изменение
плановых дат/длительности. Отчёты: references/implementation/20261116/stage-13-fix3/.
