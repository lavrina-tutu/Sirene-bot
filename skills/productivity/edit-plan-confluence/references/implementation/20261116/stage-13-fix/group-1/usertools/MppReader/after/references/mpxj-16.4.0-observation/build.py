"""Reproducible MPXJ 16.4.0 observation overlay; run with Python, Java required."""
from pathlib import Path
import hashlib, subprocess, zipfile, tempfile, os
ROOT = Path(__file__).resolve().parent
PINS = {"mpxj-sources.jar":"df43a054f70b3c96083404b5bc2a663af8cc917762c7ac44cf571de82e81312d", "ecj.jar":"f7686c4960cf70c2ebc5c500a73a8cfc04541b730c18f1c5c21329889b137f45"}
for name, sha in PINS.items():
    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == sha, name
import mpxj
libs = Path(mpxj.__file__).parent / "lib"
assert hashlib.sha256((libs/"mpxj.jar").read_bytes()).hexdigest() == "4c44b12beed38d7a2b744f56c9df02b29611f1b9606a38d9a8e37be880880410"
with tempfile.TemporaryDirectory() as tmp:
    subprocess.run(["java", "-jar", str(ROOT/"ecj.jar"), "-8", "-cp", os.pathsep.join(map(str,sorted(libs.glob("*.jar")))), "-d", tmp,
                    *map(str, sorted((ROOT/"source").rglob("*.java")))], check=True)
    with zipfile.ZipFile(ROOT/"mpxj-observation.jar", "w", zipfile.ZIP_STORED) as output:
        for p in sorted(Path(tmp).rglob("*.class")):
            info = zipfile.ZipInfo(str(p.relative_to(tmp)), (2026,1,1,0,0,0))
            info.external_attr = 0o644 << 16
            output.writestr(info,p.read_bytes())
print(hashlib.sha256((ROOT/"mpxj-observation.jar").read_bytes()).hexdigest())
