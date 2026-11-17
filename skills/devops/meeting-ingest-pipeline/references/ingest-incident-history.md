History and diagnostic examples; do not treat schedule timing or old paths as a current guarantee.

## Диагностика «пришли криво» (порядок, read-only)

Жалоба «встречи в Необработанных без правильного резолва имён / задачи без слагов» =
проверка всей цепочки, не только одного звена:

1. **Сверка трёх списков:** `WorkVault/Meetings/NewMeetings/*-summary.md` за период ↔
   MOFS-реестр (`~/USERTOOLS/MarkObjectsFromSummary/_mark_objects_registry.json`) ↔ PFS-реестр
   (`~/WorkVault/ProtocolFromSummary/_registry.json`).
   **MOFS processed ≠ PFS published**: встреча может быть в NewMeetings и MOFS-обработана
   (objects_version проставлен), но отсутствовать целиком в PFS-реестре — не опубликована.
   «Все пришли» доказывается только записью в PFS-реестре.
   **Но отсутствие записи может быть легитимным skip:** если у summary пусты секции
   Задачи/Решения/Блокеры/Риски (есть только Участники+Обсудили), `summary_has_content_sections`
   даёт false → `skipped_empty`, реестр не тронут, следующий тик перечитает файл. Сначала
   проверить пустоту секций (`grep -E '^## (Задачи|Решения|Блокеры|Риски)' <file>`) — если пусто,
   это дефект самаризации (пересамаривать штатной командой источника MFKT/FF), а не «PFS потерял
   файл»; принудительная публикация пустой строки запрещена.
2. **Гонка PFS→MOFS при диагностике «без слагов/контактов»:** `pfs_batch` (XX:10) ингестит
   раньше `mofs_run_cron` (XX:16) — YAML `project_bind`/`contacts` на момент прохода 1 может
   ещё не существовать, и это не сбой резолва. Сверять `published_at` (PFS-реестр) и
   `processed_at` (MOFS-реестр): если MOFS позже — обычный повторный тик не поможет, нужен
   реплан с заменой строки (см. Правило 3).
2. **GET площадки** (`523032632`, Bearer `CONFLUENCE_TOKEN` из
   `~/USERTOOLS/ConfluenceSync/.env`), вырезать `<tr>` строки по row_anchor и посчитать
   `ri:userkey`: `0` = имена голым текстом, резолв участников/исполнителей не прошёл.
3. **Слаги задач** — в `<ac:task-body>`: отсутствие префикса-слага при hypothesized/`slug`
   в MOFS `project_bind` = разрыв MOFS→PFS (see protocolfromsummary);
   `status: unbound` в MOFS = слаг не назначен ещё на MOFS-стороне.
4. **frontmatter summary** — `contacts: []` при участниках в теле и `project_bind` с
   unbound-задачами: признаки неполного MOFS; не лечить правкой HTML на площадке.
5. **Фикс в коде ≠ строки переписаны.** Наличие token-set Pass 2 в `store.py` (§35
   protocolfromsummary) не означает, что старые строки площадки уже залинкованы — они
   остаются голым текстом до republish/перезаписи; факт исправления доказывает только GET.
6. **По одному звену на вопрос.** При первичном разборе не гадать про звено: выводить
   «сырьё есть / MOFS ok|bad / PFS published|missing» по реестрам и странице, потом отдавать
   архитектору (BUG:diagnose) полные факты с путями и ожиданиями.

