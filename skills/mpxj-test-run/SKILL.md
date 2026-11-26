---
name: mpxj-test-run
version: "1.0.0"
license: MIT
author: sirene
description: "Use when прогон JVM-тестов MppReader/edit-plan-confluence."
metadata:
  hermes:
    tags: [mpxj, jvm, pytest, mpp, verification]
    related_skills: [read-mpp, hermes-feature]
---

# Прогон JVM/mpxj-зависимых тестов USERTOOLS (MppReader / edit-plan-confluence)

## When to Use
Загружается, когда нужно прогнать pytest-наборы JVM/mpxj-зависимых модулей (MppReader, edit-plan-confluence, workvault-rag plan-запросы) или диагностировать `ModuleNotFoundError: mpxj` / кашу из anyio-импортов в таких наборах.

Пакеты, читающие MS Project (MppReader, edit-plan-confluence, workvault-rag plan-запросы), зависят от `mpxj`+`jpype` (JVM). Прогон их pytest-наборов имеет жёстко заданное рабочее окружение:

```bash
unset PYTHONPATH PYTHONHOME
cd ~/hermes-workspace/skills/productivity/edit-plan-confluence
/usr/bin/python3.9 -m pytest -m "not live" -q
cd ~/USERTOOLS/MppReader && /usr/bin/python3.9 -m pytest -q
```

## Интерпретаторы — где живёт mpxj
- `mpxj`/`jpype` стоят в `/usr/bin/python3.9`. Они **не** в `/usr/bin/python3` (3.11) и **не** в `~/hermes-agent/.venv`.
- `ModuleNotFoundError: No module named 'mpxj'` = выбран не тот интерпретатор, а НЕ что движок не установлен. Сначала проверь python3.9, не доустанавливай.
- Под системным `python3` (3.11) до ~13 JVM-тестов падают на `ModuleNotFoundError: mpxj` в collection — это ложный регресс; зелёная логика доступна из python3.9 (`edit-plan-confluence: 82 passed`, MppReader `84 passed, 1 skipped`).

## Питфолл 1 — загрязнённый PYTHONPATH
`/usr/bin/python3.9 -m pytest` без очистки падает на `ImportError: cannot import name 'TypeAlias' from 'typing'` (каша из anyio hermes-py3.14 venv). Сессия Hermes наследует засорённый PYTHONPATH. Всегда `unset PYTHONPATH PYTHONHOME` перед прогоном JVM-набора. Это не регресс кода.

## Питфолл 2 — subprocess выбирает свой интерпретатор
Часть тестов (`test_cli_convert_offline`) запускают `cli.py` как subprocess; тот выбирает интерпретатор через `scripts/mpp_input.py::_pick_python()`, а в его кандидатах (hermes venv, `/usr/bin/python3`, `which python3`) mpxj нет ни в одном — модуль падает даже под python3.9. Это дефект `_pick_python()` (не знает про python3.9), а не регресс теста/кода.

## Что НЕ регресс
- Логический pre-existing fail (`test_find_macro` — рассинхрон fixture: в SAMPLE другой macro-id, `tests/test_macro.py` давно не менялся). Фиксировать как известный, не чинить в рамках чужого пакета.
- JVM-тесты под интерпретатором без mpxj — не регресс.

## Верификация по живым артефактам
Отчёт исполнителя (`agent -p` / self-report) не замена проверке. Перед объявлением приёмки: git-status реальных файлов, pytest из правильного интерпретатора, mtime готовых артефактов. Расхождение заявленных и реальных чисел падений вскрывается прогоном под python3.9 — важна природа падения (mpxj vs логика), не голый count.
