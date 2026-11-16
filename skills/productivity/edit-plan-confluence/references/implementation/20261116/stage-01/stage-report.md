# Этап 01 — Закрыть ложное подтверждение публикации

Gate: **passed**. Реализован только этап 1; этапы 2–13 не выполнялись.

## Реализация по файлам

| Компонент / файл | Изменение |
|---|---|
| S/scripts/pipeline.py | False и SHA mismatch останавливают до PUT; фактические ID/version, новый GET после PUT, проверка current attachment; регистрация после проверок; дочерняя ветка и повторная проверка квитанций. |
| S/scripts/gantt_attachment.py | Upload возвращает фактический AttachmentInfo; нет fallback на чужое имя/выдуманную версию; конкретная и актуальная версии проверяются отдельно. |
| S/scripts/plan_verify.py (новый) | Общие результаты проверки SHA-256 и storage; адресное reuse version/macro-count из tutu-confluence-jira/verify_skeleton.py. Секционный patch не подходит произвольной Gantt-странице. |
| S/scripts/macro.py | Перечисление всех целей, вложенные макросы, порядок атрибутов; дубли/неполные параметры блокируют find_macro. |
| S/scripts/itogo.py | Одна актуальная строка перед макросом, правильные значения, отсутствие «Трудозатрат». |
| S/scripts/conf_client.py | Некэшированный GET storage, пагинация attachments, конкретный ID/version/container перед скачиванием; имя URL-кодируется. |
| S/scripts/plan_receipt.py | Atomic replace; failure receipts с published:null и partial/unknown external effect. |
| S/scripts/child_page.py | Фиксация фактической версии созданной страницы и частичного эффекта; ответ POST не равен подтверждению всей операции. |
| S/scripts/plan_reconcile.py | Совпадение одного вложения подтверждает только attachment scope; операция остаётся unknown. |
| M/mofs_index/plan/schema.py | Новая 0006_publication_trust; доверие, historical status и отдельные verification observations; 0001–0005 неизменны. |
| M/mofs_index/plan/migrate.py | Проверка checksum уже применённых миграций; повтор идемпотентен. |
| M/mofs_index/plan/writer.py | PublicationSpec/PageObservationSpec, проверка evidence и связей проекта/страницы; запрещено повышение старого пути до verified_v1. |
| M/mofs_index/plan/query.py, render.py | Trust и historical_status в ответах; регистрация не представлена доказанным новым подтверждением. |
| S/tests/conftest.py, pytest.ini | Изоляция БД/WorkVault/cache/копий fixtures; symlink guard, запрет сети и ConfluenceClient для архивных групп; маркеры, pytest options, обязательная карта test ID, отчёт hooks. |
| S/tests/{test_pipeline,test_child_page,test_gantt_attachment,test_plan_reconcile,test_plan_verify}.py | Негативные проверки обеих веток, фактический read-back, версии, ложные квитанции и reconciliation. |
| M/tests/plan/{test_migrate,test_writer,test_query,conftest}.py | Миграция старой схемы, сохранность baseline/истории, typed API trust, query/render и изоляция. |

## Миграции

Новая: `0006_publication_trust`. Старые публикации получают `legacy_unverified`. В старой таблице публикаций не было поля status: `historical_status=registered` фиксирует регистрацию, не выдумывает confirmed. Исходный status попыток сохранён и скопирован в historical_status. События, связи, snapshots и обе таблицы baseline сохранены; integrity_check/foreign_key_check и повтор миграции проверены. Production-БД не открывалась.

## Реальные команды и результаты

**s-acceptance**: rc=0; tests=132, failures=0, errors=0, skipped=0.

