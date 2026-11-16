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


import hashlib
import os
import stat
from dataclasses import replace

import pytest
from mpp_input import freeze_input,InputError
from env import load_settings


def _limits(**overrides):
    return {**load_settings().values,**overrides}


def test_freeze_renamed_container_and_mpp_with_zip_suffix(tmp_path):
    payload=b"MPP bytes"
    archive=tmp_path/"looks-like-mpp.mpp"
    with zipfile.ZipFile(archive,"w") as z:
        z.writestr("folder/source.mpp",payload)
    first=freeze_input(archive,operation_id="op-one",workvault=tmp_path/"wv",settings=_limits())
    assert first.zip_member=="folder/source.mpp"
    assert first.container_sha256==hashlib.sha256(archive.read_bytes()).hexdigest()
    assert Path(first.container_locator).read_bytes()==archive.read_bytes()
    archive.unlink()
    assert first.mpp_path.read_bytes()==payload
    direct=tmp_path/"renamed.zip";direct.write_bytes(payload)
    second=freeze_input(direct,operation_id="op-two",workvault=tmp_path/"wv",settings=_limits())
    assert second.container_sha256 is None and second.sha256==first.sha256


def test_multiple_candidates_no_first_selection_preserves_container(tmp_path):
    path=tmp_path/"two.zip"
    with zipfile.ZipFile(path,"w") as z:
        z.writestr("b.mpp",b"B");z.writestr("a.mpp",b"A")
    with pytest.raises(InputError,match="multiple_mpp_candidates") as caught:
        freeze_input(path,operation_id="op",workvault=tmp_path/"wv",settings=_limits())
    assert caught.value.candidates==("b.mpp","a.mpp")
    root=tmp_path/"wv/_plan-receipts/op/input"
    assert not list(root.rglob("source.mpp"))
    sources=list(root.glob("*.source"))
    assert len(sources)==1 and sources[0].read_bytes()==path.read_bytes()


@pytest.mark.parametrize("name",["../evil.mpp","/absolute.mpp","C:/absolute.mpp","C:relative.mpp","a/../../b.mpp","a\\b.mpp","./a.mpp","a//b.mpp"])
def test_zip_unsafe_paths(tmp_path,name):
    path=tmp_path/"unsafe.zip"
    with zipfile.ZipFile(path,"w") as z:
        z.writestr(name,b"source")
    with pytest.raises(InputError,match="zip_unsafe_path"):
        freeze_input(path,operation_id="op",workvault=tmp_path/"wv",settings=_limits())
    assert not list((tmp_path/"wv").rglob("source.mpp"))


@pytest.mark.parametrize("names",[("x.mpp","x.mpp"),("x.mpp","X.mpp"),("é.mpp","e\u0301.mpp"),("a","a/plan.mpp")])
def test_zip_collisions(tmp_path,names):
    path=tmp_path/"collision.zip"
    with zipfile.ZipFile(path,"w") as z:
        for name in names:
            z.writestr(name,b"source")
    with pytest.raises(InputError,match="zip_name_collision"):
        freeze_input(path,operation_id="op",workvault=tmp_path/"wv",settings=_limits())


def test_zip_symlink_and_input_symlink_forbidden(tmp_path):
    path=tmp_path/"link.zip"
    entry=zipfile.ZipInfo("link.mpp");entry.create_system=3;entry.external_attr=(stat.S_IFLNK|0o777)<<16
    with zipfile.ZipFile(path,"w") as z:
        z.writestr(entry,"/etc/passwd")
    with pytest.raises(InputError,match="zip_link_forbidden"):
        freeze_input(path,operation_id="op",workvault=tmp_path/"wv",settings=_limits())
    source=tmp_path/"plan.mpp";source.write_bytes(b"source")
    link=tmp_path/"alias.mpp";link.symlink_to(source)
    with pytest.raises(InputError,match="input_not_regular"):
        freeze_input(link,operation_id="op2",workvault=tmp_path/"wv",settings=_limits())


@pytest.mark.parametrize("limit,value,code",[("ZIP_MAX_ENTRIES",1,"zip_entries_limit"),("ZIP_MAX_UNPACKED_BYTES",10,"zip_unpacked_limit"),
    ("ZIP_MAX_RATIO",1,"zip_ratio_limit"),("ZIP_MAX_BYTES",10,"zip_size_limit"),("MPP_MAX_BYTES",10,"mpp_size_limit")])
def test_zip_numeric_limits(tmp_path,limit,value,code):
    path=tmp_path/"limited.zip"
    with zipfile.ZipFile(path,"w",compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("source.mpp",b"x"*5000);z.writestr("metadata.txt",b"hello")
    with pytest.raises(InputError,match=code):
        freeze_input(path,operation_id="op",workvault=tmp_path/"wv",settings=_limits(**{**{"ZIP_MAX_RATIO":10000},limit:value}))


def test_freeze_direct_exact_limit_and_missing(tmp_path):
    path=tmp_path/"plan.mpp";path.write_bytes(b"12345")
    assert freeze_input(path,operation_id="one",workvault=tmp_path/"wv",settings=_limits(MPP_MAX_BYTES=5)).size_bytes==5
    with pytest.raises(InputError,match="mpp_size_limit"):
        freeze_input(path,operation_id="two",workvault=tmp_path/"wv",settings=_limits(MPP_MAX_BYTES=4))
    path.unlink()
    with pytest.raises(InputError,match="input_missing"):
        freeze_input(path,operation_id="three",workvault=tmp_path/"wv",settings=_limits())


def test_input_changed_during_copy_is_never_accepted(tmp_path,monkeypatch):
    import mpp_input
    source=tmp_path/"changing.mpp";source.write_bytes(b"before")
    original_hash=hashlib.sha256
    touched=False
    class MutatingHash:
        def __init__(self):
            self.inner=original_hash()
        def update(self,data):
            nonlocal touched
            self.inner.update(data)
            if not touched:
                touched=True
                info=source.stat()
                source.write_bytes(b"AFTER!")
                os.utime(source,ns=(info.st_atime_ns,info.st_mtime_ns))
        def __getattr__(self,name):
            return getattr(self.inner,name)
    monkeypatch.setattr(mpp_input.hashlib,"sha256",MutatingHash)
    with pytest.raises(InputError,match="input_changed"):
        freeze_input(source,operation_id="op",workvault=tmp_path/"wv",settings=_limits())
    assert not list((tmp_path/"wv/_plan-receipts/op/input").iterdir())


def test_input_path_replaced_during_copy(tmp_path,monkeypatch):
    import mpp_input
    source=tmp_path/"replaced.mpp";source.write_bytes(b"same")
    replacement=tmp_path/"other.mpp";replacement.write_bytes(b"same")
    real_fstat=os.fstat
    calls=0
    def replacing(fd):
        nonlocal calls
        calls+=1
        if calls==2:
            replacement.replace(source)
        return real_fstat(fd)
    monkeypatch.setattr(mpp_input.os,"fstat",replacing)
    with pytest.raises(InputError,match="input_changed"):
        freeze_input(source,operation_id="op",workvault=tmp_path/"wv",settings=_limits())
