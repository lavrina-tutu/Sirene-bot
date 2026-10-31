# Склейка страницы: ручные правки владельца + потерянные строки из истории

Проверено live 26.08.2026 (pageId 508804979 «Кирилл 1-1»): v199 (битая) оставила 2 правленые
владельцем строки + 30 пустых; v198 (полная) содержит все 31. Восстановление целиком из v198
затёрло правки владельца; корректно — склейка, сделанная по шагам ниже (итог v201: 31 строка,
правки владельца сохранены).

## Идея

Из полного тела (источник = история страницы, НЕ данные PFS/инструмента) берём все потерянные
строки. Но строки, которые в БИТОЙ версии непустые И изменены относительно полной = ручные
правки владельца — их подставляем из битой версии поверх полной.

## Алгоритм

```python
from hashlib import sha1
import json, re, subprocess, os

def get_ver(v, hist=True):
    url = (f'https://dom.tutu.ru/rest/api/content/508804979'
           f'?status=historical&version={v}&expand=body.storage' if hist else
           f'https://dom.tutu.ru/rest/api/content/508804979?expand=version,body.storage')
    r = subprocess.run(['curl','-s','-H','Authorization: Bearer '+tok, url],
                       capture_output=True, text=True)
    return json.loads(r.stdout)

def extract_trs(body):  # -> {pfsrow_anchor: tr_xml} (по первому pfsrow в строке)
    out = {}
    for m in re.finditer(r'<tr[^>]*>.*?</tr>', body, re.S):
        a = re.findall(r'pfsrow-([a-z0-9]+)', m.group(0))
        if a: out[a[0]] = m.group(0)
    return out

full  = extract_trs(get_ver(198, True )['body']['storage']['value'])  # полная (история)
yours = extract_trs(get_ver(199, True )['body']['storage']['value'])  # битая (ручные правки)

merged = get_ver(198, True)['body']['storage']['value']  # стартуем от полной
for anchor, tr in yours.items():
    if anchor in full and sha1(full[anchor].encode()).hexdigest() != sha1(tr.encode()).hexdigest():
        merged = merged.replace(full[anchor], tr, 1)   # правка владельца побеждает
```

Проверка перед PUT: `len(pfsrow in merged) == 31`, `count('<br /></td><td>') == 0`,
`count(sha1(этой строки) in merged)` для каждого правленого якоря — 1.

## Не захватывать
- Не таскать `json`/`re`-импорты в скрипт-файл этого скилла отдельно — алгоритм выше самодостаточен.
- Verifying: после PUT — независимый GET, посчитать pfsrow, 0 пустых `<br/>`, присутствие правленых якорей.