"""Resolve .mpp / .zip input and invoke read_mpp.py for CSV export."""
from __future__ import annotations

import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path

VENV_PYTHON = Path.home() / "hermes-agent" / ".venv" / "bin" / "python3"
SYSTEM_PYTHON = Path("/usr/bin/python3")
# Системный python с mpxj/jpype (RHEL9: python3.9; в python3.11/venv mpxj нет)
SYSTEM_MPXJ_PYTHON = Path("/usr/bin/python3.9")
READ_MPP = Path.home() / "USERTOOLS" / "MppReader" / "read_mpp.py"


def _pick_python() -> str:
    """Select only a validated shared MPXJ/JVM runtime."""
    from env import select_mpxj_python
    return select_mpxj_python().python


@dataclass
class MppCsvPaths:
    mpp_path: Path
    tasks_csv: Path
    resources_csv: Path
    assignments_csv: Path
    out_dir: Path


def resolve_mpp_path(path: str | Path) -> Path:
    # Compatibility adapter; the future save pipeline supplies its operation ID.
    from uuid import uuid4
    return freeze_input(path, operation_id="input-"+uuid4().hex).mpp_path


def _extract_mpp_from_zip(zip_path: Path) -> Path:
    return resolve_mpp_path(zip_path)


def export_csv(mpp_path: Path, out_dir: Path | None = None) -> MppCsvPaths:
    mpp_path = mpp_path.resolve()
    out = out_dir or mpp_path.parent
    out.mkdir(parents=True, exist_ok=True)
    python = _pick_python()
    cmd = [
        python,
        str(READ_MPP),
        str(mpp_path),
        "--format",
        "csv",
        "--out-dir",
        str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"read_mpp.py failed: {proc.stderr or proc.stdout}")
    stem = mpp_path.stem
    tasks = out / f"{stem}__tasks.csv"
    resources = out / f"{stem}__resources.csv"
    assignments = out / f"{stem}__assignments.csv"
    for f in (tasks, resources, assignments):
        if not f.is_file():
            raise FileNotFoundError(f"Expected CSV missing: {f}")
    return MppCsvPaths(
        mpp_path=mpp_path,
        tasks_csv=tasks,
        resources_csv=resources,
        assignments_csv=assignments,
        out_dir=out,
    )


# Input profile v1 consumes the numeric limits already installed in unified YAML.
import hashlib
import os
import re
import shutil
import stat
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import PurePosixPath, PureWindowsPath


class InputError(ValueError):
    def __init__(self, code, candidates=()):
        self.code = code
        self.candidates = tuple(candidates)
        super().__init__(code + (": " + ", ".join(candidates) if candidates else ""))


@dataclass(frozen=True)
class FrozenInput:
    mpp_path: Path
    sha256: str
    size_bytes: int
    original_name: str
    original_locator: str
    frozen_at: str
    container_sha256: str | None = None
    container_locator: str | None = None
    zip_member: str | None = None
    source_mtime_ns: int | None = None


def _sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _signature(st):
    return st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns


def _copy_consistent(source: Path, target: Path, limit: int):
    """Two reads of the same open file plus pathname identity and metadata."""
    try:
        fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError as exc:
        raise InputError("input_missing") from exc
    except OSError as exc:
        raise InputError("input_not_regular") from exc
    with os.fdopen(fd,"rb") as src:
        before = os.fstat(src.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise InputError("input_not_regular")
        if before.st_size > limit:
            raise InputError("input_size_limit_exceeded")
        digest = hashlib.sha256()
        size = 0
        with target.open("xb") as dst:
            for chunk in iter(lambda: src.read(1024*1024),b""):
                size += len(chunk)
                if size > limit:
                    raise InputError("input_size_limit_exceeded")
                digest.update(chunk)
                dst.write(chunk)
            dst.flush()
            os.fsync(dst.fileno())
        src.seek(0)
        control = hashlib.sha256()
        control_size = 0
        for chunk in iter(lambda: src.read(1024*1024),b""):
            control_size += len(chunk)
            if control_size > limit:
                raise InputError("input_changed")
            control.update(chunk)
        after = os.fstat(src.fileno())
        try:
            named = source.lstat()
        except OSError as exc:
            raise InputError("input_changed") from exc
        if (_signature(before) != _signature(after) or _signature(before) != _signature(named)
                or size != before.st_size or control_size != size or control.digest() != digest.digest()):
            raise InputError("input_changed")
    # Independently read back the copy, not just the digest fed to write().
    if hashlib.sha256(target.read_bytes()).digest() != digest.digest():
        raise InputError("frozen_input_hash_mismatch")
    return digest.hexdigest(),size,before.st_mtime_ns


def _unpack_zip(container, directory, limits):
    try:
        with zipfile.ZipFile(container) as zf:
            entries = zf.infolist()
            if len(entries) > limits["ZIP_MAX_ENTRIES"]:
                raise InputError("zip_entries_limit_exceeded")
            names = {}
            total = 0
            candidates = []
            for entry in entries:
                name = entry.orig_filename
                pure = PurePosixPath(name)
                mode = entry.external_attr >> 16
                if (not name or "\x00" in name or "\\" in name or pure.is_absolute() or PureWindowsPath(name).drive
                        or any(part in ("..", ".", "") for part in name.rstrip("/").split("/"))):
                    raise InputError("zip_unsafe_path")
                if stat.S_IFMT(mode) not in (0,stat.S_IFREG,stat.S_IFDIR) or stat.S_ISLNK(mode):
                    raise InputError("zip_link_forbidden")
                if entry.flag_bits & 1:
                    raise InputError("zip_encrypted_forbidden")
                normalized = unicodedata.normalize("NFC",name.rstrip("/")).casefold()
                if normalized in names:
                    raise InputError("zip_name_collision")
                names[normalized] = entry.is_dir()
                total += entry.file_size
                if total > limits["ZIP_MAX_UNPACKED_BYTES"]:
                    raise InputError("zip_unpacked_limit_exceeded")
                if entry.file_size > max(entry.compress_size,1)*limits["ZIP_MAX_RATIO"]:
                    raise InputError("zip_ratio_limit_exceeded")
                if not entry.is_dir() and name.lower().endswith(".mpp"):
                    candidates.append(entry)
            for name in names:
                parts=name.split("/")
                if any(names.get("/".join(parts[:i])) is False for i in range(1,len(parts))):
                    raise InputError("zip_name_collision")
            if len(candidates) > 1:
                raise InputError("multiple_mpp_candidates",[c.filename for c in candidates])
            if not candidates:
                raise InputError("mpp_candidate_missing")
            chosen=candidates[0]
            if chosen.file_size > limits["MPP_MAX_BYTES"]:
                raise InputError("mpp_size_limit_exceeded")
            total=0
            digest=hashlib.sha256()
            size=0
            with (directory/"source.mpp").open("xb") as dst:
                # Validate actual expanded bytes and CRC of every file. Nothing is
                # extracted under member-supplied paths.
                for entry in entries:
                    if entry.is_dir():
                        continue
                    actual=0
                    with zf.open(entry) as src:
                        for chunk in iter(lambda:src.read(1024*1024),b""):
                            actual += len(chunk)
                            total += len(chunk)
                            if total > limits["ZIP_MAX_UNPACKED_BYTES"] or actual > entry.file_size:
                                raise InputError("zip_unpacked_limit_exceeded")
                            if entry is chosen:
                                size += len(chunk)
                                if size > limits["MPP_MAX_BYTES"]:
                                    raise InputError("mpp_size_limit_exceeded")
                                digest.update(chunk)
                                dst.write(chunk)
                    if actual != entry.file_size:
                        raise InputError("zip_size_mismatch")
                dst.flush()
                os.fsync(dst.fileno())
            return digest.hexdigest(),size,chosen.filename
    except (zipfile.BadZipFile,NotImplementedError,RuntimeError) as exc:
        raise InputError("invalid_zip") from exc


def freeze_input(path: str | Path, *, operation_id: str, workvault: Path | None = None, settings=None) -> FrozenInput:
    from env import get_workvault_path,load_settings
    if not re.fullmatch(r"[A-Za-z0-9_-]+",operation_id):
        raise InputError("invalid_operation_id")
    source = Path(path).expanduser().absolute()  # Do not resolve a symlink away.
    limits = settings.values if hasattr(settings,"values") and not isinstance(settings,dict) else settings
    if limits is None:
        limits=load_settings().values
    # Unified loader returns environment-compatible strings; validate the same
    # numeric contract as PlanContext before using limits in arithmetic.
    import json
    import jsonschema
    from plan_context import SETTINGS_CONTRACT
    contract=json.loads(SETTINGS_CONTRACT.read_text())
    numeric=("MPP_MAX_BYTES","ZIP_MAX_BYTES","ZIP_MAX_ENTRIES","ZIP_MAX_UNPACKED_BYTES","ZIP_MAX_RATIO")
    converted={}
    for key in numeric:
        raw_limit=limits[key]
        if isinstance(raw_limit,bool) or not str(raw_limit).isdigit():
            raise InputError("invalid_input_limit")
        converted[key]=int(raw_limit)
        jsonschema.validate(converted[key],contract["properties"][key])
    limits=converted
    root=(Path(workvault) if workvault is not None else get_workvault_path())/"_plan-receipts"/operation_id/"input"
    root.mkdir(parents=True,exist_ok=True)
    staging=Path(tempfile.mkdtemp(prefix=".receiving-",dir=root))
    durable_source=None
    digest=None
    try:
        raw=staging/"input.bin"
        digest,size,source_mtime_ns=_copy_consistent(source,raw,max(limits["MPP_MAX_BYTES"],limits["ZIP_MAX_BYTES"]))
        # Preserve accepted transport bytes even if candidate selection fails.
        durable_source=root/(digest+".source")
        try:
            os.link(raw,durable_source)
        except FileExistsError:
            if hashlib.sha256(durable_source.read_bytes()).hexdigest() != digest:
                raise InputError("frozen_input_conflict")
        _sync_dir(root)
        is_zip=zipfile.is_zipfile(raw)
        container_sha=container_locator=member=None
        if is_zip:
            if size > limits["ZIP_MAX_BYTES"]:
                raise InputError("zip_size_limit_exceeded")
            raw.rename(staging/"container.zip")
            container_sha=digest
            sha,size,member=_unpack_zip(staging/"container.zip",staging,limits)
        else:
            if raw.read_bytes()[:4] in (b"PK\x03\x04",b"PK\x05\x06",b"PK\x07\x08"):
                raise InputError("invalid_zip")
            if size > limits["MPP_MAX_BYTES"]:
                raise InputError("mpp_size_limit_exceeded")
            sha=digest
            raw.rename(staging/"source.mpp")
        _sync_dir(staging)
        dest=root/digest
        try:
            staging.rename(dest)
        except OSError:
            # Concurrent completion can only reuse byte-identical durable data.
            if not dest.is_dir() or hashlib.sha256((dest/"source.mpp").read_bytes()).hexdigest() != sha:
                raise InputError("frozen_input_conflict")
            if container_sha and hashlib.sha256((dest/"container.zip").read_bytes()).hexdigest() != container_sha:
                raise InputError("frozen_input_conflict")
        _sync_dir(root)
        if container_sha:
            container_locator=str(dest/"container.zip")
        return FrozenInput(dest/"source.mpp",sha,size,source.name,str(source),datetime.now(timezone.utc).isoformat(),
                           container_sha,container_locator,member,source_mtime_ns)
    except InputError as exc:
        exc.container_sha256=digest if durable_source else None
        exc.container_locator=str(durable_source) if durable_source else None
        raise
    finally:
        if staging.exists():
            shutil.rmtree(staging)
