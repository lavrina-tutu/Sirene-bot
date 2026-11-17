# Requirements and Back-of-the-Envelope Estimation

Загружай этот файл, когда надо собрать требования, оценить capacity или проверить, оправдано ли масштабное решение.

## Design brief

```markdown
Goal: <какой outcome создаёт система>
Actors: <кто вызывает систему и кто её эксплуатирует>
Core flows: <2–3 обязательных сценария>
Out of scope: <что сознательно исключено>
Scale: <DAU/tenants/devices, avg/peak RPS, data volume>
Quality attributes: <latency percentile, availability, durability, consistency>
Constraints: <stack, budget, team, timeline, regions, compliance>
Assumptions: <неподтверждённые величины>
Success evidence: <метрики/тесты>
```

## Какие вопросы действительно архитектурные

Уточняй параметр, если его изменение способно поменять storage, topology, consistency, partitioning, protocol или failure strategy.

Примеры высокоценностных вопросов:

- Нагрузка read-heavy или write-heavy? Насколько bursty и skewed?
- Какой exact critical flow и его p95/p99 latency?
- Какие данные нельзя потерять, продублировать или показать устаревшими?
- Есть ли hot tenant/key, global audience или data residency?
- Допустима ли asynchronous completion и как пользователь узнаёт статус?
- Какой failure важнее выдержать: instance, zone, region, dependency, operator?

Не трать обсуждение на вкусовые вопросы о языке программирования, если он не ограничивает задачу.

## Workload model

Пусть:

- `U` — daily active users/tenants/devices;
- `R` — read actions на активного пользователя в день;
- `W` — write actions на активного пользователя в день;
- `Pr`, `Pw` — средний payload read/write в bytes;
- `K` — peak factor к среднему;
- `D` — retention в днях;
- `F` — replication factor;
- `H` — headroom (>1).

Тогда:

```text
average_read_rps  = U × R / 86_400
average_write_rps = U × W / 86_400
peak_read_rps     = average_read_rps × K × H
peak_write_rps    = average_write_rps × K × H

read_egress_Bps   = peak_read_rps × Pr
write_ingress_Bps = peak_write_rps × Pw

raw_storage       = U × W × Pw × D
physical_storage  = raw_storage × F × H
```

Это нижняя оценка: indexes, metadata, object overhead, WAL/log, tombstones, compaction, backups и temporary headroom считаются отдельно.

## Availability math

Для availability target `A%` допустимая доля плохих событий/времени:

```text
error_budget_fraction = 1 - A / 100
allowed_bad_time      = window_seconds × error_budget_fraction
```

В реальной SLO лучше считать долю успешных good events, а не только downtime. Обязательно укажи measurement window, eligible events и exclusions.

Ориентир для года из 365 дней:

| Target | Допустимое bad time / год |
|---:|---:|
| 99% | ~3.65 дня |
| 99.9% | ~8 ч 46 мин |
| 99.95% | ~4 ч 23 мин |
| 99.99% | ~52 мин 34 с |
| 99.999% | ~5 мин 15 с |

Не проектируй «пять девяток» без product need: цена и операционная сложность растут нелинейно.

## Deterministic helper

Используй скрипт:

```bash
python3 scripts/estimate_capacity.py \
  --dau 10000000 \
  --reads-per-user-day 20 \
  --writes-per-user-day 2 \
  --read-bytes 2000 \
  --write-bytes 1000 \
  --retention-days 365 \
  --peak-factor 4 \
  --replication-factor 3 \
  --headroom 1.3 \
  --availability 99.99
```

По умолчанию вывод — Markdown; `--format json` удобен для дальнейшей автоматизации. Скрипт не оценивает server count: для него нужен измеренный throughput конкретного workload, а не универсальная цифра.

## Оценка server/partition count

Используй только benchmark конкретного workload:

```text
required_units = ceil(peak_demand / tested_safe_capacity_per_unit)
provisioned    = required_units + failure_headroom
```

`tested_safe_capacity` должна быть получена при реалистичных payload, indexes, cache hit ratio, consistency, skew и tail latency. Не используй vendor maximum как safe capacity.

Для partitions учитывай максимум из storage, throughput и operational bounds:

```text
partitions = max(
  ceil(total_data / safe_data_per_partition),
  ceil(peak_writes / safe_writes_per_partition),
  minimum_failure_or_parallelism_partitions
)
```

Затем проверь, что partition key не создаёт один горячий shard при монотонном времени, celebrity tenant или low-cardinality prefix.

## Read/write amplification

Считай не только входной запрос:

- write может породить replicas, indexes, WAL, CDC, cache invalidation, search projection;
- read может стать cache miss + DB read + fanout/scatter-gather;
- retry умножает load во время отказа;
- backfill/replay конкурирует с online traffic;
- fanout-on-write умножает записи на число получателей;
- fanout-on-read умножает merge work на число источников.

Покажи amplification factor хотя бы диапазоном.

## Uncertainty and sensitivity

Не маскируй неизвестность точными числами.

1. Дай base case.
2. Назови наиболее неопределённые 1–2 параметра.
3. Посчитай 10× или high/low scenario только для них.
4. Покажи design threshold: «до X остаёмся на одной БД; после Y нужен partitioning/async path».

## Units and rounding

- Явно указывай decimal (`MB = 10^6`) или binary (`MiB = 2^20`) units.
- Для order-of-magnitude округляй вверх и показывай формулу одной строкой.
- Не смешивай events/s, requests/s и DB ops/s.
- Не смешивай payload size с physical storage size.
- Отдельно показывай average, peak и recovery/backfill load.

## Compact estimation output

```markdown
### Assumptions
- …

### Envelope
- Average / peak reads: … / … RPS
- Average / peak writes: … / … RPS
- Peak ingress / egress: … / …
- Raw / replicated storage at retention: … / …
- Error budget: … per 30 days

### Architectural consequences
- Because …, choose …
- Avoid … until metric … exceeds …

### Sensitivity
- If X grows 10×, component Y becomes the first bottleneck.
```
