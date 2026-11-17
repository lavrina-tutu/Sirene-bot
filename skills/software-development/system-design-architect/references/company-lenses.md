# Public Engineering Lenses: Google, Amazon, Apple, Yandex, Ozon Tech

Используй этот файл для cross-check дизайна через публичные инженерные практики разных компаний.

## Важная граница

Это не официальные company-wide standards и не утверждение, что все команды компании проектируют одинаково. Это практические линзы, синтезированные из публичных официальных документов и инженерных публикаций. Всегда отделяй:

- `Public practice`: что прямо следует из источника;
- `Design inference`: как применить идею к текущей задаче;
- `Unverified generalization`: не выдавать за факт.

Ссылки и дата исследования — в [sources.md](sources.md).

## Google lens

### Публичные акценты

- Начинать reliability с поведения, важного пользователю: SLI/SLO, измеренные у корректной границы, включая client-side там, где server metric не отражает опыт.
- Использовать percentiles и tail behavior, а не только averages.
- Балансировать темп изменений и надёжность через error budget.
- Наблюдать latency, traffic, errors и saturation; alerts должны вести к действию.
- Проектировать для изменений, документировать архитектуру и сокращать непонятную сложность.
- Loose coupling и stateless compute повышают независимость изменений, scale-out и restartability, если state вынесен в подходящее хранилище.
- Рассматривать operations, security/privacy, reliability, performance, cost и sustainability как взаимосвязанные pillars.

### Вопросы к дизайну

1. Какой user journey имеет SLO и где он измеряется?
2. Как error budget влияет на rollout и prioritization?
3. Что происходит с p99 при skew, cache miss или dependency slowdown?
4. Какие компоненты stateful и почему? Можно ли stateless scale-out без потери correctness?
5. Документированы ли data flow, failure domains и ownership?
6. Как дизайн меняется малыми безопасными шагами?

### Типичная ошибка

«У нас 99.99% uptime» без eligible events, окна и реакции — не SLO. «Средняя latency 30 ms» скрывает tail.

## Amazon / AWS lens

### Публичные акценты

- Well-Architected оценивает operational excellence, security, reliability, performance efficiency, cost optimization и sustainability.
- Любой remote call имеет timeout; retry ограничен, выполняется на правильном слое, использует exponential backoff и jitter.
- Retry безопасен только при idempotent effect или другом доказуемом recovery contract.
- Система должна избегать превращения малой доли ошибок в полный outage: throttling, bounded work, backpressure, load shedding и dependency isolation.
- Static stability: полезный data path продолжает работать, когда dependency/control plane impaired, используя заранее доступное состояние.
- Cells/shuffle sharding/bulkheads уменьшают blast radius и noisy-neighbor impact.
- Safe change — часть architecture: automation, canary, tested rollback, backward compatibility.
- Нет единственного правильного паттерна вне контекста; публичные практики требуют адаптации к constraints.

### Вопросы к дизайну

1. Где общий end-to-end deadline и кто владеет retry?
2. Что произойдёт при retry storm или backlog после восстановления?
3. Все ли side effects idempotent? Где хранится idempotency result?
4. Может ли data plane работать без control plane/dependency?
5. Как ограничен blast radius одного tenant/region/dependency?
6. Как deployment автоматически остановится или откатится?

### Типичная ошибка

Retry на каждом уровне стека создаёт multiplicative load. Бесконечная queue откладывает, но не решает overload.

## Apple lens

Apple публикует меньше единого cloud-architecture guidance, поэтому линза объединяет официальные privacy/product principles и open-source FoundationDB engineering.

### Product and privacy practice

- Начинать с purpose и ценности; простота часто требует сознательно не добавлять функцию.
- Давать пользователю agency и безопасное восстановление после разрушительных действий.
- Privacy-by-design: data minimization, on-device processing where possible, transparency/control и security.
- Учитывать network round trips, client responsiveness, energy/thermal cost и degraded connectivity как часть experience.

### FoundationDB distributed-systems practice

- Делать core минимальным и сильным; специализированные возможности выносить в composable layers. Явно называть anti-features и границы продукта.
- Разделять heterogeneous roles и масштабировать read/write paths независимо.
- Не отказываться от strong transactions автоматически: оценивать инженерную простоту/correctness против latency/cost.
- Держать transactions короткими и небольшими; large/long work дробить и строить reconciliation at higher layer.
- Shared-nothing replication учитывает correlated failure locality (rack/datacenter), не только число copies.
- Проверять correctness и fault tolerance simulation/failure testing, включая необычные interleavings и degraded hardware/network.

