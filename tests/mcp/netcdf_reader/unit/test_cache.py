from src.mcp.netcdf_reader.cache import (
    inspection_key, read_inspection, write_inspection,
)


def test_inspection_key_local_single(tmp_path):
    f = tmp_path / "data.nc"
    f.write_bytes(b"x" * 100)
    k1 = inspection_key([str(f)])
    k2 = inspection_key([str(f)])
    assert k1 == k2
    assert isinstance(k1, str)
    assert len(k1) >= 16

def test_inspection_key_changes_with_mtime(tmp_path):
    f = tmp_path / "data.nc"
    f.write_bytes(b"x" * 100)
    k1 = inspection_key([str(f)])
    # bump mtime
    import os
    import time
    time.sleep(0.01)
    os.utime(f, None)
    k2 = inspection_key([str(f)])
    # Same content but different mtime → different key
    assert k1 != k2

def test_inspection_key_multifile_includes_all(tmp_path):
    f1 = tmp_path / "a.nc"
    f1.write_bytes(b"a")
    f2 = tmp_path / "b.nc"
    f2.write_bytes(b"b")
    k_pair = inspection_key([str(f1), str(f2)])
    k_single = inspection_key([str(f1)])
    assert k_pair != k_single

def test_inspection_key_remote_url():
    k = inspection_key(["https://example.org/data.nc"], remote=True)
    assert isinstance(k, str)

def test_write_then_read_inspection(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    payload = {"path": str(tmp_path / "x.nc"), "variables": []}
    key = "abc123"
    write_inspection(key, payload)
    out = read_inspection(key)
    assert out == payload

def test_read_inspection_missing_returns_none(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert read_inspection("nope") is None
