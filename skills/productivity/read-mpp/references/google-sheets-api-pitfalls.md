# Google Sheets API — питфоллы (tkachenkoav, 2026-07-17)

## Имя листа зависит от локали аккаунта

При создании таблицы через API (`sheets create`) первый лист называется **«Лист1»** (не «Sheet1»)
если аккаунт с русским интерфейсом. Запрос к диапазону `Sheet1!A1:H24` вернёт:

```
HttpError 400: Unable to parse range: Sheet1!A1:H24
```

**Диагностика перед первой записью:**
```python
ss = service.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
for s in ss['sheets']:
    print(s['properties']['title'], s['properties']['sheetId'])
# → «Лист1» | 0   (русская локаль)
# → «Sheet1» | 0  (английская локаль)
```

Через `google_api.py` (CLI):
```bash
python3 ~/USERTOOLS/MppReader/push_to_gs.py ...  # push_to_gs.py создаёт лист сам — имя там хардкодено,
                                                  # проверяй через get если хочешь патчить отдельно
```

**Правило:** после `$GAPI sheets create` всегда определять реальное имя листа — никогда не хардкодить «Sheet1».

## Пустые колонки не возвращаются при `sheets get`

API Sheets обрезает каждую строку до последней непустой ячейки.
Если исходные данные содержали пустые колонки между заполненными, реальная структура при чтении будет отличаться от записанной.

**Пример (CSV-экспорт «Брейншторм ML-платформа», 2026-07-17):**
- Записали: A=Title, B=Description, C=Status, D=Assignee, E=Start Date, F=End Date, G=Estimate, H=Priority
- При чтении `sheets get ... 'Лист1!A1:H2'` вернулось: `['Title', 'Start Date', 'End Date', 'Estimate', 'Priority']`
- Пустые колонки B(Description), C(Status), D(Assignee) — пропали, реальные Start/End оказались в B и C

**Следствие:** попытка обновить `E2:F24` (ожидаемые Start/End) не затронет нужные ячейки — реально нужно `B2:C24`.

**Правило:** перед патчем конкретных колонок всегда читать заголовочную строку и проверять реальные позиции:
```bash
$GAPI sheets get $SHEET_ID 'Лист1!A1:Z1'
```
