from src.mcp.plot_renderer.envelope import (
    success, error, ambiguous, warn,
    ErrorCode, AmbiguitySubcode, WarningCode,
)


def test_success_shape():
    env = success({"path": "x.png"})
    assert env == {"ok": True, "result": {"path": "x.png"}, "warnings": []}


def test_success_with_warnings():
    w = warn(WarningCode.AUTO_DOWNSAMPLED, "downsampled", {"factor": 2})
    env = success({"k": 1}, warnings=[w])
    assert env["ok"] is True
    assert env["warnings"][0]["code"] == "auto_downsampled"
    assert env["warnings"][0]["context"]["factor"] == 2


def test_error_shape():
    env = error(ErrorCode.INVALID_SPEC, "missing values", context={"field": "values"})
    assert env == {
        "ok": False,
        "error": {"code": "invalid_spec",
                  "message": "missing values",
                  "context": {"field": "values"}},
    }


def test_ambiguous_shape():
    env = ambiguous(
        subcode=AmbiguitySubcode.CARTOPY_MISSING,
        message="install cartopy",
        candidates=[{"param": "install", "value": "uv pip install cartopy"}],
        retry_with_param=None,
        context={"hint": "use conda-forge"},
    )
    assert env["ok"] is False
    assert env["error"]["code"] == "ambiguous"
    assert env["error"]["subcode"] == "cartopy_missing"
    assert env["error"]["candidates"][0]["param"] == "install"
