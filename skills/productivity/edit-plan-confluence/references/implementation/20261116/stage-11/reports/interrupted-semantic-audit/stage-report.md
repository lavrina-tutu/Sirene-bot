# Этап 11 — доказательное сравнение и доверие к публикациям

Gate: **failed**; S rc=2; selected=598; passed=358.

Покрытие: §20/AC-23, AC-24 (все десять подслучаев), AC-25, AC-27 в объёме этапа 11.

- `M/mofs_index/plan/selectors.py`: exact snapshot/publication IDs, project/page/attachment/lineage/snapshot link checks before diff.
- `M/mofs_index/plan/query.py`: all saved task fields/nested data, dependency multisets, calendar/assignment/resource semantics, structured unmatched records, precise dates, identity-safe dependent queries.
- `M/mofs_index/plan/history.py`: scoped publications/links and append-only verification observations with distinct times and stable cursor watermark.
- `M/mofs_index/plan/render.py`: derived MD with exact IDs/page/attachment/representation/revision/evidence/completeness; no positional proof.
- `S/scripts/plan_queries.py + cli.py`: compare, final history, publication verify; global isolated paths and structured exit codes.
- `S/scripts/plan_publication_verify.py`: GET-only request/download guard; expected bytes, exact metadata, archived storage, historical/current scopes, fresh target checks and append-only local observations.
- `S/scripts/plan_history.py`: archive-history remains legacy_unverified; archived bytes do not prove historical publication.
- `M/tests/plan/test_query.py + test_render.py`: direct typed API regressions and semantic field matrix.
- `S/tests/test_compare_e2e.py + test_publication_verify.py`: all ten AC-24 subcases via CLI, exact v2 IDs, GET guard, actual loopback concurrency and dedicated live reads.
- `S/tests/conftest.py`: stage-11 mandatory set, group ordering and evidence-derived gate; stages 01–10 preserved.
- `Q/SKILL.md + references/plan-queries.md`: same typed API, exact selectors, mapping/trust and distinct observation times.

Команда S:

```text
/usr/bin/python3.9 -m pytest -c /home/tkachenkoav/hermes-workspace/skills/productivity/edit-plan-confluence/tests/pytest.ini /home/tkachenkoav/hermes-workspace/skills/productivity/edit-plan-confluence/tests --acceptance-stage 11 --test-root /home/tkachenkoav/.cache/edit-plan-confluence-acceptance/20261117T045241Z/stage-11 -m unit or archive_integration or confluence_live --junitxml=/home/tkachenkoav/.cache/edit-plan-confluence-acceptance/20261117T045241Z/stage-11/reports/junit.xml
```

Отдельные команды/rc/JUnit MofsIndex, проверка восстановления patch и after-copy: external-checks.json.

Live GET-only: {'GET': None, 'POST': None, 'PUT': None}; concurrent CLI loopback: {'GET': None, 'POST': None, 'PUT': None}.

Дерево исходников: `dbec6af5e513648da9109ad13a9afb7a05250cc6aba637b1ea5d8c931f626a65`. Защищено файлов: 1273, изменено: 0.

Завершающий SHA записывается после commit в журнал канонического плана. canon.md в поставку не включается.

Ограничения:

- Only stage 11; stages 12/13, active skill delivery and full §20/§19 acceptance are not claimed.
- Unknown or partial identity remains structured unmatched data. Positional Gantt IDs never prove entity identity; unlinked/MPP-source publications expose raw structures with unknown mapping.
- Completeness is conservative. Timezone alone does not establish calendar/field completeness. Working-time drift and causal schedule attribution are not calculated.
- Read-back is scoped to observed versions and time; current_state never restores a historical publication date. Insufficient expected bytes/storage/link yields not_verified/5.
- Live stage-11 uses immutable synthetic stage-10 evidence on a dedicated page: historical version matches, current attachment deliberately differs. No arbitrary real-MPP schedule equality is claimed.
- Master on disk is 0.5.1 with separate §21; only agreed §20 is implemented. No schema/config/previous-stage evidence modifications.
- canon.md was clean at entry; its original bytes are protected and it is excluded from the commit. OwnCloud sync is not confirmed.
- Production DB/WorkVault plan data and A–D/AB pages, Gateway, crons, watchers and schedules are unchanged. Existing live regression tests create only dedicated acceptance targets.
