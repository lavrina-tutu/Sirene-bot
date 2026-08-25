# Legacy: Google Sheets-центричный workflow (устарел)

> Расшифровка исторического процесса (24.07–17.08.2026), когда результаты в первую очередь велись в
> **Google Sheets**, а Confluence-страницы были вторичны. С 18.08.2026 хранилище переведено на
> **Confluence-центричную** схему (см. SKILL.md → «Структура хранения»). Этот блок сохранён для справки
> и миграций, НЕ для текущего заполнения новых ответов.

## Google Sheets с критериями

`https://docs.google.com/spreadsheets/d/12JKbfPiq0OpyABaNVOiJb6eJosKJOiDNFGuzLos2fdo/edit`

- Строки = вопросы (13 технических + 3 по оплате, итого 16); столбец A = вопросы.
- Столбцы A–F заняты, новые сервисы вписывались начиная с G.
- Запись одного столбца ответов (строки 2–17 = ответы 1–16):
  ```
  GAPI sheets update SHEET_ID "Sheet1!G1:G17" --values '[["Название"],["отв1"],...]'
  ```
- Имя листа может быть не «Sheet1» → при ошибке `Unable to parse range` опустить имя листа (`"A1:Z3"`).
- `googleapiclient` не в системном Python → активировать venv: `source ~/hermes-agent/.venv/bin/activate`.
- Токен протухает (`invalid_grant`) → `python setup.py --auth-url` → пользователь вводит code → `setup.py --auth-code "..."`.

**Текущие столбцы (на момент 24.07.2026):** G=proxy6.net, H=proxy5.net, I=webshare, J=proxywing.com, K=proxiempire.io, L=shifter.io, M=fineproxy.org, N=2captcha.com, O=InfraProxy.ru.

## Скачанные папки сервисов (WorkVault, 21.07.2026)

| Папка | Сервис |
|---|---|
| `2captcha.com/` | 2captcha.com |
| `fineproxy.org/` | fineproxy.org |
| `https___proxywing.com_/` | proxywing.com |
| `proxiempire.io/` | proxiempire.io |
| `proxy5.net/` | proxy5.net |
| `proxy6/` | proxy6.net |
| `shifter.io/` | shifter.io |
| `webshare/` | webshare.io |

## Старые pageId страниц сервисов (созданы 24.07.2026, до введения нумерации N.)

| Сервис | pageId |
|---|---|
| Парсинг. webshare | 511562669 |
| Парсинг. proxy6.net | 511562679 |
| Парсинг. proxy5.net | 511562680 |
| Парсинг. proxywing.com | 511562681 |
| Парсинг. proxiempire.io | 511562682 |
| Парсинг. shifter.io | 511562683 |
| Парсинг. fineproxy.org | 511562684 |
| Парсинг. 2captcha.com | 511562685 |
| Парсинг. InfraProxy.ru | 511562686 |

> ⚠️ Сейчас подстраницы имеют формат `Парсинг. N. <name>` (N — порядок пригодности). Актуальный список —
> через `/rest/api/content/<pageId-сводной>/child/page` (см. SKILL.md «Структура хранения»).