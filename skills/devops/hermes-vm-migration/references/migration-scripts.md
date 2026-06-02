# Скрипты миграции VM

Все скрипты лежат в `C:\Users\tkachenkoav\WorkVault\Hermes-Backlog\MigrationToVM\`

## Готовые скрипты

| Скрипт | Блок | Статус |
|--------|------|--------|
| `setup_owncloud_vm.sh` | — | ✅ Выполнен 02.06.2026 |
| `master_migration.sh` | 0+1 | ✅ Блоки выполнены вручную |
| `block1_continue.sh` | 1 | ✅ Выполнен 02.06.2026 |
| `block2_personality.sh` | 2 | 🔄 В процессе |
| `migrate_usertools.sh` | 4 | ⬜ Не начат |

## Запуск (всегда из git-bash на Windows)

```bash
bash /c/Users/tkachenkoav/WorkVault/Hermes-Backlog/MigrationToVM/<script>.sh
```

## Паттерн скрипта с SSH-агентом (один пароль на весь скрипт)

```bash
#!/bin/bash
set -euo pipefail
VM="tkachenkoav@hermes-agents.devel.tutu.ru"
SSH_OPTS="-o ConnectTimeout=15 -o ServerAliveInterval=60 -o ServerAliveCountMax=10 -o StrictHostKeyChecking=no"
SSH="ssh $SSH_OPTS $VM"

# Один пароль в начале
eval "$(ssh-agent -s)"
ssh-add "/c/Users/tkachenkoav/.ssh/id_ed25519"

# Передача файла через stdin (без tar, мгновенно):
cat /local/file | $SSH "cat > /remote/file"

# Выполнение блока на VM:
$SSH 'bash -s' << 'REMOTE'
  # код выполняется на VM
REMOTE

# Конец — убиваем агент
eval "$(ssh-agent -k)" 2>/dev/null || true
```

## Известные питфоллы при написании скриптов

- `python3` → нет в git-bash, использовать `$(which python3 2>/dev/null || which python)`
- `tar czf` с большими папками (>100MB) → зависает молча, заменить на git clone прямо на VM
- Несколько `ssh` вызовов в скрипте → каждый просит пароль, использовать паттерн выше
- heredoc с переменными: `<< 'REMOTE'` (кавычки) = переменные не раскрываются на ноуте, `<< REMOTE` (без кавычек) = раскрываются. Использовать правильно по ситуации.
- `set -euo pipefail` в heredoc на VM: нужен отдельный `set -euo pipefail` в начале heredoc, не наследуется
