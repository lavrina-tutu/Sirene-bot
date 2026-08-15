# SOUL.md / AGENTS.md Restructure — 2026-08-11

Complete restructure of default profile's SOUL.md and AGENTS.md per Hermes documentation: SOUL = identity, AGENTS = operational rules. Includes final optimization pass (dedup audit).

## SOUL.md — Before vs After

| Metric | Before | After |
|--------|--------|-------|
| Size | 5,907 bytes | 2,296 bytes |
| Sections | Identity, Character, Values (4+10), Implementation principles, R0-R3 | Identity, Character, Principles (3), Hard rules (4) |
| Age | 22 | 30 |

## AGENTS.md — Evolution

| Version | Size | Key change |
|---------|------|------------|
| Before | 1,931 B | Original TZ/AGENTS.md (shared with tz-dev) |
| v1 (isolation) | 1,931 B | `~/AGENTS.md` created, `terminal.cwd` isolated |
| v2 (restructure) | 3,800 B | +Impl principles (moved from SOUL), +R1-R2, +Skills, +Dev routing |
| v3 (dedup) | 3,514 B | −Conventions (duplicated SOUL), −workvault-rag, −Profiles |
| **v4 (final)** | **3,225 B** | −Token economy, −Safety, −Consistency (duplicated SOUL), −3 tool paths, −R0 merge |

## Final AGENTS.md (v4)

```markdown
# Default Profile — Сирень (повседневные задачи, не dev). Личность: SOUL.md.

## Implementation principles
- Integrity — do not distort, do not fabricate. Don't know → say so.
- Maintainability — decisions reproducible without extra explanation.

## Правила диалога
R1 — Ответ первым.
R2 — Старое не блокирует.
R3 — Вопросы Саше. По одному, варианты, рекомендация.

## Приоритет скиллов
Перед ЛЮБОЙ задачей — проверить <available_skills>. Совпадение → skill_view(name).

## Маршрутизация dev-задач → tz-dev, HermesDEV
[Таблица триггеров + процесс передачи]

## Пути
WorkVault, Inbox, Бэклог
```

## Dedup audit — what was removed and why

| Removed | From | Reason |
|---------|------|--------|
| Token economy | AGENTS | Дубль SOUL «чётко и по делу» |
| Safety (no action without go-ahead) | AGENTS | Дубль SOUL R3 |
| Consistency (same style/language) | AGENTS | Дубль SOUL «всегда на русском» |
| Общие конвенции (язык, обращение, футер) | AGENTS | Дубль SOUL характер |
| workvault-rag skill mention | AGENTS | Covered by general skills-first rule |
| Profile descriptions (default, tz-dev) | AGENTS | Система знает профиль |
| Tool paths: Скиллы, Кроны, Память | AGENTS | Инструменты знают свои пути |
| Implementation principles (5 шт.) | SOUL | → AGENTS.md (operational, not identity) |
| R0, R1, R2 | SOUL | → AGENTS.md (dialog procedures) |
| Ценности (14 пунктов) | SOUL | → 3 главных принципа |

## Design decisions

1. **R3, clarify ban, cron/gateway rules stay in SOUL** — critical safety rules, must load in slot #1 even if `--ignore-rules` skips AGENTS.md. Violates docs' SOUL=who/AGENTS=how split intentionally.

2. **Приоритет скиллов stays in AGENTS** despite system prompt duplication — user explicitly chose to keep it. Explicit reinforcement improves compliance.

3. **R3 — Вопросы Саше** stays in AGENTS (not SOUL) — procedural detail is operational, not identity. Numbered to match R1/R2.

4. **What stays in AGENTS:** only rules that are NEITHER in SOUL NOR injected by the system. Two Implementation Principles (Integrity, Maintainability — no SOUL equivalent), three dialog rules (procedural), dev routing table, three user paths (not auto-discovered).

## Token savings

SOUL.md: 5.9 KB → 2.3 KB (−61%)
AGENTS.md: 1.9 KB → 3.2 KB (+68%, but gained unique operational content)
Combined: 7.8 KB → 5.5 KB (−29%)
After dedup pass from peak: 9.7 KB → 5.5 KB (−43%)
