import pytest
from src.mcp.netcdf_reader.paths.classify import classify, PathKind, ClassifyError


def test_classify_local_single(tmp_path):
    f = tmp_path / "data.nc"
    f.write_bytes(b"")
    k = classify(str(f))
    assert k.kind == PathKind.LOCAL_SINGLE
    assert k.scheme == "file"
    assert k.paths == [str(f.resolve())]

def test_classify_file_url(tmp_path):
    f = tmp_path / "data.nc"
    f.write_bytes(b"")
    k = classify(f"file://{f}")
    assert k.kind == PathKind.LOCAL_SINGLE

def test_classify_local_glob(tmp_path):
    (tmp_path / "a.nc").write_bytes(b"")
    (tmp_path / "b.nc").write_bytes(b"")
    k = classify(str(tmp_path / "*.nc"))
    assert k.kind == PathKind.LOCAL_MULTI
    assert sorted(k.paths) == [
        str((tmp_path / "a.nc").resolve()),
        str((tmp_path / "b.nc").resolve()),
    ]

def test_classify_local_directory(tmp_path):
    (tmp_path / "a.nc").write_bytes(b"")
    (tmp_path / "b.nc").write_bytes(b"")
    k = classify(str(tmp_path))
    assert k.kind == PathKind.LOCAL_MULTI
    assert len(k.paths) == 2

def test_classify_http_url():
    k = classify("https://example.org/data.nc")
    assert k.kind == PathKind.REMOTE_URL
    assert k.scheme == "https"

def test_classify_s3_url():
    k = classify("s3://bucket/key.nc")
    assert k.kind == PathKind.REMOTE_URL
    assert k.scheme == "s3"

def test_classify_ssh_url():
    k = classify("ssh://user@host:22/path/to/file.nc")
    assert k.kind == PathKind.SSH_REMOTE
    assert k.scheme == "ssh"
    assert k.user == "user"
    assert k.host == "host"
    assert k.port == 22
    assert k.remote_path == "/path/to/file.nc"

def test_classify_ssh_url_no_user_no_port():
    k = classify("ssh://host/path/file.nc")
    assert k.kind == PathKind.SSH_REMOTE
    assert k.user is None
    assert k.port is None

def test_classify_rejects_ftp():
    with pytest.raises(ClassifyError):
        classify("ftp://example.org/x.nc")

def test_classify_rejects_missing_local(tmp_path):
    with pytest.raises(ClassifyError):
        classify(str(tmp_path / "does-not-exist.nc"))
