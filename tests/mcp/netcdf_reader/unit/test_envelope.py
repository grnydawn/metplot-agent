# tests/mcp/netcdf_reader/unit/test_envelope.py
from src.mcp.netcdf_reader.envelope import ErrorCode, WarningCode, error, success


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


def test_error_code_constants_present():
    assert ErrorCode.FILE_NOT_FOUND == "file_not_found"
    assert ErrorCode.REMOTE_FILE_NOT_FOUND == "remote_file_not_found"
    assert ErrorCode.MULTI_FILE_COMBINE_FAILED == "multi_file_combine_failed"
    assert ErrorCode.SSH_AUTH_FAILED == "ssh_auth_failed"
    assert ErrorCode.UNKNOWN_VARIABLE == "unknown_variable"
    assert ErrorCode.OUT_OF_BOUNDS == "out_of_bounds"
    assert ErrorCode.EMPTY_SLICE == "empty_slice"
    assert ErrorCode.SIZE_LIMIT_EXCEEDED == "size_limit_exceeded"
    assert ErrorCode.CONVENTION_TRANSFORM_UNAVAILABLE == "convention_transform_unavailable"
    assert ErrorCode.NOT_4D == "not_4d"
    assert ErrorCode.AMBIGUOUS == "ambiguous"
    assert ErrorCode.UNSTRUCTURED_DYCORE_UNSUPPORTED == "unstructured_dycore_unsupported"

def test_warning_code_constants_present():
    assert WarningCode.SLOW_REMOTE_READ == "slow_remote_read"
    assert WarningCode.HIGH_NAN_FRACTION == "high_nan_fraction"
    assert WarningCode.CONSTANT_FIELD == "constant_field"
    assert WarningCode.NON_MONOTONIC_COORD == "non_monotonic_coord"
    assert WarningCode.NON_STANDARD_CALENDAR == "non_standard_calendar"
    assert WarningCode.PERCENTILE_CLIP_SUGGESTED == "percentile_clip_suggested"
    assert WarningCode.DYCORE_VARS_PRESENT == "dycore_vars_present"

def test_error_uses_code_constants():
    env = error(ErrorCode.FILE_NOT_FOUND, "nope")
    assert env["error"]["code"] == "file_not_found"
