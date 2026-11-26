# Серийная нарезка адресных частей (W1-стиль, вне канбана)

Класс: задача разбита на части (W1-01…W1-12); исполнитель гоняется кодексом-подобной командой из
terminal с `background=true`, `notify=true`, `persist_on_release=true` и `tee evidence/<round>.log`.

## Запуск адресного раунда

1. Записать адресный промпт в `/tmp/<round>-prompt.md` (write_file) — ТОЛЬКО на остаток по чек-листу,
   не «закрой всё»; каждый пункт с source-ссылкой на вердикт (`out/*-ADVICE.md`).
2. Запустить в фоне:
   `codex exec -C <D> -m gpt-6.1-sol --skip-git-repo-check --json --sandbox danger-full-access --
   "$(cat /tmp/<round>-prompt.md)" 2>&1 | tee evidence/<round>.log`
   с `background=true, notify=true, persist_on_release=true`.
3. По нотификации «exit 0» — НЕ доверять обрезанному хвосту лога в превью.

## Readback вердикта (после нотификации)

Точный вердикт исполнителя — последний `"type":"agent_message","text":"..."` в `evidence/<round>.log`:
```python
import re
t = open(".../<round>.log", encoding="utf-8", errors="replace").read()
msgs = re.findall(r'"type":"agent_message","text":"((?:[^"\\]|\\.)*)"', t)
print(msgs[-1].encode().decode('unicode_escape', errors='replace')[-4500:])
```
Превью нотификации (последние ~170 симв.) не эквивалентна результату; commit/тесты/остаток читать
из лога.

## Независимая сверка перед закрытием части (не полагаться на самоотчёт)

Оркестратор перепроверяет глазами, как Саша:
```bash
git log --oneline -5 && git status --porcelain  # HEAD + worktree чист
git diff --name-only <HEAD>^..<HEAD>             # ровно allowlist части (write-scope)
W1_PY -m pytest <tests...> --collect-only -q -p no:cacheprovider   # ровно ожидаемые nodeids
W1_PY -m pytest <tests...> -q -p no:cacheprovider                  # full run, 0 skip/xfail
W1_PY -m pipeline.cli --help && git diff <HEAD>^ <HEAD> --check   # rc 0, trailing whitespace чист
```
Полный прогон на тяжёлых suite (W1-06: 37 тестов) > 400 с: первый форграунд-вызов таймаутится
(exit 124 — не дефект), повторять в фоне с большим wait. Всегда `TMPDIR=/tmp` + `PYTHONDONTWRITEBYTECODE=1`
(жёсткое read-only H), тесты в fone/taymaут.

## Write-scope дисциплина
Каждая W1-часть имеет allowlist файлов из `out/PREP-01-ADMISSION.md` (таблица `| W1-XX; ARCH:`)
и/или `out/ARCH-W1-DECOMPOSITION.md` (столбец files). `git diff --name-status <base>..HEAD` — первая
проверка: исполнитель не должен трогать чужой write-set и не должен создавать новые schema/test-файлы.

## Блокер ENV/транспорта
Если capability (external failure → worker rc75/78) НЕ ДОКАЗАНА на среде (ENV-03 NOT_PROVEN),
часть, зависящая от неё, остаётся OPEN с именованным owner; НЕ выдумывать HOST-carrying stub.
Продолжать на незаблокированных ветвях; блокер упакован честно (NOT_PROVEN) в отчёт и в
`out/W1-0X-CLOSE.md`, не декларировать её закрытой отчётом исполнителя.

## Ведение серии
- После закрытия части — переходить к следующей по серии без переспроса («Продолжай», «не спрашивай»).
- На каждый закрытый компонент писать `out/W1-0X-CLOSE.md`: HEAD, commit, независимую сверку, что
  материализовано, что открыто с owner, rollback-команду (`git revert <commit>`).
- Вопрос Саше — только при NEW-ENTITY (требует явного согласования) или реальной развилке своего
  мнения, а не на каждый переход/блокер: блокер не означает стоп серии.
- Premature/сомнительный срез исполнителя (зависший тест, незакоммиченные файлы) — откатить
  `git checkout -- <files>` на стабильный HEAD и чистый повтор, не цеплять полусделанный коммит.
