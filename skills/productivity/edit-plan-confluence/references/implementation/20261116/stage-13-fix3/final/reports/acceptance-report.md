# Этап 13 — комплексная приёмка

Gate: **failed**; pytest rc=1; selected=812.

## Команда

```text
/usr/bin/python3.9 -m pytest -c /home/tkachenkoav/hermes-workspace/skills/productivity/edit-plan-confluence/tests/pytest.ini /home/tkachenkoav/hermes-workspace/skills/productivity/edit-plan-confluence/tests --acceptance-stage 13 --test-root /home/tkachenkoav/.cache/edit-plan-confluence-acceptance/accept-fix3-20261117-174642/final -m unit or archive_integration or mpp_fixtures or confluence_live --junitxml=/home/tkachenkoav/.cache/edit-plan-confluence-acceptance/accept-fix3-20261117-174642/final/reports/junit.xml -q
```

## Матрица AC

| AC | Статус | Подслучаи passed / всего |
|---|---|---|
| AC-01 | passed | 0/0 |
| AC-02 | failed | 0/0 |
| AC-03 | failed | 0/0 |
| AC-04 | passed | 8/8 |
| AC-05 | passed | 0/0 |
| AC-06 | passed | 0/0 |
| AC-07 | passed | 0/0 |
| AC-08 | passed | 0/0 |
| AC-09 | failed | 8/8 |
| AC-10 | passed | 0/0 |
| AC-11 | passed | 0/0 |
| AC-12 | passed | 0/0 |
| AC-13 | passed | 0/0 |
| AC-14 | passed | 0/0 |
| AC-15 | passed | 0/0 |
| AC-16 | passed | 0/0 |
| AC-17 | passed | 0/0 |
| AC-18 | passed | 0/0 |
| AC-19 | passed | 20/20 |
| AC-20 | passed | 11/11 |
| AC-21 | passed | 0/0 |
| AC-22 | passed | 11/11 |
| AC-23 | passed | 0/0 |
| AC-24 | passed | 10/10 |
| AC-25 | passed | 0/0 |
| AC-26 | passed | 0/0 |
| AC-27 | passed | 0/0 |

Каждый подслучай с точными test ID, fixtures, требованиями evidence и результатом находится в acceptance-report.json.

## Кейсы

| Кейс | Статус | Evidence |
|---|---|---|
| A | passed | [JSON](cases/A.json) |
| B | failed | [JSON](cases/B.json) |
| C | failed | [JSON](cases/C.json) |
| D | failed | [JSON](cases/D.json) |
| E | passed | [JSON](cases/E.json) |
| F | passed | [JSON](cases/F.json) |
| G | passed | [JSON](cases/G.json) |
| D-risks | passed | [JSON](cases/D-risks.json) |

## Пользовательские сценарии

- 01-publish-no-general-consent: **failed**.
- 02-save-no-client-baseline: **passed**.
- 03-inbox-one-text-command: **passed**.
- 04-batch-show-errors: **passed**.
- 05-register-then-retry-decisions: **passed**.
- 06-arrival-chronology: **passed**.
- 07-today-local-offset: **passed**.
- 08-exact-selectors: **passed**.
- 09-current-vs-confirmed-publication: **passed**.
- 10-reconcile-before-resume: **passed**.
- 11-new-MPP-identity-resume: **passed**.

## Gate checks

- nonempty_results: True.
- all_required_selected: True.
- all_required_passed: False.
- all_AC_passed: False.
- all_cases_passed: False.
- all_journeys_passed: False.
- fixtures_verified: True.
- populated_baseline_preserved: True.
- protected_files_unchanged: True.
- sources_stable: True.
- external_regression_passed: True.
- external_sources_restorable: True.
- prior_twelve_commits: True.
- original_stage13_failed_preserved: True.
- no_production_live_targets: True.
- pytest_exit_zero: False.
- ordered_phases_2_through_11: True.
- ordered_unit_archive_mpp_live: True.

## Ограничения

- Acceptance of §20 only; §19 W5/ZD/AC-101…144 remains independent.
- Master v0.5.3 with separate §21; по плану; факт — в колонках. Actuals do not claim equivalent schedule recalculation. Original archived stages 01–13 and failed cycles remain preserved.
- Product defects belong to earlier stages and are reported, not repaired in stage 13.
- No token economy claim: tokens were not measured.
- Process-death tests do not model power loss. Gateway, cron and watchers are unchanged.
- Unknown counters/observations remain null; absent live publication cannot pass.

Все проверки выполняются на изолированных БД/WorkVault/cache. Baseline before/after, hashes, источники, версии, счётчики, команды/rc, storage из GET и причины отказа сохранены в JSON и reports/evidence/.

Непрошедшие обязательные тесты:

- `test_live_publication.py::test_real_publish_repeat_and_observed_dates[B]`
- `test_live_publication.py::test_real_publish_repeat_and_observed_dates[C]`
- `test_live_publication.py::test_real_publish_repeat_and_observed_dates[D]`
