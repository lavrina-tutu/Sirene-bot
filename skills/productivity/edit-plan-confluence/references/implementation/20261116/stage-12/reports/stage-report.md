# Этап 12 — интеграция скилла и эксплуатационная документация

Gate: **passed**; S rc=0; selected=660; passed=660.

Команда S:

```text
/usr/bin/python3.9 -m pytest -c /home/tkachenkoav/hermes-workspace/skills/productivity/edit-plan-confluence/tests/pytest.ini /home/tkachenkoav/hermes-workspace/skills/productivity/edit-plan-confluence/tests --acceptance-stage 12 --test-root /home/tkachenkoav/.cache/edit-plan-confluence-acceptance/stage12-20261117/stage-12 -m unit or archive_integration --junitxml=/home/tkachenkoav/.cache/edit-plan-confluence-acceptance/stage12-20261117/stage-12/reports/junit.xml
```

Пофайловая поставка:

- `S/SKILL.md`: канонические publish/save/Inbox/history/compare/identity/resume, адресные решения и раздельное доверие.
- `W/SKILL.md`: короткое перенаправление в skill_view канона без алгоритма.
- `Q/SKILL.md + Q/references/plan-queries.md`: русские запросы того же typed API, локальные сутки и текущая/подтверждённая версия.
- `C/SKILL.md`: адресная ссылка на канон и unified credential loader, прежние JIRA правила сохранены.
- `A/edit-plan-confluence + A/confluence-gantt-plan`: штатный restore после backup/исправления live слоя по регламенту библиотеки; реальные skill_view paths/hashes.
- `S/references/mpp-to-gantt.md`: prepared data вместо обязательной CSV цепочки, качество и ограничения.
- `S/references/cli-contract.md`: все команды/флаги/defaults, глобальные пути, схемы, exit codes, исполнимые parser примеры.
- `S/references/batch-and-inbox.md`: freeze-all, manifest, неизменяемый контекст, разделение регистрации/исполнения решения.
- `S/references/identity-and-rules.md`: evidence/revision, B/C, once/project, identity bootstrap.
- `S/references/history-and-verification.md`: точные selectors, время/offset/cursor, trust и GET-only observations.
- `S/references/testing-and-acceptance.md`: изоляция, группы, ограничения покрытия этапа 12, отчёты и gate.
- `S/references/operations-and-recovery.md`: численные лимиты и реальные источники, backup до будущей миграции, recovery и частичные эффекты.
- `S/references/cases-trisigma.md`: A–G и D-risks, hashes/размеры/метрики и границы функциональной приёмки.
- `R/README.md + M/README.md`: export_full-v2 и typed API; before/after/patch/manifest и восстановление.
- `S/tests/test_skill_contract.py`: загрузчик, parser/dispatch, stdout, secret canary, offsets и совместимость.
- `S/tests/conftest.py`: STAGE12_REQUIRED, отдельные offline selection/order/report; прежние hooks/карты сохранены.
- `E/Manifest + digest/render; MAIN_TZ_INVENTORY`: согласованы существующие записи/ID, версия actual master 0.5.1, внешние пути/hashes/diffs.

Фактически загруженные имена:

- `edit-plan-confluence`: `/home/tkachenkoav/.hermes/skills/productivity/edit-plan-confluence/SKILL.md` → `/home/tkachenkoav/hermes-workspace/skills/productivity/edit-plan-confluence/SKILL.md`; SHA-256 `3a3fa33220c5dac343b9e6fe45022743540449bcaeaebb3a289d058c36e1b58a`.
- `confluence-gantt-plan`: `/home/tkachenkoav/.hermes/skills/productivity/confluence-gantt-plan/SKILL.md` → `/home/tkachenkoav/hermes-workspace/skills/productivity/confluence-gantt-plan/SKILL.md`; SHA-256 `6d2edf035cff8b933577773520abe44d8fd852fd80f16a3b9219fa2dee9292cc`.
- `productivity/edit-plan-confluence`: `/home/tkachenkoav/.hermes/skills/productivity/edit-plan-confluence/SKILL.md` → `/home/tkachenkoav/hermes-workspace/skills/productivity/edit-plan-confluence/SKILL.md`; SHA-256 `3a3fa33220c5dac343b9e6fe45022743540449bcaeaebb3a289d058c36e1b58a`.
- `productivity/confluence-gantt-plan`: `/home/tkachenkoav/.hermes/skills/productivity/confluence-gantt-plan/SKILL.md` → `/home/tkachenkoav/hermes-workspace/skills/productivity/confluence-gantt-plan/SKILL.md`; SHA-256 `6d2edf035cff8b933577773520abe44d8fd852fd80f16a3b9219fa2dee9292cc`.

Внешние команды/rc/JUnit, восстановление USERTOOLS, конфиг-источники и Registries: external-checks.json и связанные evidence.

Source tree: `e0f876a39bf2c4307d3c18109d1bc0899b707e58747902c9269a480f7a65ab14`; защищено 1559 файлов, изменено 0.

Удалены предварительный save, ручное копирование /tmp, автоудаление связей, доказательство отсутствия публикации по nullable дате и повторное общее да для publish.

Timeout: reader 180 с, JVM probe 60 с, HTTP 120 с; retry limit 1 (GET до 2 попыток); MPP/ZIP 64 MiB, ZIP 128 entries/256 MiB unpacked/ratio 100.

Secret-redaction: canary stdout/receipt и сканирование поставки без сохранения реальных секретов. Backup/recovery описаны, production миграция не выполнялась.

Завершающий commit/SHA — после gate, в журнале канонического плана; canon.md исключён.

Ограничения:

- Только этап 12. Полная приёмка этапа 13, live A–D/G и отдельные A–F записи §20.7.3 этим gate не закрываются; прежние evidence не редактировались.
- Маршрутизация проверена по инструкции, реальному parser/dispatch CLI и выбранной регрессии. Сообщение через Gateway/LLM не прогонялось; отклонённое сообщение скилл исправить не может.
- Настоящий skill_view успешен, но штатный загрузчик предупреждает о symlink вне trusted root; loader/Gateway не изменены.
- Generic Codex quick_validate не принимает существующие Hermes frontmatter keys platforms/tools/version (rc=1); рабочий формат сохранён и проверен настоящим Hermes loader. Это не ошибка загрузки Hermes.
- Master на диске 0.5.1 с отдельным §21, исполнялся §20. Inventory приведено к фактической версии, новый APPROVE не заявлен.
- Manifest имеет прежние ошибки общей schema вне новой дельты; список/равенство before-after в registry/manifest-ids.json. Новые ошибки и Tool ID не добавлены.
- Schedule остаётся независимым, unknown/partial identity не превращается в доказанное соответствие. Полный счётчик всех reader/cache регрессий не измерен (null).
- Production БД/архивы/страницы A–D/AB не менялись; приёмка offline. Gateway, кроны, наблюдатели и расписания не менялись. OwnCloud sync не подтверждён.
- Первый отдельный smoke 74 passed выполнялся с изолированным стандартным pytest tmp; финальная приёмка и внешние проверки целиком в T/stage-12. Предварительный smoke не используется как gate.