### Вопросы к дизайну

1. Какую функцию/данные можно убрать без потери purpose?
2. Какие данные можно обработать локально и не централизовать?
3. Где core boundary, а где layer/projection? Какие anti-features осознанны?
4. Как разделены read/write scaling и stateful roles?
5. Как correctness проверяется при concurrency и correlated failures?
6. Как ведёт себя client при latency, offline/reconnect и partial completion?

### Типичная ошибка

«Eventual consistency всегда нужна для масштаба» и «больше функций в core лучше» — обе позиции требуют доказательства, а не считаются default.

## Yandex / YDB lens

### Публичные акценты

- YDB демонстрирует, что horizontal scale, automatic partitioning/replication и strong consistency могут сочетаться, но цена зависит от transaction/partition scope.
- Primary/partition key определяет распределение нагрузки и locality access patterns.
- Monotonically increasing prefix и low-cardinality key создают hot partition; hash/composite key может распределить writes, но влияет на range queries.
- Single-shard operation существенно проще и быстрее distributed transaction; cross-shard scope должен быть осознанным.
- Distributed transactions стоят больше latency/resources; application logic должна уменьшать participants/conflicts, когда это не ломает invariant.
- Retry выполняется на уровне всей transaction, а не отдельного query; optimistic conflicts ожидаемы и должны быть bounded/observable.
- Failure tolerance рассматривает node/rack/availability-zone/network, а troubleshooting — overloaded shards, split/merge/moves, disk/CPU/memory/network и clock drift.

### Вопросы к дизайну

1. Какие access patterns обслуживает prefix key?
2. Может ли один timestamp/tenant/key стать hot shard?
3. Какие invariants действительно требуют cross-shard transaction?
4. Можно ли co-locate aggregate, сохранив locality и balance?
5. Где transaction-level retry и как ограничен contention?
6. Как shard moves/splits и AZ failure проявятся в tail latency?

### Типичная ошибка

Автоматическое sharding не исправляет плохой key: новый «последний» range снова может принять весь write load.

## Ozon Tech lens

Публичные кейсы Ozon Tech отражают large-scale marketplace/platform context в момент публикации; конкретные цифры из старых статей не считать текущими.

### Публичные акценты

- При тысячах сервисов internal platform, conventions и paved roads сдерживают технологическую энтропию и переносят повторяющуюся инфраструктурную сложность из product teams.
- Платформа строится слоями: infrastructure/compute → shared services → libraries/frameworks → product services.
- Надёжность требует не только replicas и basic load balancing, но адаптации к degraded/slow endpoints и клиентской routing intelligence.
- Для distributed workflow применим forward recovery: persistent saga state, retry с backoff, observable failures.
- Saga steps должны быть atomic, idempotent или безопасно повторяемы; ошибки сохраняются и имеют owner.
- Простота и организационная применимость паттерна иногда важнее теоретически идеального distributed rollback.

### Вопросы к дизайну

1. Что должно быть convention/paved road, а где продуктовой команде нужна свобода?
2. Как service discovery/routing реагирует на slow instance, а не только hard-down?
3. Какие platform dependencies становятся shared blast radius?
4. Где хранится состояние saga и кто получает alert о застрявшем шаге?
5. Какие действия atomic/idempotent и как обрабатывается duplicate execution?
6. Как backoff, deadline и manual recovery отражены в UX/status?

### Типичная ошибка

Стандартизация без escape hatch блокирует продукт; свобода без conventions превращает fleet в неоперабельный набор уникальных решений.

## Cross-company synthesis

| Универсальный вопрос | Google | Amazon | Apple | Yandex/YDB | Ozon Tech |
|---|---|---|---|---|---|
| Что ценит пользователь? | user-centric SLO | customer impact | purpose/agency/privacy | predictable correctness/latency | marketplace/product flow |
| Как контролируется failure? | error budget/monitoring | static stability/isolation | minimal core/fault testing | replicated shards/AZ scope | adaptive routing/forward recovery |
| Как контролируется scale? | stateless/decoupled | bounded work/cells | decoupled roles/layers | partition key/local transactions | platform standards/shared services |
| Как контролируется change? | small changes/docs | automated safe rollback | simplicity/clear boundaries | retry/rebalance observability | conventions/paved roads |
| Главный anti-pattern | targetless reliability | retry/queue amplification | feature/data excess | hot key/cross-shard by accident | fleet entropy/non-idempotent saga |

Не пытайся одновременно оптимизировать дизайн под все линзы. Выбери 2–3, которые соответствуют architecture drivers пользователя, и объясни выбор.
