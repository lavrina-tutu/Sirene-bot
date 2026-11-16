"""Thin adapter of the installed unified config/env loaders.

Archive settings never request credentials. No per-skill .env or loader priority.
"""
from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

LIB = Path.home() / ".hermes" / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))
import usertools_config as unified
from usertools_env import load_usertools_env, _parse_env_file

SETTING_KEYS = (
    "WORKVAULT_PATH", "CONFLUENCE_URL", "CACHE_DIR", "MPXJ_PYTHON",
    "MPP_READ_TIMEOUT_SECONDS", "HTTP_TIMEOUT_SECONDS", "HTTP_RETRY_LIMIT",
    "MPP_MAX_BYTES", "ZIP_MAX_BYTES", "ZIP_MAX_ENTRIES", "ZIP_MAX_UNPACKED_BYTES", "ZIP_MAX_RATIO",
    "NORMALIZATION_PROFILE", "SUMMARY_PROFILE", "PLUGIN_PROFILE",
)
ENV_PATH = Path.home() / "USERTOOLS" / "ConfluenceSync" / ".env"  # explicit legacy adapter only


@dataclass(frozen=True)
class Settings:
    values: dict[str, str]
    sources: dict[str, str]


def load_settings(*, ecosystem_path=None) -> Settings:
    values = unified.load_tool_config("edit_plan_confluence", keys=list(SETTING_KEYS),
                                      ecosystem_path=ecosystem_path, required=False)
    sources = {key: r.source for key in values
               if (r := unified.resolve_key("edit_plan_confluence", key, ecosystem_path=ecosystem_path)) is not None}
    return Settings(values, sources)


def load_confluence_env(env_path: Path | None = None) -> dict[str, str]:
    """Compatibility API; default respects unified_only without local .env.

    An explicit path is the old allowlisted import API, never used implicitly.
    """
    if env_path is not None:
        values = _parse_env_file(Path(env_path))
        out = {k: values[k] for k in ("CONFLUENCE_TOKEN", "WORKVAULT_PATH") if values.get(k)}
    else:
        load_usertools_env()  # installed shared secret source; no local fallback
        status = unified.migration_status(unified.load_manifest(), "confluence_sync")
        if status in ("not_started", "dual_read") or unified._legacy_mode():
            load_usertools_env(ENV_PATH)
        token = os.environ.get("CONFLUENCE_TOKEN")
        if not token:
            raise RuntimeError("CONFLUENCE_TOKEN missing in unified credential source")
        out = {"CONFLUENCE_TOKEN": token}
        workvault = load_settings().values.get("WORKVAULT_PATH")
        if workvault:
            out["WORKVAULT_PATH"] = workvault
    if not out.get("CONFLUENCE_TOKEN"):
        raise RuntimeError("CONFLUENCE_TOKEN missing in unified credential source")
    return out


def get_token() -> str:
    return load_confluence_env()["CONFLUENCE_TOKEN"]


def get_workvault_path() -> Path:
    value = load_settings().values.get("WORKVAULT_PATH")
    if not value:
        raise RuntimeError("WORKVAULT_PATH missing in unified configuration")
    return Path(value).expanduser().resolve()


def page_url(page_id: str | int) -> str:
    return f"{load_settings().values['CONFLUENCE_URL'].rstrip('/')}/pages/viewpage.action?pageId={page_id}"


# Existing imports in conf_client remain compatible; canonical value is shared YAML.
CONFLUENCE_BASE = load_settings().values.get("CONFLUENCE_URL", "").rstrip("/")


@dataclass(frozen=True)
class MpxjRuntime:
    python: str
    versions: dict[str, str]


def select_mpxj_python(*, settings=None, candidates=None, timeout=60) -> MpxjRuntime:
    """Validate JVM and the real shared reader API. Never return a failed candidate.

    PYTHONPATH follows the caller/process environment; no hidden env alias.
    An explicitly configured interpreter fails closed rather than silently changing.
    """
    import json
    settings = settings or load_settings()
    configured = settings.values.get("MPXJ_PYTHON")
    choices = candidates if candidates is not None else ([configured] if configured else [sys.executable, "/usr/bin/python3.9", "/usr/bin/python3"])
    manifest = unified.load_manifest()
    tool = (manifest.get("tools") or {}).get("mpp_reader", {})
    root = Path(tool["path"]).expanduser().resolve()
    probe = ("import sys,json;sys.path.insert(0,sys.argv[1]);"
             "from read_mpp import _start_jvm,reader_versions,read_project_file;"
             "_start_jvm();from org.mpxj.reader import UniversalProjectReader;"
             "assert callable(UniversalProjectReader().read);print(json.dumps(reader_versions()))")
    failures = []
    for candidate in dict.fromkeys(str(c) for c in choices):
        try:
            result = subprocess.run([candidate, "-c", probe, str(root)], capture_output=True, text=True, timeout=timeout)
            if result.returncode == 0:
                versions = json.loads(result.stdout.strip().splitlines()[-1])
                return MpxjRuntime(candidate, versions)
            failures.append(f"{candidate}:rc={result.returncode}")
        except (OSError, subprocess.TimeoutExpired, ValueError, IndexError) as exc:
            failures.append(f"{candidate}:{type(exc).__name__}")
    raise RuntimeError("No working MPXJ Python/JVM: " + "; ".join(failures))
