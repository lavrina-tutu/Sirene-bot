# Components and Trade-offs

Загружай этот файл при выборе architecture style, storage, cache, messaging, partitioning, consistency или multi-region. Не считай таблицы автоматическим решателем: access patterns и invariants главнее категории продукта.

## Формула решения

Для каждого значимого компонента заполни одну строку:

| Need / invariant | Workload | Choice | Alternative | Cost / risk | Revisit signal |
|---|---|---|---|---|---|
| … | … | … | … | … | … |

Если `Need` пуст, компонент, вероятно, преждевременный.

## Modular monolith vs services

### Начинай с modular monolith, когда

- одна команда и один release cadence;
- границы домена ещё меняются;
- общий ACID boundary заметно упрощает correctness;
- нагрузка компонентов сходна;
- independent deployment не окупает network/ops overhead.

### Выделяй service, когда есть конкретная граница

- отдельный owner и release cadence;
- radically different scale/resource profile;
- security/compliance/isolation boundary;
- failure isolation или blast-radius benefit;
- стабильный контракт и bounded context;
- независимая эволюция важнее распределённой сложности.

Микросервисы не устраняют coupling; они делают его сетевым и операционным. Проверь ownership, API compatibility, data ownership, tracing, retries и incident coordination.

## Synchronous vs asynchronous interaction

| Выбирай sync, когда | Выбирай async, когда |
|---|---|
| Caller нуждается в ответе сейчас | Completion может быть отложен |
| Короткая цепочка и bounded latency | Нужно сгладить bursts или decouple rates |
| Ошибка должна быть видна пользователю сразу | Нужны fanout, replay, pipeline, background work |
| Strong read-after-write по одному пути | Eventual projection приемлема |

Для sync зафиксируй deadline propagation, timeout, retry ownership и degradation. Для async — delivery semantics, ordering key, dedupe/idempotency, retry/DLQ, backlog SLO и schema evolution.

Не превращай sync call в async только добавлением queue, если пользователь всё равно блокируется до результата.

## API styles

| Style | Сильная сторона | Цена / риск |
|---|---|---|
| REST/HTTP | простота, ubiquitous tooling, cache semantics | over/under-fetching, versioning discipline |
| RPC | typed contracts, efficient internal calls | tighter coupling, deadline/retry discipline |
| GraphQL | client-shaped reads, aggregation | resolver fanout/N+1, auth/cost control |
| WebSocket | bidirectional realtime | connection ownership, backpressure, reconnect/state |
| Webhook | cross-system push | retries, signatures, replay, receiver availability |
| Events | decoupling and multiple consumers | eventual consistency, schema/order/duplication |

Контракт включает errors, idempotency, pagination, rate limits и compatibility, а не только happy-path fields.

## Storage selection by access pattern

| Потребность | Подходящий класс | Главный вопрос |
|---|---|---|
| Multi-row invariants, joins, evolving queries | Relational/transactional DB | Как масштабировать writes и сохранить constraints? |
| Key-based low-latency access at scale | Distributed key-value | Какой partition key и consistency? |
| Flexible aggregate/document access | Document store | Не появятся ли cross-document invariants/joins? |
| Wide sparse/time-series events | Wide-column/time-series | Как распределить time/tenant hotspots и retention? |
| Append/replay/change streams | Durable log | Ordering/retention/consumer lag? |
| Full-text/filter/ranking | Search index | Где source of truth и какая freshness? |
| Large immutable blobs | Object storage | Metadata, multipart upload, lifecycle, CDN? |
| Relationship traversals | Graph DB или indexed adjacency model | Реально ли traversal доминирует над simpler model? |

«SQL или NoSQL?» — недостаточный вопрос. Сначала выпиши queries, write invariants, data lifecycle, scale и failure semantics.

## Source of truth, projections and caches

- `Source of truth` принимает authoritative writes и восстанавливает производные данные.
- `Projection/read model` оптимизирован под конкретный query и может быть rebuilt/reconciled.
- `Cache` допускает eviction и потерю; correctness не должна зависеть от его долговечности.
- `Log` может быть source of truth только если retention, schema evolution, compaction и replay действительно поддерживают это обещание.

Для каждого duplicate store опиши propagation, lag SLI, reconciliation и rebuild path.

## Техническое состояние: отдельное хранилище или метаданные проекции

Если техническое состояние обслуживает изменение существующей бизнес-проекции, сравни оба варианта до добавления нового хранилища. Нужность долговечной дедупликации сама по себе не определяет место её хранения.

| Критерий | Метаданные существующей проекции | Отдельный ledger/inbox |
|---|---|---|
| Владелец и назначение | Один владелец, состояние относится к этой проекции | Самостоятельный журнал приёма/обработки, несколько результатов или иной lifecycle |
| Атомарность | Бизнес-поля и маркер применения меняются в одной транзакции | В одной БД возможна общая транзакция; для разных хранилищ нужен явный протокол согласования |
| Retention и rebuild | Удаление/пересборка проекции должно сохранять требуемую защиту от повторов | Независимый срок хранения, история обработки и восстановление могут оправдать отдельность |
| Цена изменения | Меньше сущностей, но технические поля связываются со схемой проекции | Дополнительные схема, очистка, доступ и эксплуатация; оправдывай их требованием |

