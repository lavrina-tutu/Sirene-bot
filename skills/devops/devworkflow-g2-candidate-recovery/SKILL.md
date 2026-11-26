---
name: devworkflow-g2-candidate-recovery
version: 1.0.0
description: "Use when G2 source-drift или потерян .git кандидата."
---

# Приёмка и восстановление кандидата dev-workflow

Класс оркестраторских операций вокруг фазы: сверка пакета G2 перед `complete-phase`,
формат `--evidence`, пересборка кандидата и восстановление git. Процесс —
скилл `dev-workflow` (его `references/invoke.md` и `references/operational-pitfalls.md`);
этот файл не заменяет маршрут, а закрепляет приёмы, проверенные на живых поездах.

## `complete-phase --evidence`: обязательный ключ

`--evidence` принимает только ключевые формы `path=<abs>`, `sha256=<hex>` или
`session_id=<id>`. Голый список значений отклоняется до записи rc=1
(«evidence must include path= or sha256= or session_id=»). Считать sha ДО вызова
(`sha256sum <файл>` в ту же команду) и вставлять значение; плейсхолдеры запрещены.

## G2 source-drift сверяет sha + size + mtime_ns

Любой файл, на который ссылается emitted packet (inputs/must_read/sources), при
`complete-phase` сверяется с пакетной копией по sha256, size_bytes И mtime_ns.
Одного восстановленного sha недостаточно: после правки файла отработает
`G2: source drift: <path>` даже при совпавшем хеше.
- Не редактировать файлы пакета (в т.ч. оркестраторские `HF-backup-manifest.json`)
  после `emit-prompt` — rebind/rebuild делается ДО emit, чтобы emit зафиксировал
  актуальную версию ref.
- Если файл уже в пакете и обязан быть исправлен: восстановить точный контент,
  size и mtime_ns из пакетной копии (`touch -d @<mtime_ns/1e9> <файл>`), затем
  повторять `complete-phase`.

## Роль-исполнитель может сама сломать G2, переписав оркестраторский файл

Оркестраторские файлы (`HF-backup-manifest.json`, `_state.json`, `journal.md`,
queue) лежат ВНЕ write_scope роли, но роль иногда «на всякий случай» их
переписывает (например, rebind manifest на свой новый HEAD). Итог — не ошибка
кода роли, а `G2: source drift: <path>` на пост-инвок-проверке: rc=4,
`context_result`/receipt НЕ записываются, хотя кандидат и evidence уже COMPLETE.
Правильный код в candidate — это не повод чинить транзиентно в live; фаза без
полного proof не принимается.
Признак: после доработки роль внесла правильные изменения (diff в allowlist,
evidence COMPLETE), но заодно rebind-нула manifest; `complete-phase` с реальным
новым HEAD даёт `G2: accepted prepare/result receipt mismatch` (нет result), а
invoke — `G2: source drift`.
Восстановление: (1) вернуть manifest к точной пакетной версии (sha+size+mtime_ns);
(2) переоткрыть фазу штатным repair-writer, emit заново и invoke-continuation,
 дав роли явную NOTE: «НЕ трогать manifest/_state/journal/queue — rebind делает
оркестратор ПОСЛЕ твоего завершения; только подтверди готовность, прогони тесты,
перепиши своё evidence»; (3) после приёмки оркестратор сам делает финальный rebind
manifest под HEAD, затем emit следующей фазы фиксирует актуальную версию.
Manifest-rebind после rework — всегда оркестраторская операция, никогда ролевая.

## Пересборка candidate: `.git` не трогать и как восстановить

- Удаление через glob вида `rm -rf "$C"/* "$C"/.[!.]*` уничтожает `.git`
  (шаблон `.[!.]*` матчит `.git`). Чистить только именованные подкаталоги
  (`rm -rf "$C/Registries" "$C/skills"`), никогда каскадный glob по всему дереву.
- `find <cwd> -exec rm -rf` в рабочем каталоге блокируется hardline-правилом
  Hermes; путь с `find -exec rm -rf` на корне рабочего каталога не использовать.
- Потерянный `.git` кандидата восстанавливается из полного дневного tgz-бэкапа
  `~/WorkVault_backup/_full-WorkVault-backup/WorkVault_full_*.tgz`: путь
  `WorkVault/Hermes-Backlog/dev/<slug>/candidate/.git` извлекается с корректным
  `--strip-components` (считать компоненты ВКЛЮЧАЯ `WorkVault`, т.е. до `.git`),
  затем `cp -a` обратно в кандидат. История коммитов сохраняется целиком;
  после восстановления сразу проверить `git log`, `git rev-parse` старых SHA.
- Использовать дневной бэкап времени ДО момента удаления — он снимается
  ежедневно в 23:30 и содержит `.git` кандидатов. Проверить наличие в архиве
  первым делом (`tar -tzf | grep '<slug>/candidate/.git/HEAD'`).
