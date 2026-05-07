# tests/mcp/netcdf_reader/unit/test_lifecycle.py
from unittest.mock import MagicMock

from src.mcp.netcdf_reader.lifecycle import (
    cleanup_old_slice_dirs,
    on_shutdown,
    register_pool,
)


def test_cleanup_removes_old_session_dirs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    base = tmp_path / ".ncplot" / "slices"
    (base / "pid-old-1").mkdir(parents=True)
    (base / "pid-old-1" / "x.nc").write_bytes(b"x")
    (base / "pid-old-2").mkdir()
    cleanup_old_slice_dirs(keep="pid-current")
    assert not (base / "pid-old-1").exists()
    assert not (base / "pid-old-2").exists()


def test_cleanup_keeps_current(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    base = tmp_path / ".ncplot" / "slices"
    (base / "pid-current").mkdir(parents=True)
    (base / "pid-current" / "x.nc").write_bytes(b"x")
    cleanup_old_slice_dirs(keep="pid-current")
    assert (base / "pid-current" / "x.nc").exists()


def test_cleanup_handles_missing_base(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cleanup_old_slice_dirs(keep="any")  # should not raise


def test_on_shutdown_closes_registered_pools():
    pool = MagicMock()
    register_pool(pool)
    on_shutdown()
    pool.close_all.assert_called_once()