Это сравнение альтернатив, не запрет отдельных ledger/inbox. Отдельная таблица также может находиться в той же транзакционной БД; не приравнивай её автоматически к отдельному сервису. Журнал решений `Decision ledger` в Architecture Drill относится к состоянию обсуждения, а не к хранению событий.

### Проверочный пример: удалить ledger, сохранив применение события

**Условия примера.** Consumer получает события at-least-once. Каждое содержит полный снимок полей одного агрегата, `event_id` и строго возрастающую `revision` в рамках этого агрегата; одна revision обозначает один неизменный снимок. Применение новой revision может заменить пропущенные старые. Проекция и метаданные принадлежат одному владельцу в одной транзакционной БД, существуют столько, сколько нужна защита от повторов; независимый аудит всех событий и внешние побочные эффекты не требуются. Это условия примера, а не обязательные поля любого события.

**Задание.** Убрать отдельный ledger и предложить этапы доставки работающего consumer.

**Достаточное решение.** Хранить `last_applied_revision` в существующей проекции; `last_event_id` добавлять только при потребности диагностики/проверки идентичности. Последний event_id сам по себе не защищает от повторения более старого события. Consumer должен быть подключён к runtime. В одной транзакции атомарный conditional upsert либо блокировка с повторной проверкой revision применяет бизнес-поля и продвигает маркер только для новой revision; уникальный ключ агрегата защищает и конкурентное первое создание. Простого чтения revision перед безусловной записью недостаточно. Подтверждать обработку можно после commit либо установленного факта, что событие уже применено/перекрыто; ошибка транзакции оставляет событие для повтора. Если подтверждение означает продвижение offset потока, оно не должно пропускать ещё незафиксированные события.

Повторно проследи цепочку: доставка → вызов обработчика → проверка revision и изменение бизнес-полей в одной транзакции → commit → подтверждение. Сопоставь исходный результат, удалённый механизм и новое место каждой гарантии. Если ledger уже используется, включи перенос достоверных маркеров и переключение обработки без окна потери дедупликации в план перехода.

| Проверка | Ожидаемое поведение |
|---|---|
| Первое событие и более новая revision | Создают/обновляют бизнес-проекцию вместе с маркером |
| Повтор, старая revision после новой | Не меняют бизнес-данные; порядок снимков не откатывается |
| Конкурентные повторы/разные revisions, включая отсутствие строки | Уникальность и условная запись/блокировка сохраняют максимальную применённую revision и соответствующие ей поля |
| Сбой до commit, включая ошибку после записи бизнес-полей | Бизнес-поля и маркер откатываются вместе, повтор может применить событие |
| Сбой после commit до подтверждения | Повтор не применяет эффект второй раз |
| Выделен только adapter без runtime и записи | Явно подготовительный этап; применение события остаётся в следующем шаге |

**Граница применимости.** Для дельт, где нельзя пропускать промежуточные события, одного максимума revision недостаточно: нужен контроль пропусков и восстановление порядка. Для произвольных event_id без порядка последнее значение не обеспечивает дедупликацию истории. Если проекция удаляется/пересобирается раньше окончания окна повторов или требуется независимая история обработки, повторно сравни отдельный inbox/ledger с подходящими метаданными/tombstone. Если есть внешний эффект, локальная транзакция не делает его атомарным: отдельно определи доставку, идемпотентность и восстановление. При этих условиях не объявляй удаление ledger безопасным без подходящего механизма.

## Consistency by invariant

Не выбирай одну consistency для всей системы.

| Invariant / flow | Обычно нужная гарантия |
|---|---|
| Деньги, лимит, уникальная бронь | serializable/conditional write/single owner |
| User reads own update | read-your-writes/session consistency |
| Counter/likes/analytics | eventual, approximate или CRDT при обосновании |
| Ordered chat per conversation | per-key ordering, не global ordering |
| Search/feed projection | bounded staleness + freshness SLI |
| Config/control plane | strong publish semantics + statically stable data plane |

Выбирай smallest consistency scope: один key/partition/aggregate обычно дешевле global transaction.

## Concurrency control

| Механизм | Когда уместен | Риск |
|---|---|---|
| Optimistic compare-and-set/version | conflicts редки | retries под contention |
| Pessimistic lock | conflicts часты, short critical section | deadlocks, lock hold latency |
| Unique constraint/conditional insert | uniqueness/inventory claim | hotspot, error mapping |
| Single-writer/partition owner | ordered state machine | owner failover, hot partition |
| Idempotency key | repeated command | retention/window and result storage |
| Saga | cross-service workflow | intermediate states, compensation/recovery |
| Transactional outbox | atomic state+event publication | duplicate delivery, relay/backlog |

Never claim exactly-once end-to-end without defining the boundary. Обычно практическая цель — at-least-once delivery + idempotent effects + reconciliation.

## Replication

