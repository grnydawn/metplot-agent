from src.mcp.netcdf_reader.tools.transforms import regrid_to_centers


def test_regrid_appends_transform():
    spec = {
        "path": "/tmp/x.nc", "variable": "U",
        "selectors": {}, "resolved": {}, "slice_shape": [1, 33, 290, 201],
        "estimated_bytes": 7700000, "applied_transforms": [], "notes": [],
    }
    env = regrid_to_centers(spec)
    assert env["ok"] is True
    out = env["result"]
    transforms = out["applied_transforms"]
    assert any(t["kind"] == "regrid_to_centers" for t in transforms)


def test_regrid_idempotent():
    spec = {
        "path": "/tmp/x.nc", "variable": "U",
        "selectors": {}, "resolved": {}, "slice_shape": [1, 33, 290, 201],
        "estimated_bytes": 7700000,
        "applied_transforms": [{"kind": "regrid_to_centers"}],
        "notes": [],
    }
    env = regrid_to_centers(spec)
    out = env["result"]
    n = sum(1 for t in out["applied_transforms"] if t["kind"] == "regrid_to_centers")
    assert n == 1


def test_regrid_preserves_other_fields():
    spec = {
        "path": "/x.nc", "variable": "U",
        "selectors": {"time": "last"}, "resolved": {"time_index": 0},
        "slice_shape": [1, 1, 4, 5], "estimated_bytes": 80,
        "applied_transforms": [], "notes": ["hi"],
    }
    out = regrid_to_centers(spec)["result"]
    assert out["variable"] == "U"
    assert out["selectors"]["time"] == "last"
    assert out["notes"] == ["hi"]
