# RTF → plain text extraction (resume / any .rtf)

Происхождение: адаптировано из resume-optimization (license: proprietary); перенос не означает перелицензирование в MIT.

Резюме от hh.ru приходит как `.rtf` (ANSI, codepage 1251). read_file видит его как binary; текст не инлайн.

## Проверенный способ (striprtf через uv venv)

В проверенной ранее среде `pandoc -f rtf` вернул `Unknown input format rtf`; один из рабочих обходов — striprtf:

```bash
cd ~/.hermes/cache/scratch
uv venv .venv --python 3.11 && uv pip install --python .venv/bin/python striprtf
.venv/bin/python - <<'EOF'
from striprtf.striprtf import rtf_to_text
data = open('resume.rtf', encoding='cp1251', errors='replace').read()
txt = rtf_to_text(data, errors='replace', encoding='cp1251')
open('resume.txt','w',encoding='utf-8').write(txt)
EOF
```

## Заметки

- Кодировка файла: `file` покажет `ANSI, code page 1251` → читать/писать через cp1251 (не utf-8), иначе мусор.
- Копировать исходный файл в scratch, а не парсить из cache/documents напрямую.
- striprtf теряет структуру таблиц (возвращает текст почти линейно), но для чтения содержимого резюме достаточно — читать результат через read_file по строкам.
- После чтения текст идёт в анализ; сам RTF-шаблон (hh.ru) не трогать при извлечении.

## Очистка извлечённого текста

При извлечении удалять из текстового результата служебные destination-группы (`pict`, `object`, `fonttbl`, `colortbl`, `stylesheet`, `datastore`, `themedata`), длинный hex-мусор и хвост стилей; проверять, что конец содержит реальный текст. Сам RTF-эталон при этом не изменять.
