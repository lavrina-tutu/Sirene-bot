# Вызов роли и граница wrapper

Нормы процесса — Б55 и `../SKILL.md`; backend и модели — YAML `tools.dev_workflow`.

```text
pipeline emit-prompt --slug <slug> --phase <PHASE> --out /tmp/task.md
# только rc=0
pipeline invoke-role --role <architect|reviewer|executor> --prompt-file /tmp/task.md --workspace <ABS>
```

- Передавать канонические `--slug` и `--phase`; G6 обязан совпасть с `canon.md`.
- `/tmp/task.md` создаёт emit; вручную менять, сокращать или заменять его нельзя. `--force` запрещён.
- Роль запускается одним фоновым wrapper с notify и persistent release; не использовать raw role launch, `agent -p`, `head`, `tail` или `--continue` как альтернативный маршрут.
- После wrapper terminal result сверить с journal, живостью точного процесса и канонным файлом. Notify, transport-ошибка и `rc=0` без артефакта не закрывают фазу.
- Фатал/квота означает WAIT; не меняет модели, лимиты или счётчики. Ровно один технический corrective-повтор допускается по `SKILL.md`.

Ревизор пишет только `REV-tz.md` или `REV-plan.md`; verdict читается из канонного блока, не из имени или старого stdout.
