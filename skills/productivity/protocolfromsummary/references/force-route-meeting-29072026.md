# Force-route встречи на нестандартную entity (29.07.2026)

## Контекст

Встреча **«OKR. Рассказ о логике ведения целей и KR в АИД»** (28.07.2026) была ошибочно
опубликована на странице `okr` (508804852 — «Встречи неразобранное») вместо `lenya_1on1`
(508804891 — «Леня 1-1»), так как Fireflies назвал её по теме, а не по собеседнику.

- meeting_id: `2026-07-28 11-30-00 OKR. Рассказ о логике ведения целей и KR в АИД`
- anchor: `pfsrow-eab7fc633be8`
- Участники: Цыба Леонид, Ткаченко Александр Владимирович

---

## Метод A: Прямой API-перенос (РЕКОМЕНДОВАН, проверен 29.07.2026)

Используй этот метод когда строка **уже опубликована** и нужен именно перенос (не republish).
Не требует запуска PFS pipeline и работает полностью через curl + Python.

### Шаг 1: GET обеих страниц

```bash
source ~/USERTOOLS/ConfluenceSync/.env

curl -s -H "Authorization: Bearer $CONFLUENCE_TOKEN" \
  "https://dom.tutu.ru/rest/api/content/508804852?expand=body.storage,version" \
  > /tmp/page_source.json

curl -s -H "Authorization: Bearer $CONFLUENCE_TOKEN" \
  "https://dom.tutu.ru/rest/api/content/508804891?expand=body.storage,version" \
  > /tmp/page_target.json
```

**Питфолл: поле `space` отсутствует** в ответе GET по умолчанию. Payload PUT нужно собирать
только из `title` + `version.number` (не из `space`). Если нужен space_key — добавить
`?expand=body.storage,version,space` явно.

### Шаг 2: Извлечь `<tr>...</tr>` блок с нужным anchor

```python
import json

data = json.load(open('/tmp/page_source.json'))
body = data['body']['storage']['value']
anchor_marker = 'pfsrow-<ANCHOR_HASH>'

# Откат до ближайшего <tr> перед anchor
anchor_pos = body.find(anchor_marker)
tr_start = body.rfind('<tr>', 0, anchor_pos)

# Найти matching </tr> с учётом вложенности
depth = 0
i = tr_start
end_pos = -1
while i < len(body):
    if body[i:i+3] == '<tr':
        depth += 1; i += 3
    elif body[i:i+4] == '</tr':
        depth -= 1
        if depth == 0:
            end_pos = i + len('</tr>')
            break
        i += 4
    else:
        i += 1

tr_block = body[tr_start:end_pos]
new_source_body = body[:tr_start] + body[end_pos:]

# Сохраняем
with open('/tmp/extracted_tr.txt', 'w') as f:
    f.write(tr_block)
with open('/tmp/new_source_body.txt', 'w') as f:
    f.write(new_source_body)
```

### Шаг 3: PUT — удалить строку с исходной страницы (version + 1)

```python
import json

data = json.load(open('/tmp/page_source.json'))
payload = {
    "version": {"number": data['version']['number'] + 1},
    "title": data['title'],
    "type": "page",
    "body": {"storage": {"value": open('/tmp/new_source_body.txt').read(),
                         "representation": "storage"}}
}
with open('/tmp/payload_source.json', 'w') as f:
    json.dump(payload, f, ensure_ascii=False)
```

```bash
source ~/USERTOOLS/ConfluenceSync/.env
curl -s -X PUT \
  -H "Authorization: Bearer $CONFLUENCE_TOKEN" \
  -H "Content-Type: application/json" \
  "https://dom.tutu.ru/rest/api/content/508804852" \
  -d @/tmp/payload_source.json | python3 -c "
import json,sys; d=json.load(sys.stdin)
print('OK version:', d['version']['number']) if 'version' in d else print('ERROR:', d)
"
```

### Шаг 4: Вставить строку на целевую страницу (после строки-заголовка таблицы)

```python
import json

data_target = json.load(open('/tmp/page_target.json'))
body = data_target['body']['storage']['value']
tr_block = open('/tmp/extracted_tr.txt').read()

# Вставить сразу после <tr>...<th>...</tr> (строка-заголовок таблицы)
header_end = body.find('</tr>', body.find('<th>')) + len('</tr>')
new_target_body = body[:header_end] + tr_block + body[header_end:]

payload = {
    "version": {"number": data_target['version']['number'] + 1},
    "title": data_target['title'],
    "type": "page",
    "body": {"storage": {"value": new_target_body, "representation": "storage"}}
}
with open('/tmp/payload_target.json', 'w') as f:
    json.dump(payload, f, ensure_ascii=False)
```

