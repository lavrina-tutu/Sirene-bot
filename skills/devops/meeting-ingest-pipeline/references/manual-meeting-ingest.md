Historical example: the synthetic timestamp recipe below is not source data. Do not invent timestamps for real ingest; mark any explicitly requested synthetic example as synthetic.

## Ручной прогон одной встречи (в т.ч. имитация ingest «как будто из KTalk»)

Когда Саша даёт транскрипт текстом и просит «запиши как будто получили из ktalk и проведи
по стандартному пути» — это полный ручной цикл по контуру, без API источника:

1. **Создать пару файлов** в `WorkVault/Meetings/NewMeetings/` с meeting_id в имени
   (время — UTC, как у контура):
   - `<дата> <время> <Название> - transcript.md` — сырьё: заголовок + `**Date (UTC):**` +
     `**Duration:**` + `**Participants:**` + реплики `00:00:31 **Имя:** текст` (таймстампы
     расставить с шагом ~8–22 сек на реплику — правдоподобная длительность).
   - `<...> - summary.md` — БЕЗ frontmatter (его добавит MOFS), тело: `# Саммари:` +
     секции `Участники:` / `Обсудили:` / `Решения:` / `Блокеры:` / `Задачи:` / `Риски:`
     (формат Custom Skill, обязателен для PFS-парсера).
2. **Название встречи должно содержать alias сущности** — name_match это substring-матч:
   «Синк АиД департамента» попадает в `sink_aid` (331125844), потому что содержит «синк аид».
3. **MOFS: dry-run → real** (meeting-id без суффикса ` - summary.md`):
   ```bash
   cd ~/USERTOOLS/MarkObjectsFromSummary && source ~/USERTOOLS/ProtocolFromSummary/.venv/bin/activate
   mofs run --meeting-id "<дата> <время> <Название>" --dry-run
   mofs run --meeting-id "<дата> <время> <Название>"
   ```
4. **PFS: dry-run → real** по пути summary-файла, затем верификация (реестр + GET обеих
   страниц + MofsIndex) — чек-лист ниже:
   ```bash
   cd ~/USERTOOLS/ProtocolFromSummary
   .venv/bin/python -m protocolfromsummary run "<путь>/<...> - summary.md" --dry-run
   .venv/bin/python -m protocolfromsummary run "<путь>/<...> - summary.md"
   ```
5. **Уведомление прохода 1** (`notified: False` в реестре) уходит notify-кроном; promote
   (проход 2) пойдёт после отметки «обработано» на площадке — ручной прогон их не запускает.

Ограничения, которые в такой имитации НЕ чинить (это состояние контура, не баг файла):
- однословные имена без ФИО не резолвятся в контакт и ложно матчатся на комнаты (см.
  protocolfromsummary: комнатный substring-матч);
- относительные дедлайны «через N дней» не парсятся → fallback +7 (см. protocolfromsummary);
- `contacts: []` в frontmatter при недоступном `CONTACTS_ENCRYPTION_KEY` (см. Pitfalls ниже).

