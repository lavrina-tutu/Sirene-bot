# План реорганизации GitHub-репозиториев

**Автор:** Opus-воплощение Сирени
**Дата:** 2026-05-23
**Контекст:** консолидация `workvault-tools` + `hermes-config` в один репозиторий с upstream-трекингом NousResearch/hermes-agent.

---

## 0. Состояние на момент планирования

### Что есть сейчас
| Репозиторий | Назначение | Последний коммит | Remote |
|---|---|---|---|
| `Documents/Cursor_projects/MoveFromFF` | код MoveFromFF + tests + venv | `b0e07ba Initial commit: MoveFromFF tool` (22.05) | `workvault-tools` |
| `Documents/Cursor_projects/hermes-config` | config.yaml + skills/ + Hermes-Backlog/ | `d8503f7 auto-sync 2026-05-23 02:01` | `hermes-config` |
| `Documents/Cursor_projects/hermes-agent` | клон upstream NousResearch (отстаёт от main на ~3 дня) | — | upstream NousResearch |

### Результаты ночных задач
- ✅ `bc1b0ae442f0` GitHub автосинк — **OK**, push прошёл 02:01:36 MSK, оба репо обновлены.
- ⚠️ `ea18f323a671` MoveFromFF тест с FF API — **частично не отработала**. По логам `logs/movefromff.jsonl`:
  - 00:11:51 (dry-run) → `FATAL: FF GraphQL error: Too many requests. Please retry after Sat, 23 May 2026 00:00:00 GMT (UTC)` (т.е. 03:00 MSK)
  - 01:01:11 (без dry-run) → та же ошибка с тем же UTC retry-after
  - Похоже cron сработал раньше, чем сбросился rate-limit FF. **Текущий next_run этой задачи = 24 мая 00:10** (она `once`), повторно не пойдёт. Нужно вручную пересоздать или подождать вечернего ретеста.
- ✅ `e7a53b2e2cf2` Сирень self-check — отчёт сформирован, рекомендации зафиксированы (модели крона → Haiku, обновить hermes-agent, поправить `display.personality`).

### Что важно учесть
- В `hermes-config/Hermes-Backlog/` уже лежит копия бэклога (синкается из `WorkVault/Hermes-Backlog/`).
- В `hermes-config/skills/` уже лежит копия скиллов (синкается из `AppData/Local/hermes/skills/`).
- В `MoveFromFF` есть `.venv/`, `.coverage`, `logs/`, `.locks/` — **их нельзя коммитить**.
- `config.yaml` синкается с вычищенными токенами (как уже устроено в текущем автосинке).

---

## 1. Целевая структура единого репозитория

**Имя:** `hermes-workspace` (или оставить `hermes-config` и переименовать на GitHub).
**Видимость:** private.

```
hermes-workspace/
├── README.md                       # карта репозитория и быстрый старт
├── LICENSE                         # (если применимо)
├── .gitignore                      # объединённый
├── .gitattributes
│
├── config/                         # личный конфиг Hermes
│   ├── config.yaml                 # БЕЗ секретов (как и сейчас, токены вычищены)
│   └── README.md                   # описание профиля и привязок
│
├── skills/                         # пользовательские скиллы (как сейчас в hermes-config/skills/)
│   ├── persona/
│   ├── productivity/
│   ├── software-development/
│   └── ...
│
├── tools/                          # ★ инструменты семейства MoveFrom*/WorkVault
│   ├── README.md                   # обзор: статус каждого инструмента (ready/wip/planned)
│   ├── shared/                     # общая инфраструктура (логгер, lock, конфиг-loader)
│   │   └── ...
│   ├── movefromff/                 # ← MoveFromFF (бывший workvault-tools)
│   │   ├── movefromff/             # код
│   │   ├── tests/
│   │   ├── scripts/
│   │   ├── README.md
│   │   ├── requirements.txt
│   │   └── .env.example
│   ├── movefromjira/               # ← планируется (OKRAID + OKRS)
│   ├── movefromexchange/           # ← планируется (GAL + mail/calendar)
│   ├── movefromconfluence/         # ← планируется
│   └── movefromzulip/              # ← планируется
│
├── workflows/                      # межинструментные процессы
│   ├── task-from-tg/               # быстрая постановка задачи через TG
│   └── ...
│
├── docs/                           # бэклог, ТЗ, vision
│   ├── backlog.md                  # ← Hermes-Backlog/backlog.md
│   ├── automation-tools-vision.md
│   ├── tz/                         # все *_TZ_*.md
│   │   ├── MoveFromFF_TZ_v1.md
│   │   ├── MoveFromFF_TZ_v1.1_addendum.md
│   │   ├── MoveFromFF_TZ_v2.0_minimal.md
│   │   ├── MarkObjectsFromSummary_TZ_v0.1.md
│   │   └── MarkObjectsFromSummary_Brief_Questions.md
│   └── self-checks/                # архив утренних self-check от Сирени
│       └── self-check-YYYY-MM-DD.md
│
├── upstream/                       # ★ трекинг апстрима NousResearch/hermes-agent
│   ├── README.md                   # процедура обновления и отката
│   ├── pinned-version.txt          # commit hash / тег upstream, на котором сейчас работает Hermes
│   └── changelog.md                # ручные заметки по релевантным изменениям upstream
│
└── scripts/                        # сервисные скрипты
    ├── autosync.sh                 # обновлённый GitHub-автосинк под новую структуру
    ├── upstream_update.sh          # обновление hermes-agent c пина + бэкап
    ├── upstream_rollback.sh        # откат к предыдущему пину
    └── doctor.sh                   # проверка здоровья репо (нет venv, нет токенов и т.п.)
```