```bash
cd /home/tkachenkoav/hermes-workspace/skills/productivity/edit-plan-confluence
PYTHONPATH=/home/tkachenkoav/.local/lib/python3.9/site-packages /usr/bin/python3.9 -m pytest -c /home/tkachenkoav/hermes-workspace/skills/productivity/edit-plan-confluence/tests/pytest.ini /home/tkachenkoav/hermes-workspace/skills/productivity/edit-plan-confluence/tests --acceptance-stage 01 --test-root /home/tkachenkoav/.cache/edit-plan-confluence-acceptance/20261116T101802Z/stage-01 -m 'unit or archive_integration' --junitxml=/home/tkachenkoav/.cache/edit-plan-confluence-acceptance/20261116T101802Z/stage-01/reports/junit.xml
```

**mofs-required**: rc=0; tests=36, failures=0, errors=0, skipped=0.

```bash
cd /home/tkachenkoav/USERTOOLS/MofsIndex
PYTHONPATH=/home/tkachenkoav/.local/lib/python3.9/site-packages /usr/bin/python3.9 -m pytest tests/plan/test_migrate.py tests/plan/test_writer.py tests/plan/test_query.py --basetemp=/home/tkachenkoav/.cache/edit-plan-confluence-acceptance/20261116T101802Z/stage-01/mofs-required --junitxml=/home/tkachenkoav/.cache/edit-plan-confluence-acceptance/20261116T101802Z/stage-01/reports/mofs-required-junit.xml
```

**mofs-plan-regression**: rc=0; tests=65, failures=0, errors=0, skipped=0.

```bash
cd /home/tkachenkoav/USERTOOLS/MofsIndex
PYTHONPATH=/home/tkachenkoav/.local/lib/python3.9/site-packages /usr/bin/python3.9 -m pytest tests/plan --basetemp=/home/tkachenkoav/.cache/edit-plan-confluence-acceptance/20261116T101802Z/stage-01/mofs-regression --junitxml=/home/tkachenkoav/.cache/edit-plan-confluence-acceptance/20261116T101802Z/stage-01/reports/mofs-plan-junit.xml
```

**mpp-reader-smoke**: rc=0; tests=3, failures=0, errors=0, skipped=0.

```bash
cd /home/tkachenkoav/hermes-workspace/skills/productivity/edit-plan-confluence
PYTHONPATH=/home/tkachenkoav/.local/lib/python3.9/site-packages /usr/bin/python3.9 -m pytest -c /home/tkachenkoav/hermes-workspace/skills/productivity/edit-plan-confluence/tests/pytest.ini /home/tkachenkoav/hermes-workspace/skills/productivity/edit-plan-confluence/tests --test-root /home/tkachenkoav/.cache/edit-plan-confluence-acceptance/20261116T101802Z/stage-01/mpp-reader-smoke -m mpp_fixtures --junitxml=/home/tkachenkoav/.cache/edit-plan-confluence-acceptance/20261116T101802Z/stage-01/reports/mpp-reader-junit.xml
```

Обязательный набор M (36) входит в общую регрессию M (65); числа не суммируются как уникальные. Из основного S исключены 3 MPP/JVM и 2 live-теста; MPP/JVM выполнены отдельно, live не запускались. CLI-интерпретатор — `/usr/bin/python3`; тесты и фактический reader — `/usr/bin/python3.9` с указанным PYTHONPATH. Полные stdout/stderr и JUnit лежат рядом.

## Документальная интеграция

Master получил 0.5.0, полный §20.1–§20.9 и обе истории ревизий в §20.10. Appendix побайтно совпадает с исходником и копией в снапшоте. Проверен полный текст после согласованного переноса заголовков/ссылок, все исходные 64-значные hashes и единственная строка inventory. Новый APPROVE не заявлен; §19/W5/пилот ZD не закрыты этой приёмкой.

