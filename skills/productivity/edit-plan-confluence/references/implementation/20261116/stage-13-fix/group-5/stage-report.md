# Корректирующий цикл §20 — группа 5 и повтор этапа 13

**§20: финальная приёмка failed; исправления обязательны.** Успешные целевые проверки подтверждают перечисленные исправленные контракты; обязательная live-публикация A–D не состоялась. Статус passed с ограничениями не присваивается.

Финальный полный прогон: {'passed': 754, 'failed': 4, 'skipped': 0}; pytest rc=1; выбрано 758 обязательных тестов. Машинный gate: failed. AC: {'passed': 23, 'failed': 4}; кейсы: {'failed': 4, 'passed': 4}; сценарии: {'failed': 1, 'passed': 10}. Точные подслучаи и причины — final/reports/acceptance-report.json.gz, JUnit — final/reports/junit.xml.

Работа выполнена поверх 92bea3f; первоначальные этапы 1–13, исходный failed-отчёт и их коммиты сохранены. ТЗ остаётся master v0.5.1. Критерии и числа §§15.3/15.5/15.7 не изменены.

| Группа | Выполнено и проверено | Коммиты |
|---|---|---|
| 0 | Дословные уточнения ТЗ/плана; hashes до/после; нормативные разделы и appendix provenance сохранены | 71352a6 |
| 1 | Реальный MPXJ16.4 API Timephased/List/TimeUnit, raw planned/actual/remaining; ProjectProperties lag calendar; same-read raw relation audit. Воспроизводимый overlay и полный USERTOOLS before/after/patch/manifest. R: 81 passed + 1 optional legacy §19 skipped, rc=0 | 490fa01 |
| 2 | Календарные alias/tree/bindings, FixedUnits, constraints, segments, inactive, summary dependencies; узкие эквивалентности availability/assignment interval. Защита отсутствующего UID, версия конвертера v3. 43 representation-теста + 20 cache/boundary; live14: 10 supported-контролей и 4 negative/not_verified-контроля; rc=0. Actuals и независимые offsets остаются blocking | be60c4a, c18614e, 3d19d6b |
| 3 | Одна классификация исходной причины, точные mirrors только как provenance; partial архивируется, неизвестное/влияющее/неперечисленное блокируется. Явный enumeration_complete:false всегда блокирует, policy v3. 75 passed, rc=0. B/C snapshots и keys восстановлены, правила не активированы без точной revision/текущей причины | 77c098f, 6d6fe94 |
| 4 | Отдельная воспроизводимая бинарная пара с корнем UID1000 и адресным test-only правилом; исходный relations-all-types отрицательный. 2 реальных бинарных recipe/admission теста, 4 live-цепочки, 4 batch CLI режима на versioned source: rc=0. JSON вместо бинарного экспорта не подставлялся | e2ad989, bcc2029 |
| 5 | Целевой набор209 passed; R/M отдельными процессами, M206 passed; live4 binary +14 capabilities passed. Полный новый этап13 — failed; ниже точные остаточные причины | SHA завершающего коммита возвращается в ответе; собственный SHA не включён в содержимое коммита |

Целевые результаты209/14/4 относятся к сохранённым отдельным запускам до двух последних граничных уточнений. После них проведены адресные 20/75 и новый полный этап13 на окончательном дереве. Прежние успешные результаты не подменяют этот полный прогон.

