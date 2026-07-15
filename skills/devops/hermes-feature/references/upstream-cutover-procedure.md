# Upstream hermes-agent cutover — полная процедура (проверено 05.07.2026)

Контекст: апгрейд ~1679 коммитов апстрима (NousResearch/hermes-agent) в наш форк/боевой репо `~/hermes-agent`, живой gateway работает под systemd.

## -1. Предварительный анализ диффа апстрима (ДО решения об апгрейде, проверено 15.07.2026)

Применять когда Саша спрашивает «какая версия апстрима» / «стоит ли обновляться» / «что там нового» — до того как принято решение делать cutover (Блок 0-5 ниже). Это отдельный, более лёгкий шаг: только чтение, без изменений кода.

**1. Определить диапазон коммитов между нашей базой и HEAD апстрима:**
```bash
cd ~/hermes-agent
git fetch origin main
git log origin/main -1 --format="%h %ai %s"     # текущий HEAD апстрима
git log HEAD -1 --format="%h %ai %s"              # наша база (последний upstream-коммит перед первым нашим local commit)
git log <наша_база>..<HEAD апстрима> --format="%h %ai %s" > /tmp/upstream_diff_commits.txt
wc -l /tmp/upstream_diff_commits.txt
```

**⚠️ Питфолл: shallow clone ломает merge-base до явного deepen.** Наш `~/hermes-agent` — shallow clone (`git rev-parse --is-shallow-repository` → `true`). Обычный `git fetch origin main` тянет только новые коммиты сверху текущей shallow-границы — `git merge-base --is-ancestor <наша_база> origin/main` может вернуть `NO` (мнимая расходимость) просто потому что общий предок обрезан историей. Диагностика: `cat .git/shallow` покажет SHA границы. Фикс — углубить перед анализом:
```bash
git fetch origin main --depth=2000   # или больше, если диапазон коммитов явно длиннее
git merge-base --is-ancestor <наша_база> origin/main && echo YES || echo NO
```
Только после `YES` цифра `git log A..B --oneline | wc -l` достоверна.

**2. Категоризировать коммиты по ключевым словам (не читать все 400+ подряд):**
```bash
grep -iE "telegram|gateway|SIGTERM|drain" /tmp/upstream_diff_commits.txt
grep -iE "cron|delegat|subagent|heartbeat|stale" /tmp/upstream_diff_commits.txt
grep -iE "memory|skill" /tmp/upstream_diff_commits.txt
grep -iE "token|cost|cach|compress" /tmp/upstream_diff_commits.txt
grep -iE "crash|corrupt|WAL|lock|race|leak" /tmp/upstream_diff_commits.txt
grep -iE "config.yaml|env var|breaking|migrat|deprecat|remov" /tmp/upstream_diff_commits.txt   # проверка на breaking changes
```
Для коммитов, попавших в категории «часто используемый функционал» и «надёжность» — читать полное тело коммита (`git log <sha> -1 --format="%B"`), не только заголовок: заголовок часто не отражает реальный масштаб/причину фикса (пример: заголовок «cache PyJWKClient across fires» не говорит, что это чинит лишний HTTP-запрос на каждый крон-тик).

**3. Подавать вывод в 4-факторной рамке (формат, который сработал 15.07.2026):**
1. Потеря/донастройка конфигурации и скиллов (breaking changes — есть ли вообще)
2. Экономия токенов / снижение стоимости владения
3. Устранение ошибок в часто используемом функционале (мапить найденные фиксы на реальные прецеденты из наших `references/pitfalls-incidents.md` — если апстрим чинит ровно то, от чего мы уже страдали, это самый сильный аргумент «за»)
4. Устойчивость и надёжность (crash/corruption/deadlock фиксы)

Каждый пункт — коротко, простым языком, с конкретными примерами коммитов (заголовок + одна строка "почему это важно нам"), не общими фразами. Закончить одной строкой-итогом и вопросом («обновляем?» / «план обновления нужен?») — не решать за Сашу.

