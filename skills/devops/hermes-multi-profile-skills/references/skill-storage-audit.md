# Аудит и приведение хранения скиллов к канону (всё в git)

Класс: «проверь что все скиллы хранятся единообразно и синкаются с git; если нет — перенеси по канону: план → ревизор → перенос → тест» (процесс Саши).

## Канон хранения

Цепочка рабочего каталога: `~/.hermes/skills/<cat>/<name>` (живой слой, сканируется агентом) → симлинк на `~/.hermes/profiles/default/skills/<cat>/<name>` → симлинк на `~/hermes-workspace/skills/<cat>/<name>` (git-источник). Физическая директория в `~/.hermes/skills` БЕЗ симлинка на workspace = скилл вне git: нет истории/бэкапа, автосинк не пушит.

## Аудит одним проходом (Python)

```python
import pathlib
h = pathlib.Path.home()
ws_set = {p.parent.name for p in (h/'hermes-workspace'/'skills').rglob('SKILL.md')}
violators = []
for p in (h/'.hermes'/'skills').rglob('SKILL.md'):
    d = p.parent
    if d.name in ws_set: continue
    cat = d.parent.name if d.parent.parent.name == 'skills' else '.'
    violators.append({'name': d.name, 'cat': cat, 'link': d.is_symlink(),
                      'size': sum(f.stat().st_size for f in d.rglob('*') if f.is_file())})
```

Категоризация по `author:` в frontmatter: `agent`/`sirene`/`Сирень`/отсутствует → кастомный, переносить; `Nous Research`/`Ben Barclay`/`Chris Kim`/`Orchestra Research` → ванильный store-скилл — НЕ переносить. **Store/bundled-скиллы принципиально нельзя переводить в симлинк:** hub-installer проверяет каждый компонент пути (`_resolve_lock_install_path`) и отклоняет symlink как `Unsafe install path`, поэтому их install/update/uninstall сломаются после замены каталога на симлинк. Держать их физическими; их отсутствие в git легитимно — бэкап это полный tgz-бэкап ВМ. Store-маркер смотреть не только по author, но и по sidecar `~/.hermes/skills/.hub/lock.json`/`.locks` в каталоге скилла.

## Механика переноса одного скилла

```bash
# 1. Бэкап ВСЕХ нарушителей одной папкой до любых изменений
BK=~/.hermes/_Archives/skill-canon-fix-$(date +%Y%m%d); mkdir -p "$BK"
cp -a ~/.hermes/skills/<cat>/<name> "$BK/"   # cat=. для root-скиллов: ~/.hermes/skills/<name>
# 2. mv физический каталог в репо (root-скиллы: workspace/skills/<name> без категории)
mv ~/.hermes/skills/<cat>/<name> ~/hermes-workspace/skills/<cat>/<name>
# 3. симлинк уровня профиля
mkdir -p ~/.hermes/profiles/default/skills/<cat>
ln -s ~/hermes-workspace/skills/<cat>/<name> ~/.hermes/profiles/default/skills/<cat>/<name>
# 4. живой верхний слой — БЕЗ него скилл невидим агенту (обязательно)
ln -s ../../profiles/default/skills/<cat>/<name> ~/.hermes/skills/<cat>/<name>
# 5. идемпотентная проверка/досоздание
~/hermes-workspace/sync-to-hermes.sh default
# 6. git
cd ~/hermes-workspace && git add skills/ && git commit
```

Root-скиллы (без категории) `sync-to-hermes.sh` НЕ обрабатывает (пропускает `category=`.`): их симлинки создаются только вручную (шаг 4) и после `hermes update` не пересоздаются автоматически.

## Верификация после переноса

- До миграции снять baseline: SHA-256 каждого физического SKILL.md + служебных sidecar (`~/.hermes/skills/.usage.json`, `.usage.json.lock`, `.hub/lock.json`, `.locks`). После — сравнить: sidecar и все store/bundled-скиллы должны иметь те же хэши (cp/mv их не трогает; изменение = нечаянная модификация чужого).
- `readlink -f ~/.hermes/skills/<cat>/<name>/SKILL.md` ведёт на `~/hermes-workspace/…`, а не на себя.
- `cd ~/hermes-workspace && git ls-files | grep -c <name>` > 0.
- `skills_list` + `skill_view` на 3–5 случайных перенесённых скиллах — без ошибок (живой слой виден).
- Повторный `sync-to-hermes.sh default` — «Already OK», без новых `[NEW]`/`[FIX]`.

## Питфоллы

- Ручной подсчёт числа нарушителей нестабилен (86/90/165 в зависимости от метода: `find` без `-L` не ходит по симлинк-директориям, `pathlib.rglob().resolve()` и `is_symlink()` вводят в заблуждение на двухслойных цепочках). Надёжный способ: `find -L ~/.hermes/skills -name SKILL.md -type f` + `realpath`, и только потом классификация. Точные цифры в план не зашивать — инвентаризацию делать шагом 0 самого переноса (исполнителем), с SHA-манифестом.
- Перенести файлы в git и забыть шаг 4 (живой симлинк `~/.hermes/skills/<cat>/<name>`) → скилл «в git/профиле, но невидим агенту» (двухслойная архитектура).
- `find -type d -name X` не проходит через симлинки — искать по файлу: `find ~/hermes-workspace/skills ~/.hermes/skills -name SKILL.md -path "*/<name>/SKILL.md"`.
- Категорию при mv сохранять: перекладка в другую категорию ломает относительные пути/ссылки в SKILL.md.
- Перед переносом обязателен бэкап ВСЕХ нарушителей одной папкой (не по одному).
- Ванильные store/bundled-скиллы НЕ переносятся в симлинк вовсе — hub-installer (`_resolve_lock_install_path`) отвергает symlink как `Unsafe install path`, их обновления сломаются. Это не «развилка из двух вариантов», а фиксированное архитектурное ограничение: в git+симлинк идут только кастомные, store-скиллы обязаны остаться физическими (их отсутствие в git покрыто полным tgz-бэкапом ВМ).
