---
name: epic-development
description: "Правила Epic: модульное ТЗ и бриф по одному вопросу"
version: 1.2.0
author: agent
tags: [epic, briefing, tz, planning, tools]
platforms: [linux, macos, windows]
---

# Epic Development — правила работы с эпиками

## When to Use

Использовать для «Начнём работу с Epic», «Следующий модуль», «Бриф по модулю», а также для ТЗ `TZ_*_main.md` и папок `modules/`.

## Контекст и порядок

1. Перед модулем прочитать главное ТЗ, ТЗ всех закрытых модулей и его `⚠️` кросс-вопросы; обновить план с учётом принятых решений.
2. Перед вопросами показать карточку модуля (функция, вход, выход, зависимости, статус) и записать её в ТЗ. Ждать подтверждения PM.
3. Порядок MVP: сначала независимые фундаментальные модули, затем разблокирующие несколько зависимостей, затем оркестрация/интеграция. Не менять без явного решения.
4. После ответа сразу записывать решение в ТЗ; после закрытия — резюме ключевых решений, выхода и следующего модуля.
5. Кросс-влияния помечать `⚠️ [от модуля X, ВN] ...` в ТЗ владельца вопроса.

Подробный шаблон карточки, резюме и порядок артефактов: [epic-development-details.md](references/epic-development-details.md).

## Брифинг

- Один вопрос за раз, варианты только **А/Б/В**, явная рекомендация с бизнес-обоснованием; после ответа — запись и следующий вопрос.
- Для карточек похожих сущностей сравнивать поля поштучно; сначала подтвердить карточку, затем одинаковые и различные блоки.
- Неизвестную концепцию объяснять на конкретном примере из контекста, затем возвращаться к брифу.
- Архитектурное допущение сначала фиксировать как изменение, затем обновлять карточку и все затронутые ТЗ.
- Если «внешний инструмент» не имеет смысла без Epic, пересмотреть границу и включить его как модуль.
- При вопросе «сразу по-хорошему» сравнить варианты по фазам MVP/2/3 и рекомендовать путь с минимумом переписываний.

Подробные форматы и анти-паттерны: [epic-development-details.md](references/epic-development-details.md).

## Проектирование данных и пайплайна

- Артефакты Epic хранить в `WorkVault/Tools/{EpicName}/`: главное ТЗ, `modules/`, `research/`; связанные backlog-пункты связывать `^epic-[slug]`.
- Для трёх продуктов фиксировать таблицу «продукт | аудитория | хранение | владелец | MVP | Фаза 2» и сверять решение с ручным аналогом на реальных данных.
- Для накопительных файлов default — append-only: противоречие зачёркивать с датой, action items нумеровать сквозно `#N` по сущности; `pm_locked` не добавлять без реальной необходимости.
- Для больших датасетов разделять дешёвую разметку ×N и качественную агрегацию ×M; Haiku/Sonnet выбирать только после теста на 3–5 реальных записях.
- В автоматическом пайплайне в MVP предусмотреть JSONL-логи, retry 0→15→60 минут (до 3), немедленные ошибки и дайджесты; подробная матрица ошибок — в [epic-development-details.md](references/epic-development-details.md).
- Источник фактов — реальные данные, не догадки. Владелец каждого алгоритма один; остальные модули ссылаются на него.

Правила классификации, алиасов, карточек People/Syncs и данные AggregateFromMeetings: [meeting-classification-algorithm.md](references/meeting-classification-algorithm.md), [aggregate-cards-architecture.md](references/aggregate-cards-architecture.md), [aggregate-E-H-decisions.md](references/aggregate-E-H-decisions.md), [aggregate-from-meetings-arch.md](references/aggregate-from-meetings-arch.md).

## Единые правила формата и целостности

- Модули всегда называть `Буква.Название` (`B.Роутер`, `D.База`, `E.Люди`, `F.Дирижёр`, `G.Срез`, `H.Синки`).
- Алиасы разделять по неймспейсам проекта, контакта и синка; операции удаления — soft-delete с восстановлением.
- Новые решения проверять по аналогии с уже проработанными сущностями (например `Projects/card.md`) и явно называть аналогию.
- Перед архитектурным решением исследовать реальные входы; проверять качество источников по принципу «мусор на входе → мусор на выходе».
- Перед закрытием Epic сверять зависимости, типы, пути, state/cache, кросс-поля, PM Notes, `#N`, фазу 2 и владельцев генерируемых артефактов.

## Верификация и реализация