**3а. Дополнительные критерии (по запросу Саши, зафиксировано 15.07.2026)** — сверх основной 4-факторной рамки, добавлять при развёрнутом анализе, если применимо к найденному диффу:

5. **Риск конфликта с нашими локальными коммитами** — сверить список файлов апстрим-диффа (`git diff --name-only <база> <HEAD>`) со списком файлов, которые трогают наши local commits (`git log --name-only <база>..HEAD_local -- .` или аналог); пересечение = потенциальные конфликты при cherry-pick, не просто «применить».
6. **Нестабильность области (revert-сигнал)** — `revert "..."` сразу после `fix(...)` в той же области за несколько дней подряд = зона ещё штормит, разумно подождать 1-2 недели прежде чем обновляться именно на этом коммите.
7. **Security/auth-фиксы** — отдельно выделять `fix(auth)`, `security`, `CVE`, `credential`, `secret`; это единственная категория, где обновление может быть срочным вне зависимости от остальных факторов.
8. **Платформенный шум (Windows/macOS-only)** — на Linux VM фиксы под другие ОС (schtasks, macOS fsync и т.п.) нейтральны; выносить в отдельную категорию «не касается нас», чтобы объём диффа не завышал воспринимаемую релевантность.
9. **Новые фичи как апсайд, не только риск** — отдельно перечислять то, что можно осознанно начать использовать (новый провайдер, toolset, улучшение delegation), не только «что могло сломаться».
10. **Соотношение fix/test как грубый прокси качества** — доля `fix` без сопутствующего `test:` в критичных зонах (state/gateway/cron) — повод присмотреться внимательнее к конкретному коммиту.

**Важно:** этот анализ НЕ равен разрешению на cutover. Даже однозначно позитивный вывод («апстрим чинит наши болевые точки») — это рекомендация, реализация (Блок 0-5 ниже) стартует только по отдельному явному «делай»/«обновляй» от Саши (Блок 5Б основного скилла — `question-answer`/`own-inference` не дают права action).

## 0. Защита ДО любых git-операций

1. `cd ~/hermes-agent && git status --short` — **обязательно**, даже если задача выглядит как «просто git pull». Живой gateway может работать поверх незакоммиченных правок в working tree.
2. Если есть незакоммиченные изменения:
   - `git diff --stat` / `git diff <file>` — посмотреть что именно менялось, по каждому файлу понять логический смысл
   - Прогнать relevant тесты на текущем (старом) коде, чтобы убедиться что правки рабочие: `pytest tests/<relevant>/ -q`
   - Разбить на 2-4 логичных коммита по смыслу (НЕ один общий "wip snapshot") — упрощает cherry-pick и ревью
   - Удалить временные `.bak`-файлы после коммита (история git уже бэкап)
   - `git push fork <branch>` — push в fork-remote как независимая защита от потери, даже если основная ветка ещё не влита никуда
3. tar-бэкап конфига/кронов/скиллов (отдельно от git hermes-agent):
   ```bash
   mkdir -p ~/.hermes/_Archives
   tar -czf ~/.hermes/_Archives/hermes-backup-$(date +%Y%m%d-%H%M%S).tar.gz -C ~/.hermes config.yaml cron skills
   ```
4. `pip freeze > ~/hermes-workspace/upstream/pip-freeze-before-<date>.txt` — снапшот зависимостей.
5. Записать prev SHA в `~/hermes-workspace/upstream/rollback-history.txt`.
6. Написать/обновить `~/Upstream/RECOVERY.md` — самодостаточная инструкция отката (быстрый rollback командами, что НЕ делать при восстановлении, чеклист проверки после отката). Должна работать без контекста этой сессии — рассчитана на то, что её может выполнить другой ассистент (Cursor и т.п.).

## 1. Fetch + pull

```bash
git fetch origin --tags
git rev-list --count HEAD..origin/main   # сколько отстаём
git pull --ff-only origin main            # или checkout origin/main + reset --hard если ветка разошлась
```

