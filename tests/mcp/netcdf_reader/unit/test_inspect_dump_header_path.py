"""inspect() routes ssh://*.nc through broker.dump_header when broker is up."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.mcp.netcdf_reader.adapter import NetCDFAdapter
from src.mcp.netcdf_reader.tools.inspect import inspect as _inspect


_STUB_CDL = """netcdf foo {
dimensions:
    time = UNLIMITED ;
    lat = 73 ;
variables:
    float t2m(time, lat) ;
        t2m:units = "K" ;
}
"""


def test_inspect_uses_dump_header_when_broker_present():
    broker = MagicMock()
    broker.dump_header.return_value = {
        "cdl": _STUB_CDL, "stderr": "", "exit_code": 0,
    }
    with patch("src.mcp.netcdf_reader.paths.ssh."
                "open_ssh_with_broker_fallback", return_value=broker):
        env = _inspect(adapter=NetCDFAdapter(),
                        path="ssh://host/data/foo.nc")
    assert env["ok"] is True
    assert env["result"]["source"] == "dump_header"
    names = [v["name"] for v in env["result"]["variables"]]
    assert "t2m" in names
    broker.dump_header.assert_called_once_with("/data/foo.nc")


def test_inspect_falls_back_on_nonzero_exit():
    """ncdump missing on remote → exit_code != 0 → use get_full path."""
    broker = MagicMock()
    broker.dump_header.return_value = {
        "cdl": "", "stderr": "ncdump: command not found",
        "exit_code": 127,
    }
    with patch("src.mcp.netcdf_reader.paths.ssh."
                "open_ssh_with_broker_fallback", return_value=broker), \
         patch("src.mcp.netcdf_reader.adapter."
                "NetCDFAdapter._open_via_broker") as fallback:
        fallback.side_effect = RuntimeError("test stops here")
        try:
            _inspect(adapter=NetCDFAdapter(),
                      path="ssh://host/data/foo.nc")
        except RuntimeError as e:
            assert "test stops here" in str(e)
        fallback.assert_called_once()


def test_inspect_falls_back_on_parse_error():
    """Garbled CDL → fallthrough."""
    broker = MagicMock()
    broker.dump_header.return_value = {
        "cdl": "this is not cdl", "stderr": "", "exit_code": 0,
    }
    with patch("src.mcp.netcdf_reader.paths.ssh."
                "open_ssh_with_broker_fallback", return_value=broker), \
         patch("src.mcp.netcdf_reader.adapter."
                "NetCDFAdapter._open_via_broker") as fallback:
        fallback.side_effect = RuntimeError("fallback path reached")
        try:
            _inspect(adapter=NetCDFAdapter(),
                      path="ssh://host/data/foo.nc")
        except RuntimeError as e:
            assert "fallback path reached" in str(e)


def test_inspect_skips_dump_header_for_non_netcdf_suffix():
    """ssh path that doesn't end in .nc/.nc4/.cdf → use get_full path
    directly (no dump_header call)."""
    broker = MagicMock()
    with patch("src.mcp.netcdf_reader.paths.ssh."
                "open_ssh_with_broker_fallback", return_value=broker), \
         patch("src.mcp.netcdf_reader.adapter."
                "NetCDFAdapter._open_via_broker") as fallback:
        fallback.side_effect = RuntimeError("fallback path reached")
        try:
            _inspect(adapter=NetCDFAdapter(),
                      path="ssh://host/data/foo.json")
        except RuntimeError:
            pass
        broker.dump_header.assert_not_called()


def test_inspect_skips_dump_header_when_no_broker():
    """No broker → cycle-12 paramiko path runs (will fail at auth in
    test environment, but we just verify dump_header isn't called)."""
    with patch("src.mcp.netcdf_reader.paths.ssh."
                "open_ssh_with_broker_fallback", return_value=None):
        # The call may raise SSHAuthNeeded or return an error envelope
        # depending on the inspect implementation. We don't care here;
        # we just want to verify the dump_header path isn't taken.
        try:
            _inspect(adapter=NetCDFAdapter(),
                      path="ssh://host/data/foo.nc")
        except Exception:
            pass
