"""JSON schemas for charter batches and architecture themes."""
from __future__ import annotations

from typing import Any

_SECTION_ITEM = {
  "type": "object",
  "properties": {
    "field": {"type": "string"},
    "content": {"type": "string"},
    "source_page_id": {"type": "string"},
    "status": {"type": "string"},
  },
  "required": ["field", "content", "source_page_id"],
  "additionalProperties": False,
}

_BATCH_SCHEMA = {
  "type": "object",
  "properties": {
    "batch": {"type": "integer"},
    "sections": {
      "type": "array",
      "items": _SECTION_ITEM,
    },
  },
  "required": ["batch", "sections"],
  "additionalProperties": False,
}

CHARTER_BATCH_FIELDS: dict[int, list[str]] = {
  1: [
    "Параметры/сроки", "Описание и границы", "КТ", "ИСР",
    "Календарный план", "Ресурсный план", "Критерии приёмки",
  ],
  2: [
    "Что получит Туту", "Если проекта не будет", "Как заказчик поймёт",
    "Цель", "Финмодель", "Ключевые поставки", "Бюджет",
  ],
  3: [
    "Контекст", "Реестр стейкхолдеров", "Матрица коммуникаций",
    "Допущения", "Ограничения", "Реестр угроз и рисков",
  ],
  4: [
    "Повтор инвариантов ceil", "Повтор инвариантов пилот",
    "Повтор инвариантов time", "Повтор инвариантов бюджет",
    "Повтор инвариантов сроки", "Повтор инвариантов формат",
  ],
  5: [
    "Дожим стейкхолдеров", "Дожим рисков", "Дожим коммуникаций",
    "Дожим допущений", "Дожим ограничений",
  ],
}

CHARTER_BATCH_SCHEMAS: dict[int, dict[str, Any]] = {
  n: {**_BATCH_SCHEMA, "title": f"charter_batch_{n}"}
  for n in range(1, 6)
}

ARCHITECTURE_THEME_SCHEMAS: dict[str, dict[str, Any]] = {
  "architecture": {
    "type": "object",
    "title": "architecture_theme",
    "properties": {
      "theme": {"type": "string"},
      "sections": {
        "type": "array",
        "items": _SECTION_ITEM,
      },
    },
    "required": ["theme", "sections"],
    "additionalProperties": False,
  },
  "security": {
    "type": "object",
    "title": "security_theme",
    "properties": {
      "theme": {"type": "string"},
      "sections": {
        "type": "array",
        "items": _SECTION_ITEM,
      },
    },
    "required": ["theme", "sections"],
    "additionalProperties": False,
  },
}