Если наша ветка разошлась с main через локальные коммиты (не просто "позади") — `git pull --ff-only` откажет. В этом случае: `git branch -f <branch> origin/main` на самой ветке НЕ делать сразу — сначала high-level стратегия: перейти на main, `git reset --hard origin/main`, затем cherry-pick локальные коммиты (они уже отдельно защищены в fork из шага 0).

## 2. Cherry-pick локальных коммитов поверх нового upstream

```bash
git cherry-pick --no-commit <sha1> <sha2> <sha3> ...
```

При конфликте — **прежде чем брать "свою" сторону автоматически**, прочитать оба варианта:
- Если upstream решил ТУ ЖЕ проблему другой реализацией — сравнить полноту покрытия кейсов. Взять более полную реализацию (может быть upstream), не свою по умолчанию.
- Если это два независимых новых поля/фичи в одном файле (например оба добавляют разные dataclass-поля) — это union-merge, оставить оба, конфликт чисто текстовый.
- После разрешения: `python -m py_compile <file>` на каждый тронутый файл, `git add`, `git commit --no-edit` (сохраняет исходное сообщение коммита cherry-pick).
- Если наш тестовый файл проверял функцию, которая была заменена upstream-версией — **переписать тест под выжившую функцию**, сохраняя оригинальный intent проверок (не удалять файл, не оставлять сломанным).

## 3. Пересборка venv и smoke-check

```bash
source .venv/bin/activate
pip install -e ".[dev]" --upgrade
hermes --version    # должен показать "+N carried commits" если наши коммиты поверх upstream
hermes doctor
HERMES_HOME=~/.hermes hermes cron list   # схема jobs.json совместима?
```

## 4. Триаж тестовых падений — baseline diff, не паника

Полный regression suite неизбежно покажет N failed даже на чистом upstream (flaky тесты, тесты завязанные на конкретную live-систему, старые известные баги). Не считать это блокером автоматически.

```bash
# рабочая ветка (наши коммиты применены)
pytest tests/gateway/ -q > /tmp/our_test.log 2>&1   # используй background=true, суита ~8 мин

# baseline — чистый origin/main без наших коммитов, изолированная worktree
git worktree add /tmp/baseline-check origin/main
ln -s ~/hermes-agent/.venv /tmp/baseline-check/.venv   # переиспользуем venv, не пересобираем
cd /tmp/baseline-check && pytest tests/gateway/ -q > /tmp/baseline_test.log 2>&1

# сравнить
diff <(grep FAILED /tmp/baseline_test.log) <(grep FAILED /tmp/our_test.log)
```

- Падения, присутствующие в ОБОИХ логах → pre-existing, не наша забота.
- Падения ТОЛЬКО в нашей ветке → реальный регресс от cherry-pick, разобрать точечно (`pytest <file> -q` в изоляции, затем сравнить с/без нашего patch на том же файле через `git checkout origin/main -- <file>` временно).
- Убрать worktree после: `git worktree remove /tmp/baseline-check --force`.
- Файлы, которых нет в git (`git ls-tree HEAD -- <file>` пусто) но лежат на диске и падают — проверить `.git/info/exclude`: могут быть намеренно локально-игнорируемые тестовые артефакты, не относящиеся к апгрейду вообще.

## 5. Cutover (реальный рестарт)

Финальный шаг — рестарт gateway на новый код. **Только по явной команде пользователя** (см. Блок 5А в основном SKILL.md — рестарт изнутри заблокирован архитектурно, только `bash ~/.hermes/scripts/restart_gateway_MANUAL_ONLY.sh` из внешнего шелла пользователя).

## Питфоллы, найденные на практике (05.07.2026)

- Первый `pip install -e .` из тестовой копии-клона (`~/hermes-agent.next`) без собственного venv — переустановил пакет в ОСНОВНОЙ venv с pth-mapping на .next (потому что shebang/venv не был создан заново, `pip` резолвился в родительский). Всегда создавать отдельный `python3.11 -m venv` в клоне ПЕРЕД первым `pip install -e .`, не полагаться на скопированный `.venv`.
- Копия через `cp -r` тестового клона репо ~2GB — быстрее через `rsync -a` (20с в замере).
