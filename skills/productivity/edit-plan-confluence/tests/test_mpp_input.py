from __future__ import annotations

import zipfile
from pathlib import Path

from mpp_input import resolve_mpp_path


def test_resolve_mpp_from_zip(tmp_path):
    mpp_src = Path(__file__).parent / "fixtures" / "ab_080926_пункт12.mpp"
    zip_path = tmp_path / "plan.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(mpp_src, "inside/plan.mpp")
    resolved = resolve_mpp_path(zip_path)
    assert resolved.suffix.lower() == ".mpp"
    assert resolved.is_file()