- `/home/tkachenkoav/WorkVault/Hermes-Backlog/TZ/EditPlanConfluence/EditPlanConfluence_TZ.md` — SHA-256 `ad246fac0a363d2b9d6e9b5c177b76b06dcbe1b8b07d4ea6c9f8c769018dc369`.
- `/home/tkachenkoav/WorkVault/Hermes-Backlog/TZ/EditPlanConfluence/appendix_unified-pipeline-source_20261116.md` — SHA-256 `542391a2544c2a95143832f3a1e66fee59d7f9660e656a99deb3f69eedb7c697`.
- `/home/tkachenkoav/WorkVault/Hermes-Backlog/TZ/EditPlanConfluence/plans/HF-plan_EditPlanConfluence_20261116.md` — SHA-256 `1772fe0e05dc1efdaac3897feeedbc9e70aebd0d5b0d73d0a1fbac48cdbcea64`.
- `/home/tkachenkoav/WorkVault/Hermes-Backlog/TZ/MAIN_TZ_INVENTORY.md` — SHA-256 `2f8ce1dfc1da0163588d7248445b22ee01e5170e498189ef89f36228062d31a4`.
- `/home/tkachenkoav/WorkVault/Hermes-Backlog/TZ/edit-plan-confluence-eadinyi-konveer-16.11.26.md` — SHA-256 `64a13411eacf6d06f16ea5733abf5778cfe08f01b5355671f1c00335e1239423`.
- `/home/tkachenkoav/WorkVault_backup/Hermes-Backlog/TZ/EditPlanConfluence/EditPlanConfluence_TZ_snapshots-20261116-1318.tgz` — SHA-256 `d20b396631cc4f9543bb93cd9d2648289324e95b818c8ee90d4ada75c6f9e09e`.

План hash фиксирует нормативный текст до добавляемого после коммита журнала исполнения. `documentation-manifest.json` содержит hashes и результаты изолированной инкрементальной индексации docs: 1 upsert, затем 1 unchanged; plan_* не создавались и не менялись. Production docs index не обновлялся по прямому запрету пользователя.

## Воспроизводимость и evidence

Проверенное дерево исходников: `f6476717560305d3ee5da02a3778eb98867a97cbd321d62cb12f1920b58398e6`. Контракт конфигурации: `fde8820f018818f92e5b520d6423339ea9c933779ee52edc16a4490e796a4ec4`. Исходный H commit: `3770a64bf6b5dfeff0a4c3e29ac132b5f8760849`.

Комплект `usertools/MofsIndex/{before,after,changes.patch,manifest.json}` содержит все 9 затронутых файлов. Patch применён к отдельному временному дереву; все after-hashes и режимы совпали. Runtime использует M, импорты из D отсутствуют. `publication-evidence.json` содержит реальные строки из изолированных БД: наблюдаемый storage, hashes, версии, события и отсутствие публикаций при негативных сценариях.

Счётчики FakeConfluence в обязательном S: {"MPXJ_read": 0, "cache_hit": 0, "cache_miss": 0, "attachment_POST_fake": 33, "page_POST_fake": 14, "page_PUT_fake": 18, "live_POST": 0, "live_PUT": 0}. Старые MagicMock-only тесты в эти счётчики не входят. В основном наборе реального MPXJ чтения нет; для отдельного MPP-smoke точное число reader.read не инструментировано и не заявляется.

## Ограничения

- Full admission/prepared snapshot/schedule verification and verified_v1 belong to later stages; repaired legacy publication registrations remain legacy_unverified, with separate current_state observations.
- No live Confluence calls: REST contracts validated with fakes; installed plugin behaviour not accepted in stage 01.
- Storage comparison uses canonical XML and rejects every unexpected content/whitespace change conservatively.
- Production docs index left unchanged under user prohibition; incremental docs indexing verified in isolated database only.
- ownCloud synchronization has not been verified.
- Active skill library registration/synchronization is reserved for plan stage 12; Gateway and schedules untouched.

## Привязка коммита

Код, тесты, отчёт и внешний комплект входят в один завершающий коммит `edit-plan-confluence: stage 01`. Его фактический SHA записывается после коммита в журнал канонического плана. SHA не включается в содержимое самого коммита.
