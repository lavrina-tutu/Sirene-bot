"""Follow-outbound link policy for graph layer A."""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from .graph import extract_outbound_page_ids
from .project_config import FollowPolicy

_JIRA_RE = re.compile(r"hq\.tutu\.ru/browse/([A-Z][A-Z0-9]+-\d+)", re.IGNORECASE)
_ATTACHMENT_RE = re.compile(r"/download/attachments/", re.IGNORECASE)
_ANCHOR_RE = re.compile(r"#")


def parse_follow_outbound(body: str) -> set[str]:
  """Extract outbound pageIds from L0 body."""
  return extract_outbound_page_ids(body)


def target_kind_from_url(url: str) -> str | None:
  if _JIRA_RE.search(url):
    return "jira"
  if _ATTACHMENT_RE.search(url):
    return "attachment"
  if "#" in url and "pageId=" not in url:
    return "anchor"
  return None


def is_denylist_title(title: str, policy: FollowPolicy) -> bool:
  lower = title.lower()
  for sub in policy.denylist_title_substrings:
    if sub.lower() in lower:
      return True
  return False


def stub_reason(
  *,
  space: str | None,
  title: str | None,
  policy: FollowPolicy,
  over_limit: bool = False,
) -> str:
  if over_limit:
    return "max_outbound_pull exceeded"
  if title and is_denylist_title(title, policy):
    return "denylist title"
  if space and space not in policy.allowed_spaces:
    return f"unknown space: {space}"
  if not space:
    return "unknown space"
  return "policy stub"


def classify_outbound(
  page_id: str,
  *,
  space: str | None,
  title: str | None,
  policy: FollowPolicy,
  known_spaces: set[str],
  pull_count: int,
) -> tuple[str, str | None]:
  """Return (action, stub_reason). action is 'pull' or 'stub'."""
  if not policy.enabled:
    return "stub", "follow disabled"
  if pull_count >= policy.max_outbound_pull:
    return "stub", stub_reason(space=space, title=title, policy=policy, over_limit=True)
  if title and is_denylist_title(title, policy):
    return "stub", stub_reason(space=space, title=title, policy=policy)
  if space and space in policy.allowed_spaces:
    return "pull", None
  if space and space not in known_spaces:
    return "stub", stub_reason(space=space, title=title, policy=policy)
  return "stub", stub_reason(space=space, title=title, policy=policy)


def extract_non_page_links(body: str) -> list[tuple[str, str]]:
  """Return list of (url_fragment, target_kind) for non-page links."""
  results: list[tuple[str, str]] = []
  for match in _JIRA_RE.finditer(body):
    results.append((match.group(0), "jira"))
  for line in body.splitlines():
    if "pageId=" in line:
      continue
    kind = target_kind_from_url(line)
    if kind:
      results.append((line.strip()[:120], kind))
  return results
