# Этап 08 — представление Confluence, Итого и профиль плагина

Gate: **passed**. rc=0; passed=282; selected=284; optional skips=2.

- `S/scripts/mpp_convert.py`: PreparedPlan converter; source-local tree/resources; profiled dependencies/units/signed lag/basis; explicit losses; deterministic bytes; CSV adapter kept separate
- `S/scripts/mpp_calendar.py`: pure prepared calendar conversion, intervals/exceptions/bindings; retained source semantics and explicit unsupported constructs
- `S/scripts/itogo.py`: summary-v1; unique/explicit root, Decimal work and coefficients, ceil days, ROUND_HALF_UP display; no work in storage
- `S/scripts/gate_diff.py`: independent source/representation/model/observation diagnostics
- `S/scripts/plugin_profile.py`: version/schema/evidence-bound profile loading and capability/code lookup; unknown unsupported
- `S/scripts/plan_cache.py`: derived cache keyed by normalized/converter/rules/plugin/summary/template/root; integrity checked
- `S/references/profiles/`: summary-v1, strict plugin-profile schema, installed profile with hashed live evidence
- `S/tests/`: semantic/decimal/MPP work/cache/profile tests and actual browser plugin controls; required test IDs and stage report hook
- `S/tests/fixtures/golden/`: versioned plugin input bytes/expected dates and source representation/storage golden contracts
- `S/references/cli-contract.md`: internal stage08 contracts and stage09/10 integration boundary

Команда:

```text
/usr/bin/python3.9 -m pytest -c /home/tkachenkoav/hermes-workspace/skills/productivity/edit-plan-confluence/tests/pytest.ini /home/tkachenkoav/hermes-workspace/skills/productivity/edit-plan-confluence/tests --acceptance-stage 08 --test-root /home/tkachenkoav/.cache/edit-plan-confluence-acceptance/20261116-stage08/stage-08 -m unit or mpp_fixtures or confluence_live --junitxml=/home/tkachenkoav/.cache/edit-plan-confluence-acceptance/20261116-stage08/stage-08/reports/junit.xml
```

A–D work (допуск ≤0.001 ч):

- A: 1576 ч; эталон 1576; delta=0; N=85; work quality=partial.
- B: 2096 ч; эталон 2096; delta=0; N=85; work quality=partial.
- C: 2088 ч; эталон 2088; delta=0; N=77; work quality=partial.
- D: 3136 ч; эталон 3136; delta=0; N=107; work quality=partial.

Live: passed, page=537571938, controls=11, POST=11, PUT=0. Inputs/received/storage/browser observations/screenshots: live/.

Проверено защищённых файлов: 273, изменений: 0. Дерево: `40059ffc4127a4605c92cae45b1491a19f1691ede599379ea95793cbd9ac38cd`.

Ограничения:

- Только этап 08. Подключение к первичному архиву/admission diff/publish — этап 09; сетевые стадии — этап 10.
- Legacy CSV adapter/старый pipeline сохранены совместимыми; новый converter/calendar/itogo работают только с PreparedPlan.
- Installed profile pins exact frontend build and asset hash; server marketing release version is unavailable to this account (UPM 401).
- Unknown plugin capabilities remain not_verified; local scheduler capability matrix does not prove plugin behavior.
- A–D work known sum matches reference; extraction quality partial because exporter reports unsupported timephased getters. Missing totals never become zero.
- Legacy test_rest_live GET/apply harness is optional in stage08 (EDITPLAN_LIVE unset); required dedicated controls ran separately without mocks.
- Production DB/WorkVault, plan pages A–D/AB, Gateway and schedules were not modified. No migrations or R/E changes.
- ownCloud sync not confirmed. Test-only browser packages and browser binary remain under the isolated test root.
