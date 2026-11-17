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
обязательный тест не PASS. Ступени 01–11 сохраняют собственные карты/hooks.
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
