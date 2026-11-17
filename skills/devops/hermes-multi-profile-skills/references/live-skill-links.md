Source examples: normal find does not follow symlinks unless explicitly configured. Classify custom/bundled/hub before any conversion.

## КРИТИЧЕСКИЙ питфолл: симлинк в `profiles/default/skills/` НЕ делает скилл видимым

**Прецедент 04.09.2026 (`deep-mine-project`):** скилл существовал в git (`hermes-workspace/skills/research/deep-mine-project/`), симлинк был в `~/.hermes/profiles/default/skills/research/deep-mine-project` (sync-to-hermes.sh показывал «Already OK 163»), но агент его **не видел**: его не было в `<available_skills>`, `skill_view` его не находил, CLI из скилла не вызывался.

**Причина — ДВА СЛОЯ симлинков, а не один.** Сканируемый путь — НЕ `~/.hermes/profiles/default/skills/`, а **живой** `~/.hermes/skills/<category>/<name>`. Это отдельное дерево верхнеуровневых симлинков вида:
```bash
~/.hermes/skills/research/research-tools  ->  ../../profiles/default/skills/research/research-tools
~/.hermes/skills/research/workvault-rag   ->  ../../profiles/default/skills/research/workvault-rag
```
`sync-to-hermes.sh` / `restore-all-skills.sh` (`sync-to-hermes.sh default`) заполняют **только** `profiles/default/skills/` и НЕ трогают этот живой верхний слой. Поэтому скилл может быть в профиле, но невидим агенту.

**Симптом диагностики:** у `ls ~/.hermes/skills/research/` видны старожилы (`research-tools`, `workvault-rag`), а нового скилла нет, при этом в `profiles/default/skills/research/` он есть.

**Фикс (создать живой симлинк):**
```bash
cd ~/.hermes/skills/research && \
  ln -s ../../profiles/default/skills/research/deep-mine-project deep-mine-project
```
После этого `skill_view(name)` и `<available_skills>` начинают видеть скилл.

**Проверка после ЛЮБОГО добавления кастомного скилла:** не ограничиваться `find ~/.hermes/profiles/default/skills/` — обязательно убедиться, что скилл появился в живом `~/.hermes/skills/<category>/<name>` (и воспроизводится `skill_view`). Если новый скилл «невидим» — проверять этот верхний слой ПЕРВЫМ делом, прежде чем искать проблему в git/профиле.

**Принципы:**
- **Git** — единственный канонический источник кастомных скиллов. WorkVault НЕ используется (rsync перетирает).
- **default** — профиль Hermes, куда симлинками подключаются кастомные скиллы из git.
- Скрипты идемпотентны — можно запускать многократно без вреда.


## Скиллы, которые НЕ в git: реальная папка vs симлинк

**Прецедент 15.08.2026** (`hermes-prompt-architecture`): канонический источник — `~/hermes-workspace/skills/` (git-репо). Но часть dev-скиллов лежит **реальной папкой** прямо в `~/.hermes/skills/devops/`, не являясь симлинком на workspace → они вне git, не версионируются, autosync их не пушит. После правки `git status` в workspace молчит.

**Проверка связи:**
```bash
readlink -f ~/.hermes/skills/devops/<name>/SKILL.md
# возвращает тот же путь → НЕ симлинк → скилл вне git
# ведёт на ~/hermes-workspace/… → ок, под контролем
```
Проверить в git: `cd ~/hermes-workspace && git ls-files | grep -c <name>` (0 → вне версионирования).

**Подключить к версионированию (только для КАСТОМНЫХ скиллов):**

Store/bundled-скиллы (skill-store/hub-managed) НЕ переносить в симлинк: hub-installer (`_resolve_lock_install_path`) отклоняет symlink как `Unsafe install path`, их install/update сломаются — они обязаны остаться физическими. Разделять по автору/маркеру `.hub/lock.json` до переноса.

```bash
cp -r ~/.hermes/skills/devops/<skill> ~/hermes-workspace/skills/devops/<skill>
cd ~/hermes-workspace && git add -A && git commit && git push
```

**Питфолл — реальная папка затеняет свежую правку симлинка-источника:** если скилл живёт реальной папкой в `~/.hermes/skills/` (НЕ симлинк), то правка в canonical-источнике (`~/hermes-workspace/skills/…`) НЕ доходит до runtime — `skill_view`/агент продолжают читать старую копию, даже если `sync-to-hermes.sh` уже создал симлинк в `profiles/default/skills/`. Исполнитель, правящий скилл, часто касается только canonical (workspace) и не обновляет живую папку — self-report «правка внесена» при этом верен для источника и ЛОЖЕН для runtime.

**Проверка эффективности правки — по runtime-версии, не по источнику:** после патча скилла проверять `grep '^version:' ~/.hermes/skills/<cat>/<name>/SKILL.md` (тот путь, что реально читает агент), а не `~/hermes-workspace/…`. Старый номер в живом пути = правка не подхвачена, сколько бы её ни декларировал исполнитель.

**Завершающий шаг — конвертировать реальную папку в симлинк (с бэкапом):**
```bash
TS=$(date +%Y%m%d-%H%M%S); BK=~/.hermes/_Archives/skill-sync-fix-$TS; mkdir -p "$BK"
cp -a ~/.hermes/skills/<cat>/<name> "$BK/"
rm -rf ~/.hermes/skills/<cat>/<name>
ln -s ../../profiles/default/skills/<cat>/<name> ~/.hermes/skills/<cat>/<name>
```
После — повторно сверить версию в живом пути: совпадает с источником. Это восстанавливает канон «скилл = симлинк на workspace» и убирает источник будущих рассинхронов. Прецедент: `kanban-dev-pipeline-orchestration` и `cron-troubleshooting` жили реальными папками со старыми версиями; правка в canonical не достигала runtime до конвертации.


## Питфолл: `find -type d -name X` не проходит через симлинки — ложный NOT_FOUND

При локации скилла для правки не используй `find <root> -maxdepth N -type d -name "<skill>"` — он НЕ обходит симлинки и врёт «NOT_FOUND» про скиллы, которые существуют как симлинк на `~/hermes-workspace/skills/`. Это стоит времени, когда хочется снять размер/найти физический файл перед патчем.

**Правильный поиск — через файл, не директорию** (проходит сквозь симлинк):
```bash
find ~/hermes-workspace/skills ~/.hermes/skills -name SKILL.md -path "*/<name>/SKILL.md"
```
**Физический путь (readlink-разрешённый) для правки:**
```bash
readlink -f ~/.hermes/skills/<cat>/<name>/SKILL.md   # ведёт на ~/hermes-workspace/… = симлинк→git
readlink -f ~/.hermes/skills/<cat>/<name>/SKILL.md   # тот же путь = реальная папка вне git
```

**Корень НЕ единый:** большинство скиллов физически в `~/hermes-workspace/skills/`, но часть живёт реальной папкой ТОЛЬКО в `~/.hermes/skills/<cat>/` без симлинка в workspace (напр. `confluence-minutki-creation`). Искать по обоим корням и править по readlink-разрешённому пути, а не хардкодить workspace-путь заранее.

