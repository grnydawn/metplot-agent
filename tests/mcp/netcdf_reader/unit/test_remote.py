from unittest.mock import MagicMock
from src.mcp.netcdf_reader.adapter import NetCDFAdapter


def test_adapter_passes_http_url_to_open_dataset(monkeypatch):
    captured = {}
    def fake_open(path, **kwargs):
        captured["path"] = path
        captured["kwargs"] = kwargs
        return MagicMock(data_vars={}, coords={}, dims={}, sizes={}, attrs={})
    monkeypatch.setattr("xarray.open_dataset", fake_open)
    a = NetCDFAdapter()
    a.open(["https://example.org/data.nc"])
    assert captured["path"] == "https://example.org/data.nc"


def test_classify_recognises_s3():
    from src.mcp.netcdf_reader.paths.classify import classify, PathKind
    k = classify("s3://bucket/path/file.nc")
    assert k.kind == PathKind.REMOTE_URL
    assert k.scheme == "s3"


def test_inspect_handles_open_failure_for_remote(tmp_path, monkeypatch):
    """If xarray fails on a remote URL (e.g., connection refused), we
    return a clear error envelope rather than a stack trace."""
    monkeypatch.chdir(tmp_path)
    from src.mcp.netcdf_reader.tools.inspect import inspect

    def fake_open_dataset(path, **kwargs):
        raise OSError("Network unreachable")
    monkeypatch.setattr("xarray.open_dataset", fake_open_dataset)
    env = inspect("https://example.org/x.nc", adapter=NetCDFAdapter())
    assert env["ok"] is False
    assert env["error"]["code"] in (
        "remote_file_not_found", "internal_error", "ssh_timeout",
    )
