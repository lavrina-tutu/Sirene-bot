---
name: photo-deduplication
description: "Дедупликация фото: удаление дублей из burst/motion серий Sam"
version: 1.0.1
author: agent
tags: [photos, deduplication, opencv, samsung, burst, sharpness, webdav]
platforms: [linux]
---

# photo-deduplication

## Триггеры
- «удали дубли фотографий»
- «режим анимированного/motion фото Samsung — по 4 одинаковых»
- «оставить только резкие фото из серии»
- «почисти папку с фотками»

## Контекст: Samsung Motion Photo

Samsung S-серия в режиме Motion Photo снимает **burst из 15-25 кадров за 1-2 секунды**.
Формат имени: `IMG_YYYYMMDD_HHMMSS_milliseconds.jpg`
Группа = одинаковый `IMG_YYYYMMDD_HHMMSS` (первые 3 части через `_`).

Обычные фото Samsung: `YYYYMMDD_HHMMSS.jpg` — иногда серии по 2-3 снятых подряд.

---

## Алгоритм

### Шаг 1 — Разведка
```bash
ls ~/YandexDisk/ПапкаФото/ | wc -l
ls ~/YandexDisk/ПапкаФото/ | head -30
```
Определить типы файлов: IMG_* (motion) и 202* (обычные).

### Шаг 2 — Анализ перед удалением (показать план)
Перед удалением показать сколько групп, сколько удалится, сколько останется.
Спросить подтверждение или сразу удалять — по ситуации.

### Шаг 3 — Обработка IMG_* серий (Motion Photo)
```python
from collections import defaultdict
import os

folder = "/path/to/photos"
files = sorted(os.listdir(folder))
img_files = [f for f in files if f.startswith("IMG_") and f.endswith(".jpg")]

img_groups = defaultdict(list)
for f in img_files:
    key = "_".join(f.split("_")[:3])  # IMG_20260612_234558
    img_groups[key].append(f)

to_delete = []
for key, group in sorted(img_groups.items()):
    group_sorted = sorted(group)
    # Оставить 2-й кадр (первый часто смазан при нажатии)
    keep = group_sorted[1] if len(group_sorted) >= 2 else group_sorted[0]
    to_delete.extend([f for f in group_sorted if f != keep])
```

**Почему 2-й кадр:** первый кадр часто захватывает момент нажатия на кнопку (смаз). Пользователь подтвердил этот выбор.

### Шаг 4 — Обработка обычных фото (резкость)
```python
import cv2
from datetime import datetime

def sharpness(filepath):
    img = cv2.imread(filepath, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return 0
    # Даунсэмплинг до 800px — ОБЯЗАТЕЛЬНО для скорости
    # Без этого: ~1 сек/файл (200 файлов = 200 сек, таймаут). С ним: ~0.05 сек/файл.
    h, w = img.shape
    if w > 800:
        img = cv2.resize(img, (800, int(h * 800 / w)), interpolation=cv2.INTER_AREA)
    return cv2.Laplacian(img, cv2.CV_64F).var()

def parse_dt(f):
    try:
        return datetime.strptime(f[:15], "%Y%m%d_%H%M%S")
    except:
        return None

# Группировать по времени: разница < 30 сек = одна группа
regular = [f for f in files if f.startswith("202") and f.endswith(".jpg")]
times = [(f, parse_dt(f)) for f in regular if parse_dt(f)]

groups = []
current = [times[0]]
for i in range(1, len(times)):
    if (times[i][1] - times[i-1][1]).total_seconds() < 30:
        current.append(times[i])
    else:
        groups.append(current)
        current = [times[i]]
groups.append(current)

for g in groups:
    if len(g) == 1:
        continue
    scored = [(f, sharpness(os.path.join(folder, f))) for f, t in g]
    best = max(scored, key=lambda x: x[1])[0]
    to_delete.extend([f for f, s in scored if f != best])
```

### Шаг 5 — Удаление
```python
deleted = 0
for f in to_delete:
    try:
        os.remove(os.path.join(folder, f))
        deleted += 1
    except Exception as e:
        print(f"Ошибка: {f}: {e}")
print(f"Удалено: {deleted}, осталось: {len(os.listdir(folder))}")
```

---

## Повторный запуск (новые фото добавлены)

Пользователь добавил новые фото в уже обработанную папку — стандартный сценарий. Передать список уже сохранённых файлов как `ALREADY_PROCESSED` и обрабатывать только новые.

**Реальный опыт (15.06.2026):** 843 файла (730 новых + 113 уже обработанных) → удалено 553, осталось 290. При этом execute_code упал по таймауту 300 сек — правильный путь: скрипт в `/tmp/` + `terminal(background=True, notify_on_complete=True)`.

Если папка уже частично обработана — передать список уже сохранённых файлов как `already_kept` и обрабатывать только новые:

```python
already_kept = {'file1.jpg', 'file2.jpg', ...}  # результат прошлого прогона
all_files = sorted(os.listdir(folder))
new_files = [f for f in all_files if f not in already_kept]
# далее обрабатывать только new_files
```

**Важно:** при большом количестве файлов (200+) расчёт резкости через OpenCV занимает 200-300 секунд. Использовать скрипт в `/tmp/` + `terminal(background=True, notify_on_complete=True)` — не `execute_code` (таймаут 300 сек). При 700+ файлах `execute_code` гарантированно падает по таймауту даже с даунсэмплингом.

---

## Питфоллы

- **Таймаут execute_code при 200+ файлах** — OpenCV на каждый файл занимает ~1 сек без даунсэмплинга. **Решение: всегда даунсэмплировать до 800px перед Laplacian** — ускоряет в 20x. При 700+ файлах — записать скрипт в `/tmp/dedupe.py` и запускать через `terminal(command="python3 /tmp/dedupe.py", background=True, notify_on_complete=True)`. `execute_code` с таймаутом 300 сек не годится — гарантированный провал.
- **WebDAV медленнее локального FS** — чтение каждого файла для анализа резкости идёт по сети. Учитывать при оценке времени.
- **Первый кадр Motion Photo смазан** — оставлять 2-й, не 1-й.
- **Порог группировки 30 сек** — подходит для большинства случаев. Если фотограф снимал одну сцену дольше — увеличить до 60 сек.
- **OpenCV уже есть** на VM (`pip install opencv-python-headless` если нет).
- **Перед удалением** — показывать план (сколько групп, сколько удалится). Не удалять молча без подтверждения если объём большой.
- **mp4 файлы** — не трогать, они не входят ни в IMG_* ни в 202*.jpg паттерны.

---

## Зависимости
```bash
pip install opencv-python-headless  # если нет
```

## Пример результата
307 файлов → удалено 249 → осталось 58 (37 фото + 1 видео + 21 motion)
