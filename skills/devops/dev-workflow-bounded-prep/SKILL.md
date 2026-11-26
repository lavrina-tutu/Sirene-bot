---
name: dev-workflow-bounded-prep
version: 1.1.0
author: sirene
description: "Use when bounded regression в HF:test prep DevWorkflow."
---

# Bounded regression и publication identity в HF:test prep

Работает внутри dev-workflow (roles architect/reviewer/executor — по ролям в
pipe); этот скилл фиксирует предметные правила доказательства полного набора и
immutable publication в фазе HF:test prep. Не заменяет dev-workflow/SKILL.md,
B55/master-ТЗ и `dev-workflow/references/operational-pitfalls.md` (файл лежит в
соседнем скилле dev-workflow); читать их как канон первыми.

## Полный bounded набор в сотни nodeids

Последовательный per-node прогон над большим collection (177/437 и более) НЕ
умещается в окно сессии: 7–60 s на узел × N выливается в rc=130 (SIGINT
interrupted), а не в валидный результат. Это не «тест сломан» — это
проблема масштаба запуска, решаемая планировщиком, а не сокращением набора.

Обязательный параллельный bounded scheduler:
- полный collect-only inventory фиксируется ДО dispatch (collection_sha256,
  ordered nodeids, count);
- до 8 изолированных worker-процессов, каждый со своей process-group и своим
  временным test root;
- каждый nodeid выдаётся ровно один раз в порядке collection; rows после
  завершения нормализуются обратно в этот порядок;
- никаких resume/backfill/state/journal/queue/global-mutex; scheduler не пишет
  состояние;
- PASS только при len(executed)==len(collected), duplicate_nodeids=[],
  missing_records=[], remaining_nodeids=[], active_nodeid=null, у каждого
  nodeid rc=0 и timeout=false; любой rc=130/124 или non-empty remaining —
  честный FAIL без PREPARED.

Лимиты конечные, не бесконечные: per-node timeout 180 s покрывает медленные
optional-ветки, total wall-clock budget фиксируется (3600 s). Increased per-node
limit допустим (180, не 60), когда наблюдали legitimately-долгие узлы; НЕ
увеличивать безгранично и НЕ перезапускать отдельный nodeid ради зелёного.

## `--ignore` — только абсолютный путь

`--ignore <file>` в pytest collection нормализуется к АБСОЛЮТНОМУ пути
относительно test-root. Относительный путь исполняется с cwd=collection-root
(часто `pipeline_root.parent`) и НЕ совпадает с `pipeline/tests/<file>`: файл
остаётся в наборе (437 vs 431 nodeids), и reader/fixture-зависимые тесты
запускаются до PREPARED, ломая staged-порядок и возвращая FAIL/NOT_RUN.

- один и тот же абсолютный argv обязателен и для collection, и для dispatch;
- reader запускается ОТДЕЛЬНЫМ post-PREPARED вызовом с собственной
  collection/sha;
- в pre-pilot summary reader_nodeids=[] и обязательно проверить, что reader
  nodeid не попал в prepilot executed_nodeids.

## Immutable publication identity

`publication_id` immutable publication-манифеста вычисляется как SHA-256 от
канонического объекта БЕЗ самого поля `publication_id` (self-reference
исключается из хешируемых bytes — иначе хеш нестабилен/самореферентен).

- байт-идентичный canonical допустим ТОЛЬКО после НОВОЙ публикации со свежим
  manifest; stale proof или identical bytes без новой публикации — Fail
  (rc=4) с сохранением прежнего accepted result;
- единый verify_* helper обязан вызываться и в publisher, и в finalizer
  (check_canonical_after_invoke), и в completion-метадате
  (compressor_metadata) — иначе transparent writer закроет фазу, минуя
  проверку публикации;
- manifest пишется как regular non-symlink immutable artifact
  `context/extract-publication-<id>.json`, содержимое без пробелов/sorted
  keys/UTF-8 для детерминированного хеша.

## Двоичная целостность против установленного редактора

Когда кандидат сериализует закрытый формат (receipt, publication manifest, evidence, snapshot),
который обязан побайтово пережить установленный redactor: собрать полный body и прогнать через
настоящий native redaction ПЕРЕД записью, а не белым списком полей-исключений и не публикацией
результата redaction ради прохождения. Разделитель выбирать так, чтобы установленный regex его не
трогал: hex/цифровые строки, склеенные через `:`, матчатся Telegram-токен-паттерном
(`digits8+:token30+`) и заменяются на `***`, ломая bytes → fail-closed до успешной записи. `|`
между значениями фиксированной длины regex не ломает. Если установленный код всё же меняет bytes —
это граница класса P22: адресный вердикт архитектора об изменении ЗАКРЫТОГО формата кандидата
(version /1.0 → /1.1 и т.п.), не правка установленной среды и не бесконечные раунды исполнителя.
Успешный pytest в окружении кандидата может маскировать дефект, если тесты не гоняют проверку на
том же установленном redactor; включать golden-body-кейсы (полностью цифровые строки, цифровой
хвост) в набор.

## Accepted pin (B60.3.1/3.2)

Перед producer dispatch fixture сохраняет accepted A-вход: `acceptance-<sha256>.json`
с exact brief bytes, source FileRef, origin/author/date/id, revision, basis.
- source-derived response строится из captured master; ответ отказывается при
  отсутствии/подмене/drift любой ссылки;
- build_source_inventory детерминированно сохраняет все полные AC/IAC/COD IDs,
  [NEW-ENTITY, требует согласования Саши], inline-code вне fenced, макс.
  non-whitespace fenced/plain/changelog spans с абсолютными byte offsets;
- size-based trimming и regex-only coverage запрещены; missing/duplicate/
  reordered/source/pin drift — deterministic FAIL до publication.
