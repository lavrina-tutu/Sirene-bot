# BUILD_CHECKLIST — AggregateFromMeetings

Формат: `[ ]` открыт · `[x]` зелёный · `[~] причина` заблокирован.

*Актуализирован 2026-06-22 по dev-log.md (реальное состояние кода)*
*Обновлён 2026-06-30: бриф 29–30.06 — Opus упразднён (Фаза 3 переоткрыта), H3-rework — блокер Фазы B, добавлен Шаг 1 `pm_notes_reconciler` (Фаза 7).*

---

## Фаза T. Тестовые данные (RUN_IMPLEMENTATION §5)

- [x] T.1 LLM сгенерировал тестовые встречи (10 синтетических FF-подобных файлов)
- [x] T.2 `TEST_DATA_MANIFEST.md` заполнен
- [x] T.3 **GATE H0** — PM подтвердил тестовый набор ✅

---

## Фаза 0. Инфраструктура

- [x] 0.1 Структура папок проекта
- [x] 0.2 `models.py` (все типы) + `memory_schemas.py`
- [x] 0.3 `state.py` (read/write/update/queue)
- [x] 0.4 Фикстуры: `syncs_memory.json` (3), `classification_memory.json` (5), `sample_meetings/` (10)
- [x] 0.5 `utils/ff_parser.py` → `parse_ff_summary()`
- [x] 0.6 AC методы `ContactStore.add_alias()` / `resolve_name()` каскад 6 шагов → **GATE H1** ✅

---

## Фаза 1. A.Сборщик + B.Роутер

- [x] 1.1 `A.scan_new_meetings()`
- [x] 1.2 `A.parse_meeting_file()`
- [x] 1.3 `A.filter_already_processed()`
- [x] 1.4 `B.load_syncs_memory()`
- [x] 1.5 `B.load_classification_memory()`
- [x] 1.6 `B.match_sync_aliases()` (шаг 0, ПРИОРИТЕТ 1)
- [x] 1.7 `B.match_project_aliases()`
- [x] 1.8 `B.count_real_participants()` (исключить `fred@fireflies.ai`)
- [x] 1.9 `B.resolve_ambiguous_alias()`
- [x] 1.10 `B.determine_route()` (шаги 0–6, единая точка истины C1)
- [x] **GATE H2** — B-checkpoint: ≥90% точность route ✅ (bootstrap: 0 unclear из 504)

---

## Фаза 2. C.Добытчик шаг 1 (Haiku)

- [x] 2.1 `C.haiku_tag_meeting()` (bootstrap)
- [x] 2.1b `C.extract_signals_increment()` (increment-path)
- [x] 2.2 `C.pre_classify()` (LLM при low confidence от B) — R10 ✅
- [x] 2.3 `C.build_tag_cache()` → `meetings_index.json`
- [x] 2.4 `C.load_tag_from_cache()`

---

## Фаза 3. C.Добытчик — единый Haiku-проход (Opus УПРАЗДНЁН, PD-028, бриф 29–30.06)

> ⚠️ **Opus убран полностью** (PD-028/036). Двухшаговая архитектура (Haiku-разметка → Opus-агрегация) отменена. Весь прогон — единый поштучный Haiku-проход (TZ_C «Архитектура (единый проход)»). Шаги 3.1–3.5 ниже относятся к старой Opus-архитектуре и переоткрыты под Haiku-only (IQ-B10).

- [~] 3.1 ~~`C.opus_aggregate_project()`~~ → заменить на единый Haiku-проход (IQ-B10) — PD-028
- [~] 3.2 `C.build_meeting_signals()` — переснять под Haiku-проход
- [x] 3.3 `C.normalize_signal_text()` (переиспользуется)
- [~] 3.4 `C.dedup_signal()` — расширить дедупом задач между срезами (stable-id, Q-A3)
- [x] 3.5 `C.resolve_people_in_signals()` (переиспользуется)
- [~] **GATE H3 — ПЕРЕОТКРЫТ (H3-rework, блокер Фазы B):** precision C теперь на Haiku-only. После IQ-B10 — прогон Haiku на H0, таблица сравнения Opus↔Haiku по сущностям (project/1on1/multisync) с подсветкой смысловых расхождений → `pm/sessions/h3-rework-comparison.md` → вердикт PM (Q-A2, IQ-B10a). Прежний H3 (✅ 2026-06-20) на Opus — не репрезентативен.

---

## Фаза 4. D.База (Projects/<slug>/ai/)

