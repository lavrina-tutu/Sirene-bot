# HF:plan — пофайловый план (SKILL-CHANGE, kanban-notify-subscribe)

ТЗ DevKanbanPipeline_TZ.md 0.2.6 (mtime 16:38, дрейфа нет), раздел «Уведомления графа» (стр. 455–482).
Кейс: SKILL-CHANGE — контент уже на диске, план = верификация, НЕ переписывание.
Диск-факт снят (pipeline_hf_plan_diskfact.py, disk_before в комменте HF:plan).

## Файл 1 — skills/devops/tz-workflow/SKILL.md → 2.3.1 (уже в HEAD)
- подраздел «Подписка графа на уведомления (notify-subscribe)» стр. 158–172: фикс-контракт
  `hermes kanban notify-subscribe <task_id> --platform telegram --chat-id 400307920 --chat-type dm --delivery-mode notify+wake --notifier-profile default`;
  только TERMINAL_KINDS (completed/GATE:done, blocked, gave_up, crashed, timed_out);
  «ядро не трогать»; случаи батчей (триггер, багфикс, IDEA feed).
- version: 2.3.1. git_porcelain пуст → закоммичено.

## Файл 2 — skills/devops/hermes-feature/SKILL.md → 2.6.1 (граф-артефакт, незакоммичено)
- подраздел «Подписка графа на уведомления (notify-subscribe)» стр. 81–95 (тот же контракт + PLAN-IMPL-TAIL/HF-TAIL, багфикс, IDEA feed).
- Блок 6В стр. 103: «# сразу после батча — notify-subscribe ОБЕИХ».
- version: 2.6.0 → 2.6.1. git_porcelain: `M skills/devops/hermes-feature/SKILL.md` — это deliverable текущего графа.

## Изменений нет (read-only фаза)
ни Python-кода, ни новых сущностей/cron/.env/манифеста. premature_impl=false —
контент присутствовал уже в disk_before (легальный черновик, ТЗ утверждено REV:tz).
HF:impl (по графику после GATE:plan-approve) сверяется с планом и не пишет второй раз;
коммит — на ORCH:shared-state.

Handoff → REV:plan (t_2f50b6dc).