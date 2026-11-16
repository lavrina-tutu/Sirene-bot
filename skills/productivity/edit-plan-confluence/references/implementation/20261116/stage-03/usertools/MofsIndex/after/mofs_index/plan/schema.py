"""DDL для долговечных plan_*-таблиц (архив слепков плана, R-015).

Фаза 0 (P0.SAFE.3): только реестр версий схемы `plan_schema_migration` —
долговечный, не входит в общий `drop_all()` индекса встреч/docs (mofs_index/db.py).

Каждая следующая фаза плана (1..3) добавляет свою миграцию в MIGRATIONS ниже
(см. mofs_index/plan/migrate.py::ensure_plan_schema). Это единственное место,
где описывается DDL `plan_*`.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Migration:
    """Один шаг миграции: уникальный id + список DDL-стейтментов."""

    migration_id: str
    statements: tuple[str, ...]


# Таблица реестра миграций — создаётся migrate.py отдельно от списка MIGRATIONS
# (она должна существовать до применения первой миграции, чтобы можно было
# проверить, какие уже применены).
PLAN_SCHEMA_MIGRATION_DDL = """
CREATE TABLE IF NOT EXISTS plan_schema_migration (
    migration_id TEXT PRIMARY KEY,
    applied_at   TEXT NOT NULL,
    checksum     TEXT NOT NULL
)
"""

# ─────────────────────────────────────────────────────────────────────────
# Фаза 1 (P1.SCHEMA.1-3, R-015/R-016): core identity + import attempt +
# publication/page-observation таблицы. Identity-уровень только — без
# версионных snapshot-данных (они в Фазе 2, R-015 §7.1 строки plan_snapshot+).
# ─────────────────────────────────────────────────────────────────────────

PHASE1_CORE_DDL: tuple[str, ...] = (
    # plan — PK plan_id, существующий project slug (один план на проект,
    # Q1/Q2 DECISIONS-owner.md), стабильный MD path, default-удобства.
    """
    CREATE TABLE IF NOT EXISTS plan (
        plan_id TEXT PRIMARY KEY,
        project_slug TEXT NOT NULL,
        name TEXT,
        md_path TEXT,
        default_target TEXT,
        default_representation TEXT,
        created_at TEXT NOT NULL,
        UNIQUE(project_slug)
    )
    """,
    # plan_lineage — FK plan, namespace исходника, основание линии; page_id —
    # привязка к конкретной Confluence-странице (R-007 §4.2: привязка
    # фиксируется явно до первого архивного commit, не угадывается).
    """
    CREATE TABLE IF NOT EXISTS plan_lineage (
        lineage_id TEXT PRIMARY KEY,
        plan_id TEXT NOT NULL REFERENCES plan(plan_id),
        source_namespace TEXT NOT NULL,
        page_id TEXT,
        basis TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE(lineage_id, plan_id),
        UNIQUE(plan_id, source_namespace, page_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_plan_lineage_plan ON plan_lineage(plan_id)
    """,
    # plan_artifact — content-addressed байты (MPP/JSON/storage), UQ raw hash.
    """
    CREATE TABLE IF NOT EXISTS plan_artifact (
        artifact_id TEXT PRIMARY KEY,
        raw_sha256 TEXT NOT NULL,
        kind TEXT NOT NULL,
        format TEXT,
        size_bytes INTEGER,
        path TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE(raw_sha256)
    )
    """,
    # plan_task_identity / plan_resource_identity — identity-only (§7.1,
    # R-018): UQ(lineage_id, uid) только при подтверждённой непрерывности
    # (partial unique index WHERE confirmed=1), т.к. неподтверждённые UID
    # могут повторяться между независимыми локальными identity.
    """
    CREATE TABLE IF NOT EXISTS plan_task_identity (
        plan_id TEXT NOT NULL REFERENCES plan(plan_id),
        task_key TEXT NOT NULL,
        lineage_id TEXT NOT NULL REFERENCES plan_lineage(lineage_id),
        uid TEXT,
        confirmed INTEGER NOT NULL DEFAULT 0,
        basis TEXT,
        created_at TEXT NOT NULL,
        PRIMARY KEY (plan_id, task_key)
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_plan_task_identity_confirmed_uid
        ON plan_task_identity(lineage_id, uid) WHERE confirmed = 1
    """,
    """
    CREATE TABLE IF NOT EXISTS plan_resource_identity (
        plan_id TEXT NOT NULL REFERENCES plan(plan_id),
        resource_key TEXT NOT NULL,
        lineage_id TEXT NOT NULL REFERENCES plan_lineage(lineage_id),
        uid TEXT,
        confirmed INTEGER NOT NULL DEFAULT 0,
        basis TEXT,
        created_at TEXT NOT NULL,
        PRIMARY KEY (plan_id, resource_key)
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_plan_resource_identity_confirmed_uid
        ON plan_resource_identity(lineage_id, uid) WHERE confirmed = 1
    """,
    # plan_import_attempt / plan_attempt_event — append-only журнал попытки
    # записи (R-009 п.5, R-010). event_id — PK, повтор идемпотентен
    # (INSERT OR IGNORE в writer.py).
    """
    CREATE TABLE IF NOT EXISTS plan_import_attempt (
        attempt_id TEXT PRIMARY KEY,
        plan_id TEXT NOT NULL REFERENCES plan(plan_id),
        lineage_id TEXT REFERENCES plan_lineage(lineage_id),
        source_namespace TEXT,
        range_from TEXT,
        range_to TEXT,
        prepared_sha256 TEXT,
        status TEXT NOT NULL DEFAULT 'not_started',
        created_at TEXT NOT NULL,
        FOREIGN KEY (lineage_id, plan_id) REFERENCES plan_lineage(lineage_id, plan_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_plan_import_attempt_plan ON plan_import_attempt(plan_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS plan_attempt_event (
        event_id TEXT PRIMARY KEY,
        attempt_id TEXT NOT NULL REFERENCES plan_import_attempt(attempt_id),
        stage TEXT NOT NULL CHECK (stage IN (
            'archive', 'page_create', 'attachment_post', 'attachment_verify',
            'storage_put', 'storage_verify', 'projection'
        )),
        status TEXT NOT NULL CHECK (status IN (
            'not_started', 'prepared', 'confirmed', 'failed',
            'unknown', 'conflict', 'not_applicable'
        )),
        detail TEXT,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_plan_attempt_event_attempt ON plan_attempt_event(attempt_id)
    """,
    # plan_publication — FK plan/lineage/artifact; UQ(namespace, attachment,
    # version) — R-010 §5.2: тот же source/version с иным hash — конфликт,
    # не upsert (AC-112).
    """
    CREATE TABLE IF NOT EXISTS plan_publication (
        publication_id TEXT PRIMARY KEY,
        plan_id TEXT NOT NULL REFERENCES plan(plan_id),
        lineage_id TEXT REFERENCES plan_lineage(lineage_id),
        artifact_id TEXT REFERENCES plan_artifact(artifact_id),
        source_namespace TEXT NOT NULL,
        attachment_id TEXT NOT NULL,
        attachment_version INTEGER NOT NULL,
        page_id TEXT,
        macro_id TEXT,
        filename TEXT,
        published_at TEXT,
        observed_at TEXT,
        recorded_at TEXT NOT NULL,
        page_version INTEGER,
        raw_sha256 TEXT,
        UNIQUE (source_namespace, attachment_id, attachment_version),
        FOREIGN KEY (lineage_id, plan_id) REFERENCES plan_lineage(lineage_id, plan_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_plan_publication_plan ON plan_publication(plan_id)
    """,
    # plan_page_observation — отдельная от publication наблюдение страницы
    # («Итого»/storage), R-015 §7.1: не требуется 1:1 соответствие с publication.
    """
    CREATE TABLE IF NOT EXISTS plan_page_observation (
        observation_id TEXT PRIMARY KEY,
        plan_id TEXT NOT NULL REFERENCES plan(plan_id),
        page_id TEXT NOT NULL,
        page_version INTEGER,
        fetched_at TEXT NOT NULL,
        storage_artifact_id TEXT REFERENCES plan_artifact(artifact_id),
        itogo_raw TEXT,
        itogo_text TEXT,
        itogo_d1 TEXT,
        itogo_d2 TEXT,
        itogo_n INTEGER,
        itogo_m INTEGER,
        quality TEXT NOT NULL DEFAULT 'unknown'
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_plan_page_observation_page ON plan_page_observation(page_id, page_version)
    """,
    # plan_publication_page_link — publication <-> page observation,
    # intended/observed, confirmed/inferred/unknown (R-015 §7.1).
    """
    CREATE TABLE IF NOT EXISTS plan_publication_page_link (
        link_revision_id TEXT PRIMARY KEY,
        publication_id TEXT NOT NULL REFERENCES plan_publication(publication_id),
        observation_id TEXT NOT NULL REFERENCES plan_page_observation(observation_id),
        link_kind TEXT NOT NULL,
        confidence TEXT NOT NULL CHECK (confidence IN ('confirmed', 'inferred', 'unknown')),
        evidence TEXT,
        supersedes TEXT,
        recorded_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_plan_pub_page_link_pub
        ON plan_publication_page_link(publication_id)
    """,
)

# ─────────────────────────────────────────────────────────────────────────
# Фаза 2 (P2.SCHEMA.1-8, R-012-019): версионные snapshot-данные полного
# графа плана (задачи ES-EF-LS-LF/constraints/actuals/splits, связи с
# lag+calendar, ресурсы/назначения timephased, календари, baseline 0..10),
# качество/диагностика графа, mapping-ревизии identity, выбор базы.
# plan_task_identity/plan_resource_identity (идентичность) — уже в Фазе 1;
# здесь только версионные "/version"-таблицы конкретных снимков (R-015 §7.1:
# identity и version — разные уровни, не одна таблица).
# ─────────────────────────────────────────────────────────────────────────

PHASE2_SNAPSHOT_DDL: tuple[str, ...] = (
    # plan_snapshot — один полный снимок плана (из MPP full-export либо
    # Gantt JSON), корень версионного графа Фазы 2. Две оси времени
    # (R-017): published_at (время события источника) != observed_at (время
    # получения) != recorded_at (commit в архив).
    """
    CREATE TABLE IF NOT EXISTS plan_snapshot (
        snapshot_id TEXT PRIMARY KEY,
        plan_id TEXT NOT NULL REFERENCES plan(plan_id),
        lineage_id TEXT REFERENCES plan_lineage(lineage_id),
        source_artifact_id TEXT REFERENCES plan_artifact(artifact_id),
        representation TEXT NOT NULL,
        timezone_hint TEXT,
        status_date TEXT,
        published_at TEXT,
        observed_at TEXT,
        recorded_at TEXT NOT NULL,
        FOREIGN KEY (lineage_id, plan_id) REFERENCES plan_lineage(lineage_id, plan_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_plan_snapshot_plan ON plan_snapshot(plan_id)
    """,
    # plan_publication_snapshot — связь Confluence-публикации (байты) со
    # снимком, к которому её разобрали (не всегда 1:1, как publication<->page
    # observation в Фазе 1).
    """
    CREATE TABLE IF NOT EXISTS plan_publication_snapshot (
        link_id TEXT PRIMARY KEY,
        publication_id TEXT NOT NULL REFERENCES plan_publication(publication_id),
        snapshot_id TEXT NOT NULL REFERENCES plan_snapshot(snapshot_id),
        confidence TEXT NOT NULL CHECK (confidence IN ('confirmed', 'inferred', 'unknown')),
        evidence TEXT,
        recorded_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_plan_pub_snapshot_pub ON plan_publication_snapshot(publication_id)
    """,
    # plan_snapshot_collection — статус/count/reason каждой коллекции снимка
    # (R-013): complete|partial|missing|unsupported, known 0 отличим от
    # неизвестности. UQ(snapshot_id, collection_kind).
    """
    CREATE TABLE IF NOT EXISTS plan_snapshot_collection (
        collection_id TEXT PRIMARY KEY,
        snapshot_id TEXT NOT NULL REFERENCES plan_snapshot(snapshot_id),
        collection_kind TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('complete', 'partial', 'missing', 'unsupported')),
        count INTEGER,
        reason TEXT,
        recorded_at TEXT NOT NULL,
        UNIQUE(snapshot_id, collection_kind)
    )
    """,
    # plan_quality_issue — diagnose_graph (циклы/множественные корни/
    # service-строки/висячие связи, AC-115) + персистентная отметка
    # "MPP vN missing" (AC-111 хвост) + любая иная проблема качества без
    # привязки 1:1 к завершённому снимку (snapshot_id нулевой допустим —
    # напр. версия источника недоступна, снимок не создан).
    """
    CREATE TABLE IF NOT EXISTS plan_quality_issue (
        issue_id TEXT PRIMARY KEY,
        plan_id TEXT NOT NULL REFERENCES plan(plan_id),
        lineage_id TEXT REFERENCES plan_lineage(lineage_id),
        snapshot_id TEXT REFERENCES plan_snapshot(snapshot_id),
        issue_kind TEXT NOT NULL,
        severity TEXT NOT NULL CHECK (severity IN ('info', 'warning', 'error')),
        detail TEXT,
        recorded_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_plan_quality_issue_plan ON plan_quality_issue(plan_id, issue_kind)
    """,
    # plan_task_version — версионные атрибуты задачи на конкретном снимке
    # (ES/EF/LS/LF, constraints, actuals/remaining, R-012-014). Identity —
    # в plan_task_identity (Фаза 1), здесь только значения снимка.
    # UQ(snapshot_id, task_key).
    """
    CREATE TABLE IF NOT EXISTS plan_task_version (
        task_version_id TEXT PRIMARY KEY,
        snapshot_id TEXT NOT NULL REFERENCES plan_snapshot(snapshot_id),
        plan_id TEXT NOT NULL REFERENCES plan(plan_id),
        task_key TEXT NOT NULL,
        uid TEXT,
        wbs TEXT,
        name TEXT,
        outline_level INTEGER,
        start_raw TEXT,
        finish_raw TEXT,
        duration_raw TEXT,
        early_start TEXT,
        early_finish TEXT,
        late_start TEXT,
        late_finish TEXT,
        percent_complete REAL,
        milestone INTEGER,
        summary INTEGER,
        constraint_type TEXT,
        constraint_date TEXT,
        actual_start TEXT,
        actual_finish TEXT,
        actual_duration_raw TEXT,
        remaining_duration_raw TEXT,
        notes TEXT,
        quality TEXT NOT NULL DEFAULT 'unknown',
        extensions TEXT,
        recorded_at TEXT NOT NULL,
        UNIQUE(snapshot_id, task_key)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_plan_task_version_snapshot ON plan_task_version(snapshot_id)
    """,
    # plan_task_segment — split-сегменты задачи (R-012).
    """
    CREATE TABLE IF NOT EXISTS plan_task_segment (
        segment_id TEXT PRIMARY KEY,
        task_version_id TEXT NOT NULL REFERENCES plan_task_version(task_version_id),
        segment_index INTEGER NOT NULL,
        start_raw TEXT,
        finish_raw TEXT,
        recorded_at TEXT NOT NULL,
        UNIQUE(task_version_id, segment_index)
    )
    """,
    # plan_dependency_version — связи снимка с lag+calendar (R-012).
    """
    CREATE TABLE IF NOT EXISTS plan_dependency_version (
        dependency_version_id TEXT PRIMARY KEY,
        snapshot_id TEXT NOT NULL REFERENCES plan_snapshot(snapshot_id),
        predecessor_task_key TEXT NOT NULL,
        successor_task_key TEXT NOT NULL,
        link_type TEXT,
        lag_raw TEXT,
        lag_calendar TEXT,
        recorded_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_plan_dependency_version_snapshot ON plan_dependency_version(snapshot_id)
    """,
    # plan_external_dependency — висячие/внешние связи, не исчезают молча
    # (AC-115).
    """
    CREATE TABLE IF NOT EXISTS plan_external_dependency (
        external_dependency_id TEXT PRIMARY KEY,
        snapshot_id TEXT NOT NULL REFERENCES plan_snapshot(snapshot_id),
        local_task_key TEXT NOT NULL,
        external_ref TEXT,
        direction TEXT NOT NULL CHECK (direction IN ('predecessor', 'successor')),
        reason TEXT NOT NULL,
        recorded_at TEXT NOT NULL
    )
    """,
    # plan_resource_version — версионные атрибуты ресурса на снимке
    # (идентичность — в plan_resource_identity, Фаза 1).
    """
    CREATE TABLE IF NOT EXISTS plan_resource_version (
        resource_version_id TEXT PRIMARY KEY,
        snapshot_id TEXT NOT NULL REFERENCES plan_snapshot(snapshot_id),
        plan_id TEXT NOT NULL REFERENCES plan(plan_id),
        resource_key TEXT NOT NULL,
        uid TEXT,
        name TEXT,
        type TEXT,
        email TEXT,
        resource_group TEXT,
        max_units REAL,
        std_rate_raw TEXT,
        ot_rate_raw TEXT,
        cost_per_use REAL,
        extensions TEXT,
        recorded_at TEXT NOT NULL,
        UNIQUE(snapshot_id, resource_key)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_plan_resource_version_snapshot ON plan_resource_version(snapshot_id)
    """,
    # plan_resource_availability — изменение max_units по датам (таблица
    # доступности ресурса в MSP).
    """
    CREATE TABLE IF NOT EXISTS plan_resource_availability (
        availability_id TEXT PRIMARY KEY,
        resource_version_id TEXT NOT NULL REFERENCES plan_resource_version(resource_version_id),
        available_from TEXT,
        available_to TEXT,
        max_units REAL,
        recorded_at TEXT NOT NULL
    )
    """,
    # plan_assignment_version — назначение задача<->ресурс на снимке.
    # UQ(snapshot_id, task_key, resource_key).
    """
    CREATE TABLE IF NOT EXISTS plan_assignment_version (
        assignment_version_id TEXT PRIMARY KEY,
        snapshot_id TEXT NOT NULL REFERENCES plan_snapshot(snapshot_id),
        task_key TEXT NOT NULL,
        resource_key TEXT NOT NULL,
        units REAL,
        work_raw TEXT,
        start_raw TEXT,
        finish_raw TEXT,
        actual_work_raw TEXT,
        remaining_work_raw TEXT,
        recorded_at TEXT NOT NULL,
        UNIQUE(snapshot_id, task_key, resource_key)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_plan_assignment_version_snapshot ON plan_assignment_version(snapshot_id)
    """,
    # plan_assignment_timephased — почасовые/дневные сегменты работы
    # назначения (R-012 "ресурсы/назначения timephased").
    """
    CREATE TABLE IF NOT EXISTS plan_assignment_timephased (
        timephased_id TEXT PRIMARY KEY,
        assignment_version_id TEXT NOT NULL REFERENCES plan_assignment_version(assignment_version_id),
        period_start TEXT NOT NULL,
        period_end TEXT NOT NULL,
        work_raw TEXT,
        recorded_at TEXT NOT NULL
    )
    """,
    # plan_calendar_version — календарь снимка (R-012 "календари").
    """
    CREATE TABLE IF NOT EXISTS plan_calendar_version (
        calendar_version_id TEXT PRIMARY KEY,
        snapshot_id TEXT NOT NULL REFERENCES plan_snapshot(snapshot_id),
        calendar_key TEXT NOT NULL,
        name TEXT,
        base_calendar_key TEXT,
        minutes_per_day REAL,
        minutes_per_week REAL,
        recorded_at TEXT NOT NULL,
        UNIQUE(snapshot_id, calendar_key)
    )
    """,
    # plan_calendar_interval — рабочие дни недели/исключения календаря.
    """
    CREATE TABLE IF NOT EXISTS plan_calendar_interval (
        interval_id TEXT PRIMARY KEY,
        calendar_version_id TEXT NOT NULL REFERENCES plan_calendar_version(calendar_version_id),
        interval_kind TEXT NOT NULL CHECK (interval_kind IN ('weekday', 'exception')),
        day_or_date TEXT NOT NULL,
        working INTEGER NOT NULL,
        time_from TEXT,
        time_to TEXT,
        recorded_at TEXT NOT NULL
    )
    """,
    # plan_embedded_baseline_value — baseline-слоты 0..10 на задачу
    # (R-012/R-014: baseline не домысливается, хранится только фактически
    # присутствующий слот).
    """
    CREATE TABLE IF NOT EXISTS plan_embedded_baseline_value (
        baseline_value_id TEXT PRIMARY KEY,
        task_version_id TEXT NOT NULL REFERENCES plan_task_version(task_version_id),
        baseline_slot INTEGER NOT NULL CHECK (baseline_slot BETWEEN 0 AND 10),
        baseline_start TEXT,
        baseline_finish TEXT,
        baseline_duration_raw TEXT,
        baseline_work_raw TEXT,
        baseline_cost REAL,
        recorded_at TEXT NOT NULL,
        UNIQUE(task_version_id, baseline_slot)
    )
    """,
    # plan_mapping_revision / plan_identity_mapping — identity-mapping run
    # (R-018: вся использованная mapping revision фиксируется в run,
    # позднее исправление не переписывает старый ответ — append-only новая
    # ревизия, не UPDATE старой).
    """
    CREATE TABLE IF NOT EXISTS plan_mapping_revision (
        mapping_revision_id TEXT PRIMARY KEY,
        plan_id TEXT NOT NULL REFERENCES plan(plan_id),
        basis TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS plan_identity_mapping (
        identity_mapping_id TEXT PRIMARY KEY,
        mapping_revision_id TEXT NOT NULL REFERENCES plan_mapping_revision(mapping_revision_id),
        entity_kind TEXT NOT NULL CHECK (entity_kind IN ('task', 'resource')),
        local_key TEXT NOT NULL,
        identity_key TEXT NOT NULL,
        confidence TEXT NOT NULL CHECK (confidence IN ('confirmed', 'inferred', 'unknown')),
        evidence TEXT,
        recorded_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_plan_identity_mapping_rev ON plan_identity_mapping(mapping_revision_id)
    """,
    # plan_snapshot_selection — какой snapshot принят "базой" для lineage
    # (R-019/AC-120): default — первая доступная, явный выбор владельца не
    # переопределяется автоматическим default. Append-only: новая ревизия
    # ссылается на supersedes, старая строка не удаляется/не правится.
    """
    CREATE TABLE IF NOT EXISTS plan_snapshot_selection (
        selection_id TEXT PRIMARY KEY,
        lineage_id TEXT NOT NULL REFERENCES plan_lineage(lineage_id),
        snapshot_id TEXT NOT NULL REFERENCES plan_snapshot(snapshot_id),
        is_explicit INTEGER NOT NULL DEFAULT 0,
        basis TEXT NOT NULL,
        supersedes TEXT,
        recorded_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_plan_snapshot_selection_lineage ON plan_snapshot_selection(lineage_id)
    """,
    # plan_baseline_selection — какой embedded baseline-слот (0..10)
    # принят эталоном сравнения для плана (R-019, отдельно от выбора
    # snapshot). Та же политика default/explicit, append-only.
    """
    CREATE TABLE IF NOT EXISTS plan_baseline_selection (
        baseline_selection_id TEXT PRIMARY KEY,
        plan_id TEXT NOT NULL REFERENCES plan(plan_id),
        snapshot_id TEXT NOT NULL REFERENCES plan_snapshot(snapshot_id),
        baseline_slot INTEGER NOT NULL CHECK (baseline_slot BETWEEN 0 AND 10),
        is_explicit INTEGER NOT NULL DEFAULT 0,
        basis TEXT NOT NULL,
        supersedes TEXT,
        recorded_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_plan_baseline_selection_plan ON plan_baseline_selection(plan_id)
    """,
)

# ─────────────────────────────────────────────────────────────────────────
# Фаза 3 (P3.SCHEMA.1, R-015 последняя группа строк, R-016.1): persistence
# для аналитического модуля MppReader/plan_attribution.py+plan_scheduler.py
# (W5) — run/scenario/task_result/contribution квитанции — и `plan_projection`
# (generation/hash/status для MD-рендера, P3.MD.*). Append-only: повторный
# прогон с теми же входами создаёт НОВЫЙ run_id (R-035), старый не
# переписывается. Все FK ссылаются на один plan_id/snapshot_id (критерий
# готовности P3.SCHEMA.1).
# ─────────────────────────────────────────────────────────────────────────

PHASE3_ANALYSIS_DDL: tuple[str, ...] = (
    # plan_analysis_run — один аналитический прогон (R-035: все IDs/hash/
    # engine/target/endpoints/completeness/время). Смена baseline_selection_id/
    # mapping_revision_id создаёт новый run, не апдейтит существующий.
    """
    CREATE TABLE IF NOT EXISTS plan_analysis_run (
        run_id TEXT PRIMARY KEY,
        plan_id TEXT NOT NULL REFERENCES plan(plan_id),
        snapshot_a_id TEXT NOT NULL REFERENCES plan_snapshot(snapshot_id),
        snapshot_b_id TEXT NOT NULL REFERENCES plan_snapshot(snapshot_id),
        mapping_revision_id TEXT REFERENCES plan_mapping_revision(mapping_revision_id),
        baseline_selection_id TEXT REFERENCES plan_baseline_selection(baseline_selection_id),
        target_task_key TEXT,
        engine_name TEXT NOT NULL,
        engine_version TEXT,
        scale_basis TEXT,
        result_class TEXT NOT NULL,
        method TEXT,
        delta_obs_raw TEXT,
        delta_model_raw TEXT,
        residual_raw TEXT,
        completeness TEXT NOT NULL DEFAULT 'unknown',
        blockers TEXT,
        input_hash_a TEXT,
        input_hash_b TEXT,
        duration_ms INTEGER,
        scenario_count INTEGER,
        receipt_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_plan_analysis_run_plan ON plan_analysis_run(plan_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_plan_analysis_run_pair
        ON plan_analysis_run(snapshot_a_id, snapshot_b_id)
    """,
    # plan_analysis_scenario — один сценарий Shapley/последовательного
    # разложения (`2^n` для точного Shapley, R-034); кеш по group_ids_hash.
    """
    CREATE TABLE IF NOT EXISTS plan_analysis_scenario (
        scenario_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL REFERENCES plan_analysis_run(run_id),
        method TEXT NOT NULL CHECK (method IN ('sequential', 'sequential_reverse', 'shapley')),
        group_ids_json TEXT NOT NULL,
        applied_order INTEGER,
        is_valid INTEGER NOT NULL DEFAULT 1,
        finish_scale_value REAL,
        finish_raw TEXT,
        recorded_at TEXT NOT NULL,
        UNIQUE(run_id, method, group_ids_json)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_plan_analysis_scenario_run ON plan_analysis_scenario(run_id)
    """,
    # plan_analysis_task_result — per-task replay результат (ES/EF/LS/LF/
    # slack/driving, R-028/R-030), по каждому сценарию/эндпоинту прогона.
    """
    CREATE TABLE IF NOT EXISTS plan_analysis_task_result (
        task_result_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL REFERENCES plan_analysis_run(run_id),
        scenario_id TEXT REFERENCES plan_analysis_scenario(scenario_id),
        task_key TEXT NOT NULL,
        early_start TEXT,
        early_finish TEXT,
        late_start TEXT,
        late_finish TEXT,
        total_slack_raw TEXT,
        free_slack_raw TEXT,
        is_driving INTEGER NOT NULL DEFAULT 0,
        recorded_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_plan_analysis_task_result_run
        ON plan_analysis_task_result(run_id, task_key)
    """,
    # plan_analysis_contribution — signed+residual вклад каждой целостной
    # группы по каждому методу (последовательный/контрольный/Shapley,
    # R-031/R-033/R-034).
    """
    CREATE TABLE IF NOT EXISTS plan_analysis_contribution (
        contribution_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL REFERENCES plan_analysis_run(run_id),
        method TEXT NOT NULL CHECK (method IN ('sequential', 'sequential_reverse', 'shapley')),
        group_id TEXT NOT NULL,
        group_category TEXT,
        contribution_value REAL NOT NULL,
        contribution_raw TEXT,
        rank_in_order INTEGER,
        recorded_at TEXT NOT NULL,
        UNIQUE(run_id, method, group_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_plan_analysis_contribution_run
        ON plan_analysis_contribution(run_id)
    """,
    # plan_projection — generation/hash/status фактического MD-рендера
    # (P3.MD.1-2, R-024/R-025): temp -> hash-проверка -> atomic rename
    # протокол читает/пишет состояние через эту таблицу (не через mtime).
    """
    CREATE TABLE IF NOT EXISTS plan_projection (
        projection_id TEXT PRIMARY KEY,
        plan_id TEXT NOT NULL REFERENCES plan(plan_id),
        md_path TEXT NOT NULL,
        generation INTEGER NOT NULL,
        content_sha256 TEXT NOT NULL,
        last_snapshot_id TEXT REFERENCES plan_snapshot(snapshot_id),
        status TEXT NOT NULL CHECK (status IN ('ok', 'conflict', 'stale', 'failed')),
        conflict_detail TEXT,
        rendered_at TEXT NOT NULL,
        UNIQUE(plan_id, md_path)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_plan_projection_plan ON plan_projection(plan_id)
    """,
)

# Список миграций Фазы 0+. Пополняется в следующих фазах — НЕ переписывать
# задним числом уже применённые записи (append-only, R-016.3): новые поля
# добавляются новой миграцией, не правкой существующей.
MIGRATIONS: tuple[Migration, ...] = (
    # Фаза 0 пока не создаёт прикладных plan_*-таблиц — core-identity-таблицы
    # добавляет P1.SCHEMA.1-3. Явный маркер "phase0-baseline" фиксирует, что
    # реестр миграций работает и пуст по прикладным таблицам до Фазы 1.
    Migration(
        migration_id="0001_phase0_baseline",
        statements=(),
    ),
    # Фаза 1 (P1.SCHEMA.1-3): core identity + attempt/event + publication/
    # page-observation таблицы (R-015, R-016, R-009, R-010).
    Migration(
        migration_id="0002_phase1_core",
        statements=PHASE1_CORE_DDL,
    ),
    # Фаза 2 (P2.SCHEMA.1-8): версионные snapshot-данные полного графа плана
    # + качество/диагностика + mapping + выбор базы (R-012-019).
    Migration(
        migration_id="0003_phase2_snapshot",
        statements=PHASE2_SNAPSHOT_DDL,
    ),
    # Фаза 3 (P3.SCHEMA.1): run/scenario/task_result/contribution квитанции
    # аналитического модуля + plan_projection для MD-рендера (R-015, R-016.1).
    Migration(
        migration_id="0004_phase3_analysis",
        statements=PHASE3_ANALYSIS_DDL,
    ),
    # Фаза 3 доб. (P3.RAG.5, R-027): FTS по границам публикаций — селектор
    # «последний» разрешается в typed SQL (query.py), не по FTS rank
    # (AC-130). plan_fts — внешний контент (content='') со столбцами ровно
    # границ публикации: plan_id/publication_id/snapshot_id/representation/
    # anchor/generation + body (текст MD-секции). Запись — только из
    # render.py при рендере проекции (не на каждый ingest).
    Migration(
        migration_id="0005_phase3_fts",
        statements=(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS plan_fts USING fts5(
                plan_id UNINDEXED,
                publication_id UNINDEXED,
                snapshot_id UNINDEXED,
                representation UNINDEXED,
                anchor UNINDEXED,
                generation UNINDEXED,
                body
            )
            """,
        ),
    ),
    Migration(
        migration_id="0006_publication_trust",
        statements=(
            "ALTER TABLE plan_publication ADD COLUMN trust TEXT NOT NULL DEFAULT 'legacy_unverified' "
            "CHECK (trust IN ('legacy_unverified','verified_observation','verified_v1','verification_failed'))",
            "ALTER TABLE plan_publication ADD COLUMN historical_status TEXT",
            # The old table had no status column. 'registered' describes the
            # existing row, not an invented historical confirmation.
            "UPDATE plan_publication SET historical_status = 'registered'",
            "ALTER TABLE plan_import_attempt ADD COLUMN historical_status TEXT",
            "UPDATE plan_import_attempt SET historical_status = status",
            "ALTER TABLE plan_page_observation ADD COLUMN verification_status TEXT NOT NULL DEFAULT 'not_verified' "
            "CHECK (verification_status IN ('not_verified','verified_observation','verification_failed'))",
            "ALTER TABLE plan_page_observation ADD COLUMN verification_scope TEXT",
            "ALTER TABLE plan_page_observation ADD COLUMN verification_profile TEXT",
            "ALTER TABLE plan_page_observation ADD COLUMN verification_json TEXT",
            "ALTER TABLE plan_page_observation ADD COLUMN storage_sha256 TEXT",
        ),
    ),
)


# Stage 03. Earlier migration objects and their checksums are immutable.
IMPORT_DDL = (
    """CREATE TABLE plan_operation (
        operation_id TEXT PRIMARY KEY, action TEXT NOT NULL,
        plan_id TEXT REFERENCES plan(plan_id), lineage_id TEXT REFERENCES plan_lineage(lineage_id),
        context_json TEXT NOT NULL, preparation_revision INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        FOREIGN KEY(lineage_id,plan_id) REFERENCES plan_lineage(lineage_id,plan_id),
        CHECK(lineage_id IS NULL OR plan_id IS NOT NULL)
    )""",
    """CREATE TABLE plan_import_batch (
        batch_id TEXT PRIMARY KEY, manifest_version INTEGER NOT NULL,
        manifest_json TEXT NOT NULL, manifest_sha256 TEXT NOT NULL,
        source TEXT NOT NULL, created_at TEXT NOT NULL, inputs_frozen_at TEXT,
        completed_at TEXT, on_error TEXT NOT NULL CHECK(on_error IN ('continue','stop')),
        context_json TEXT NOT NULL, status TEXT NOT NULL, stop_reason TEXT
    )""",
    """CREATE TABLE plan_import_item (
        item_id TEXT PRIMARY KEY, operation_id TEXT NOT NULL UNIQUE REFERENCES plan_operation(operation_id),
        batch_id TEXT REFERENCES plan_import_batch(batch_id), ordinal INTEGER NOT NULL DEFAULT 0,
        plan_id TEXT REFERENCES plan(plan_id), lineage_id TEXT REFERENCES plan_lineage(lineage_id),
        original_name TEXT NOT NULL, original_locator TEXT NOT NULL, transport_json TEXT,
        source_mpp_sha256 TEXT, size_bytes INTEGER, container_sha256 TEXT, container_locator TEXT,
        zip_member TEXT, received_at TEXT NOT NULL, frozen_at TEXT, frozen_locator TEXT,
        source_version_date TEXT, source_version_basis TEXT,
        artifact_id TEXT REFERENCES plan_artifact(artifact_id), snapshot_id TEXT REFERENCES plan_snapshot(snapshot_id),
        normalization_profile_fingerprint TEXT, resolved_timezone TEXT, dedup_key TEXT,
        status TEXT NOT NULL DEFAULT 'not_started', error_code TEXT, retryable INTEGER NOT NULL DEFAULT 0,
        UNIQUE(batch_id,ordinal), FOREIGN KEY(lineage_id,plan_id) REFERENCES plan_lineage(lineage_id,plan_id),
        CHECK(lineage_id IS NULL OR plan_id IS NOT NULL)
    )""",
    """CREATE TABLE plan_import_attempt_new (
        attempt_id TEXT PRIMARY KEY, plan_id TEXT REFERENCES plan(plan_id),
        lineage_id TEXT REFERENCES plan_lineage(lineage_id), source_namespace TEXT,
        range_from TEXT, range_to TEXT, prepared_sha256 TEXT,
        status TEXT NOT NULL DEFAULT 'not_started', created_at TEXT NOT NULL, historical_status TEXT,
        operation_id TEXT REFERENCES plan_operation(operation_id), item_id TEXT REFERENCES plan_import_item(item_id),
        FOREIGN KEY(lineage_id,plan_id) REFERENCES plan_lineage(lineage_id,plan_id),
        CHECK(lineage_id IS NULL OR plan_id IS NOT NULL)
    )""",
    """INSERT INTO plan_import_attempt_new
        SELECT attempt_id,plan_id,lineage_id,source_namespace,range_from,range_to,prepared_sha256,
               status,created_at,historical_status,NULL,NULL FROM plan_import_attempt""",
    "DROP TABLE plan_import_attempt",
    "ALTER TABLE plan_import_attempt_new RENAME TO plan_import_attempt",
    "CREATE INDEX idx_plan_import_attempt_plan ON plan_import_attempt(plan_id)",
    "CREATE INDEX idx_plan_import_attempt_operation ON plan_import_attempt(operation_id)",
    "ALTER TABLE plan_attempt_event ADD COLUMN event_kind TEXT",
    "ALTER TABLE plan_attempt_event ADD COLUMN snapshot_id TEXT REFERENCES plan_snapshot(snapshot_id)",
    "CREATE UNIQUE INDEX uq_item_snapshot_commit ON plan_attempt_event(event_kind,detail) WHERE event_kind='snapshot_committed'",
)

# TEXT is deliberate: decimal quantities never travel through SQLite REAL.
VERSION_EXTRA_COLUMNS = {
    'plan_task_version': ('source_id','parent_task_key','calendar_key','effective_calendar_key','task_mode',
                          'duration_amount','duration_units','duration_elapsed','work_amount','work_units',
                          'percent_complete_decimal','source_json'),
    'plan_dependency_version': ('dependency_key','lag_amount','lag_units','lag_elapsed','calendar_basis','source_json'),
    'plan_resource_version': ('calendar_key','base_calendar_key','max_units_decimal','cost_per_use_decimal','source_json'),
    'plan_assignment_version': ('assignment_key','uid','units_decimal','work_amount','work_units',
                                'effective_calendar_key','source_json'),
    'plan_calendar_version': ('parent_key','minutes_per_day_decimal','minutes_per_week_decimal','source_json'),
    'plan_resource_availability': ('max_units_decimal','source_json'),
    'plan_assignment_timephased': ('work_amount','work_units','source_json'),
    'plan_embedded_baseline_value': ('baseline_cost_decimal','source_json'),
}
SNAPSHOT_SEMANTICS_DDL = (
    "ALTER TABLE plan_snapshot ADD COLUMN normalization_profile_fingerprint TEXT",
    "ALTER TABLE plan_snapshot ADD COLUMN resolved_timezone TEXT",
    "ALTER TABLE plan_snapshot ADD COLUMN source_mpp_sha256 TEXT",
    "ALTER TABLE plan_snapshot ADD COLUMN dedup_key TEXT",
    "ALTER TABLE plan_snapshot ADD COLUMN normalized_data_sha256 TEXT",
    "ALTER TABLE plan_snapshot ADD COLUMN source_json TEXT",
    "ALTER TABLE plan_snapshot ADD COLUMN version_counts_json TEXT",
    "CREATE UNIQUE INDEX uq_snapshot_dedup_key ON plan_snapshot(dedup_key) WHERE dedup_key IS NOT NULL",
    """CREATE UNIQUE INDEX uq_snapshot_semantic_scope ON plan_snapshot
        (plan_id,lineage_id,source_mpp_sha256,representation,normalization_profile_fingerprint,resolved_timezone)
        WHERE normalization_profile_fingerprint IS NOT NULL""",
    # Parallel assignments to the same task/resource are independent records.
    """CREATE TABLE plan_assignment_version_new (
        assignment_version_id TEXT PRIMARY KEY, snapshot_id TEXT NOT NULL REFERENCES plan_snapshot(snapshot_id),
        task_key TEXT NOT NULL, resource_key TEXT NOT NULL, units REAL, work_raw TEXT,
        start_raw TEXT, finish_raw TEXT, actual_work_raw TEXT, remaining_work_raw TEXT, recorded_at TEXT NOT NULL
    )""",
    "INSERT INTO plan_assignment_version_new SELECT * FROM plan_assignment_version",
    "DROP TABLE plan_assignment_version",
    "ALTER TABLE plan_assignment_version_new RENAME TO plan_assignment_version",
    "CREATE INDEX idx_plan_assignment_version_snapshot ON plan_assignment_version(snapshot_id)",
    """CREATE TABLE plan_calendar_interval_new (
        interval_id TEXT PRIMARY KEY, calendar_version_id TEXT NOT NULL REFERENCES plan_calendar_version(calendar_version_id),
        interval_kind TEXT NOT NULL CHECK(interval_kind IN ('weekday','exception')),
        day_or_date TEXT NOT NULL, working INTEGER, time_from TEXT, time_to TEXT, recorded_at TEXT NOT NULL
    )""",
    "INSERT INTO plan_calendar_interval_new SELECT * FROM plan_calendar_interval",
    "DROP TABLE plan_calendar_interval",
    "ALTER TABLE plan_calendar_interval_new RENAME TO plan_calendar_interval",
) + tuple(f"ALTER TABLE {table} ADD COLUMN {column} " + ("INTEGER" if column in ("duration_elapsed","lag_elapsed") else "TEXT")
          for table, columns in VERSION_EXTRA_COLUMNS.items() for column in columns) + (
    "CREATE UNIQUE INDEX uq_assignment_source_key ON plan_assignment_version(snapshot_id,assignment_key) WHERE assignment_key IS NOT NULL",
)
MIGRATIONS += (
    Migration('0007_durable_imports', IMPORT_DDL),
    Migration('0008_snapshot_semantics', SNAPSHOT_SEMANTICS_DDL),
)


def all_plan_table_names() -> tuple[str, ...]:
    """Имена всех таблиц, которые когда-либо вводятся этим пакетом.

    Используется тестом `test_drop_all_preserves_plan_tables`, чтобы
    зафиксировать инвариант: ни одна из них не должна появиться в списке
    `mofs_index.db.drop_all()`/`drop_docs()`.
    """
    return (
        "plan_operation",
        "plan_import_batch",
        "plan_import_item",
        "plan_schema_migration",
        "plan",
        "plan_lineage",
        "plan_artifact",
        "plan_task_identity",
        "plan_resource_identity",
        "plan_import_attempt",
        "plan_attempt_event",
        "plan_publication",
        "plan_page_observation",
        "plan_publication_page_link",
        # Фаза 2 (P2.SCHEMA.1-8)
        "plan_snapshot",
        "plan_publication_snapshot",
        "plan_snapshot_collection",
        "plan_quality_issue",
        "plan_task_version",
        "plan_task_segment",
        "plan_dependency_version",
        "plan_external_dependency",
        "plan_resource_version",
        "plan_resource_availability",
        "plan_assignment_version",
        "plan_assignment_timephased",
        "plan_calendar_version",
        "plan_calendar_interval",
        "plan_embedded_baseline_value",
        "plan_mapping_revision",
        "plan_identity_mapping",
        "plan_snapshot_selection",
        "plan_baseline_selection",
        # Фаза 3 (P3.SCHEMA.1)
        "plan_analysis_run",
        "plan_analysis_scenario",
        "plan_analysis_task_result",
        "plan_analysis_contribution",
        "plan_projection",
        # Фаза 3 доб. (P3.RAG.5)
        "plan_fts",
    )
