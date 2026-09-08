# MPP → gantt-chart-planner JSON: полный рецепт конвертера

Проверено 08.09.2026 на тестовой странице pageId=519501810 (план «Доработки АБ-платформы ТУТУ до Trisigma», 33 задачи). Заливка MPP 080926 и синк календаря подтверждены рендером.

## Источник: CSV от read_mpp.py

Используем `read_mpp.py` (скилл `read-mpp`), который уже валит mpxj в CSV:
```bash
source /home/tkachenkoav/hermes-agent/.venv/bin/activate
python3 /home/tkachenkoav/USERTOOLS/MppReader/read_mpp.py /tmp/plan.mpp --format csv
# → /tmp/plan__tasks.csv, plan__resources.csv, plan__assignments.csv
```

## Схема сборки JSON вложения

### eventsData (дерево)
- Читать `__tasks.csv`: `id, outline_level, name, duration, start, finish, percent_complete, milestone, summary, predecessors`.
- Построить дерево из `outline_level` (стек, как в MS Project). 
- Каждое событие — объект с полями (шаблон из любого существующего вложения):
  ```
  {baselines:[], calendar:None, constraintType:'', duration:d, durationUnit:'day',
   effort:eff|None, effortDriven:False, effortUnit:'hour', ignoreResourceCalendar:None,
   inactive:None, manuallyScheduled:False, parentId:int|None, parentIndex:int,
   percentDone:0, rollup:bool, schedulingMode:'FixedDuration', segments:None,
   unscheduled:False, startDate, endDate, name, children:[]}
  ```
- `rollup` = `summary` MPP (сводная). `duration` = `duration` MPP (0 у вех). `startDate`/`endDate` = `start`/`finish` MPP.
- Веха (milestone=True) → `duration:0`, `effort:0`.
- КОРЕНЬ дерева (`eventsData[0]`) — сводная-корень всего плана (в MPP это строка outline_level=1, в тесте «Доработки АБ-платформы ТУТУ до Trisigma - оценка»).

### resourcesData (активная группа + новые)
- Читать `__resources.csv`: `id, name, max_units`.
- В существующем JSON плагина ресурсы могут иметь НЕСКОЛЬКО записей с одинаковым `name` и разными id (группы копий). **Активная = запись с наибольшим id на имя.**
- Матчить ресурсы MPP с активной группой **по имени**; у кого нет матча (напр. «Найм») — **создать новый** ресурс с id из idCounter (или max(id)+1):
  `{id:NEW, parentId:None, name, eventColor:'red', resourceType:'custom'}`.

### assignmentsData (назначения)
- Читать `__assignments.csv`: `task_id, resource_name, units, work`.
- Для каждой строки: `{id:ASN_ID, event:<task_id>, resource:<plugin_res_id>, units:<units>}`.
  `units` = % загрузки (напр. 70). Одна задача может иметь несколько назначений (тестирование: продуктовые 100% + Гладких 50%).
- **effort события** = СУММА `work` (ч/ч) всех назначений на эту задачу (в mpp `work` в формате "X h").
- id назначений — из idCounter, инкрементировать.

### dependenciesData (связи)
- Из `__tasks.csv` колонка `predecessors` (строка вида `[2]` или `[15, 17, 19]`).
- Для каждого предшественника: `{id:DEP_ID, from:<pred_id>, to:<task_id>, type:2, lag:0, lagUnit:'day', active:true}`. `type:2` = финиш-старт (FS).
- ⚠️ задача/предшественник должны существовать в flat-мапе событий; сравнивать id как int.

### Остальные ключи
- `startDate` (верхний уровень) = дата старта корня.
- `idCounter` = след. свободный id; нормализовать под новые id сущностей.
- `macroConfig, calendarsData, initialState, baselineVersions, customColumns, linkedSites` — **копировать из существующего вложения как есть** (не трогать, кроме calendarsData при синке календаря).

## Синк календаря MPP → плагин

Календарь «рабочее время» в MPP («Стандартный») читается через java-API mpxj (не CSV):
```python
# импорты: import mpxj; import jpype; import jpype.imports; if not jpype.isJVMStarted(): jpype.startJVM()
from org.mpxj.reader import UniversalProjectReader  # НЕ net.mpxj.*
pj = UniversalProjectReader().read('/tmp/plan.mpp')
cal = pj.getDefaultCalendar()   # не getProjectCalendar
# нерабочие исключения:
for x in cal.getCalendarExceptions():
    if not x.getWorking():
        fd = str(x.getFromDate())  # '2026-11-04'
        td = str(x.getToDate())
        # в плагине интервал [fd, td+1день) нерабочий
# рабочие часы по умолчанию: cal.getCalendarHours()
# проверка дня: cal.isWorkingDate(java.time.LocalDate.parse('2026-11-04'))
```

Маппинг в `calendarsData` (один календарь general):
```json
{
  "id": "general", "name": "General", "unspecifiedTimeIsWorking": true,
  "intervals": [
    {"recurrentStartDate": "at 12:00", "recurrentEndDate": "at 13:00", "isWorking": false},  // обед
    {"recurrentStartDate": "at 18:00", "recurrentEndDate": "at 09:00", "isWorking": false},  // ночь
    {"recurrentStartDate": "on Sun", "recurrentEndDate": "on Mon", "isWorking": false},      // вс
    {"recurrentStartDate": "on Sat", "recurrentEndDate": "on Sun", "isWorking": false},       // сб
    {"startDate": "2026-11-04 00:00", "endDate": "2026-11-05 00:00", "isWorking": false},     // праздник из MPP
    ...
  ]
}
```
Receipt: для каждого нерабочего исключения `{startDate: f.isoformat()+" 00:00", endDate: (t+timedelta(days=1)).isoformat()+" 00:00", isWorking:false}` (end эксклюзивен).

## Проверка после заливки
1. POST вернул 200, version вложения бампнулась.
2. Пере-GET вложения → сверить: число событий (дерево с корнем), resourcesData (новый ресурс есть), calendarsData (праздники в периоде плана), суммарный effort листьев.
3. Визуально на странице: план отрисовался, связи-стрелки, ресурсы на барах, праздники/выходные как неработающие дни.

## Ключевые питфоллы конвертера
- **id типов:** события с `id` из MPP (1..N) могут конфликтовать с существующими id наследуемого плагина. При точечных вставках после заливки — пересчитывать idCounter, не хардкодить (тестовый конвертер ставил 300000 — сломан, см. вероятность коллизии).
- **predecessors парс:** строка `[2]` → приводить к int и сверять с int-ключами flat-мапы (сравнение str vs int молча даёт 0 связей).
- **несколько людей на задаче** (тестирование): в assignments несколько записей на один `event` с разными `resource`/`units`, effort = сумма work.
- **`import mpxj` и `import jpype.imports` ДО `startJVM()`** — иначе Java-пакеты не резолвятся.