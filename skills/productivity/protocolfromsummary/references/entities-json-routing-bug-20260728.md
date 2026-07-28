# Инцидент: entities.json routing bug (2026-07-28)

## Встреча
`2026-07-28 11-30-00 OKR. Рассказ о логике ведения целей и KR в АИД`  
Участники: Цыба Леонид, Ткаченко Александр Владимирович

## Симптом
Встреча падала с ошибкой: `KeyError: 'vstrechi_nerazobrannoe'` в `route.py::_route_from_entity`.

## Два независимых дефекта

### Дефект 1: entity `okr` без блока `pfs`
Файл: `~/WorkVault/Registries/entities.json`, секция `"okr"` (строки 479–494)

Сущность `okr` содержала aliases (`"okr"`, `"окр"`, и др.) — alias `"okr"` совпал бы с именем
встречи. Но блок `pfs` отсутствовал, поэтому `_load_routes_from_registry()` пропустил её:
```python
pfs = entry.get("pfs")
if not pfs:
    continue  # okr пропускается здесь
```
Итог: `okr` не входит в ROUTES → name_match (шаг 2) не срабатывает → встреча падает в fallback.

### Дефект 2: entity `vstrechi_nerazobrannoe` отсутствует в entities.json
Файл: `~/WorkVault/Registries/entities.json` — сущности нет совсем.

`vstrechi_nerazobrannoe` — системный fallback-таргет, жёстко прописан в `route.py` (строка 169)
и `config.py` (строка 100). Без блока `pfs` в entities.json он не попадает в ROUTES → KeyError
при первом же обращении через fallback-ветку.

## Цепочка выполнения (почему именно этот fallback)

`route.py::resolve_route` шаг 3 (строки 163–169):
1. `_all_participants_aid(...)` → `False` (Цыба Леонид не из АиД или не резолвится)
2. `_has_pro_topic("OKR. Рассказ...")` → `False` (нет слов: `pmo`, `гильдия`, `лекци`, `управлени проект`, `адм.`)
3. → `return _route_from_entity("vstrechi_nerazobrannoe")` → **KeyError**

## Диагностика (воспроизведение)

```python
cd ~/USERTOOLS/ProtocolFromSummary && source .venv/bin/activate
python3 -c "
from protocolfromsummary.route import resolve_route
r = resolve_route(
    'OKR. Рассказ о логике ведения целей и KR в АИД',
    participants=['Цыба Леонид', 'Ткаченко Александр Владимирович'],
)
print(r)
"
# → KeyError: 'vstrechi_nerazobrannoe'
```

Быстрая проверка состояния ROUTES:
```python
from protocolfromsummary.config import ROUTES
for key in ["okr", "vstrechi_nerazobrannoe", "sink_aid", "vstrechi_pro"]:
    print(key, "→", "OK" if key in ROUTES else "MISSING!")
```

## Необходимые правки entities.json (не сделаны в рамках этой сессии)

### 1. Добавить `pfs` к `okr`
```json
"okr": {
  "kind": "project",
  "display_name": "OKR",
  "aliases": ["окр", "okr", "цели и ключевые результаты", "заполняем джиру",
               "собираем q2", "собираем q1", "выравнивание по целям", "okr-tool"],
  "pfs": {
    "page_id": "<РЕАЛЬНЫЙ page_id Confluence-страницы OKR-протоколов>",
    "tag": "OKR."
  },
  "parent": null,
  "folder": "Entities/okr"
}
```

### 2. Добавить `vstrechi_nerazobrannoe` (системный fallback)
```json
"vstrechi_nerazobrannoe": {
  "kind": "unknown",
  "display_name": "Встречи неразобранное",
  "aliases": [],
  "pfs": {
    "page_id": "508804852",
    "tag": null
  },
  "parent": null,
  "folder": null
}
```
page_id `508804852` — из `tests/test_entities_registry.py` строки 74, 101.

## Проверка после правки
```bash
cd ~/USERTOOLS/ProtocolFromSummary && source .venv/bin/activate
python -m pytest tests/test_entities_registry.py -q
# Обязательно: test_baseline_invariant_matches_pfs_routes
python -m pytest -q -m "not live_confluence"
```
