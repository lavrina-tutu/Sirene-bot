# G2 source-drift: TZ-фаза законно пишет master, `complete-phase` падает

Когда `TZ:patch` / `TZ:finalize` законно изменяют master (дополнение контракта,
смена версии, draft -> approved), `complete-phase` даёт
`G2: context packet missing or changed` (rc=1) и `next` -> `RECONCILE`. Причина:
принятый binding в `context_packet` держит snapshot master ПО правке, hash файла
разошёлся с диском. Это НЕ баг роли и НЕ повод обходить guard — это нормативный
разрыв Б56.6, и штатный путь приёмки — переснимок («следующий emit с новым
snapshot», Б56.6 п.5).

## Правила

- **Не обходить G2** ручной правкой state/packet и не «чинить» guard-код.
  Правка master на этой фазе завершающая; сам `complete` её не перепринимает.
- **emit-prompt сам по себе НЕ обновляет accepted binding.** Повторный emit
  создаёт новый packet, но `context_packet.packet_id` в state остаётся прежним;
  `check` всё ещё падает. Нужен именно повторный invoke, чтобы роль
  перезакрепила консистентный packet.

## Штатная приёмка (переснимок)

```text
# 1) новый snapshot захватит уже изменённый master
pipeline emit-prompt --slug <slug> --phase <PHASE> --out /tmp/resnap.md
# 2) invoke той же ролью — роль перепримет консистентный packet и обновит binding
pipeline invoke-role --role <architect|reviewer> --prompt-file /tmp/resnap.md \
  --workspace <ABS> --slug <slug> --phase <PHASE>   # только background
# 3) проверить переприём: packet_id в _state.json сменился, `check` rc=0
pipeline check --slug <slug> --phase <PHASE>
# затем complete-phase — проходит
pipeline complete-phase --slug <slug> --phase <PHASE> --reason ... --evidence ...
```

- Перерисовывать канонный артефакт при resnap НЕ нужно: роль уже написала
  документ, повторный invoke лишь закрепляет binding (не пересоздаёт файл).
- То же самое повторяемо при каждом фаза-изменении master: патч, затем финализация
  (меняется статус/дата/версия) — каждый легитимный мейнтейнер master на своём
  шаге вызывает G2 до пересъёмки.

## Сопутствующие требования

- `invoke-role` только `background=true, notify=true, persist_on_release=true`;
  foreground упирается в жёсткий кап терминала и оставляет dead-pid.
- `GATE:take-into-work` (AUTO_GATE, role `sirene`) требует `--evidence` с
  `path=`/`sha256=`/`session_id=` — без обязательной улики `complete-phase`
  падает; pass без улики недопустим.
- Маpкер токена «invoke-role» в аргументах CLI — не использовать (ложный wrapper alive,
  см. основной разбор pitfalls); в reason/evidence писать «role call»/«invocation».
