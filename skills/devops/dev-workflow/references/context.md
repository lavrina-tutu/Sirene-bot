# Точечный контекст между фазами

Процесс, очередь и регламенты определяет Б55/`../SKILL.md`; модели и backend определяет YAML. Эта страница задаёт только содержимое межфазового пакета и MUST-read.

Норматив для `emit-prompt` и для текста, который получает роль. Мастер-ТЗ: DevWorkflow **Б12**.

## B56 envelope

Контентная роль получает только проверенный `devworkflow-packet/1.0` и его
детерминированный Markdown. Прочитать `must_read` и required inputs; inline
digest/canon/context rules проверены побайтно. Ручной prompt, fallback master
и старый snapshot не являются входом.

## Зачем

Между фазами передаётся **не** весь чат и **не** тело master-ТЗ целиком, а пакет-указатель:

1. digest экосистемы (что есть в системе);
2. канон кейса из `references/canon.md`;
3. выжимка `dev/<slug>/extract.md` (3–5 КБ или части 1/N);
4. **абсолютные пути** к digest, канону и master-ТЗ.

## Доктрина двух источников

| Источник | Роль | При конфликте |
|---|---|---|
| `extract.md` | индекс: имена, CLI, лимиты, «не трогать», `[NEW-ENTITY]` | проигрывает |
| master `TZ/<Tool>/<Tool>_TZ.md` на диске | смысл и нормы | **побеждает** |

В пакет всегда входит явная строка: **выжимка ≠ SoT; при расхождении — открыть master**.

Маркер `[NEW-ENTITY, требует согласования Саши]` не сглаживать общими словами.

## MUST-read по фазам

Роль обязана открыть полный файл, когда указано «да». Чтение **без обрезки**; если файл длинный — читать блоками (offset), не пропускать секции AC и «не трогать».

| Фаза | Открыть полный master / план | Достаточно выжимки как индекса |
|---|---|---|
| `TZ:patch`, `TZ:finalize`, `REV:tz` | **не** весь master по умолчанию. Обязательные секции: frontmatter + Б0.3 (границы хода); «Что НЕ трогать»; Б33; Б34 сводка AC (таблица); секция **текущего** пакета (последний БNN) + changelog **последние 3** записи. Полный master — если роль **пишет или судит** норму вне этого набора, есть `[NEW-ENTITY]`, выжимка расходится с путём, или путь короче 5 КБ | как индекс; формулировки норм — с диска открытых секций |
| `HF:plan` | секции AC, «не трогать», контракты | ориентир; формулировки AC — с диска |
| `HF:impl` | план + IAC; полное ТЗ при расхождении IAC с выжимкой | да, если IAC покрывает AC |
| `HF:test` | только `IAC.verify` | да |
| `REV:plan` | план + IAC + запреты master | нет как замена покрытия |
| `BUG:diagnose` | логи, код; ТЗ при контракте бага | да как карта |
| **Всегда** | расхождение пути и выжимки; короткий master; есть `[NEW-ENTITY]`; роль собирается обобщить имя | нет |

## Процедура оркестратора (обязательно)

```text
pipeline emit-prompt --slug <slug> --phase <PHASE> --out /tmp/task.md
# только при exit 0:
pipeline invoke-role --role <architect|reviewer|executor> \
  --prompt-file /tmp/task.md --workspace <ABS>
```

- Обход emit-prompt запрещён (`--force` нет).
- `/tmp/task.md` — только выход emit-prompt, не архив.
- После успешного emit в journal пишется `context-used:` с `tz_version`, `extract_sha256`, …
- `complete-phase` без этого маркера на TZ/HF/BUG/REV → fail (G2).

Перед complete можно: `pipeline check --slug … --phase …`.

## Выжимка и reuse

- Файл `extract.md` живёт **внутри слага**, не шарится между слагами.
- Reuse без повторного compress — только если совпал `extract_key` (path + version + mtime ТЗ + hash промпта компрессора).
- Drift version/mtime ТЗ → пересжать; skip compress «на глаз» запрещён.

Компрессор: промпты в `Registries/core-compressor-prompt.md` и `tz-compressor-prompt.md`; файл на диск пишет Python после проверки покрытия имён.

## Сборка контекста (справочно)

Логика digest и путей — в модуле `pipeline_context.py`. Отдельный скилл `cursor-task-context` после W4 не активен; его смысл перенесён сюда и в emit-prompt.

## B56: immutable packet

`emit-prompt` создаёт `devworkflow-packet/1.0`: JSON snapshot, SHA-256 sidecar и
детерминированный Markdown. Markdown содержит абсолютные FileRef и doctrine, но не тело
master. Каждый FileRef фиксирует path/hash/mtime; перед `invoke-role` повторно проверяются
slug, phase, G6, render, marker и refs. Ручной prompt, symlink, неизвестное поле,
изменённый source или исчезнувшая часть extract дают context error до prepare/backend.

`context-used:` содержит schema, packet_id, packet_path, prompt_sha256 и status/reason
master/extract. Это запись об emit, не accepted result. После prepare exact packet
связывается с фазой; G2 проверяет snapshot и не требует сохранённый `/tmp`.

`handoff-contract` в brief/утверждённом плане — data-only YAML. Он определяет master,
write_scope, prohibitions, inputs и outputs; команды из него никогда не исполняются.

LIGHT-эмит `HF:impl`/`HF:test` (CHANGE-LIGHT/BUGFIX-LIGHT) требует непустой
`master_section` в контракте + `--master-tz` в emit, иначе
`LIGHT: explicit master IAC section required`. Значение `master_section` — ТОЧНАЯ
уникальная строка заголовка секции IAC из master-ТЗ (полный текст `###`, напр.
`"22.5. План реализации и IAC (LIGHT)"`), не голый код вроде `IAC`: голый код
даёт `ReadRef: missing or ambiguous section: <name>`, потому что секция матчится
по заголовку, а не по коду.

## MIG: concrete slot admission

В `MIGRATION` общий `pipeline_mig_complete_guard` вызывается до публикации
packet, `invoke_prepare`, выбора следующего slot и любого `complete-phase` writer.
Для каждого предшествующего `MIG:block-N` проверяются own acceptance, identity,
absolute evidence path, hash, timestamp и result receipt. Aggregate status
`GATE:block-accept` не является proof. Прямой `ORCH:shared-state` или
`GATE:done` до собственного accept последнего блока отказывает без мутации;
sirene не получает packet или invoke.

Native compressor: `hermes-native` is the prepare/status selector for `hermes-internal`. The existing native adapter sends concrete `--model` before YAML `roles.compressor.model`; a selected null/empty/native selector uses static `HERMES_COMPRESSOR_MODEL`. Whitespace/non-string or non-concrete ENV models are refused. A successful HTTP response with no valid completion is a post-prepare local refusal (rc=4): it writes no extract/result/receipt and is not provider-fatal. Missing static model/key/base URL, worker failure, or a provider/transport failure remains rc=3/provider-fatal; the static refusal occurs before SDK construction/send/publication. One send, SDK retries=0, no alternative/fallback/rotation. No configuration discovery or new keys.
