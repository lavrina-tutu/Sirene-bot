# Этап 13 — комплексная приёмка

Gate: **failed**. Полная приёмка §20 остаётся незавершённой.

Финальная команда S: **716 passed, 6 failed, 0 skipped; rc=1**. MofsIndex: **206 passed; rc=0**. MppReader: **58 passed, 1 необязательный legacy ZD skip §19; rc=0**.

[Полный читаемый итог](../final/reports/acceptance-report.md), [машинный итог](../final/reports/acceptance-report.json), [сырой отчёт pytest hook](reports/stage-report.json), [JUnit](reports/junit.xml).

## Поставка по файлам

- `S/tests/acceptance/ac-matrix.json`: 27 AC, 66 обязательных подслучаев, все 685 прежних test IDs и 37 новых; fixtures и требования evidence; reuse существующей матрицы сбоев.
- `S/tests/acceptance/test_user_journeys.py`: Реальные E/F через CLI, Inbox continue/stop/corrupt/duplicate/delete-after-freeze/resume, точный compare, локальные сутки с offset, общий аудит baseline.
- `S/tests/acceptance/test_cases_trisigma.py`: Холодный и повторный save A–F/D-risks, typed archive read-back, counts/work/ceil, подтверждённый именованный A, отдельная история B/C.
- `S/tests/acceptance/test_failure_matrix.py`: Fail-closed проверка итогов pytest, полнота AC/подслучаев, порядок фаз, scope source/runtime cache, пять сценариев выбора identity revision. Продуктовые crash/concurrency тесты переиспользуются.
- `S/tests/acceptance/test_migration_preservation.py`: Новая схема и изолированная старая схема 0006, typed setup, online backup/verify, повтор миграций, сохранность исходной БД, истории/артефактов/строк baseline.
- `S/tests/acceptance/test_live_publication.py`: Реальные A–D через public CLI на новых test pages, дельты версий, браузерный observer, бинарные diff/publish → identity → resume, финальная загрузка обоих имён и parser smoke совместимых команд.
- `S/tests/conftest.py`: STAGE13_REQUIRED; изолированный pytest cache; phase/group ordering; manifests и SHA-256 перед каждым тестом; subprocess guards/counters; live inventory; acceptance-report и отдельные cases; отчёты 01–12 сохранены.
- `S/tests/pytest.ini`: Маркеры acceptance/loopback_http и strict markers; штатный pytest без нового runner/CLI.

## AC и пользовательские сценарии

Passed: AC-01, AC-05–AC-08, AC-10–AC-27. Failed: AC-02, AC-03, AC-04, AC-09. Обязательные подслучаи: 58 passed / 8 failed; blocked/not_run=0 в матрице. Точные ID/команды/fixtures/evidence каждого подслучая — в полном JSON.

Сценарии 2–10 passed; сценарии 1 (publish) и 11 (новый MPP → identity → resume → публикация) failed.

## Реальные кейсы

| Кейс | Архив / отображение / связи | Work, ч-ч | Итог |
|---|---|---|---|
| [A](../final/reports/cases/A.json) | 58/57/53 | 1576 | failed |
| [B](../final/reports/cases/B.json) | 62/61/60 | 2096 | failed |
| [C](../final/reports/cases/C.json) | 62/61/61 | 2088 | failed |
| [D](../final/reports/cases/D.json) | 72/71/76 | 3136 | failed |
| [E](../final/reports/cases/E.json) | 78/77/84 | 3048 | passed |
| [F](../final/reports/cases/F.json) | 86/85/93 | 3608 | passed |
| [G](../final/reports/cases/G.json) | Inbox/batch | — | passed |
| [D-risks](../final/reports/cases/D-risks.json) | 74/73/81 | 2992 | passed |

A: identity_status=confirmed, именованный 150526 и hash проверены. Архивные численные критерии A–D совпали; D: 106.875→107. E/F/D-risks work в таблице — наблюдение, не дополнительный нормативный критерий.

## Живые результаты и ограничения

Контроли установленного плагина прошли: Confluence 8.9.4, frontend H6u7SQymvwxeyojc1ur6Z, Bryntum 5.4.1. Elapsed-lag остался not_verified по профилю. Input/received/browser bytes, storage GET, наблюдения дат и screenshots сохранены в final/live/.

A/D: collection_partial. B/C: rule_reference_or_evidence_missing (historical-unresolved-v1, inactive). Извлечение/представление также содержит неподдержанные поля и actuals; подробная группировка — [readiness-gaps.json](../final/reports/readiness-gaps.json). Обход допуска не использовался.
- A: test page 537573662; page 1→1; MPXJ-read=1; publication POST/PUT=0/0.
- B: test page 537573663; page 1→1; MPXJ-read=1; publication POST/PUT=0/0.
- C: test page 537573664; page 1→1; MPXJ-read=1; publication POST/PUT=0/0.
- D: test page 537573665; page 1→1; MPXJ-read=1; publication POST/PUT=0/0.

Публикация, её повтор и даты A–D в плагине не подтверждены: операция остановилась до загрузки. Новый бинарный diff/publish: identity confirm успешен, resume использует тот же snapshot без нового reader, но collection_partial блокирует публикацию.

Legacy verification прошла только GET; версии вложений не менялись. Списки всех live-целей и сырые запросы находятся в final/reports/live-targets.json и http-observations.json.

## Сохранность и воспроизводимость

1611 файлов исходников/конфигов/fixtures/прежних evidence неизменны, baseline сохранён. Шесть служебных runtime cache путей исключены из protection scope явно; pytest cache финального запуска внутри T. Все 12 прежних коммитов проверены, 64 внешних after-файла восстановлены и сверены; 29 последних USERTOOLS файлов совпали с рабочими. 15 прежних report/source hooks побайтно эквивалентны по AST; старый stage-12 selection — те же 660 тестов.

Этапы 01–12, production DB/архивы/страницы A–D/AB, Gateway и расписания не изменялись. Master фактически 0.5.1 с отдельным §21, исполнялся §20. W5/ZD/AC-101…144 §19 остаются отдельными. OwnCloud sync не подтверждён.

Предварительные ошибки подготовки, остановленный прогон и первый полный failed-прогон сохранены в history/. Коммит сохраняет тесты и доказательства неуспешной приёмки; SHA записывается после commit в журнал канонического плана. canon.md исключён.

Крупные дополнительные prepared/reader receipt dumps сохранены как `.json.gz` без изменения содержимого; `gzip -dc FILE` восстанавливает оригинал. Source SHA-256 и физические пути — final/copy-map.json. Обязательные отчёты и cases остаются обычным JSON/Markdown.
