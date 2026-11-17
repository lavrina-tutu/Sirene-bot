# Real Architecture and RFC Workflow

Используй этот файл для production-дизайна, RFC, tech spec, платформенной архитектуры и миграции. Production-архитектура обязана учитывать существующий контекст, ownership, delivery path и стоимость изменения.

## Сначала выбери размер результата

| Ситуация | Достаточный артефакт |
|---|---|
| Обратимое локальное решение | Короткая recommendation + risks |
| Новый сервис или значимая интеграция | One-page design / mini-RFC |
| Необратимое data/API решение | RFC + ADRs + rollout/migration |
| Платформа или cross-team изменение | RFC + context/container diagrams + ownership + adoption plan |
| Неясный домен | Discovery model / EventStorming до component design |

Не создавай большой пакет документов только потому, что пользователь сказал «архитектура».

## 1. Контекст и evidence baseline

Если доступны repo/docs, найди:

- текущие deployment units и service boundaries;
- публичные API/events и их consumers;
- schemas, migrations, partition/index choices;
- critical paths, queues, caches и third-party dependencies;
- SLO/alerts/runbooks/deploy pipeline;
- team ownership и уже принятые ADR/RFC;
- ограничения platform/cloud/security/compliance.

Разделяй `Observed`, `Stated`, `Inferred`, `Unknown`. Не считай README доказательством runtime-поведения, если код/config противоречат ему.

## 2. Architecture drivers

Составь компактную таблицу:

| Driver | Target / constraint | Почему важен | Как проверим |
|---|---|---|---|
| Business outcome | … | … | product metric |
| Peak workload | … | … | load test / forecast |
| Latency | p95/p99 per flow | … | client/server SLI |
| Availability/durability | … | … | SLO, fault test |
| Consistency invariant | … | … | concurrency test |
| Privacy/security | … | … | threat/privacy review |
| Cost/team/time | … | … | budget, delivery milestone |

Drivers должны конфликтовать достаточно, чтобы требовать решения. «Scalable, reliable, secure» без target не является driver.

## 3. System context и domain boundaries

Определи actors, внешние системы, trust boundaries, data ownership и critical business flows.

Используй EventStorming, когда:

- доменные события и границы ответственности неясны;
- процесс пересекает много команд/агрегатов;
- сложно определить consistency boundary;
- текущая архитектура повторяет организационную путаницу.

Минимальная последовательность EventStorming:

1. Domain events в бизнес-времени.
2. Commands и actors, вызывающие события.
3. Policies/automation и внешние системы.
4. Aggregates/invariants.
5. Hotspots и ownership boundaries.

Не применяй EventStorming к простому stateless utility или уже ясному data pipeline.

## 4. Контракты до компонентов

Зафиксируй:

- API commands/queries и error semantics;
- domain events: producer, schema, ordering key, delivery semantics;
- core entities и lifecycle;
- invariants и authoritative owner;
- compatibility/versioning policy;
- idempotency key и dedupe window там, где возможны повторы.

Контракт должен быть описан на уровне, достаточном для независимой реализации producer/consumer, но не превращаться в полный OpenAPI/DDL без запроса.

## 5. Варианты и decision record

Для необратимого решения сравни минимум два жизнеспособных варианта. Не добавляй заведомо слабый strawman.

### ADR mini-template

```markdown
## Decision: <название>
Status: proposed | accepted | superseded

Context: <drivers и ограничения>
Decision: <что выбираем>
Alternatives: <реальные альтернативы>
Consequences: <плюсы, цена, новые риски>
Revisit when: <измеримый сигнал>
```

Оцени варианты по drivers, а не по популярности. Отдельно отмечай reversibility и migration cost.

## 6. High-level design и critical flows

Покажи:

- context: actors/external systems/trust boundaries;
- containers/services: ответственность и source of truth;
- data flow: один critical write и один critical read;
- async path, retries и failure handling;
- deployment/failure boundaries.

Для каждого stateful компонента укажи:

| Вопрос | Ответ |
|---|---|
| Какие данные хранит? | … |
| Почему он source/projection/cache/log? | … |
| Как partition/replicate? | … |
| Какая consistency/freshness? | … |
| Как backup/restore/rebuild? | … |
| Кто владелец и кто меняет schema? | … |

## 7. Deep dives

Выбирай по risk × irreversibility × uncertainty. Типовые темы:

- data model, partitioning, indexing, transactions;
- concurrency and ordering;
- workload isolation, quotas, fairness;
- cache/fanout/index freshness;
- multi-region placement and failover;
- overload/backpressure/load shedding;
- security/privacy/abuse;
- rollout, migration, dual-read/write, backfill;
- cost model и capacity.

## 8. Production readiness

Перед завершением проверь [reliability-security-operations.md](reliability-security-operations.md):

- user-centric SLI/SLO и error budget;
- dependency timeouts/retries/circuit/load shedding;
- failure domains, blast radius, degraded mode;
- observability и actionable alerts;
- safe deploy, rollback и data compatibility;
- RPO/RTO, backup restore test, regional failure;
- authn/authz, encryption, secrets, privacy and abuse;
- capacity limit, cost guardrail и scaling signal.

## 9. Migration and delivery plan

Если есть существующая система, HLD без перехода неполон.

Для каждого предлагаемого этапа укажи наблюдаемый результат либо конкретный снимаемый риск/зависимость, способ проверки и оставшуюся часть исходного сценария. Этап без самостоятельного пользовательского эффекта обозначай как **подготовительный** и связывай с шагом, на котором сценарий заработает. Например, adapter с разбором события, но без runtime-подключения и изменения проекции — подготовительный этап; его проверка не доказывает применение бизнес-данных. Такой этап допустим, если его выделение обосновано, но не означает завершения исходной задачи. Этап без понятной пользы или необходимой зависимости объедини с полезным шагом либо убери.

### Безопасная последовательность

1. Добавить observability и сравнимую baseline-метрику.
2. Ввести backward-compatible contract/schema.
3. Выполнить shadow traffic или dual-read для проверки.
4. Backfill с rate limit, checkpoints и reconciliation.
5. Canary по tenant/region/percentage.
6. Иметь kill switch и проверенный rollback.
7. Переключить source of truth только после invariants/reconciliation.
8. Удалить старый путь после observation window.

Dual-write требует явного решения проблемы partial success; сам по себе он не является стратегией консистентности.

## 10. Validation plan

Свяжи каждый driver с проверкой:

| Driver | Проверка |
|---|---|
| Throughput/latency | load + stress + soak test с реалистичным skew |
| Correctness | property/concurrency/invariant tests |
| Failure tolerance | dependency fault injection / game day |
| Recovery | restore/failover drill с измерением RPO/RTO |
| Deploy safety | canary + automated rollback threshold |
| Security/privacy | threat model, abuse cases, access review, data flow map |
| Cost | per-request/per-tenant unit economics и budget alert |

## Done criteria

Архитектура готова к обсуждению, когда:

- scope и open questions видимы;
- решения трассируются к drivers;
- critical flows и invariants однозначны;
- alternatives/trade-offs/revisit signals зафиксированы;
- failure, operations и migration не оставлены «на потом»;
- есть способ доказать ключевые утверждения тестом или метрикой;
- ownership следующего шага понятен.

Не называй RFC «утверждённым», если пользователь не сообщил о реальном согласовании.
