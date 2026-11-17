# Идентичность и правила B/C

Identity — направленная пара snapshot одного проекта с representation,
source hashes и профилями. Имя, UID, lineage и идентификация эталона A не
подтверждают continuity между разными MPP. Автотранзитивности нет.
Same-source proof ограничен одним snapshot или одинаковым источником в
одинаковых представлении, нормализации и timezone.

Новый MPP сначала архивируется внутри diff/publish. При пригодном источнике
остановка возвращает snapshot_id, archive:verified, published:false,
external_effect:none. Предварительный отдельный save не требуется.

```cli-example
cli.py diff --mpp /inputs/new.mpp --page-id test-page --project-slug trisigma
cli.py operation show --operation-id test-operation
cli.py identity confirm --project-slug trisigma --from snapshot:test-anchor --to snapshot:test-new --mode continuity --evidence /inputs/user-statement.txt --reason "Пользователь подтвердил сохранение UID namespace"
cli.py identity show --project-slug trisigma --mapping-revision test-revision
cli.py resume --operation-id test-operation --mapping-revision test-revision
```

Использовать реальные ID из operation show, включая identity_requirements и
точные source hashes. Свидетельство — явное утверждение пользователя, не
сгенерированная догадка. Evidence копируется в content-addressed архив,
сохраняются SHA-256/author/source/time/reason/policy.
Confirm регистрирует revision, но не продолжает публикацию. Resume использует
тот же исходный snapshot/item и frozen source без повторного поступления.

Для явного частичного соответствия:

```json
{"schema_version":1,"pairs":[{"entity_kind":"task","from_key":"anchor-task","to_key":"new-task","identity_key":"confirmed-business-task"}]}
```

```cli-example
cli.py identity confirm --project-slug trisigma --from snapshot:test-anchor --to snapshot:test-new --mode mapping --mapping /inputs/mapping.json --evidence /inputs/user-statement.txt --reason "Подтверждена указанная пара"
```

`schemas/identity-mapping.schema.json` запрещает null/неизвестные поля;
entity_kind=task/resource/calendar/assignment, ключи из точных version-данных.
Обе стороны однозначны, partial сохраняет несопоставленные сущности.
Выбор: явная пригодная revision → единственная active → unknown;
несколько active — mapping_ambiguous/3. Неподходящая область/отзыв — конфликт/4.
Для B/C нужны обе задачи и остальные требуемые сущности. Недостаточный partial
даёт identity_mapping_incomplete/3 и не занимает слот выбора операции.
Достаточная revision фиксируется атомарно; замена — mapping_revision_conflict/4.
Supersedes — явный `identity confirm --supersedes ID`, прежняя история остаётся.
Отзыв доступен typed writer `revoke_identity_revision`, самостоятельного CLI нет.
Superseded/revoked выбранная revision блокирует resume, автоматически не заменяется.

## Преобразования и область согласия

```cli-example
cli.py diff --mpp /inputs/new.mpp --page-id test-page --project-slug trisigma --drop-dep 16:17
cli.py operation show --operation-id test-operation
cli.py resume --operation-id test-operation --accept-proposal test-proposal --rule-scope once --reason "Пользователь согласовал исключение указанной связи в этой операции"
cli.py resume --operation-id test-project-operation --accept-proposal test-project-proposal --rule-scope project --reason "Пользователь явно согласовал правило проекта"
cli.py resume --operation-id timezone-operation --timezone-hint Europe/Moscow
```

`--drop-dep` — предложение для точного source hash, разрешаемое в устойчивые
source-local endpoints; не автоматическое удаление. B/C проверяют проект,
опорный snapshot/evidence, mapping revision, endpoints, исходные type/signed
lag и контекст/причину. Меняется только производное представление, исходный
MPP snapshot остаётся. Затем повторяется допуск. Исправленная конвертация
может дать not_needed; исторические 98/84.875 и 89/76.875 не цель подгонки.
Неподтверждённое старое правило остаётся неактивным. Доказанно применимое
согласованное правило повторно не согласуется.

Scope once — только операция, project — явное версионированное правило с
immutable consent evidence. На новый источник правило переносится только
при достаточной identity и актуальной причине. Общее согласие не отменяет
hash/read-back или запрет записи до допуска. Несколько корней и новое
преобразование потерь требуют принятия точного proposal из operation show.
Без готового proposal не придумывать флаг «игнорировать предупреждения».

Timezone уточняется до внешнего эффекта и только если ещё неизвестна:
новая подготовка и snapshot сохраняют прежние; mapping/decisions на новую
пару не переносятся автоматически. Разрешённая timezone меняется новой
операцией. Для batch-item timezone/mapping/project-scope запрещены:
`batch_context_immutable / 4`; нужны новый manifest и batch ID.

## Д4 — решение владельца о публикации исходного файла

`owner-decision-v1.json` с хешем адресного evidence фиксирует, что историческое
правило B/C не применяется: UID510→UID323 сохраняется, `result=not_needed`,
пометка «историческое правило не применяется (решение владельца)». Отсутствующая
историческая ревизия остаётся неактивной. Это не подтверждение удаления связи.
Новые точные адресные предложения по прежнему требуют своего evidence.

`resource_uid: missing` с причиной `not_set` и пустым resource_key допускается
при сохранении исходных интервалов/работы в видимой текстовой колонке задачи.
Пометка допуска: «назначение без ресурса публикуется как есть (resource_uid: missing)».
Плагин не создаёт native assignment на выдуманный ресурс. Задача/плановые даты
сохранены; независимый пересчёт ресурсной загрузки не заявляется. Неразрешённый
известный UID, ошибка чтения, скрытые/потерянные данные продолжают блокировать допуск.

Режим снимка удерживает source start/finish: native `manuallyScheduled=true`,
`skipNonWorkingTimeWhenSchedulingManually=false` — способ отображения, не правка
MPP. Исходный task_mode виден в колонке «Показ дат / исходный режим MPP» и архиве.
Связи остаются активными и проверяются в модели плагина. Это не утверждение об
эквивалентном пересчёте. Профиль подтверждён GET-only загрузками A/B/C; источник D
содержит отдельное противоречие UID373: milestone=true, duration=0, start 30.03,
finish 22.04. По решению владельца такая веха публикуется как есть
(`milestone_interval_conflict=publish_collapsed`): плагин рисует точку на одну
дату, интервал сжат при отображении с пометкой, обе исходные даты сохранены в
архиве; решение о пустом ресурсе на это не влияет. Если веха в последующем плане
становится задачей — применяется общее правило актуальности последнего плана.
