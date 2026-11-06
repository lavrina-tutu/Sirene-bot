# Вызов роли и граница wrapper

## B56 accepted binding

До `invoke_prepare` проверяются snapshot, sidecar, render, G6 и все FileRef.
В state сохраняется immutable binding schema/id/path/prompt hash/slug/phase.
После принятого invoke G2 не перечитывает master как вход: разрешённая роль
могла изменить его как output.

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

## B56 binding

До `invoke_prepare` адаптер принимает только пару, выпущенную `emit-prompt`: immutable
packet snapshot и byte-exact Markdown. Он сверяет schema/id/slug/phase/G6, sidecar,
marker и FileRef; затем держит принятые bytes в памяти до backend. Контекстная ошибка
имеет rc=1, не provider_fatal и не расходует ход.

После prepare phase получает exact `context_packet`; только оно вместе с marker допускает
G2. Наличие packet_id не означает completion/APPROVE. Для compressor accepted publication
должна соответствовать packet+prepare и обычному receipt; extract сам по себе не результат.

`MIG:block-N` additionally enters only through the shared
`pipeline_mig_complete_guard`. It verifies every required earlier block's own
acceptance evidence and receipt before emit/prepare; direct ORCH/done uses the
same owner before its idempotent or state-writer branch. Repeating an accept is
a no-op only while that exact proof still verifies.

Native compressor: `hermes-native` is the prepare/status selector for `hermes-internal`. The existing native adapter sends concrete `--model` before YAML `roles.compressor.model`; a selected null/empty/native selector uses static `HERMES_COMPRESSOR_MODEL`. Whitespace/non-string or non-concrete ENV models are refused. A successful HTTP response with no valid completion is a post-prepare local refusal (rc=4): it writes no extract/result/receipt and is not provider-fatal. Missing static model/key/base URL, worker failure, or a provider/transport failure remains rc=3/provider-fatal; the static refusal occurs before SDK construction/send/publication. One send, SDK retries=0, no alternative/fallback/rotation. No configuration discovery or new keys.
