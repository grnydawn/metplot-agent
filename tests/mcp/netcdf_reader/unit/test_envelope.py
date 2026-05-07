# tests/mcp/netcdf-reader/unit/test_envelope.py
from src.mcp.netcdf_reader.envelope import success

def test_success_envelope_minimal():
    env = success({"foo": "bar"})
    assert env == {
        "ok": True,
        "result": {"foo": "bar"},
        "warnings": [],
        "resolved": {},
    }

def test_success_envelope_with_warnings_and_resolved():
    env = success(
        {"value": 1},
        warnings=[{"code": "slow_remote_read", "message": "took 45s", "context": {}}],
        resolved={"time_value": "2024-09-01T12:00:00"},
    )
    assert env["ok"] is True
    assert len(env["warnings"]) == 1
    assert env["warnings"][0]["code"] == "slow_remote_read"
    assert env["resolved"] == {"time_value": "2024-09-01T12:00:00"}
