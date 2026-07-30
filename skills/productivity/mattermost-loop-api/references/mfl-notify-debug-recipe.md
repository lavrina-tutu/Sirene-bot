# MFL notify debug recipe (30.07.2026)

Воспроизводимый рецепт расследования «почему urgent-уведомление не пришло».
Применялся для поста aralov `a7e3ewyemfbuunotzngoxwd17w`.

---

## 1. Извлечь post_id из URL

```
https://loop.tutu.ru/tutu/pl/{post_id}
```

## 2. Проверить seen_ids

```bash
python3 -c "
import json
from datetime import datetime, timezone, timedelta
MSK = timezone(timedelta(hours=3))
data = json.load(open('/home/tkachenkoav/USERTOOLS/MoveFromLoop/state/watermark.json'))
target = 'ТВОЙ_POST_ID'
hit = next((e for e in data['seen_ids'] if e['id'] == target), None)
if hit:
    print('Помечен seen:', datetime.fromtimestamp(hit[\"ts\"]/1000, tz=MSK))
else:
    print('НЕТ в seen_ids — крон не видел')
"
```

**Интерпретация:**
- `Помечен seen: 2026-07-29 22:51:59 МСК` → крон нашёл пост, обработал. Проблема в deliver.
- `НЕТ в seen_ids` → крон не обработал пост. Возможные причины ↓.

## 3. Если НЕТ в seen_ids — почему крон не видел?

```bash
# Проверить urgent_contacts в loop_rules.yaml
grep -A10 "urgent_contacts:" /home/tkachenkoav/USERTOOLS/MoveFromLoop/loop_rules.yaml

# Получить автора поста
LOOP_TOKEN="ujde9bzqepb6t8hraym6wz73ir"
POST_ID="ТВОЙ_POST_ID"
curl -s --max-time 15 -H "Authorization: Bearer $LOOP_TOKEN" \
  "https://loop.tutu.ru/api/v4/posts/$POST_ID" | python3 -c "
import json,sys
p=json.load(sys.stdin)
print('user_id:', p['user_id'])
print('channel_id:', p['channel_id'])
print('create_at:', p['create_at'])
print('message:', p['message'][:100])
"

# Сверить user_id с user_cache в watermark.json
python3 -c "
import json
data = json.load(open('/home/tkachenkoav/USERTOOLS/MoveFromLoop/state/watermark.json'))
for username, v in data.get('user_cache', {}).items():
    print(username, '->', v['id'])
"
```

Если `user_id` поста отсутствует в `user_cache` → автор не в `urgent_contacts`.

## 4. Если ЕСТЬ в seen_ids — проверить Telegram

```bash
# Статус gateway
cat ~/.hermes/gateway_state.json | python3 -c "
import json,sys
g=json.load(sys.stdin)
tg=g['platforms'].get('telegram',{})
print('Telegram state:', tg.get('state'))
print('Updated at:', tg.get('updated_at'))
print('last_delivery_error (jobs.json):', '— смотри отдельно')
"

# Статус deliver для конкретного крона
python3 -c "
import json
data = json.load(open('/home/tkachenkoav/.hermes/cron/jobs.json'))
jobs = data if isinstance(data, list) else data.get('jobs', [])
for job in jobs:
    if job.get('id') == 'f61b26cbbdf5':
        print('last_status:', job.get('last_status'))
        print('last_delivery_error:', job.get('last_delivery_error'))
        print('deliver:', job.get('deliver'))
"
```

**Красный флаг:** `telegram.state = "disconnected"` + `last_delivery_error = null` = уведомление сформировано но потеряно при доставке.

Фикс: `systemctl --user restart hermes-gateway`

## 5. Посмотреть логи рядом по времени (через дайджест)

```bash
# Логи urgent-крона за вчера могут быть удалены ротацией (~480 файлов/день)
ls ~/.hermes/cron/output/f61b26cbbdf5/ | sort | wc -l

# Логи дайджеста живут дольше (13 файлов/день)
ls ~/.hermes/cron/output/2865cc674493/ | sort

# Если дайджест ОКОЛО нужного времени доставлял (нет строки "Status: silent") —
# значит Telegram был connected и проблема не в нём
cat ~/.hermes/cron/output/2865cc674493/2026-07-29_19-00-57.md
```

## 6. Вывести временну́ю шкалу

```python
from datetime import datetime, timezone, timedelta
MSK = timezone(timedelta(hours=3))

# Из watermark.json: seen_ids, urgent_last_ts
import json
data = json.load(open('/home/tkachenkoav/USERTOOLS/MoveFromLoop/state/watermark.json'))

print('urgent_last_ts:', datetime.fromtimestamp(data['urgent_last_ts']/1000, tz=MSK))
print()
print('Последние seen_ids:')
for e in sorted(data['seen_ids'], key=lambda x: x['ts'])[-5:]:
    dt = datetime.fromtimestamp(e['ts']/1000, tz=MSK)
    print(f"  {dt.strftime('%m-%d %H:%M:%S МСК')} | {e['id']}")
```

---

## Итог по случаю 29.07.2026 (aralov → a7e3ewyemfbuunotzngoxwd17w)

| Факт | Вывод |
|------|-------|
| Пост есть в seen_ids (ts=22:51:59 МСК) | Крон нашёл и обработал |
| aralov в urgent_contacts | is_urgent=True |
| Дайджест 22:00 МСК доставлял | Telegram был connected в 22:00 |
| Логов urgent за 29.07 нет | Ротация (не означает что не работал) |
| Telegram disconnected сейчас | Системная проблема, повторяется |
| last_delivery_error=null | Бесшумная потеря при disconnected |

**Наиболее вероятная причина:** Telegram был временно disconnected в узком окне 22:51 МСК → deliver упал бесшумно → пост потерян навсегда (уже в seen_ids).
