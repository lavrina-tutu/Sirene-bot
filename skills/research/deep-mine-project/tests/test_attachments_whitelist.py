"""T3: attachment whitelist."""
from deepmine.attachments import WHITELIST_EXT, is_ole2_or_zip, is_whitelisted


def test_whitelist_extensions():
  assert is_whitelisted("plan.mpp", set())
  assert is_whitelisted("plan.mpx", set())
  assert is_whitelisted("data.xml", set())
  assert is_whitelisted("gantt-chart-abc.json", set())
  assert not is_whitelisted("notes.pdf", set())
  assert is_whitelisted("custom name", {"custom name"})
  assert ".json" in WHITELIST_EXT


def test_zip_not_unzipped(tmp_path):
  z = tmp_path / "fake.zip"
  z.write_bytes(b"PK\x03\x04" + b"rest")
  assert is_ole2_or_zip(z) == "zip"


def test_ole2_detect(tmp_path):
  f = tmp_path / "proj.mpp"
  f.write_bytes(b"\xd0\xcf\x11\xe0" + b"rest")
  assert is_ole2_or_zip(f) == "ole2"