- Восстановленный из tgz `.git` приносит мусорный **gitlink `candidate`** в индекс:
  `git ls-tree HEAD candidate` → `160000 commit <sha>	candidate`, а
  `git status`/`diff --name-status` показывает ` M candidate` / `D candidate`.
  Это сломает allowlist-сверку (`baseline..HEAD` получит лишнюю строку). Чистка:
  `git rm --cached candidate`; затем find/rm физический `candidate/candidate/.git`
  (остаток от неправильного strip), + `candidate/candidate` каталог.
- После restore `.git` стоит на `master`/старом HEAD с ветками-сиротами;
  orphan-rebuild поверх него даёт gitlink-artefact. Проверенный порядок: reset
  `--hard` к baseline-коммиту, `git rm --cached candidate`, commit чистого baseline
  БЕЗ gitlink, заново применить carry-over patch и commit → `diff --name-status
  baseline..HEAD` обязан быть ровно allowlist-пути, без `D candidate`.

## prep rc=0 ≠ PASS: verdict читать по содержимому evidence, не по exit-коду

HF:test prep может вернуть rc=0 (prepare+result+receipt записаны, post-invoke
прошёл — оркестрация ОК) и ТЕМ НЕ МЕНЕЕ зафиксировать контентный FAIL в самой
верификации. Оркестратор обязан открыть `evidence/HF-test.md` и его таблицу
проверок, а не полагаться на exit-код wrapper. rc=0 здесь означает только «scope и
proof в порядке»; `status: FAIL` в evidence означает, что smoke/регрессии красные
и PREPARED-контракт НЕ обеспечил PASS. Признак, что блокер контентный, а не
оркестраторский: slash-блокер закрыт (файлы B55-pilot записаны), но в таблице
верификаций строки FAIL/timeout.

## Bounded-регрессии: рекорд nodeid обязателен; обрезанный rc=124 — не green

Bounded-команда регрессии (context/full) обязана вывести ТОЧНУЮ зависшую/упавшую
nodeid как FAIL, а не просто `bounded_rc=124` + обрезанный хвост dots. Обрезанный
до 2–3 строк лог без имён упавших тестов — само по себе нарушение плана (§2
«зависшая nodeid → FAIL») и повод вернуть фазе, а не засчитывать. Лог, который
не даёт воспроизвести fail-имена, не является evidence ни для PASS, ни для
diagnose — повторный целевой прогон даёт только pass/fail без причины.

## «Статичный native model» ≠ «codex-ветка с model=None»: проверять реальный resolve

Если план требует «compressor держит native model static (model=null), effort
явно», а fixture задаёт `default_backend: codex` — кодекс-ветка `_resolve_model_backend`
потребует непустую строку `resolved_model` (roles.compressor.model или --model)
иначе `prepare: no Codex model for compressor` rc=2; `HERMES_COMPRESSOR_MODEL`
в этот путь не попадает. Замысел плана может быть верным, но проверять его надо
по реально выполняемой ветке resolve (grep по `resolved_backend == "codex"` для
роли), а не по комментарию в fixture. При несовместимости — это развилка для
архитектора (A: резолвить из env-переменной; B: fixture → hermes-internal backend;
C: иное), а не слепой rework исполнителя.

## Приёмка HF:impl: проверять banned-паттерн grep-ом, не только тестами

Требование «единый verifier без ветки по типу случая» (типа «убрать
caller-specific ранний отказ») закрывается только отсутствием паттерна в коде:
`grep -n '<banned condition>' candidate/...` должен вернуть NOT FOUND.
Зелёные targeted-тесты этого не доказывают — исполнитель добавляет общий
verifier (projection inputs/outputs/write_scope/prohibitions), но может оставить
старый ранний отказ рядом. При нахождении banned-ветки: reconcile помечать
`ARCHITECT_REVIEW_REQUIRED` с мотивом, не `COMPLETE`; вернуть исполнителю адресную
доработку через штатный repair-writer; diff повторного кандидата должен показать
удаление именно banned-строк, а не только добавление новых проверок.

## Staged HF:test (§67 PREPARED/partial): исполнитель его молча пропускает

Планируемый staged-контракт фазы (prep пишет только два canonical со статусом
`PREPARED`/`partial`, ORCH создаёт pilot evidence, reader на втором emit пишет
финальный PASS; prep не расходует recover_counts) реализуется в кандидате, а не
принимается по умолчанию. Исполнитель закрывает projection-verifier и "implementation
clean", но status-aware result-check чаще всего НЕ добавляет. Перед первым
invoke HF:test (и после rework HF:impl) проверять grep-ом и diff-ом:
- `grep -rn 'PREPARED\|partial\|staged' candidate/.../(pipeline_context.py|invoke_role.py)`
  — пусто значит staged-механика не реализована; prep-вызов упадёт на пост-проверке
  результата, а не на своём коде.
