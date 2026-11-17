# Reliability, Security and Operations

Загружай этот файл для production-readiness, SLO, failure design, overload, DR, security/privacy, observability и rollout.

## Reliability starts with the user journey

Определи SLI на уровне поведения, важного пользователю, а не удобной внутренней метрики.

| User expectation | Возможный SLI |
|---|---|
| Запрос успешно завершён | good responses / eligible requests |
| Результат приходит быстро | fraction below latency threshold, usually p95/p99 context |
| Данные не потеряны | durable acknowledged writes / accepted writes |
| Projection свежая | fraction with lag below threshold |
| Job выполнен вовремя | jobs completed before deadline / accepted jobs |

SLO должен определить target, window, eligible events, measurement point и reaction policy. Error budget = разрешённая доля bad events; он помогает балансировать reliability и change velocity.

Не делай 100% целью по умолчанию. Это обычно дорого, не проверяемо и создаёт скрытую зависимость пользователей от недокументированного уровня сервиса.

## Four operational signals

Минимально наблюдай:

- latency — распределение, не только average;
- traffic — requests/events/bytes/connections;
- errors — user-visible и dependency failures;
- saturation — CPU/memory/IO/pool/queue/concurrency headroom.

Добавь domain correctness metrics: double charge, oversell, stale index, reconciliation mismatch, dropped event. Технически «зелёная» система может нарушать бизнес-инварианты.

## Failure model

Перед механизмами составь таблицу:

| Failure | Detection | Containment | User behavior | Recovery | Proof |
|---|---|---|---|---|---|
| instance/process | … | … | … | … | … |
| zone/rack/network | … | … | … | … | … |
| region/control plane | … | … | … | … | … |
| dependency slow/down | … | … | … | … | … |
| overload/retry storm | … | … | … | … | … |
| corrupt/partial data | … | … | … | … | … |
| bad deploy/schema | … | … | … | … | … |
| operator/credential abuse | … | … | … | … | … |

Availability claims должны указывать failure scope: «переживает потерю одного instance/zone» полезнее, чем «highly available».

## Dependency call contract

Для каждого remote call опиши:

1. End-to-end deadline и per-attempt timeout.
2. Какие errors retryable.
3. Где один владелец retry, чтобы слои не умножали попытки.
4. Bounded attempt/time budget.
5. Exponential backoff + jitter.
6. Idempotency/side-effect safety.
7. Concurrency limit/bulkhead.
8. Fallback/degraded behavior.
9. Metrics: timeout rate, attempts/request, dependency latency, rejected work.

Retry — это усилитель нагрузки. Не retry permission/config/validation errors. Не retry non-idempotent command без idempotency key или reconciliation.

Circuit breaker применяй, если fail-fast на систематически плохой зависимости уменьшает resource exhaustion. Учти state tuning, half-open probes и риск синхронного открытия всей fleet. Иногда concurrency limit + timeout + load shedding проще и предсказуемее.

## Overload and metastability

Главный принцип: выполнять bounded work и не принимать больше работы, чем система способна безопасно завершить.

- admission control и quotas на edge;
- per-tenant fairness, чтобы noisy neighbor не занял весь pool;
- concurrency limits перед scarce dependency;
- bounded queues и deadline-aware scheduling;
- backpressure producer-у;
- load shedding по приоритету;
- degrade optional features раньше critical path;
- separate live/replay/backfill capacity;
- autoscaling по leading signal, но не как единственная защита.

Queue без bound переносит outage в будущее. Cache fallback на source может превратить cache outage в database outage. Заранее определяй safe degraded mode.

## Isolation and blast radius

Используй:

- bulkheads/separate pools для независимых функций;
- tenant/region/cell boundaries;
- shuffle sharding или ограниченное пересечение ресурсов для multi-tenant isolation;
- dependency isolation;
- feature flags/kill switches;
- separate control and data planes;
- statically stable data plane: продолжает полезную работу при impaired dependency, используя уже имеющееся состояние.

Цена isolation — lower utilization, routing complexity и operational overhead. Выбирай boundary по expected failure and business impact.

## Idempotency and distributed workflows

Idempotency contract включает:

- key scope (user/tenant/operation);
- semantic equality payload;
- retention/dedupe window;
- stored result or terminal state;
- behavior при concurrent duplicate;
- cleanup and abuse limits.

Для cross-service workflow выбирай между:

- orchestration saga — видимый coordinator/state, проще audit/recovery;
- choreography — loose publisher coupling, но сложнее global visibility;
- forward recovery — повторять шаги до known-good state;
- compensation — бизнес-действие, а не технический rollback;
- transactional outbox/inbox — убрать dual-write gap, принимая duplicate delivery.

Каждый шаг saga должен быть atomic, idempotent или безопасно повторяем с reconciliation. Сохраняй failure state и alert ownership.

