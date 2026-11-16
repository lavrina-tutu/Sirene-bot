"""Read-back evidence for the existing publisher; no CLI and no schedule proof."""
from __future__ import annotations

import hashlib
import importlib.util
import re
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from xml.etree import ElementTree as ET

from macro import MacroInfo, find_macros


@dataclass
class VerificationResult:
    ok: bool
    checks: dict[str, bool] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    expected_sha256: str | None = None
    actual_sha256: str | None = None
    scope: str = "current_state"
    profile: str = "stage01-readback-v1"


class PublicationVerificationError(RuntimeError):
    """A remote effect exists but publication has not been confirmed."""


def verify_attachment_bytes(raw: bytes, expected_sha256: str) -> VerificationResult:
    actual = hashlib.sha256(raw).hexdigest()
    valid_hash = bool(re.fullmatch(r"[0-9a-f]{64}", expected_sha256 or ""))
    ok = valid_hash and actual == expected_sha256
    return VerificationResult(
        ok, {"sha256": ok}, [] if ok else ["attachment SHA-256 mismatch"],
        expected_sha256, actual, scope="attachment_version",
    )


@lru_cache(maxsize=1)
def _skeleton_verifier():
    # Reuse the sibling component without copying its implementation or
    # changing sys.path. Section-patching and brief-specific rules do not
    # describe a Gantt page; only its version/macro-count checks apply here.
    path = Path(__file__).resolve().parents[2] / "tutu-confluence-jira/scripts/verify_skeleton.py"
    spec = importlib.util.spec_from_file_location("_editplan_verify_skeleton", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.verify_skeleton


def _canonical_storage(storage: str) -> str:
    wrapped = ('<root xmlns:ac="http://atlassian.com/content" '
               'xmlns:ri="http://atlassian.com/resource/identifier">' + storage + '</root>')
    return ET.canonicalize(wrapped.replace("&nbsp;", "&#160;"))


def verify_storage_observation(
    storage: str,
    *,
    expected_storage: str,
    expected_macro: MacroInfo,
    expected_itogo: tuple[str, str, int],
    expected_version: int,
    actual_version: int,
) -> VerificationResult:
    """Check actual GET against intended storage, preserving foreign content.

    Canonical XML permits attribute order/empty-tag serialization changes;
    every other unexpected change is rejected conservatively.
    """
    from itogo import verify_itogo

    checks = {}
    errors = []
    skeleton = _skeleton_verifier()(
        storage, expected_version=expected_version, actual_version=actual_version,
        reference_macro_count=len(re.findall(r"<ac:structured-macro\b", expected_storage)),
    )
    for key in ("version", "macro_count"):
        checks["skeleton_" + key] = skeleton.checks[key]
    # For this observation we require the exact version written, not >=.
    checks["page_version"] = actual_version == expected_version
    try:
        macros = find_macros(storage)
        checks["one_gantt_macro"] = len(macros) == 1
        for key in ("macro_id", "param_id", "param_hash", "attachment_name"):
            checks[key] = len(macros) == 1 and getattr(macros[0], key) == getattr(expected_macro, key)
    except ValueError as exc:
        checks["one_gantt_macro"] = False
        errors.append(str(exc))
    checks.update(verify_itogo(storage, *expected_itogo))
    try:
        checks["storage_preserved"] = _canonical_storage(storage) == _canonical_storage(expected_storage)
    except ET.ParseError as exc:
        checks["storage_preserved"] = False
        errors.append(f"invalid storage XML: {exc}")
    errors.extend(key for key, ok in checks.items() if not ok)
    return VerificationResult(all(checks.values()), checks, errors)
