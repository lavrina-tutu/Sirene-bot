#!/usr/bin/env python3
"""ResolveAIDUnit: AC read + GAL in-memory + walk for VestnikTheme."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

from vestnik_theme_ews import GalPerson, resolve_names
from vestnik_theme_errors import HitlStop, VestnikError

__all__ = [
  "AID_HEADS",
  "AID_DIRECTOR",
  "KNOWN_BLOCK_LABELS",
  "HEAD_BLOCK_LABELS",
  "OrgNode",
  "ContactLookup",
  "contact_to_node",
  "gal_to_node",
  "lookup_author",
  "lookup_or_gal",
  "walk_aid_unit",
  "format_block",
  "_load_store",
]

ANYWHERE_CONTACTS = Path.home() / "USERTOOLS" / "AnywhereContacts"
CONTACTS_ENC = Path.home() / "WorkVault" / "Contacts" / "contacts.enc"

AID_HEADS = frozenset({
  "peretyatkova", "zhirov", "kotelnikova", "rasov",
  "nabieva", "alekseeva.ym", "sereda", "tkachenkoav",
})
AID_DIRECTOR = "aralov"
KNOWN_BLOCK_LABELS = {"DS", "BI", "MLE", "DA", "DE", "DS/MLE"}
HEAD_BLOCK_LABELS: dict[str, str] = {}


@dataclass
class OrgNode:
  login: str
  department: str
  team: str
  reports_to: str


class ContactLookup(Protocol):
  def get_contact(self, login: str) -> dict[str, Any] | None: ...
  def find_contacts(self, query: str) -> list[dict[str, Any]]: ...


def _load_store():
  if str(ANYWHERE_CONTACTS) not in sys.path:
    sys.path.insert(0, str(ANYWHERE_CONTACTS))
  from anywhere_contacts import create_store  # type: ignore

  key = os.environ.get("CONTACTS_ENCRYPTION_KEY", "")
  if not key:
    raise VestnikError(stage="block", message="CONTACTS_ENCRYPTION_KEY not set")
  return create_store(CONTACTS_ENC, key)


def contact_to_node(contact: dict[str, Any]) -> OrgNode:
  login = str(contact.get("login") or "").lower()
  return OrgNode(
    login=login,
    department=str(contact.get("department") or ""),
    team=str(contact.get("team") or ""),
    reports_to=str(contact.get("reports_to") or "").lower(),
  )


def gal_to_node(person: GalPerson) -> OrgNode:
  return OrgNode(
    login=person.login.lower(),
    department=person.department,
    team=person.team or person.department,
    reports_to=person.reports_to_login.lower() if person.reports_to_login else "",
  )


def lookup_author(
  username: str,
  *,
  store: ContactLookup,
  userkey: str | None = None,
) -> OrgNode | None:
  login = username.lower()
  contact = store.get_contact(login)
  if contact:
    return contact_to_node(contact)
  hits = store.find_contacts(username)
  if len(hits) == 1:
    return contact_to_node(hits[0])
  return None


def _gal_lookup(
  username: str,
  *,
  email_hint: str | None,
  ews_resolve: Callable[[str], list[GalPerson]],
) -> GalPerson | None:
  queries: list[str] = []
  if is_latin(username):
    queries.append(username)
    queries.append(f"{username}@tutu.ru")
  if email_hint:
    queries.append(email_hint)
  seen: set[str] = set()
  for q in queries:
    q = q.strip()
    if not q or q in seen:
      continue
    seen.add(q)
    hits = ews_resolve(q)
    if hits:
      return hits[0]
  return None


def is_latin(s: str) -> bool:
  from vestnik_theme_ews import is_latin_query
  return is_latin_query(s)


def lookup_or_gal(
  username: str,
  *,
  store: ContactLookup,
  ews_resolve: Callable[[str], list[GalPerson]],
  email_hint: str | None = None,
) -> tuple[OrgNode, str]:
  node = lookup_author(username, store=store, userkey=None)
  if node:
    return node, "ac"
  person = _gal_lookup(username, email_hint=email_hint, ews_resolve=ews_resolve)
  if person is None:
    raise HitlStop(
      kind="contact_missing",
      message=f"контакт не найден в AC и GAL: {username}",
    )
  return gal_to_node(person), "gal"


def format_block(department: str, team: str, head_login: str | None) -> str:
  if head_login and head_login in HEAD_BLOCK_LABELS:
    return HEAD_BLOCK_LABELS[head_login]
  for candidate in (team, department):
    c = (candidate or "").strip()
    if not c:
      continue
    for label in KNOWN_BLOCK_LABELS:
      if c.casefold() == label.casefold():
        return label
  return (department or team or "").strip()


def walk_aid_unit(
  node: OrgNode,
  *,
  store: ContactLookup,
  gal_nodes: dict[str, OrgNode],
) -> tuple[str, str]:
  current = node
  previous: OrgNode | None = None
  visited: set[str] = set()
  limit = 20

  for _ in range(limit):
    if current.login in visited:
      break
    visited.add(current.login)

    if current.login in AID_HEADS:
      block = format_block(current.department, current.team, current.login)
      return block, ""

    if current.login == AID_DIRECTOR:
      if previous is not None:
        block = format_block(previous.department, previous.team, None)
        return block, ""
      return "", "контакт/блок не найден"

    previous = current
    if not current.reports_to:
      return "", "контакт/блок не найден"

    nxt_login = current.reports_to.lower()
    if nxt_login == AID_DIRECTOR:
      block = format_block(previous.department, previous.team, None) if previous else ""
      return block, "" if block else "контакт/блок не найден"

    nxt = gal_nodes.get(nxt_login)
    if nxt is None:
      contact = store.get_contact(nxt_login)
      if contact:
        nxt = contact_to_node(contact)
      else:
        return "", "контакт/блок не найден"
    current = nxt

  return "", "контакт/блок не найден"
