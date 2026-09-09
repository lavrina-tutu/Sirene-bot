"""Shared data models."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


SCHEMA_VERSION = "1.1"
PAGE_KIND = "confluence_page"

VALID_EDGE_TYPES = frozenset({"parent", "child", "links_to", "seed"})
VALID_NODE_KINDS = frozenset({"page", "stub"})


@dataclass
class GraphNode:
  page_id: str
  title: str
  space: str
  kind: str
  seed: bool = False
  local_path: str | None = None
  version: str | None = None
  content_sha256: str | None = None
  stub_reason: str | None = None

  def to_dict(self) -> dict[str, Any]:
    data: dict[str, Any] = {
      "title": self.title,
      "space": self.space,
      "kind": self.kind,
      "seed": self.seed,
    }
    if self.local_path:
      data["local_path"] = self.local_path
    if self.version:
      data["version"] = self.version
    if self.content_sha256:
      data["content_sha256"] = self.content_sha256
    if self.stub_reason:
      data["stub_reason"] = self.stub_reason
    return data


@dataclass
class GraphEdge:
  from_id: str
  to_id: str
  type: str
  target_kind: str | None = None

  def to_dict(self) -> dict[str, Any]:
    data: dict[str, Any] = {"from": self.from_id, "to": self.to_id, "type": self.type}
    if self.target_kind:
      data["target_kind"] = self.target_kind
    return data


@dataclass
class Manifest:
  schema_version: str
  slug: str
  pages: dict[str, dict[str, Any]]
  attachments: list[dict[str, Any]] = field(default_factory=list)
  digests: dict[str, Any] = field(default_factory=dict)
  contexts: dict[str, Any] = field(default_factory=dict)

  def to_dict(self) -> dict[str, Any]:
    return {
      "schema_version": self.schema_version,
      "slug": self.slug,
      "pages": self.pages,
      "attachments": self.attachments,
      "digests": self.digests,
      "contexts": self.contexts,
    }