После брифа всех модулей собрать пакет внешней проверки с полными ТЗ, ASCII-графом, таблицей передачи данных, контрольными вопросами и глоссарием; вести дельту прошлой итерации и повторять аудит после правок. Процесс и шаблоны: [tz-verification-workflow.md](references/tz-verification-workflow.md).

После APPROVED создать `IMPLEMENTATION_PLAN.md` с принципами, функциями, графом bootstrap/increment, этапами с тестами/метриками, путями USERTOOLS vs WorkVault, naming, dev-log, checkpoints и рисками.

При реализации разделять HUMAN-GATES: автоматические H1/H2 продолжаются при зелёных тестах; H3–H7 (смысл, деньги, unclear, боевые записи, противоречия) требуют остановки PM. Машинный GATE-отчёт сначала переводить в русский контекст с примерами выходов и конкретными вопросами.

Подробности пакета, плана, gates и перевода отчётов: [epic-development-details.md](references/epic-development-details.md), [tz-verification-workflow.md](references/tz-verification-workflow.md).

## Unclear и исследования

Перед брифом unclear собрать реестр из очереди пайплайна, дедуплицировать `-actions.md`/`-summary.md`, классифицировать и показать сводку. При >20 записей группировать по сущностям, читать саммари (первые 600 символов/ключевые bullet points), передавать группы по одной; рекомендация строится по содержимому, не заголовку.

При исследовании по backlog создать `bk-NNN`, файл `WorkVault/Hermes-Backlog/research/bk-NNN-slug.md`, запустить исследование и привязать результат. Для one-shot cron проверять `last_run_at/next_run_at/output`, запускать пропущенную задачу вручную и использовать `origin` для доставки.

Подробные unclear-решения и восстановление cron: [aggregate-unclear-brief-2026-06-21.md](references/aggregate-unclear-brief-2026-06-21.md), [aggregate-unclear-brief-2026-06-22.md](references/aggregate-unclear-brief-2026-06-22.md), [cron-oneshot-recovery.md](references/cron-oneshot-recovery.md).

## Логический аудит и отладка

При расхождении кода и ТЗ сначала выполнить read-only аудит и определить, что именно неверно; не откатывать работающий код без доказательства. Для решения «переписать или дописать» учитывать архитектурные конфликты и покрытие тестами.

`explain_unclear()` должна выдавать одну решающую причину. Для R10 проверять импорт `AnthropicLLM()`, модель `claude-haiku-4-5`, ключ в `~/.config/hermes/.env` и fallback `bullet_points/notes`; перед bootstrap — `pip install -e .`.

Детали аудитов и R10: [aggregate-logic-audit.md](references/aggregate-logic-audit.md), [aggregate-logic-audit-full.md](references/aggregate-logic-audit-full.md), [aggregate-r10-llm-fallback-debug.md](references/aggregate-r10-llm-fallback-debug.md).

## References

- [epic-development-details.md](references/epic-development-details.md) — перенесённые подробные процедуры, примеры и питфоллы этого скилла.
- [aggregate-from-meetings-arch.md](references/aggregate-from-meetings-arch.md), [aggregate-D-decisions.md](references/aggregate-D-decisions.md), [aggregate-E-H-decisions.md](references/aggregate-E-H-decisions.md) — архитектура и решения модулей AggregateFromMeetings.
- [aggregate-cards-architecture.md](references/aggregate-cards-architecture.md), [meeting-classification-algorithm.md](references/meeting-classification-algorithm.md) — карточки и классификация.
- [tz-verification-workflow.md](references/tz-verification-workflow.md) — внешняя верификация и запуск реализации.
- [aggregate-logic-audit.md](references/aggregate-logic-audit.md), [aggregate-logic-audit-full.md](references/aggregate-logic-audit-full.md), [aggregate-r10-llm-fallback-debug.md](references/aggregate-r10-llm-fallback-debug.md) — аудиты и отладка.
- [aggregate-unclear-brief-2026-06-21.md](references/aggregate-unclear-brief-2026-06-21.md), [aggregate-unclear-brief-2026-06-22.md](references/aggregate-unclear-brief-2026-06-22.md) — результаты unclear-брифов.
- [cron-oneshot-recovery.md](references/cron-oneshot-recovery.md), [AC-integration-analysis-v1.0.md](references/AC-integration-analysis-v1.0.md), [exchange-org-lookup-research.md](references/exchange-org-lookup-research.md) — operational references.

## Scripts

`scripts/parse_unclear_queue.py` строит `unclear_registry.md` из `unclear_queue.md`; запуск: `python parse_unclear_queue.py <src> [output.md]`.