- [x] 4.1 `D.get_next_action_item_number()`
- [x] 4.2 `D.dedup_check()`
- [x] 4.3 `D.append_decision()` (с `· 🔗 [[Syncs/<slug>]]` для source_sync)
- [x] 4.4 `D.append_action_item()` (#N сквозная)
- [x] 4.5 `D.append_timeline_entry()`
- [x] 4.6 `D.update_card_meta()`
- [x] 4.7 `D.parse_inline_pm_commands()`

---

## Фаза 5. E.Люди (People/{login}/)

- [x] 5.1 `E.ensure_people_dir()` (латиница)
- [x] 5.2 `E.resolve_participant()` (каскад)
- [x] 5.3 `E.get_next_commitment_number()`
- [x] 5.4 `E.append_commitment()` (двусторонние секции)
- [x] 5.5 `E.append_agreement()`
- [x] 5.6 `E.write_meeting_note()` (метка `<!-- ac: ... -->`)
- [x] 5.7 `E.update_people_card_meta()`
- [x] 5.8 `E.queue_unclear_name()` → `state/unclear_names.jsonl`

---

## Фаза 6. H.Синки (Syncs/<slug>/)

- [x] 6.1 `H.resolve_sync_participants()` (S2 ∪ S3)
- [x] 6.2 `H.get_next_sync_action_number()`
- [x] 6.3 `H.append_sync_decision()`
- [x] 6.4 `H.append_sync_action()`
- [x] 6.5 `H.write_sync_meeting_note()`
- [x] 6.6 `H.update_sync_card()`
- [x] 6.7 `H.update_projects_touched()`
- [x] 6.8 `H.update_syncs_memory()`

---

## Фаза 7. F.Дирижёр

- [x] 7.1 `F.fan_out_signals()` (H→D нет)
- [x] 7.2 `F.update_state()`
- [x] 7.3 `F.handle_unclear()`
- [x] 7.4 `F.trigger_snapshot()` (ВП4: multisync → только sync-snapshot)
- [x] 7.5 `F.retry_logic()` (backoff 0→15→60)
- [x] 7.6 `F.log_event()`
- [x] 7.7 `F.haiku_diagnostics()`
- [x] 7.8 `F.send_tg_digest()` (20:00 МСК)
- [x] 7.9 `F.send_weekly_digest()` (пн 09:00 МСК)
- [x] 7.10 `F.retrigger_after_pm_markup()`
- [x] 7.11 `F.run_pipeline()` (cron каждые 2ч)
- [x] 7.12 `F.parse_tg_command()` (TZ_B/E/H команды)
- [ ] 7.13 `pm_notes_reconciler` (Шаг 1): окно 5 дней, хэш блока PM Notes `(snapshot,idx)`, CRUD, ручной `--only-pm-notes` — PD-046/049…052, IQ-B18 ← **бриф 30.06**
- [ ] 7.14 `F.run_pipeline()` — два шага: Шаг 1 reconciler → Шаг 2 встречи; запуск всегда после MoveFromFF — IQ-B19

---

## Фаза 8. G.Срез

- [x] 8.1 `G.find_prev_snapshot()`
- [x] 8.2 `G.extract_pm_notes()`
- [x] 8.3 `G.generate_project_snapshot()` (PM Warnings §9.1–9.8)
- [x] 8.4 `G.generate_1on1_snapshot()`
- [x] 8.5 `G.generate_sync_snapshot()`
- [x] 8.6 `G.save_snapshot()` (иммутабельно)

---

## Фаза 9. Bootstrap + боевой прогон

- [x] 9.1 `scripts/bootstrap.py` — A+B на 504 файлах
- [x] 9.2 PM ревью unclear_queue + алиасы синков → **GATE H5** ✅ (бриф 22.06, 0 unclear)
- [x] 9.3 C шаг 1 (Haiku R10) на 504 summary — resolved 51/74 ✅
- [ ] 9.4 PM ревью `classification_memory.json` → **GATE H5b** ← **нужен PM**
- [ ] 9.5 PM ревью сигналов по 15 проектам (`Inbox/signals-review-2026-06-29/`) → **GATE H4** ← **нужен PM**
- [ ] 9.6 Прогон D на реальных данных
- [ ] 9.7 Прогон E на реальных данных
- [ ] 9.8 Прогон H на реальных данных
- [ ] 9.9 PM-ревью 3–5 проектов → **GATE H6** ← **нужен PM**

---

## HUMAN-GATES (трекер)

- [x] H0 тестовый набор ✅
- [x] H1 AC diff (add_alias/resolve_name) ✅
- [x] H2 B-checkpoint (≥90% route) ✅ — 100% на 504 файлах
- [~] H3 C-checkpoint (precision) — **ПЕРЕОТКРЫТ как H3-rework** (Haiku-only, блокер Фазы B, IQ-B10a). Прежний ✅ 2026-06-20 был на Opus — не репрезентативен
- [~] H4 ~~bootstrap $ (Opus×15)~~ — неактуален (Opus убран, PD-028); приёмка через golden compare (IQ-C01/C02/C05)
- [ ] H5 classification_memory ревью ← **ждёт PM**
- [ ] H6 финальный ревью + разрешение писать в боевой WorkVault ← **ждёт PM**
- [x] H7 противоречия — нет критических ✅
- [ ] H8 очистка тестов

---

## Cleanup

- [ ] CL.1 удалены `_sandbox/` артефакты
- [ ] CL.2 `TEST_RESULTS_LOG.md` аудит-лог сверён
- [ ] CL.3 рабочее дерево чистое (`scripts/cleanup_sandbox.py` → нет утечек в WorkVault)
