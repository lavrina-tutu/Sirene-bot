# Перенумерация дублей bk-якорей

## Диагностика

```bash
grep -oE '\^bk-[0-9]+' ~/WorkVault/Hermes-Backlog/dialog-backlog.md | sort | uniq -d
```
Если вывод непустой — есть дубли.

## Причина

`backlog_merge.py` читает `next_id` из frontmatter, но если в файл добавляли пункты вручную или через несколько каналов, реальный максимум может быть выше, чем `next_id`. При следующем запуске merge присваивает уже занятые номера.

## Фикс — Python-скрипт

Оставляет первое вхождение якоря, перенумеровывает последующие дубли:

```python
import re, shutil
from collections import defaultdict

path = '/home/tkachenkoav/WorkVault/Hermes-Backlog/dialog-backlog.md'
raw = open(path, encoding='utf-8').read()
lines = raw.split('\n')

anchor_re = re.compile(r'\^(bk-\d+)')
seen = defaultdict(list)
for i, line in enumerate(lines):
    m = anchor_re.search(line)
    if m:
        seen[m.group(1)].append(i)

all_nums = [int(a.split('-')[1]) for a in seen]
next_new = max(all_nums) + 1

for anchor, idxs in seen.items():
    if len(idxs) > 1:
        for dup_idx in idxs[1:]:
            new_anchor = f"bk-{next_new:03d}"
            lines[dup_idx] = lines[dup_idx].replace(f'^{anchor}', f'^{new_anchor}', 1)
            next_new += 1

new_content = '\n'.join(lines)
new_content = re.sub(r'(next_id:\s*)\d+', f'\\g<1>{next_new}', new_content, count=1)
shutil.copy2(path, path + '.bak')
open(path, 'w', encoding='utf-8').write(new_content)
print(f"Done. next_id = {next_new}")
```

## Проверка после

```bash
grep -oE '\^bk-[0-9]+' ~/WorkVault/Hermes-Backlog/dialog-backlog.md | sort | uniq -d
# Должно быть пусто
```

## Профилактика

Перед каждым `backlog_merge.py --plan` синхронизировать `next_id` с реальным максимумом:

```bash
MAX=$(grep -oE '\^bk-[0-9]+' dialog-backlog.md | grep -oE '[0-9]+' | sort -n | tail -1)
echo "Реальный max: $MAX"
# next_id в frontmatter должен быть > MAX
```
