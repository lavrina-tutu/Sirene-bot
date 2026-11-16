"""Explicit non-secret dependencies for internal prepared-plan operations."""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from env import Settings, load_settings, unified

SKILL_ROOT = Path(__file__).resolve().parents[1]
PROFILES = SKILL_ROOT / "references" / "profiles"
SETTINGS_CONTRACT = SKILL_ROOT / "references" / "schemas" / "settings.schema.json"


@dataclass(frozen=True)
class PlanContext:
    db: Path
    workvault: Path
    cache_dir: Path
    mpp_reader: Path
    settings: dict[str, Any]
    sources: dict[str, str]
    frozen_profiles: dict[str, Any] | None = None

    @classmethod
    def from_snapshot(cls, document):
        """Resume without resolving any current defaults or credentials."""
        paths = document["paths"]
        return cls(*(Path(paths[k]) for k in ("db", "workvault", "cache_dir", "mpp_reader")),
                   dict(document["settings"]), dict(document["sources"]), document.get("profiles"))

    @classmethod
    def resolve(cls, *, db=None, workvault=None, cache_dir=None, settings: Settings | None = None):
        import jsonschema
        config = settings or load_settings()
        contract = json.loads(SETTINGS_CONTRACT.read_text())
        effective = dict(config.values)
        sources = dict(config.sources)
        for key, spec in contract["properties"].items():
            if key in effective and spec.get("type") == "integer":
                value = str(effective[key])
                if not value.isdigit():
                    raise ValueError(f"invalid integer setting: {key}")
                effective[key] = int(value)
        jsonschema.validate(effective, contract)
        manifest = unified.load_manifest()
        def tool_root(name):
            return Path(manifest["tools"][name]["path"]).expanduser().resolve()
        mofs = tool_root("mofs_index")
        if str(mofs) not in sys.path:
            sys.path.insert(0, str(mofs))
        from mofs_index.db import DEFAULT_DB_PATH
        paths = {}
        for key, override, default in [("db", db, DEFAULT_DB_PATH), ("WORKVAULT_PATH", workvault, effective["WORKVAULT_PATH"]),
                                        ("CACHE_DIR", cache_dir, effective["CACHE_DIR"])]:
            value = Path(override if override is not None else default).expanduser().resolve()
            paths[key] = value
            if override is not None:
                sources[key] = "cli_override"
            if key != "db":
                effective[key] = str(value)
        for profile in ["NORMALIZATION_PROFILE"]:
            if not (PROFILES / f"{effective[profile]}.json").is_file():
                raise ValueError(f"unknown profile: {effective[profile]}")
        return cls(paths["db"], paths["WORKVAULT_PATH"], paths["CACHE_DIR"], tool_root("mpp_reader"), effective, sources)

    def snapshot(self):
        profiles = dict(self.frozen_profiles) if self.frozen_profiles is not None else {}
        for key in (() if self.frozen_profiles is not None else ("NORMALIZATION_PROFILE", "SUMMARY_PROFILE", "PLUGIN_PROFILE")):
            path = PROFILES / f"{self.settings[key]}.json"
            profiles[key] = {"id": self.settings[key], "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None,
                             "status": "available" if path.exists() else "not_installed"}
        payload = {"paths": {"db": str(self.db), "workvault": str(self.workvault), "cache_dir": str(self.cache_dir),
                             "mpp_reader": str(self.mpp_reader)}, "settings": self.settings, "sources": self.sources,
                   "profiles": profiles}
        payload["fingerprint"] = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        return payload

    def check_input_size(self, size, *, kind="mpp"):
        key = {"mpp": "MPP_MAX_BYTES", "zip": "ZIP_MAX_BYTES"}[kind]
        if size < 0 or size > self.settings[key]:
            raise ValueError(f"{kind}_size_limit_exceeded")