```bash
source ~/USERTOOLS/ConfluenceSync/.env
curl -s -X PUT \
  -H "Authorization: Bearer $CONFLUENCE_TOKEN" \
  -H "Content-Type: application/json" \
  "https://dom.tutu.ru/rest/api/content/508804891" \
  -d @/tmp/payload_target.json | python3 -c "
import json,sys; d=json.load(sys.stdin)
print('OK version:', d['version']['number']) if 'version' in d else print('ERROR:', d)
"
```

### Шаг 5: Обновить реестр PFS (атомарно)

```python
import json, os
from pathlib import Path

reg_path = Path('~/WorkVault/ProtocolFromSummary/_registry.json').expanduser()

# Бэкап
import shutil
shutil.copy2(reg_path, reg_path.parent / '_registry.json.bak-YYYYMMDD-reason')

data = json.loads(reg_path.read_text(encoding='utf-8'))
entry = data['entries']['<MEETING_ID>']
entry['page_id'] = '<NEW_PAGE_ID>'
entry['entity'] = '<NEW_ENTITY>'

# Атомарная запись
tmp = reg_path.parent / '_registry.json.tmp'
tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
os.replace(tmp, reg_path)
print("Done:", entry['page_id'], entry['entity'])
```

### Шаг 6: Верификация

```bash
source ~/USERTOOLS/ConfluenceSync/.env
curl -s -H "Authorization: Bearer $CONFLUENCE_TOKEN" \
  "https://dom.tutu.ru/rest/api/content/508804852?expand=body.storage,version" \
  > /tmp/v_source.json
curl -s -H "Authorization: Bearer $CONFLUENCE_TOKEN" \
  "https://dom.tutu.ru/rest/api/content/508804891?expand=body.storage,version" \
  > /tmp/v_target.json

python3 -c "
import json
anchor = 'pfsrow-<ANCHOR_HASH>'
b852 = json.load(open('/tmp/v_source.json'))['body']['storage']['value']
b891 = json.load(open('/tmp/v_target.json'))['body']['storage']['value']
print('Source has anchor (должно False):', anchor in b852)
print('Target has anchor (должно True):', anchor in b891)
"
```

---

## Метод B: Monkey-patch + run_pilot (альтернатива, если строки ещё нет на Confluence)

Используй этот метод когда встреча **ещё не опубликована** или нужно переопубликовать
с нуля от оригинального summary-файла.

### Шаги B.1: Бэкап + удалить запись из реестра

```bash
cp ~/WorkVault/ProtocolFromSummary/_registry.json \
   ~/WorkVault/ProtocolFromSummary/_registry.json.bak-YYYYMMDD-reason
```

```python
import json; from pathlib import Path
reg = Path('~/WorkVault/ProtocolFromSummary/_registry.json').expanduser()
data = json.loads(reg.read_text())
data['entries'].pop('<MEETING_ID>', None)
reg.write_text(json.dumps(data, ensure_ascii=False, indent=2))
```

### Шаг B.2: Monkey-patch resolve_route + dry_run

```python
import protocolfromsummary.pipeline as pm
from protocolfromsummary.route import _route_from_entity
from pathlib import Path

pm.resolve_route = lambda name, **kw: _route_from_entity('lenya_1on1')

summary_path = Path('~/WorkVault/Meetings/NewMeetings/<FILENAME> - summary.md').expanduser()

result = pm.run_pilot(summary_path, dry_run=True)
print(result.action, result.entity, result.page_id)
# → published lenya_1on1 508804891

# После проверки row_xml:
result = pm.run_pilot(summary_path, dry_run=False)
```

---

## API сигнатуры (актуальны на 29.07.2026)

```python
# GET-ответ НЕ содержит 'space' без явного expand=...,space
# Для payload PUT достаточно: title + version.number (space не нужен)

resolve_participants(raws: list[str], *, store, confluence, rooms: set[str])
# → list[ResolvedParticipant]

render_row(*, meeting_date, meeting_name, participants, decisions, blockers,
           risks=[], tasks, tag_prefix, task_id_start=1, is_one_on_one=False,
           row_anchor=None, layout='2col', content_column_index=None) -> str
# tasks = list[tuple[MeetingTask, list[ResolvedParticipant], date]]
# НЕ принимает meeting_id как аргумент
```

## lenya_1on1 в entities.json

```json
"lenya_1on1": {
  "kind": "person_1on1",
  "display_name": "Лёня 1-1",
  "aliases": ["леня 1-1", "лёня 1-1", "lenya 1-1", "цыба 1-1",
               "леонид цыба", "цыба леонид", "леонид", "lenya", "цыба"],
  "pfs": { "page_id": "508804891", "tag": "Лёня 1-1." }
}
```

`kind: person_1on1` — новый тип. `pipeline.py` проверяет `kind == "one_on_one"` для
включения `is_one_on_one=True` в render_row. Если нужна логика 1-1 в рендере — сменить на
`kind: one_on_one` в entities.json (и проверить тест baseline_invariant).
