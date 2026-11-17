# Research Sources and Attribution

Исследовано 31 августа 2026 года. Проверяй свежесть перед утверждениями о текущих продуктах, цифрах или company practices.

Этот skill содержит оригинальный синтез и не воспроизводит главы книг, статьи или чужие SKILL.md. Публичные skills изучались как UX/structure references; их текст и обязательные формулировки не копировались.

## Skill format and export

- [OpenAI — Build skills](https://learn.chatgpt.com/docs/build-skills): skill directory, required `SKILL.md`, progressive disclosure, optional `scripts/`, `references/`, `assets/`, `agents/openai.yaml`, implicit/explicit invocation and distribution guidance.
- [OpenAI API — Create a skill](https://developers.openai.com/api/reference/python/resources/skills/methods/create): directory upload or a single ZIP file supported by the API.

Design consequence: root `SKILL.md` is a short router; mode-specific depth lives in references; the export ZIP contains one top-level skill folder.

## Alex Xu / ByteByteGo backbone

- [ByteByteGo — A Framework for System Design Interviews](https://bytebytego.com/courses/system-design-interview/a-framework-for-system-design-interviews): four-step interview process, collaboration, scope, high-level design, deep dive and wrap-up.
- [ByteByteGo — Don’t optimize prematurely](https://blog.bytebytego.com/p/system-design-interview-tip-dont): keep early HLD simple; delay unjustified optimizations until deep dive.
- [ByteByteGo — Step-by-step guide](https://blog.bytebytego.com/p/ep46-step-by-step-guide-on-system): concise restatement of the four-step framework.

Design consequence: architecture workflow preserves four distinct phases and a design checkpoint, but adds production reliability, security/privacy, operations, migration and evidence-based review.

## Google

- [Google Cloud Well-Architected Framework](https://docs.cloud.google.com/architecture/framework?hl=en): design for change, architecture documentation, simplicity, loose coupling, stateless architecture and cross-pillar review.
- [Google SRE — Service Level Objectives](https://sre.google/sre-book/service-level-objectives/): user-relevant SLIs/SLOs, percentiles, measurement clarity and error budgets.
- [Google SRE — Monitoring Distributed Systems](https://sre.google/sre-book/monitoring-distributed-systems/): latency, traffic, errors and saturation; reasons to monitor.
- [Google SRE — Production Services Best Practices](https://sre.google/sre-book/service-best-practices/): user-centric SLOs, error-budget policy and actionable monitoring.

## Amazon / AWS

- [Amazon Builders’ Library FAQ](https://aws.amazon.com/builders-library/faqs/): public articles describe context-dependent practices used at Amazon; no single universal right way.
- [AWS Well-Architected Reliability Pillar](https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/welcome.html): resilient architecture, change management and failure recovery.
- [AWS — Timeouts, retries and backoff with jitter](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/): remote-call failure handling and avoiding retry amplification.
- [AWS — Making retries safe with idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/): idempotency and retryable workflows.
- [AWS — Static stability using Availability Zones](https://aws.amazon.com/builders-library/static-stability-using-availability-zones/): continue operating with impaired dependencies using pre-positioned state.
- [AWS — Reducing scope of impact with cell-based architecture](https://docs.aws.amazon.com/wellarchitected/latest/reducing-scope-of-impact-with-cell-based-architecture/faq.html): cell and shuffle-sharding relationship for blast-radius reduction.
- [AWS Well-Architected — Control and limit retry calls](https://docs.aws.amazon.com/wellarchitected/2023-04-10/framework/rel_mitigate_interaction_failure_limit_retries.html): bounded retries, exponential backoff, jitter and idempotency.

## Apple

- [Apple Developer — Integrate privacy into your development process](https://developer.apple.com/videos/play/wwdc2025/246/): privacy across planning, design, client-server development, testing and deployment; data minimization, on-device processing, transparency/control.
- [Apple Developer — Reduce network delays for your app](https://developer.apple.com/videos/play/wwdc2021/10239/): account for network round trips and modern transport behavior in responsive client design.
- [FoundationDB — Technical overview](https://apple.github.io/foundationdb/technical-overview.html): architecture, transactions, performance, fault tolerance, simulation/testing and explicit anti-features.
- [FoundationDB — Architecture](https://apple.github.io/foundationdb/architecture.html): decoupled heterogeneous roles and independent scaling of read/write paths.
- [FoundationDB — Anti-Features](https://apple.github.io/foundationdb/anti-features.html): minimal reliable core, layers, and deliberate exclusions.
- [FoundationDB — Fault Tolerance](https://apple.github.io/foundationdb/fault-tolerance.html): shared-nothing replication, correlated failure locality and simulation of failures.
- [FoundationDB — Transaction Manifesto](https://apple.github.io/foundationdb/transaction-manifesto.html): correctness/engineering value of transactions and explicit performance trade-offs.
- [FoundationDB — Known Limitations](https://apple.github.io/foundationdb/known-limitations.html): large/long transactions and system design constraints.

Research limitation: these sources do not constitute an Apple-wide architecture standard. The company lens is an inference from official product/privacy guidance and an Apple-hosted distributed database project.

## Yandex / YDB

- [Yandex Cloud platform architecture](https://yandex.cloud/en/docs/overview/architecture): platform layers, shared resources, scalability and multi-datacenter foundation.
- [YDB overview](https://ydb.tech/docs/en/concepts/): horizontally scalable, fault-tolerant distributed DB, strong/relaxable consistency, replication, partitioning and availability zones.
- [YDB — Selecting a primary key for maximum performance](https://ydb.tech/docs/en/dev/primary-key/row-oriented): access-pattern locality, evenly distributed load and monotonic-key hotspot risk.
- [YDB — Transactions](https://ydb.tech/docs/en/concepts/transactions): sharded/distributed transactions and their additional latency/resource cost.
- [YDB — Query execution and retries](https://ydb.tech/docs/en/concepts/query_execution/): transaction-level retry, optimistic conflicts and distributed execution.
- [YDB — Troubleshooting performance issues](https://ydb.tech/docs/en/troubleshooting/performance/): overloaded shards, split/merge/moves, resource, network and clock issues.

Research limitation: YDB and Yandex Cloud documents are concrete engineering references, not a company-wide Yandex architecture standard.

## Ozon Tech

- [Ozon Tech — Одна платформа, чтобы править всеми](https://habr.com/ru/companies/ozontech/articles/708274/): platform layers, conventions/standards and managing a very large service fleet. Counts in the article describe 2022 and must not be presented as current.
- [Ozon Tech — Адаптивная балансировка нагрузки](https://habr.com/ru/companies/ozontech/articles/558926/): reliability beyond basic replicas/clustering and adaptive client-side routing/load balancing.
- [Ozon Tech — Доводим распределённые действия до конца с Saga](https://habr.com/ru/companies/ozontech/articles/590709/): forward recovery, atomic/idempotent/repeatable steps, backoff and observable failed workflow state.

Research limitation: official company-authored Habr posts are practical case studies, not universal Ozon architecture policy.

## Public system-design skills reviewed

- [wondelai/skills — system-design](https://github.com/wondelai/skills/blob/main/system-design/SKILL.md): popular public skill centered on Alex Xu, estimation, building blocks and a quick diagnostic. [skills.sh snapshot](https://www.skills.sh/wondelai/skills/system-design) showed roughly 4.6K installs and a 2K-star repository during research; counts change.
- [kid-sid/claude-spellbook — system-design](https://github.com/kid-sid/claude-spellbook/blob/main/skills/system-design/skill.md): end-to-end architecture process, technology-selection matrices and concrete reliability patterns.
- [Dwsy/agent — system-design](https://github.com/Dwsy/agent/blob/main/skills/system-design/SKILL.md): EventStorming and progressive design-catalog artifacts. Useful as an optional domain-discovery mode, but too rigid as a universal workflow.
- [ML-SystemDesign/MLSystemDesign — review skill](https://github.com/ML-SystemDesign/MLSystemDesign/blob/main/skills/ml-system-design-review/SKILL.md): strong routing, evidence modes, impact-ranked findings and progressive references.
- [tylerpayne/system-design-skill](https://github.com/tylerpayne/system-design-skill/blob/main/plugins/system-design-skill/skills/system-design-interview/SKILL.md): interview-driven capture of requirements, architecture, API, data model, decisions and build plan into reusable artifacts.
- [mattpocock/skills — grill-me](https://github.com/mattpocock/skills/blob/main/skills/productivity/grill-me/SKILL.md): minimal entrypoint for a relentless interview that sharpens a plan or design.
- [MrAlias/codex-skills — grill-me](https://github.com/MrAlias/codex-skills/blob/main/grill-me/SKILL.md): one high-leverage question per turn, evidence-first questioning, explicit recommended default and a clear stopping summary.

Patterns retained in original form:

- precise multi-language trigger description;
- mode router and progressive disclosure;
- estimation helper rather than hand-wavy capacity;
- optional EventStorming for unclear domains, not an iron law;
- evidence-aware review rubric with severity and praise;
- output templates that scale from chat answer to RFC;
- explicit failure, operations, migration, security/privacy and company-lens checks.
- architecture-specific Architecture Drill loop with one question per turn, decision ledger, contradiction checks, hint ladder and done criteria.

Patterns intentionally rejected:

- always scoring every ordinary design;
- forcing Mermaid/EventStorming/file creation for all requests;
- prescribing microservices, caches, queues or sharding before a bottleneck;
- treating book-derived diagrams or technology lists as a complete architecture method;
- claiming public company practices are universal architecture standards.
