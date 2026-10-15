# Бриф для архитектора: ТЗ deep-mine-project

Цель: Полуавтоматический сбор полного контекста проекта в MD-архив (Confluence + MPP + встречи), сжатие в digest'ы со связями (digest<->источник, digest<->digest), обновление по изменению страниц, передача сжатых контекстов архитектору (Cursor) для анализа и подготовки проектной документации.

## Собранный контекст
```json
{
  "confluence_root": "493477568 (Trisigma пилот, DPAN)",
  "pmo_brief": "490166551",
  "pmo_charter": "490167911",
  "pages_total": 33,
  "canon_l0": "~/WorkVault/Confluence/.../index.md (полные MD, frontmatter: confluence_id/title/confluence_url/space/version/synced_at)",
  "overlay_l1": "~/WorkVault/Projects/TrisigmaFull/ (MANIFEST.json, TREE.md, SOURCES.md)",
  "mpp_plan": "MPP 'Полное внедрение AB-платформы Trisigma' (84 задач, 15 ресурсов, 71 назначение, 2026-04→2028-01)",
  "meetings": "~91 встреча Trisigma/Антибот (summary+transcript)",
  "entity": "~/WorkVault/Entities/trisigma/"
}
```

## Решения Саши
- название: deep-mine-project
- вариант 4: P0-сбор (навигатор+digest), обогащение (связи/полнотекст) после первого архива
- весь архив в MD + кликабельные ссылки
- скан PMO-пространства
- архитектор продумал связи: digest->источник, digest<->digest, синхронизация
- обновление страниц ежедневно/по требованию

## Требуется от архитектора
Написать полноценное ТЗ по стандарту tz-workflow (разделы: цель, вход/выход, архитектура, шаги, связи digest-архива, синхронизация, критерии успеха, что НЕ трогать, связи с экосистемой, контракты).