Все использованные команды, cwd, параметры, rc, JUnit и окружение без значений секретов — targeted/*/reports/stage-report.json, final/reports/external-checks.json и final/reports/acceptance-report.json.gz. Полная команда приёмки:

```sh
EDITPLAN_LIVE=1 PYTHONPATH=/home/tkachenkoav/.local/lib/python3.9/site-packages /usr/bin/python3.9 -m pytest -c S/tests/pytest.ini S/tests --acceptance-stage 13 --test-root T/repeat-stage13-v4/final -m 'unit or archive_integration or mpp_fixtures or confluence_live' --junitxml=T/repeat-stage13-v4/final/reports/junit.xml -q
```

S=/home/tkachenkoav/hermes-workspace/skills/productivity/edit-plan-confluence; T=/home/tkachenkoav/.cache/edit-plan-confluence-acceptance/accept-fix-20261117-121211. Публичные команды внутри сценариев исполнялись /usr/bin/python3 scripts/cli.py, включая первичное архивирование и resume.

| A–D | Архив / показ / связи | Work ч-ч | Блокирующие диагностики | Сетевая запись и даты |
|---|---|---|---|---|
| A | 58 / 57 / 53 | 1576 (complete) | 27 | failed/5, POST=0, PUT=0; страница без изменения; наблюдение дат и успешный повтор отсутствуют |
| B | 62 / 61 / 60 | 2096 (complete) | 28 | failed/5, POST=0, PUT=0; страница без изменения; наблюдение дат и успешный повтор отсутствуют |
| C | 62 / 61 / 61 | 2088 (complete) | 103 | failed/5, POST=0, PUT=0; страница без изменения; наблюдение дат и успешный повтор отсутствуют |
| D | 72 / 71 / 76 | 3136 (complete) | 217 | failed/5, POST=0, PUT=0; страница без изменения; наблюдение дат и успешный повтор отсутствуют |

Это числа диагностик по кейсу, а не число независимых первопричин. Повторные quality_issues не считаются новой причиной. Исходные коллекции A–D полностью перечислены; совпадение количеств и Work не засчитывает обязательную публикацию.

Незакрытые причины: task actual_start/actual_finish/actual_duration/actual_work и stop/resume не имеют доказанно эквивалентного представления. Нативный кандидат actual-полей проверен на установленной обёртке и не сохранился в TaskModel; stop/resume остаются not_verified, без утверждения об универсальной невозможности реализации. Подмена actuals процентом теряет исходную точность; принудительное закрепление дат не вводилось. Для D дополнительно блокируются назначения без ресурса UID441/699/700/701 и независимые start/finish UID441. Это не объявляется повреждением источника: допустимое представление такой семантики ещё не доказано.

Для B/C восстановлены исходные typed snapshots и source hashes, UID510→UID323, точная исходная связь и старое общее указание из git-истории (historical-wrapper-recovery.json). Это не является точной активной revision с проверенной текущей причиной. Legacy snapshot не содержит полного source_id/parent context; принятие старого longest-path-критерия или безусловное удаление связи запрещено. Правила historical-unresolved-v1 остаются inactive; identity confirm не снимает иных блокеров.

Каждый оставшийся blocker перечислен отдельно в blocker-ledger.json: source_field, normalized_source, representation, layer, fix_proof:null, test_id и ссылка на evidence. Исходные snapshots, actual admission evidence и подготовленные bytes — final/blocker-audit/*.json.gz. Закрытые контракты и их test IDs также записаны в ledger.

Положительные бинарные diff/publish-цепочки: needs_decision/3 → identity confirm/0 → resume published_with_warnings/0, published:true → unchanged/0; первичное чтение1, resume0, повтор0; POST/PUT при resume по1, при повторе0. Предварительного ручного save нет, snapshot сохраняется после удаления входного MPP. Положительный fixture проверяет контракт подготовки/identity/публикации; он не заменяет наблюдение расписания A–D. Отрицательные diff/publish: failed/5 → confirm/0 → failed/5, POST/PUT0; original relations-all-types сохранён. Подробные статусы — final/reports/evidence/new-source-*.json и semantic-negative-*.json.

Установленная среда: Confluence8.9.4, frontend build H6u7SQymvwxeyojc1ur6Z, asset SHA256 4e57cf0dcdcc4f9c855d59d8f600e3682a12dadd91725426fedb096581433cfe, engine5.4.1. Разрешение capability основано на адресном поведении установленной обёртки, bytes/storage/read-back и browser observation, а не на общей документации Bryntum. Profile evidence группы2 неизменны; повторные observations и screenshots — final/capability-controls/.

Сохранность: 2122 защищённых файлов, изменённых 0; source tree 6ebede7f67be8a4db781a08390c135540d1fc2514f6ce2a5d9f58ec33e26912d; sources_stable=True. pipeline.py/cli.py неизменны относительно92bea3f. canon.md не изменён и не включён в коммиты; SHA256 a6e841a660f60f2aee932edbd558992c68fc560de4464a580ffbb1a8e0b17892. Production DB read-only SHA256 b74b632bbc1b5d02e86396786c6b07220ffc5b0a3cf6d026ebc6467e3bce6c27. Baseline, source и production сохранены; точные сравнения — preservation-checks.json и gate_checks машинного отчёта.

Live выполнялся только на выделенных тестовых дочерних страницах родителя519501810. A496600693/B499550441/C499566117/D506248940/AB519492935 исключены. Gateway, кроны, наблюдатели и расписания не менялись. R/M проверены отдельными процессами; внешние исходники восстановимы (38 текущих файлов,64 исторических), before/after/patch/manifest R — группа1. MofsIndex не изменён.

История попыток сохранена: первый полный запуск746 passed/8 failed/1 skipped, rc=1 (четыре evicted-origin cache fixture failure исправлены, live opt-in восстановлен; A–D оставались failed); второй441 passed, rc=2 после SIGINT до изменения converter version; третий438 passed, rc=2 после SIGINT до исправления enumeration flag. Они не считаются полной приёмкой окончательного дерева. history-manifest.json задаёт SHA исходных bytes, сохранённого артефакта и codec; gzip обратим. Полные runtime DB/cache остаются в изолированном T; в git не включаются.

Критерии закрытия §20 не выполнены: A–D не опубликованы, обязательного наблюдения дат/повтора для них нет; все AC и полный pytest gate не прошли. Это результат выполненной итерации и перечень оставшихся обязательных исправлений, не заявление о завершённой реализации.
