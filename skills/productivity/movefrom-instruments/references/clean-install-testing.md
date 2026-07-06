# Тестирование с нуля (clean-install verification)

Для подтверждения успешной миграции или после крупных изменений структуры — запускать тесты в свежем venv.

## Паттерн

```bash
python -m venv /tmp/test_venv_fresh
source /tmp/test_venv_fresh/Scripts/activate  # Windows (Git Bash)

# Установить все инструменты + pytest-плагины
pip install -q -e USERTOOLS/MoveFromFF -e USERTOOLS/MoveFromExchange -e USERTOOLS/MoveFromConfluence
pip install -q pytest pytest-mock pytest-xdist pytest-timeout

# Запускать КАЖДЫЙ инструмент из его собственной директории
cd USERTOOLS/MoveFromFF && python -m pytest tests/ -v --tb=short \
  --override-ini="addopts=" --timeout-method=thread

cd ../MoveFromExchange && python -m pytest tests/ -v --tb=short \
  --override-ini="addopts=" --timeout-method=thread

cd ../MoveFromConfluence && python -m pytest tests/ -v --tb=short \
  --override-ini="addopts=" --timeout-method=thread

rm -rf /tmp/test_venv_fresh
```

## ⚠️ Критические питфоллы

- **Нельзя запускать все тесты из корня hermes-agent** — корневой `pyproject.toml` содержит `addopts = -n --timeout-method=signal`, что ломает pytest на Windows (нет `signal.SIGALRM`) и конфликтует с дочерними пакетами
- **`--override-ini="addopts="`** — обязателен для сброса корневых `addopts` при запуске из директории инструмента (иначе pytest тянет корневой конфиг по иерархии)
- **`--timeout-method=thread`** — заменяет `signal` для Windows-совместимости
- **`.venv/` в каждом инструменте — НЕ удалять** — рабочие окружения для кронов
- **`*.egg-info/` — НЕ удалять** — нужны для `pip install -e` (editable install)

## Что проверяет clean-install тест

- ✅ Зависимости правильно задекларированы в `pyproject.toml`
- ✅ Пути и конфиги работают на реальной файловой структуре
- ✅ Нет «призраков» старого окружения
- ❌ Не проверяет: реальные API-запросы (мокируются), работу кронов в production

## Мусор после прогона тестов (можно чистить)

```bash
# __pycache__ и .pytest_cache — только из исходников, не из .venv
find USERTOOLS -maxdepth 3 -type d -name "__pycache__" ! -path "*/.venv/*" -exec rm -rf {} + 2>/dev/null
find USERTOOLS -maxdepth 2 -type d -name ".pytest_cache" ! -path "*/.venv/*" -exec rm -rf {} + 2>/dev/null
```

## Питфолл батч-переименования

**Не через bash:** `for f in $(ls | grep ...); do mv -- "$f" "${f}_old"; done` ломается на именах с пробелами/кириллицей — `$(...)` word-splitting разбивает одно имя на несколько «аргументов», `mv` не находит файлов. Симптом: `mv: cannot stat 'Слово': No such file or directory` пачками, при этом bash-цикл «отрабатывает» без явной ошибки — легко принять за успех.

**Решение:** `execute_code` с Python (`os.listdir()` + `re.match()` + `os.rename()`) — не подвержено word-splitting, каждое имя — атомарная строка.