**Принципы структуры:**
1. `tools/<name>/` — каждый инструмент самодостаточен: свой `requirements.txt`, `tests/`, `scripts/`, `README.md`. Никакой общий venv — каждый создаёт свой `.venv` в своей папке (gitignored).
2. `tools/shared/` — реально общий код, если что-то экстрагируется (логгер, конфиг-loader, lock-механизм). Пока пусто.
3. Скиллы и конфиг идут как `skills/` и `config/` — Hermes уже умеет их хавать из `~/AppData/Local/hermes/`, поэтому **репозиторий — это бэкап и source-of-truth, но НЕ runtime-папка**. Автосинк копирует туда-сюда.
4. `upstream/` — отдельная папка-метаданные. Сам hermes-agent живёт в `Documents/Cursor_projects/hermes-agent/` (отдельный клон), здесь лишь зафиксированный pinned commit и changelog.

---

## 2. Механизм upstream-трекинга hermes-agent

### Архитектура (вариант A — рекомендуемый: отдельный клон + pin-файл)

`hermes-agent` живёт в **отдельном репозитории-клоне** `Documents/Cursor_projects/hermes-agent`, **не внутри** `hermes-workspace`. Внутри `hermes-workspace/upstream/` хранится только метаинформация: какой commit/тег upstream сейчас считается «работающим у Саши».

**Почему так:**
- Submodule заведёт ад с обновлениями скиллов и приведёт к тому, что Hermes не будет работать пока не запушишь submodule reference.
- Fork тоже не нужен — патчей пользовательских в код Hermes мы не делаем; пользовательский слой = `config.yaml` + `skills/`, который уже отдельно живёт.
- Поэтому: hermes-agent тянем как обычный клон upstream, а в `upstream/pinned-version.txt` фиксируем «golden commit» и changelog.

### Структура `upstream/`

`upstream/pinned-version.txt`:
```
commit:  <sha>
tag:     v<x.y.z>   # если есть
date:    2026-05-20
notes:   последний коммит до релиза security-фикса API-key leakage
```

`upstream/changelog.md` — ручные заметки:
```
## 2026-05-23
- Перешли с <old_sha> на <new_sha>
- Релевантные изменения:
  - fix(security): защита от утечки API-ключей в неаутентичные custom endpoints
  - Observe unmentioned Telegram group messages → проверить gateway.telegram.allowed_chats
- Затронуты ли наши скиллы: нет
- Затронут ли config.yaml: проверить блок gateway.telegram
```

### Скрипт `scripts/upstream_update.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

HA="$HOME/Documents/Cursor_projects/hermes-agent"
WS="$HOME/Documents/Cursor_projects/hermes-workspace"

cd "$HA"

# 1. сохраняем текущий pin как rollback
CURRENT=$(git rev-parse HEAD)
echo "previous: $CURRENT" >> "$WS/upstream/rollback-history.txt"

# 2. бэкапим venv-pins (на всякий)
pip freeze > "$WS/upstream/pip-freeze-before-$(date +%F).txt" || true

