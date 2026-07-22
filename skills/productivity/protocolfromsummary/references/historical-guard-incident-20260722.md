# Инцидент 22.07.2026: массовая публикация 42 исторических встреч

## Хронология

- **11:11** — cron `pfs_batch` (`a6e62d06249f`) опубликовал 42 встречи Sep 2025 – Jun 2026 в Confluence.
- **Причина**: расширение aliases в `entities.json` сделало эти встречи видимыми для ROUTES;
  при этом они не были в реестре PFS → `process_pending` обработал как новые.
- **Обнаружение**: canary-тест `test_baseline_invariant_matches_pfs_routes` в `test_entities_registry.py`
  упал, сигнализируя о расхождении aliases между `entities.json` и `config.py`.

## Устранение

### Шаг 1 — бэкап реестра
```bash
cp /home/tkachenkoav/WorkVault/ProtocolFromSummary/_registry.json \
   /home/tkachenkoav/WorkVault/ProtocolFromSummary/_registry.json.bak-20260722-fix
```

### Шаг 2 — пометка пострадавших записей
Критерий: `published_at` начинается с `2026-07-22`, но `meeting_id` НЕ начинается с `2026-07-22`.

```python
import json, os

registry_path = '/home/tkachenkoav/WorkVault/ProtocolFromSummary/_registry.json'
with open(registry_path) as f:
    data = json.load(f)

patched = 0
for k, v in data['entries'].items():
    if (v.get('published_at') or '').startswith('2026-07-22') and not k.startswith('2026-07-22'):
        if not v.get('historical_no_reload'):
            v['historical_no_reload'] = True
            patched += 1

tmp_path = registry_path + '.tmp'
with open(tmp_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
os.replace(tmp_path, registry_path)
print(f'Помечено: {patched}')  # → 42
```

### Шаг 3 — CUTOVER_DATE guard в pipeline.py

В `pipeline.py`, после блока `from .config import (...)`:
```python
# §11.7 — встречи старше этой даты не публикуются автоматически через run-pending.
CUTOVER_DATE = date(2026, 7, 10)
```

В `process_pending`, заменить строку `pending_new = [...]`:
```python
pending_new = [
    (p, s) for p, s in parsed
    if registry.get(s.meeting_id) is None
    and s.meeting_date >= CUTOVER_DATE
]
historical_skipped = [(p, s) for p, s in parsed if registry.get(s.meeting_id) is None and s.meeting_date < CUTOVER_DATE]
if historical_skipped:
    log.info("process_pending: пропущено %d исторических встреч (до %s) — historical guard", len(historical_skipped), CUTOVER_DATE)
```

### Шаг 4 — исправление тестов
Все даты в `test_process_pending.py` поднять до >= CUTOVER_DATE (2026-07-10).
Файлы вида `2026-07-01` → `2026-07-22`, `2026-07-02` → `2026-07-23`, `2026-07-03` → `2026-07-24`.

## Итог dry-run после исправления

```
15:04:35 INFO process_pending: пропущено 197 исторических встреч (до 2026-07-10) — historical guard
15:04:35 INFO process_pending: новых встреч не найдено (575 файлов, все уже в реестре)
published: 0
```

## Масштаб

| Метрика | Значение |
|---------|---------|
| Незапланированно опубликовано | 42 встречи |
| Период встреч | Sep 2025 – Jun 2026 |
| Было с `historical_no_reload` до инцидента | 307 |
| Стало после исправления | 349 |
| Guard пропускает при dry-run | 197 встреч |
