#!/usr/bin/env python3
"""Restore Telegram «Сирень Workspace» routing from sirene-workspace-topics.yaml snapshot."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_SNAPSHOT = SCRIPT_DIR.parent / "references" / "sirene-workspace-topics.yaml"

CANON_TOPIC_NAMES = frozenset(
    {"General", "Tools", "WorkVault", "Backlog", "Monitoring", "Messages", "Errors", "Personal"}
)
CANON_TOPIC_IDS = frozenset({1, 3, 5, 6, 7, 8, 6556, 11112})

_TOKEN_RE = re.compile(r"\d{8,}:[A-Za-z0-9_-]{20,}")


@dataclass(frozen=True)
class Drift:
    file: str
    key: str
    expected: str
    actual: str

    def __str__(self) -> str:
        return f"{self.file}: {self.key} expected={self.expected!r} actual={self.actual!r}"


def hermes_home() -> Path:
    raw = os.environ.get("HERMES_HOME", "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".hermes"


def expand_path(template: str) -> Path:
    return Path(template.replace("$HERMES_HOME", str(hermes_home()))).expanduser()


def redact(text: str) -> str:
    return _TOKEN_RE.sub("<redacted>", text)


def token_prefix(token: str) -> str:
    if not token:
        return ""
    before_colon = token.split(":", 1)[0]
    return before_colon[:6] if len(before_colon) >= 6 else before_colon


def _parse_csv_set(raw: Optional[str]) -> set[str]:
    if raw is None:
        return set()
    text = str(raw).strip()
    if not text:
        return set()
    return {part.strip() for part in text.split(",") if part.strip()}


def load_snapshot(path: Optional[Path] = None) -> dict:
    snap_path = path or Path(os.environ.get("TG_TOPICS_SNAPSHOT", DEFAULT_SNAPSHOT))
    import yaml

    with snap_path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"snapshot must be a mapping: {snap_path}")
    if data.get("schema_version") != "1.0":
        raise ValueError(f"unsupported schema_version in {snap_path}")
    topics = data.get("topics") or {}
    if set(topics.keys()) != CANON_TOPIC_NAMES:
        raise ValueError(f"snapshot topics must be exactly {sorted(CANON_TOPIC_NAMES)}")
    if set(topics.values()) != CANON_TOPIC_IDS:
        raise ValueError(f"snapshot topic ids must be {sorted(CANON_TOPIC_IDS)}")
    return data


def read_env_key(env_path: Path, key: str) -> Optional[str]:
    if not env_path.is_file():
        return None
    prefix = f"{key}="
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :]
    return None


def write_env_key(env_path: Path, key: str, value: str) -> None:
    env_path.parent.mkdir(parents=True, exist_ok=True)
    prefix = f"{key}="
    lines: list[str] = []
    replaced = False
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith(prefix):
                if not replaced:
                    lines.append(f"{prefix}{value}")
                    replaced = True
                continue
            lines.append(line)
    if not replaced:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(f"{prefix}{value}")
    env_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def backup_targets(paths: Iterable[Path]) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = hermes_home() / "_Archives" / f"hermes-backup-{stamp}"
    dest.mkdir(parents=True, exist_ok=True)
    for path in paths:
        if path.is_file():
            shutil.copy2(path, dest / path.name)
    return dest


def _roundtrip_load(path: Path):
    from ruamel.yaml import YAML
    from ruamel.yaml.comments import CommentedMap

    yaml_rt = YAML(typ="rt")
    yaml_rt.preserve_quotes = True
    yaml_rt.allow_unicode = True
    yaml_rt.default_flow_style = False
    yaml_rt.indent(mapping=2, sequence=4, offset=2)
    if path.is_file():
        data = yaml_rt.load(path.read_text(encoding="utf-8"))
    else:
        data = CommentedMap()
    if not isinstance(data, CommentedMap):
        data = CommentedMap(data or {})
    return yaml_rt, data


def _ensure_map(parent, key: str):
    from ruamel.yaml.comments import CommentedMap

    child = parent.get(key)
    if not isinstance(child, CommentedMap):
        child = CommentedMap()
        parent[key] = child
    return child


def patch_config_yaml(config_path: Path, snapshot: dict, bot_token: str) -> None:
    yaml_rt, cfg = _roundtrip_load(config_path)
    extra = snapshot.get("yaml_extra") or {}
    tg = _ensure_map(cfg, "telegram")
    tg["allowed_chats"] = extra.get("allowed_chats", snapshot["allowlist_csv"])
    tg["require_mention"] = False
    tg["guest_mode"] = False
    gw = _ensure_map(cfg, "gateway")
    gw_tg = _ensure_map(gw, "telegram")
    gw_tg["token"] = bot_token
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as fh:
        yaml_rt.dump(cfg, fh)


def _read_yaml_telegram(config_path: Path) -> dict:
    if not config_path.is_file():
        return {}
    import yaml

    with config_path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    return raw.get("telegram") or {}


def _read_gateway_token(config_path: Path) -> Optional[str]:
    if not config_path.is_file():
        return None
    import yaml

    with config_path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    gw = raw.get("gateway") or {}
    tg = gw.get("telegram") or {}
    token = tg.get("token")
    return str(token).strip() if token else None


def collect_drift(snapshot: dict) -> list[Drift]:
    drifts: list[Drift] = []
    allow_expected = snapshot["allowlist_csv"]
    allow_set = _parse_csv_set(allow_expected)
    bot_prefix = snapshot["bot"]["id_prefix"]

    for env_template in snapshot.get("env_files") or []:
        env_path = expand_path(env_template)
        rel = str(env_path)
        if not env_path.is_file():
            drifts.append(Drift(rel, "missing", "file exists", "absent"))
            continue
        startup = read_env_key(env_path, "TELEGRAM_ADDITIONAL_STARTUP_CHANNELS")
        if startup is None:
            drifts.append(
                Drift(
                    rel,
                    "TELEGRAM_ADDITIONAL_STARTUP_CHANNELS",
                    snapshot["startup_channels"],
                    "<unset>",
                )
            )
        elif startup.strip() != snapshot["startup_channels"]:
            drifts.append(
                Drift(
                    rel,
                    "TELEGRAM_ADDITIONAL_STARTUP_CHANNELS",
                    snapshot["startup_channels"],
                    redact(startup),
                )
            )

    cfg_path = expand_path(snapshot["config_yaml"])
    cfg_rel = str(cfg_path)
    tg = _read_yaml_telegram(cfg_path)
    if _parse_csv_set(tg.get("allowed_chats")) != allow_set:
        drifts.append(
            Drift(
                cfg_rel,
                "telegram.allowed_chats",
                allow_expected,
                redact(str(tg.get("allowed_chats", ""))),
            )
        )
    if tg.get("require_mention") is not False:
        drifts.append(Drift(cfg_rel, "telegram.require_mention", "false", str(tg.get("require_mention"))))
    if tg.get("guest_mode") is not False:
        drifts.append(Drift(cfg_rel, "telegram.guest_mode", "false", str(tg.get("guest_mode"))))

    yaml_token = _read_gateway_token(cfg_path)
    if yaml_token:
        actual_prefix = token_prefix(yaml_token)
        if actual_prefix != bot_prefix:
            drifts.append(
                Drift(
                    cfg_rel,
                    "gateway.telegram.token",
                    f"prefix={bot_prefix}",
                    f"prefix={actual_prefix}",
                )
            )
    else:
        drifts.append(Drift(cfg_rel, "gateway.telegram.token", f"prefix={bot_prefix}", "<unset>"))

    err_db = hermes_home() / "error_bus" / "_db.py"
    if err_db.is_file():
        text = err_db.read_text(encoding="utf-8")
        chat_m = re.search(r'TELEGRAM_CHAT_ID\s*=\s*"([^"]+)"', text)
        thread_m = re.search(r'TELEGRAM_THREAD_ID\s*=\s*"([^"]+)"', text)
        if chat_m and chat_m.group(1) != snapshot["chat_id"]:
            drifts.append(
                Drift(str(err_db), "TELEGRAM_CHAT_ID", snapshot["chat_id"], chat_m.group(1))
            )
        if thread_m and thread_m.group(1) != "11112":
            drifts.append(Drift(str(err_db), "TELEGRAM_THREAD_ID", "11112", thread_m.group(1)))

    return drifts


def _print_drifts(drifts: list[Drift], *, would_write: bool = False) -> None:
    for d in drifts:
        prefix = "would write " if would_write else "drift "
        print(f"{prefix}{d}")


def cmd_check() -> int:
    snapshot = load_snapshot()
    drifts = collect_drift(snapshot)
    if drifts:
        _print_drifts(drifts)
        return 1
    print("ok: disk matches snapshot")
    return 0


def cmd_dry_run() -> int:
    snapshot = load_snapshot()
    drifts = collect_drift(snapshot)
    if drifts:
        _print_drifts(drifts, would_write=True)
        return 1
    print("ok: no changes needed")
    return 0


def cmd_apply() -> int:
    snapshot = load_snapshot()
    home = hermes_home()
    paths: list[Path] = []
    for env_template in snapshot.get("env_files") or []:
        p = expand_path(env_template)
        if p.is_file():
            paths.append(p)
    cfg_path = expand_path(snapshot["config_yaml"])
    if cfg_path.is_file():
        paths.append(cfg_path)

    if paths:
        backup_dir = backup_targets(paths)
        print(f"backup: {backup_dir}")

    root_env = home / ".env"
    bot_key = snapshot["bot"]["env_key"]
    bot_token = read_env_key(root_env, bot_key)
    if not bot_token:
        print(f"error: {bot_key} not set in {root_env}", file=sys.stderr)
        return 1

    startup = snapshot["startup_channels"]
    for env_template in snapshot.get("env_files") or []:
        env_path = expand_path(env_template)
        if not env_path.is_file():
            print(f"warn: skip missing env {env_path}", file=sys.stderr)
            continue
        write_env_key(env_path, "TELEGRAM_ADDITIONAL_STARTUP_CHANNELS", startup)

    patch_config_yaml(cfg_path, snapshot, bot_token)
    print(f"gateway.telegram.token prefix={token_prefix(bot_token)} (from {bot_key})")
    print("нужен рестарт gateway (скрипт сам не рестартует; ждать «поднимай»)")
    return cmd_check()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="restore_telegram_topics.py")
    parser.add_argument("command", choices=("apply", "check", "dry-run"))
    args = parser.parse_args(argv)
    handlers = {"apply": cmd_apply, "check": cmd_check, "dry-run": cmd_dry_run}
    return handlers[args.command]()


if __name__ == "__main__":
    sys.exit(main())