# 3. фетчим upstream и показываем что прилетит
git fetch origin --tags
git --no-pager log --oneline "$CURRENT..origin/main" | head -50

# 4. обновляем
git pull --ff-only origin main

# 5. фиксируем новый pin
NEW=$(git rev-parse HEAD)
TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")
cat > "$WS/upstream/pinned-version.txt" <<EOF
commit:  $NEW
tag:     $TAG
date:    $(date +%F)
prev:    $CURRENT
EOF

# 6. пересобираем venv (Hermes требует обновления зависимостей часто)
source "$HA/.venv/bin/activate" 2>/dev/null || source "$HA/venv/bin/activate"
pip install -e . --upgrade

# 7. smoke-тест
hermes --version
hermes doctor || true

echo "OK. Pinned: $NEW. Откат: bash scripts/upstream_rollback.sh"
```

### Скрипт `scripts/upstream_rollback.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

HA="$HOME/Documents/Cursor_projects/hermes-agent"
WS="$HOME/Documents/Cursor_projects/hermes-workspace"

PREV=$(grep '^prev:' "$WS/upstream/pinned-version.txt" | awk '{print $2}')
[ -z "$PREV" ] && { echo "Нет prev в pinned-version.txt"; exit 1; }

cd "$HA"
git checkout "$PREV"

source "$HA/.venv/bin/activate"
pip install -e . --force-reinstall