## Disaster recovery

Определи:

- `RPO`: максимальная потеря данных во времени/событиях;
- `RTO`: время восстановления user journey;
- backup scope, frequency, encryption, immutability;
- restore procedure and ownership;
- failover/failback and split-brain protection;
- dependency/DNS/credentials readiness;
- test cadence.

Replication не заменяет backup: она быстро реплицирует ошибочное delete/corruption. Backup без проверенного restore — гипотеза.

## Observability and alerting

### Instrumentation

- metrics с bounded cardinality;
- structured logs с correlation/trace/request/idempotency IDs;
- distributed traces на critical flows;
- audit trail для privileged и business-critical actions;
- queue lag, replication lag, cache hit/miss, retry amplification;
- version/config/region/tenant dimensions, где это безопасно.

Не помещай secrets или unnecessary personal data в logs/traces.

### Alerts

Page только за user impact или imminent exhaustion, требующие немедленного действия. Остальное — ticket или diagnostic data. Предпочитай burn-rate/SLO alerts одиночным noisy thresholds.

Каждый alert должен иметь owner, severity, context, runbook, dashboard и clear stop condition.

## Safe change and rollback

- small, backward-compatible changes;
- expand → migrate → contract для schema/API;
- canary по небольшой failure boundary;
- health/SLO gates и automatic halt/rollback;
- feature flags и kill switch;
- immutable/versioned config and infrastructure;
- rollback test до production;
- shadow traffic or dark reads для risk reduction;
- reconciliation при data migration.

Code rollback не всегда откатывает data/schema/event. Если old code не понимает new state, нужен roll-forward или compatibility bridge.

## Security architecture

### Минимальный threat model

1. Assets: что защищаем?
2. Actors: user, admin, service, attacker, insider.
3. Trust boundaries and entry points.
4. Threats: spoofing, tampering, repudiation, disclosure, denial, privilege escalation, abuse/fraud.
5. Controls and residual risk.
6. Detection/response and ownership.

### Controls by layer

- strong identity, short-lived credentials, workload identity;
- centralized policy with least privilege;
- authz on every object/tenant boundary, not only gateway;
- encryption in transit/at rest and managed key lifecycle;
- secret rotation and no secrets in code/logs;
- input/schema validation and output encoding;
- rate/size/complexity limits;
- network segmentation and egress control;
- signed/audited admin actions;
- supply-chain/dependency controls;
- deletion/retention enforcement.

Security control должен иметь failure behavior: fail-open или fail-closed — осознанное решение по risk.

## Privacy by design

Применяй четыре вопроса:

1. Можно ли не собирать данные или уменьшить granularity/retention?
2. Можно ли обработать их on-device/at edge вместо централизованной передачи?
3. Понимает ли пользователь purpose и имеет ли meaningful control?
4. Как ограничены access, correlation, export, deletion и secondary use?

Выполни data-flow map: collect → transmit → store → derive/share → retain/delete. Для каждого шага укажи purpose, lawful/contractual basis где применимо, owner и protection. Privacy — архитектурное ограничение, не только UI consent.

## Abuse and economic attacks

Проверь:

- credential stuffing, scraping, spam, fake accounts;
- expensive query/payload amplification;
- webhook/event replay;
- tenant enumeration and side channels;
- resource exhaustion and cost explosion;
- moderation/fraud false positives and appeal path.

Защита: quotas, rate/complexity limits, proof/challenge where appropriate, anomaly detection, staged trust, audit и manual recovery. Не раскрывай abuse-sensitive thresholds без необходимости.

## Cost and sustainability

Считай unit economics:

- cost per request/job/GB/tenant;
- steady vs peak vs recovery cost;
- storage replication, indexes, logs and backup multipliers;
- cross-region/network egress;
- idle redundancy for SLO;
- managed-service premium vs team operational cost.

Добавь budget alert и scaling guardrail. Самая дешёвая архитектура, которая регулярно нарушает SLO, не оптимальна; самая надёжная без product need тоже.

## Validation and game days

Проверяй не только component death:

- slow dependency и partial responses;
- correlated zone/network failure;
- retry storm and cache cold start;
- queue backlog/replay;
- expired credentials/control-plane outage;
- bad schema/config deploy;
- restore/failover/failback;
- hot tenant/key and skew;
- operator mistakes.

Для эксперимента зафиксируй hypothesis, blast radius, abort condition, observers, expected SLI и remediation owner.

## Production-readiness summary

```markdown
SLO/SLI: …
Capacity limit and leading saturation signal: …
Failure domains tolerated: …
Degraded mode: …
Dependency timeout/retry/idempotency: …
Backpressure/load shedding/isolation: …
RPO/RTO and last restore/failover proof: …
Security/privacy/abuse controls: …
Canary/rollback/data compatibility: …
Top residual risk and owner: …
```
