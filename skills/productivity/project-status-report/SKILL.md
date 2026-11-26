---
name: project-status-report
version: 1.0.0
description: "Use when: статусы проектов, минутки, отчет о завершении."
tags: [confluence, projects, status, minutki, workvault]
related_skills: [tutu-confluence-jira, workvault-rag, workvault-entities]
---

# Project Status Report — статусы проектов АиД

Target page: Confluence `pageId=523034979` («Проекты. Статус проектов», space DPAN).
Columns: Наименование проекта (link to root page) | Статус (link to artifact) | Дата Статуса | Комментарий.

## Sources of truth (priority order)

1. Confluence minutki of the project (protocols with customer participation).
2. Done/completion report pages ([DONE] pages, «Отчет о завершении»). Status date = report date, not last task.
3. WorkVault: mofs index (`search_meetings`, `get_meeting_body`), `Entities/<slug>/card.md`.
4. 1-1 syncs (Аралов) — use when project minutki are empty; mark source in comment.

## Workflow

1. Map projects → Confluence root pages. Root list = children of «Проекты» `310325571` + entities.json `pfs.page_id` + Sasha's additions. Missing project → ask Sasha or add via `entity-registry`.
2. For each project find its minutki page: child of root named «Задачи и договоренности (Минутки)» / «Протоколы» / «Задачи». If empty → check deeper, OpenTasks DONE (pageId 492610494 via CQL `text ~ "<kw>" and space in DPAN,~tkachenkoav`), 1-1 Аралов (mofs, contacts slug filter).
3. Extract last significant event of 2026: top rows (newest first) of minutki table; extract `<time datetime="YYYY-MM-DD">` per row. Completion event beats newer routine rows only when Sasha says so — otherwise last event wins.
4. Update target table (see Confluence mechanics). Sort rows by status date DESC (fresh on top). Keep original empty placeholder rows at the bottom.
5. **New project row (Sasha names a project, e.g. «Закупка данных ЗД»):** entities.json `pfs.page_id` = minutki page (tag «<Slug>.» tells the prefix). Root page = direct ancestor of minutki under «Проекты» — read via `GET .../content/<minutki_id>?expand=ancestors`, NOT by CQL title (root and minutki titles differ, e.g. root «Закупка данных (Обогащение клиентских данных)» vs minutki «Закупка данных (...). Задачи и договоренности (Минутки)»). Fresh protocol → status «В работе — протокол» (→ minutki), comment summarizes current tasks from the protocol rows. Show draft in chat; PUT only after «делай».
6. Sync Entities: update `Entities/<slug>/card.md` frontmatter (status, end_date, last_active, customer) — see workvault-entities.

## Правило записи (решение Саши, 22.09.2026)

- **PUT на страницу статусов — только после ЯВНОГО подтверждения Саши на конкретный черновик.** Черновики строк показывать текстом в чат; сама по себе команда «продолжаем собирать статусы» — НЕ разрешение на запись.
- Список проектов в таблице — эталон Саши: ничего не добавлять и не удалять; найденные «недостающие» проекты не вносить самовольно, только перечислить и спросить.
- Свежие протоколы, найденные при сборе, не превращаются в правку без его слова; отбрасываются по команде «забудь что есть новое».

## Row rules (fixed vocabulary)

- Status cell labels: `В работе — протокол` (→ minutki), `Завершён — Отчет о завершении` (→ report page), `Завершён — протокол` (no report), `Приостановка — протокол`, `В работе — задачи` (minutki page is «Задачи»).
- Every comment MUST contain a link labeled exactly `Задачи и договоренности (Минутки)` pointing to the project's protocol page. Links go inside meaningful words; date + participants + decision in 1-3 sentences.
- Completion info for a sub-project goes to comment as extra sentence with links: протоколы + отчет о завершении.
- If status comes from 1-1 (not published protocol), state it: «1-1 с Араловым А., <дата>: …».

## Confluence mechanics

- Auth: `CONFLUENCE_TOKEN` from `~/USERTOOLS/ConfluenceSync/.env` (load per-line, do not `source` whole file). web_extract is blocked on dom.tutu.ru — curl only.
- Read: `GET /rest/api/content/<id>?expand=body.storage,version` → save to /tmp file (JSON has backslash escapes; never parse stdout directly), delete after use.
- Write: PUT with `{id, type:page, title, version:{number:current+1}, body.storage{value, representation:storage}}`. NO `space` field. Verify by re-GET: row count, links, dates.
- Insert into empty minutki template (ver 1, columns «Дата постановки | Задачи и Договоренности»): find `<th>Задачи и Договоренности</th>` → insert `<tr><td>DATE</td><td><div class="content-wrapper"><p>TEXT</p></div></td></tr>` after header row's `</tr>`, before `</tbody>`.
- Macro pages (OpenTasks 492610494) render only first page of tasks-report-macro in body.view; for real DONE lists use CQL content search + per-page storage.
- FTS in mofs: quote hyphenated queries (`"ML" "платформа"`), otherwise sqlite error.

## Pitfalls

- Minutki tables are newest-first — top 2026 rows are the latest events; don't take the last rows.
- Fireflies attribution in meeting rooms is unreliable — 1-1 decisions attributed to Аралов may actually be Sasha's; mark as unclear when citing tasks.
- Status date = event date from protocol/report, not the sync date. If Sasha names a different date explicitly (e.g. report date 01.09.2025), his value wins.
- Projects may be renamed/closed (e.g. «Антибот ... (закрыт)») — keep the page title as-is (literal preservation).
- Page is human-edited AND version moves between touches (someone may edit while you prepare): fetch GET immediately before building the PUT payload in the same script — a version read earlier in the session is already stale. Never delete rows without explicit Sasha request.
- After WorkVault changes: rclone sync ~/WorkVault owncloud:WorkVault.

## Related

- Confluence API details, minutki format: skill `tutu-confluence-jira`.
- Meeting archive search: skill `workvault-rag`.
- Entities structure: skill `workvault-entities`.