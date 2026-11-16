"""Disposable, integrity-checked caches. Durable sources/history belong elsewhere."""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from prepared_plan import PreparedPlan, canonical_bytes, fingerprint, validate_export

CACHE_VERSION = 1


def _sha(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
        raise ValueError("invalid_sha256")
    return value


class _Cache:
    namespace = ""

    def __init__(self, root, *, counters=None):
        self.root = Path(root) / self.namespace
        self.counters = counters if counters is not None else {}

    def _count(self, key):
        self.counters[key] = self.counters.get(key, 0) + 1

    def key(self, material):
        return fingerprint({"cache_version": CACHE_VERSION, "namespace": self.namespace, "material": material})

    def path(self, material):
        return self.root / (self.key(material) + ".json")

    def load(self, material):
        try:
            data = json.loads(self.path(material).read_bytes())
            payload = data["payload"]
            if (data["cache_version"] != CACHE_VERSION or data["namespace"] != self.namespace
                    or data["complete"] is not True or data["key"] != self.key(material)
                    or data["material"] != material or data["payload_sha256"] != fingerprint(payload)
                    or data["payload_bytes"] != len(canonical_bytes(payload))):
                raise ValueError("cache_integrity_failed")
            self.validate_payload(payload, material)
        except (OSError, ValueError, KeyError, TypeError, RecursionError):
            self._count("cache_miss")
            return None
        self._count("cache_hit")
        return payload

    def validate_payload(self, payload, material):
        canonical_bytes(payload)

    def store(self, material, payload):
        self.validate_payload(payload, material)
        data = {"cache_version": CACHE_VERSION, "namespace": self.namespace, "complete": True,
                "key": self.key(material), "material": material, "payload_sha256": fingerprint(payload),
                "payload_bytes": len(canonical_bytes(payload)), "payload": payload}
        self.root.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".pending-", dir=self.root)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(canonical_bytes(data)); stream.flush(); os.fsync(stream.fileno())
            os.replace(name, self.path(material))
            directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(name):
                os.unlink(name)


class ParseCache(_Cache):
    namespace = "parse-v1"

    @staticmethod
    def material(source_sha256, *, reader, export_version, parameters=None):
        if not reader or not export_version:
            raise ValueError("reader_and_export_versions_required")
        return {"source_sha256": _sha(source_sha256), "reader": reader, "export_version": export_version,
                "parameters": parameters or {}}

    def validate_payload(self, payload, material):
        validate_export(payload)
        if payload["provenance"]["sha256"] != material["source_sha256"] or payload["export_version"] != material["export_version"]:
            raise ValueError("cache_source_or_export_mismatch")
        for key, value in material["reader"].items():
            if payload["provenance"].get(key) != value:
                raise ValueError("cache_reader_mismatch")

    def get_or_parse(self, source, material, *, parser=None):
        """Caller supplies verified durable/frozen bytes; verify again before reuse.

        Corruption is a miss, never a substitute for archive read-back. A parser
        callback is useful in-process; default uses the shared MPXJ subprocess.
        """
        import hashlib
        source = Path(source)
        if hashlib.sha256(source.read_bytes()).hexdigest() != material["source_sha256"]:
            raise ValueError("source_integrity_failed")
        cached = self.load(material)
        if cached is not None:
            # Intake provenance must describe this arrival, not the first cache writer.
            cached["source"] = str(source.resolve())
            cached["provenance"]["source_path"] = str(source.resolve())
            cached["provenance"]["original_name"] = source.name
            return cached
        if parser is None:
            parser = self._parse
        payload = parser(source)
        # Counts originate at the real reader boundary, including subprocess data.
        self.counters["MPXJ_read"] = self.counters.get("MPXJ_read", 0) + payload.get("telemetry", {}).get("MPXJ_read", 0)
        self.store(material, payload)
        return payload

    @staticmethod
    def _parse(source):
        from env import select_mpxj_python
        from plan_context import PlanContext
        context = PlanContext.resolve()
        context.check_input_size(source.stat().st_size)
        runtime = select_mpxj_python()
        process = subprocess.run([runtime.python, str(context.mpp_reader / "plan_export.py"), str(source)],
                                 capture_output=True, text=True, timeout=context.settings["MPP_READ_TIMEOUT_SECONDS"])
        if process.returncode:
            raise RuntimeError(f"MPXJ export failed:rc={process.returncode}")
        output = process.stdout
        return json.loads(output[output.index("{"):])


class RepresentationCache(_Cache):
    namespace = "representation-v1"

    @staticmethod
    def material(normalized_sha256, *, converter_version, rules_revision, plugin_profile, template_parameters):
        if not converter_version or not rules_revision or not plugin_profile:
            raise ValueError("representation_versions_required")
        return {"normalized_sha256": _sha(normalized_sha256), "converter_version": converter_version,
                "rules_revision": rules_revision, "plugin_profile": plugin_profile, "template_parameters": template_parameters}

    def validate_payload(self, payload, material):
        if not isinstance(payload, dict) or payload.get("normalized_sha256") != material["normalized_sha256"] or "representation" not in payload:
            raise ValueError("invalid_representation_payload")
        canonical_bytes(payload)

    def get_or_build(self, prepared: PreparedPlan, material, builder):
        prepared.validate()
        if prepared.semantic_hash != material["normalized_sha256"]:
            raise ValueError("representation_source_mismatch")
        payload = self.load(material)
        if payload is None:
            payload = {"normalized_sha256": prepared.semantic_hash, "representation": builder(prepared)}
            self.store(material, payload)
        return payload["representation"]
