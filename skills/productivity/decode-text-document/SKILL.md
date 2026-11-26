---
name: decode-text-document
description: "Декодирует UTF-16 .txt, который read_file видит как binary."
version: "1.0.0"
platforms: [linux, macos]
tools: [terminal, read_file, write_file]
metadata:
  hermes:
    tags: [encoding, utf-16, decoding, binary, text-document]
---

# Decode Text Document — декодирование UTF-16/UCS-2 текстовых файлов

## Триггер
- `read_file` вернул `Binary file - cannot display as text` или пустой результат на .txt/.md, который на деле — текст.
- Файл пришёл из мессенджера/кэша Hermes (`~/.hermes/cache/documents/...`) и содержит русский текст.
- Команды вроде `cat`, `head`, `unzip` дают кракозябры или `End-of-central-directory not found`.

## Почему так бывает
Мессенджеры и системные экспорты часто отдают текстовые файлы в **UCS-2/UTF-16LE или UTF-16BE** (двухбайтовая кодировка на каждый символ). `read_file` и стандартный `iconv` по умолчанию ждут UTF-8/однобайтовые кодировки, поэтому видят «бинарник».

Ключевой признак — BOM в первых байтах:
- `FE FF` → **UTF-16BE** (big-endian)
- `FF FE` → **UTF-16LE** (little-endian)

## Шаги

### 1. Определи кодировку по BOM (ОБЯЗАТЕЛЬНО)
```bash
xxd /path/to/file | head -1
```
Смотри первые 2 байта:
- `feff` → big-endian
- `fffe` → little-endian

⚠️ **Не угадывай по названию и не пробуй вслепую.** `file` иногда верно говорит («Big-endian UTF-16 Unicode text», «Little-endian UTF-16»), но решает всегда `xxd`.

### 2. Сконвертируй в UTF-8 явной кодировкой из BOM
```bash
# big-endian
iconv -f UTF-16BE -t UTF-8 /path/to/file > /tmp/decoded.txt
# little-endian
iconv -f UTF-16LE -t UTF-8 /path/to/file > /tmp/decoded.txt
```

### 3. Проверь результат
```bash
wc -c /tmp/decoded.txt
head -c 300 /tmp/decoded.txt
```
- Читаемый русский текст → файл готов, дальше `read_file`/`execute_code` читают его штатно.
- Снова кракозябры/иероглифы → была неверная endianness (BE/LE поменяй местами) или кодировка не UTF-16 (попробуй `file` и поиск по другим — cp1251 `-f WINDOWS-1251`, cp866).

## Pitfalls
- **`iconv -f UTF-16` без явного BE/LE** — может выдать мусор, если BOM не распознан. Всегда задавай конкретную (`UTF-16BE`/`UTF-16LE`) по `xxd`.
- **Не использовать `read_file` на исходном UTF-16** — он ложно вернёт `binary`; сначала `iconv`, потом читай.
- **Не путать с .mpp-as-.zip (OLE2)**: это другая обёртка (Composite Document File V2). Если `xxd` показывает `feff`/`fffe` в начале и `file` говорит «UTF-16» — это текст; если `file` говорит «Composite Document ... Microsoft Project» — это .mpp, см. скилл `read-mpp`.
- Пустой вывод `iconv` (0 строк) → почти всегда неверная endianness; поменяй.

## Outlook .msg (e-mail) — не текст, а OLE compound

`.msg` (письма провайдеров, уведомления из `~/.hermes/cache/documents/...`) не читается как текст: `read_file`/`cat` дают бинарный мусор. Извлекай через extract-msg (подтягивается за сессию через uv):

```bash
cd ~/.hermes/cache/documents && uv run --with extract-msg python3 - <<'EOF'
import extract_msg, glob
for f in sorted(glob.glob('doc_*.msg')):
    m = extract_msg.Message(f)
    print(m.subject, '|', m.sender, '|', m.date)
    print((m.body or '')[:4000])
    for att in m.attachments:
        print('ATTACH:', att.longFilename)
EOF
```

Поля сообщения: `subject`, `sender`, `to`, `date`, `body` (текст), `attachments[].longFilename`. Для писем trust&safety (бан/апелляция) читай body целиком: там статус (финальный отказ vs подтверждение приёма) и ссылки на условия — в письме часто скрыт факт, что апелляция уже отклонена.

## Связанные скиллы
- `read-mpp` — если это на самом деле MS Project (.mpp), пришедший как .zip (OLE2), а не текст.
- `record-mobile-notes` — если после декодирования нужны итоги/решения по всем темам стенограммы (мобильная запись, собрание).
- `document-to-action-items` — если после декодирования из текста нужно извлечь обязательства/задачи с цитатами (договоры, отчёты).