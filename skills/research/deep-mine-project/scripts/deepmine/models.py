"""Shared data models."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


SCHEMA_VERSION = "1.0"
PAGE_KIND = "confluence_page"


@dataclass
class Manifest:
  schema_version: str
  slug: str
  pages: dict[str, dict[str, Any]]
  attachments: list[dict[str, Any]] = field(default_factory=list)
  digests: dict[str, Any] = field(default_factory=dict)

  def to_dict(self) -> dict[str, Any]:
    return {
      "schema_version": self.schema_version,
      "slug": self.slug,
      "pages": self.pages,
      "attachments": self.attachments,
      "digests": self.digests,
    }