| Model | Benefit | Cost |
|---|---|---|
| Leader/followers | simple write ordering, read scale | leader bottleneck/failover, replica lag |
| Multi-leader | local writes in several regions | conflict detection/resolution |
| Quorum/leaderless | availability/tunable quorum | repair, read/write anomalies, complexity |
| Synchronous replicas | low RPO/strong durability | write latency and correlated failure risk |
| Asynchronous replicas | lower latency/geographic reach | non-zero RPO and stale reads |

Размещай replicas по independent failure domains; «три реплики» на одном power/network boundary не дают ожидаемой надёжности.

## Partitioning and sharding

Хороший partition key:

- присутствует в главных access patterns;
- имеет достаточную cardinality;
- распределяет текущую и будущую нагрузку;
- сохраняет нужную locality/ordering;
- ограничивает cross-partition transactions/scans;
- допускает rebalancing и tenant movement.

| Strategy | Benefit | Risk |
|---|---|---|
| Hash | ровное распределение | range queries/scatter-gather |
| Range | locality и range scans | monotonic/hot range |
| Directory/lookup | гибкое placement и movement | metadata availability/lookup |
| Composite/bucketed | баланс + locality | application complexity |

Проверь celebrity keys, timestamp-first keys, low-cardinality tenant tier и tenant size skew. Для hot key варианты: request coalescing, local/edge cache, key salting/buckets, split heavy tenant, precomputation или special path.

Не шардируй заранее без необходимости, но не принимай необратимый key/schema, который делает ожидаемый рост невозможным.

## Caching

Кеш нужен, если измеримый hot read/compute path можно ускорить ценой допустимой stale/eviction semantics.

| Pattern | Benefit | Risk |
|---|---|---|
| Cache-aside | простота, demand-driven | stale data, thundering herd |
| Read-through | единый load interface | dependency coupling |
| Write-through | cache updated on write | write latency, partial failures |
| Write-behind | high write throughput | durability/order/recovery complexity |
| CDN/edge | global latency/origin offload | invalidation, personalized/auth data |

Всегда опиши:

- key и scope;
- TTL/freshness guarantee;
- invalidation/update path;
- miss/stampede strategy (singleflight, jittered TTL, soft TTL);
- negative caching;
- behavior if cache is empty or unavailable;
- memory bound/eviction and hit-ratio SLI.

## Queues, logs and stream processing

| Need | Queue | Durable log |
|---|---|---|
| Work distribution, usually one worker handles item | сильный fit | возможно consumer group |
| Replay and independent consumers | limited | сильный fit |
| Per-key ordering/history | implementation-specific | partitioned log |
| Simple delayed retry/DLQ | часто удобно | отдельная retry topology |

Проектируй:

- partition/order key;
- producer idempotency/outbox;
- at-least-once consumer idempotency;
- retry policy и poison message handling;
- bounded backlog, age-of-oldest-message SLI;
- backpressure/load shedding;
- replay/backfill isolation от live traffic;
- schema compatibility and consumer rollout.

Queue скрывает overload только временно. Если arrival rate долго выше service rate, backlog растёт без границ.

## Search and secondary indexes

Search обычно projection, а не authoritative store.

- Определи indexing trigger: sync, outbox/CDC, batch.
- Назови freshness target и lag measurement.
- Продумай reindex/backfill без перегрузки source.
- Версионируй index/schema и переключай alias/reader safely.
- Для delete/privacy request обеспечь propagation и audit.

## Object/media path

Типовой flow:

1. Authorize and create metadata/upload session.
2. Client uploads directly to object storage by scoped signed URL.
3. Finalize with checksum/size/content-type validation.
4. Async scan/transcode/thumbnail.
5. Publish readiness state; serve through CDN.

Проверь orphan cleanup, multipart resume, duplicate finalize, malicious content, lifecycle tiers и metadata/source consistency.

## Multi-region

Сначала уточни цель: latency, regional resilience, sovereignty или capacity.

| Topology | Benefit | Cost |
|---|---|---|
| Single region, multi-zone | простота, zone resilience | regional outage |
| Active-passive region | clearer writes/failover | RTO, stale standby, failback |
| Read-local/write-home | low read latency | write latency, stale reads |
| Active-active by tenant/key | local writes, partitioned ownership | routing and tenant movement |
| Global multi-writer | maximum locality | hardest conflicts/consistency/operations |

Multi-region — не default. Опиши traffic routing, data placement, write authority, replication lag, failover trigger, split-brain prevention, failback и game day.

## Control plane and data plane

Разделяй их, если data path должен продолжать работу при недоступном control plane. Критическая идея — data plane использует заранее распространённую конфигурацию/lease и не требует control-plane round trip на каждый request. Опиши staleness window и safe default.

## Technology selection output

```markdown
Need: …
Required properties: …
Workload/evidence: …
Choice: <class, then product if needed>
Why now: …
Alternative rejected: … because …
Operational cost: …
Failure behavior: …
Revisit when metric/constraint: …
```

Технологический выбор без owner skills, managed/self-hosted constraint, migration path и operational burden неполон.