hermes --version
echo "Откатились на $PREV"
```

### Процедура обновления (вручную или из крона)

1. **Раз в неделю** (вс 04:00) запускать `upstream_update.sh` через cron.
2. После апдейта `hermes doctor` + `hermes --version` отправляются в TG.
3. Если что-то сломалось — `upstream_rollback.sh`.
4. Тэги/commit-хэши, на которых работала система, остаются в `rollback-history.txt` — всегда можно вернуться к любому.

---

## 3. Пошаговый план миграции

### Шаг 0 — Подготовка (5 мин)
- [ ] Убедиться, что текущий автосинк (02:00) не запущен прямо сейчас (lock).
- [ ] Сделать резервные ZIP-копии локальных `MoveFromFF/` и `hermes-config/` в `WorkVault/_backups/2026-05-23/`.
- [ ] Прочитать `pinned-version.txt` в hermes-agent (если нет — зафиксировать текущий HEAD).

### Шаг 1 — Создать новый репо `hermes-workspace` (10 мин)
- [ ] На GitHub: создать **новый** private-репо `ialextkachenko-byte/hermes-workspace` (без шаблона, без README).
- [ ] Локально: `mkdir -p Documents/Cursor_projects/hermes-workspace && cd $_ && git init -b main`.
- [ ] Создать каркас директорий (см. структуру выше), пока пустыми `.gitkeep`.
- [ ] Написать корневой `README.md` (карта репо).
- [ ] Написать `.gitignore` — объединить правила из обоих старых репо, плюс:
  ```
  .venv/
  venv/
  __pycache__/
  *.pyc
  .pytest_cache/
  .coverage
  .env
  *.log
  logs/
  .locks/
  ```
- [ ] **Чек:** `git status` чистый, директории на месте.

### Шаг 2 — Перенести MoveFromFF в `tools/movefromff/` (15 мин)
- [ ] `cp -r MoveFromFF/{movefromff,tests,scripts,README.md,requirements.txt,.env.example,.gitignore} hermes-workspace/tools/movefromff/`
- [ ] **НЕ копировать:** `.venv/`, `.coverage`, `.pytest_cache/`, `logs/`, `.locks/`, `.env`.
- [ ] Подправить `tools/movefromff/README.md` — указать новый путь и как запускать.
- [ ] Создать новый `tools/movefromff/.venv` (свежий) и `pip install -r requirements.txt`.
- [ ] **Чек:** `cd tools/movefromff && .venv/Scripts/python -m pytest tests/ -x` → все тесты зелёные.
- [ ] **Чек:** `python -m movefromff --help` отвечает.

### Шаг 3 — Перенести skills/, config/, docs/ (10 мин)
- [ ] `cp -r hermes-config/skills/* hermes-workspace/skills/`
- [ ] `cp hermes-config/config.yaml hermes-workspace/config/config.yaml`
- [ ] `cp -r hermes-config/Hermes-Backlog/* hermes-workspace/docs/` затем перенести ТЗ в `docs/tz/`, self-checks в `docs/self-checks/`, оставить `backlog.md` и `automation-tools-vision.md` в корне `docs/`.
- [ ] **Чек:** структура соответствует целевой; в `config/config.yaml` нет токенов (`grep -E 'sk-|ghp_|tg_token' config/config.yaml` пусто).

### Шаг 4 — Upstream-метаданные (10 мин)
- [ ] Создать `upstream/pinned-version.txt` с текущим HEAD клона hermes-agent.
- [ ] Создать `upstream/changelog.md` с первой записью.
- [ ] Создать `upstream/rollback-history.txt` (пустой).
- [ ] Написать `upstream/README.md` с инструкцией для будущей Сирени.

### Шаг 5 — Скрипты (15 мин)
- [ ] `scripts/autosync.sh` — обновлённая версия (см. секцию 4 ниже).
- [ ] `scripts/upstream_update.sh` + `upstream_rollback.sh` (см. секцию 2).
- [ ] `scripts/doctor.sh` — проверки: нет venv в индексе, нет .env, нет токенов в config.yaml.
- [ ] `chmod +x scripts/*.sh`.
- [ ] **Чек:** `bash scripts/doctor.sh` → ok.

### Шаг 6 — Первый коммит и push (5 мин)
- [ ] `git add -A && git commit -m "feat: initial consolidated structure (workvault-tools + hermes-config)"`.
- [ ] `git remote add origin https://<TOKEN>@github.com/ialextkachenko-byte/hermes-workspace.git`.
- [ ] `git push -u origin main`.
- [ ] **Чек:** на GitHub видна полная структура; `git clone` в `/tmp` работает.

### Шаг 7 — Обновить cron-задачу автосинка (10 мин)
- [ ] Отредактировать prompt в задаче `bc1b0ae442f0`:
  - старые источники → новые пути в `hermes-workspace`
  - убрать push в `workvault-tools` и `hermes-config`
  - добавить push в `hermes-workspace`
- [ ] **Чек:** `hermes cron run bc1b0ae442f0` отрабатывает без ошибок (или дождаться ночного запуска).

### Шаг 8 — Архивирование старых репо (5 мин)
- [ ] На GitHub:
  - `workvault-tools` → Settings → Archive (read-only).
  - `hermes-config` → Settings → Archive.
  - В описании каждого: `Moved to ialextkachenko-byte/hermes-workspace`.
- [ ] Локально: переименовать `MoveFromFF/` → `MoveFromFF.archived/` и `hermes-config/` → `hermes-config.archived/`. Через неделю — удалить.

### Шаг 9 — Smoke-тесты (10 мин)
- [ ] MoveFromFF из новой папки: `cd tools/movefromff && .venv/Scripts/python -m movefromff --mode manual --from-date 2026-05-21 --to-date 2026-05-22 --dry-run`.
- [ ] Hermes по-прежнему видит скиллы (они в `~/AppData/Local/hermes/skills/`, репо — это бэкап).
- [ ] Cron автосинк не падает.

### Шаг 10 — Обновить cron-задачу теста MoveFromFF (5 мин)
- [ ] В задаче `ea18f323a671` поменять путь `Cursor_projects/MoveFromFF` → `Cursor_projects/hermes-workspace/tools/movefromff`.
- [ ] (Опционально) Сделать её recurring `0 0 * * *` вместо `once`, раз rate-limit FF блочит ночные пробы.

---

## 4. Обновлённый autosync

`scripts/autosync.sh` (заменит prompt в cron-задаче `bc1b0ae442f0`):

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO="$HOME/Documents/Cursor_projects/hermes-workspace"
TOKEN=$(grep '^GITHUB_TOKEN=' "$HOME/Documents/Cursor_projects/hermes-workspace/.env" 2>/dev/null | cut -d= -f2)
[ -z "$TOKEN" ] && TOKEN=$(grep '^GITHUB_TOKEN=' "$HOME/Documents/Cursor_projects/hermes-workspace/tools/movefromff/.env" | cut -d= -f2)

cd "$REPO"

# 1. подтянуть свежие скиллы
rsync -a --delete \
  --exclude '__pycache__' \
  "$HOME/AppData/Local/hermes/skills/" "skills/"

# 2. подтянуть бэклог и self-checks
rsync -a "$HOME/WorkVault/Hermes-Backlog/" "docs/" \
  --include='backlog.md' \
  --include='automation-tools-vision.md' \
  --include='self-check-*.md' \
  --include='*_TZ_*.md' \
  --include='*_Brief_*.md'

# 3. config.yaml — копия с обнулением секретов
python "$REPO/scripts/sanitize_config.py" \
  "$HOME/AppData/Local/hermes/config.yaml" \
  "$REPO/config/config.yaml"

# 4. doctor-проверки перед коммитом
bash "$REPO/scripts/doctor.sh"

# 5. коммит и push
git remote set-url origin "https://${TOKEN}@github.com/ialextkachenko-byte/hermes-workspace.git"
git add -A
git diff --cached --quiet && { echo "no changes"; exit 0; }
git commit -m "auto-sync $(date '+%Y-%m-%d %H:%M')"
git push origin main
```

`scripts/doctor.sh` — отказывает push если:
- в индексе появилась `.venv/` или `__pycache__/`
- в `config/config.yaml` встречается паттерн токена (`sk-ant-`, `ghp_`, длинная hex-строка возле слова `token`)
- в `tools/*/` появился файл `.env` (только `.env.example` разрешён)

---

## 5. Риски и митигация

| Риск | Вероятность | Влияние | Митигация |
|---|---|---|---|
| Токены утекут в публичный коммит | low | **critical** | `doctor.sh` блокирует commit; `config.yaml` санитизируется отдельным скриптом; репо приватный |
| MoveFromFF после переезда не запустится (импорты, пути) | medium | medium | Smoke-тест на Шаге 9 + сохранены резервные ZIP; модуль `movefromff` уже самодостаточен (`python -m movefromff`) |
| Cron автосинк сломается из-за изменения путей | medium | low | Обновить prompt задачи **в той же транзакции**, что и push; на следующее утро проверить статус |
| Rate-limit FF блокирует ночные тесты | high (уже наблюдается) | low | Перенести `ea18f323a671` на 04:00 MSK или сделать recurring; в коде MoveFromFF — graceful exit на 429 (уже есть) |
| Кто-то локально продолжит коммитить в `MoveFromFF/` (старый клон) | low | low | Локально переименовать в `.archived/`, на GitHub — archive flag, README указывает на новое место |
| Submodule/upstream-pin сбивается при обновлении hermes-agent | low | medium | Отдельный клон (не submodule), `pinned-version.txt` + `rollback-history.txt` обеспечивают возврат к любому состоянию; rollback-скрипт |
| Скиллы локально и в репо разойдутся | medium | low | Автосинк rsync с `--delete` обеспечивает one-way синк локальное→репо. Если кто-то правит в репо напрямую — потеряется. Принцип: «локальное — source of truth, репо — зеркало». Зафиксировать в README. |
| Размер репо вырастет из-за LaTeX-шаблонов в `skills/research/` | low | low | Принять; либо вынести их в .gitignore, оставив один README с ссылкой на upstream Anthropic skills |

---

## 6. Что **не** входит в эту миграцию (отдельные задачи)

- Доработки MoveFromFF (убрать actions.md, оптимизация ping в cron) — из бэклога.
- Создание MoveFromExchange / MoveFromJira — отдельные эпики.
- Переезд на Haiku-модель для cron-задач — из self-check Сирени (`hermes cron edit`).
- `hermes-agent git pull` для security-фиксов — рекомендуется **сделать ДО** миграции, чтобы новый клон уже был на актуальной версии.

---

## 7. Чек-лист «миграция выполнена»

- [ ] `hermes-workspace` существует, структура соответствует разделу 1
- [ ] MoveFromFF запускается из новой папки и проходит тесты
- [ ] Hermes по-прежнему видит скиллы локально
- [ ] Cron-автосинк прошёл успешно хотя бы один раз с новой структуры
- [ ] `pinned-version.txt` создан, `upstream_update.sh` smoke-тестирован (dry-run без `git pull`)
- [ ] Старые репо архивированы на GitHub
- [ ] В TG отправлено резюме результата

---

*Готовность плана: high. Время выполнения целиком: ~90 минут. Рекомендую выполнять задачей в крон-окне 10:00 MSK с пошаговыми чеками и финальным TG-репортом.*
