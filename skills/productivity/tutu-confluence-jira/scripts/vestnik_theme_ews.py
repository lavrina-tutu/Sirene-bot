#!/usr/bin/env python3
"""Inline EWS ResolveNames for VestnikTheme (latin-only)."""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from vestnik_theme_errors import VestnikError, report_technical

__all__ = ["GalPerson", "is_latin_query", "resolve_names"]

MEETING_SCHEDULER = Path.home() / "USERTOOLS" / "MeetingScheduler"

_CYRILLIC = re.compile(r"[а-яёА-ЯЁ]")


@dataclass
class GalPerson:
  login: str
  email: str
  department: str
  team: str
  job_title: str
  manager_display: str
  reports_to_login: str


def is_latin_query(s: str) -> bool:
  return _CYRILLIC.search(s or "") is None


def _import_exchange_client():
  if str(MEETING_SCHEDULER) not in sys.path:
    sys.path.insert(0, str(MEETING_SCHEDULER))
  import exchange_client  # type: ignore

  return exchange_client


def _login_from_email(email: str) -> str:
  if "@" in email:
    return email.split("@", 1)[0].lower()
  return (email or "").lower()


def _parse_gal_item(item: Any) -> GalPerson | None:
  if isinstance(item, Exception):
    return None
  mailbox, contact = item
  if mailbox is None:
    return None
  email = getattr(mailbox, "email_address", "") or ""
  display_name = getattr(mailbox, "name", "") or email
  department = ""
  job_title = ""
  manager_display = ""
  team = ""
  if contact is not None:
    department = getattr(contact, "department", "") or ""
    job_title = getattr(contact, "job_title", "") or ""
    display_name = getattr(contact, "display_name", None) or display_name
    manager = getattr(contact, "manager", None)
    if manager is not None:
      manager_display = getattr(manager, "name", "") or ""
  return GalPerson(
    login=_login_from_email(email),
    email=email,
    department=department,
    team=team or department,
    job_title=job_title,
    manager_display=manager_display,
    reports_to_login="",
  )


def resolve_names(
  query: str,
  *,
  account=None,
  protocol_resolve: Callable[..., Any] | None = None,
) -> list[GalPerson]:
  if not is_latin_query(query):
    return []
  if protocol_resolve is None:
    exc_mod = _import_exchange_client()
    if not exc_mod.check_vpn():
      report_technical("block", "VPN not available for EWS")
      raise VestnikError(stage="block", message="VPN not available for EWS")
    account = account or exc_mod.get_account()
    protocol_resolve = account.protocol.resolve_names

  try:
    results = list(
      protocol_resolve(
        names=[query],
        return_full_contact_data=True,
        search_scope="ActiveDirectory",
      )
    )
  except Exception as exc:
    msg = str(exc)
    if "No results were found" in msg or "ErrorNameResolutionNoResults" in msg:
      return []
    report_technical("block", msg)
    raise VestnikError(stage="block", message=msg) from exc

  out: list[GalPerson] = []
  for item in results:
    person = _parse_gal_item(item)
    if person is not None:
      out.append(person)
  return out