- `diff <(sed -n '/^def check_result_outputs/,/^def /p' live/pipeline_context.py)
  <(sed -n '/^def check_result_outputs/,/^def /p' candidate/.../pipeline_context.py)`
  — IDENTICAL означает, что критичная функция не тронута реализацией.
- §214-тест на `changed_files` snapshot обязан существовать в кандидате; отсутствие
  файла теста = блокер HF:impl, ревьюер/оркестратор закрывает его до HF:test.

## HF:test запускать ТОЛЬКО с candidate-roots (§78), не с live

HF:test (и prep, и reader) обязан исполняться с candidate-roots, а не с live:
`PYTHONPATH=<C>/Registries`, `PIPELINE_ROOT=<C>/Registries/pipeline`. Причина:
post-invoke oracle `check_result_outputs` выполняет ровно тот `pipeline_context.py`,
который лежит в текущем PYTHONPATH. Если запустить prep с live-roots
(`/home/tkachenkoav/WorkVault/Registries`), oracle загрузит live-код — а live НЕ
содержит и не должен содержать фиксы кандидата (HF:impl live не пишет) → prep
падает на пост-проверке KeyError `HF-test-logs/`, хотя кандидат уже корректен.
Зелёный candidate — это не повод запускать фазу против live; §78 предписывает
candidate-roots, и это единственный путь, где oracle видит staged-фикс.
Перезапуск: сбросить фазу в todo штатным repair-writer, emit заново с
candidate-roots (packet_id сменится), invoke с теми же candidate-roots.
Проверка перед запуском: grep фикса (`prep_owned`, `staged_hf_test`,
`rstrip('/')`) в `<C>/Registries/pipeline/pipeline_context.py`, а не в live.

## Новая ревизия плана (rev N+1) требует ручного переключения цикла — `next` его не делает

Когда HF:test зафиксировал контентный FAIL и архитектор (по канону 2-го захода)
возвращает НОВУЮ ревизию HF-plan (rev10 → rev11 и т.д.), `complete-phase HF:plan`+
`next` ведёт дальше НЕ по новой ревизии, а по сдвинутому указателю текущих
`done`-фаз: после rev11 it покажет `HF:test/backup/impl done → next HF:test`.
Plan self-declares: «обязательны новый HF:backup, независимый REV:plan=APPROVE,
новый candidate commit, новый staged HF:test — прежние approvals не переиспользуются».
Оркестратор обязан САМ переключить цикл штатным repair-writer (`write_state(event=repair)`),
разу в том же скрипте:
- `REV:plan` → `WORK`/awaiting (независимая ревизия новой редакции);
- `HF:backup`/`HF:impl`/`HF:test` → `todo` (результаты старой ревизии не переиспользуются);
- `st.phase = REV:plan` уже race-free.
Без этого переключения ревизор/исполнитель возьмутся за завершённую фазу old-rev
и переиспользуют stale approvals. Эмитить REV:plan после сброса (на актуальном
state), затем invoke reviewer; тот же reset-скрипт `rev<N+1>_reset.py` переиспользовать
на каждой новой редакции. Candidate после reset пересобирается orphan-rebuild с
allowlist новой ревизии; старые HEAD — только audit anchors.

## Не править evidence между выходом роли и complete-phase

После того как invoke-role вернул rc=0, post-invoke уже зафиксировал snapshot
outputs (`context_result["outputs"]` с sha/size/mtime каждого evidence-файла).
Рукоправка evidence (напр. reconcile.json: ARCHITECT_REVIEW_REQUIRED → COMPLETE)
в этот промежуток даёт на `complete-phase` `G2: result output changed` rc=1.
Правильно: либо дождаться, пока РОЛЬ сама запишет нужный статус в том же ходе
(reconcile COMPLETE пишет исполнитель, а не оркестратор), либо после приёмки
переписывать evidence оркестратором — но не трогать его между выходом роли и
`complete-phase`. Если понадобился другой статус reconcile: вернуть фазу штатным
repair-writer и дать роли NOTE «поставь reconcile status COMPLETE», а не править
файл вручную после снапшота.

## Каталог `changed_files` (trailing slash) роняет output_snapshot/check_result_outputs

OutputRef-каталоги вида `.../evidence/HF-test-logs/` (со trailing slash) ломают
пару output_snapshot/check_result_outputs: snapshot кладёт ключ через
`str(Path(path))` (слэш схлопывается), а check ищет `after[path]` по сырому
`item["path"]` со слэшем → KeyError после выхода prep-wrapper. Нормализовать
`rstrip('/')` согласованно в обоих местах (или в snapshot, или в lookup) —
иначе любая каталоговая запись write_scope даёт rc=1/traceback на пост-проверке,
а артефакты prep уже созданы. Кандидат с такой функцией IDENTICAL live — недовыполнение;
вернуть на rework до первого вызова HF:test, не чинить транзиентно в live.
