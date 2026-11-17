

# Material moved from MOFS SKILL.md

> История исходника (даты указаны внутри), не текущая инструкция; актуальные условия — в SKILL.md.

## Запуск прогонов — обязательный порядок

**Всегда начинать с dry-run:**
```bash
cd ~/USERTOOLS/MarkObjectsFromSummary
source ~/USERTOOLS/ProtocolFromSummary/.venv/bin/activate

# 1. dry-run — убедиться в плане
mofs run --dry-run --from 2026-07-01 --to 2026-07-31

# 2. только после проверки плана — реальный прогон
mofs run --from 2026-07-01 --to 2026-07-31

# 3. точечно — одна встреча (только через --meeting-id, БЕЗ пути к файлу!)
mofs run --meeting-id "2026-07-08 11-05-00 Кирилл 1-1" --dry-run
```

**⚠️ КРИТИЧНО: `mofs run` НЕ принимает путь к файлу как позиционный аргумент.**
`mofs run "/path/to/summary.md" --yes` → `error: unrecognized arguments` (exit 2).
`--meeting-id` принимает строку meeting_id формата `YYYY-MM-DD HH-MM-SS Название` — **без суффикса ` - summary.md`**.

**Safeguard (v0.7.0):**
- `run`/`rematch` без скоупа → `exit 2`
- `rematch --all` без `--yes` → показывает N встреч, требует `--yes`
- `--mode=cron` — safeguard не применяется

## Bootstrap всего архива (когда крон поработает 1-2 недели)

```bash
# 1. снапшот
mofs bootstrap --snapshot

# 2. dry-run — убедиться
mofs rematch --all --dry-run

# 3. только после проверки — реальный прогон
mofs rematch --all --yes
```

При bootstrap создаётся манифест `state/bootstrap_manifest_<ts>.json`.
Откат: `mofs bootstrap --undo latest --yes`.

## Управление entities.json

**Только через `entity-registry` CLI — никогда не редактировать вручную.**

```bash
# Просмотр
entity-registry list

# Добавить alias к существующей сущности
entity-registry edit <slug> aliases "<alias>" --append -y

# Удалить alias
entity-registry edit <slug> aliases "<alias>" --remove-item -y

# Добавить новую сущность (--parent-null обязателен для проектов без родителя!)
entity-registry add <slug> --kind project --display-name "Название" --alias "алиас1" --alias "алиас2" --parent-null -y
# ВАЖНО: --aliases "a,b,c" не работает — только --alias повторяется для каждого значения
# ВАЖНО: без --parent-null будет ошибка "missing_required: parent"
```

## Obsidian-ссылки для проверки файлов

Генерация кликабельных ссылок:
```python
import urllib.parse
vault = "WorkVault"
file_path = "Meetings/NewMeetings/2026-07-08 11-05-00 Кирилл 1-1 - summary.md"
encoded = urllib.parse.quote(file_path, safe='/')
print(f"obsidian://open?vault={vault}&file={encoded}")
```

