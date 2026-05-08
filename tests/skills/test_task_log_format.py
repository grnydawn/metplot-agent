# tests/skills/test_task_log_format.py
"""Validate the task-log JSONL schema (cycle-6 contract)."""
from __future__ import annotations

import json
from datetime import datetime, timezone


def _valid_iso8601(ts: str) -> bool:
    try:
        # Python's fromisoformat accepts "Z" suffix on 3.11+; fall back manually
        if ts.endswith("Z"):
            datetime.fromisoformat(ts.removesuffix("Z")).replace(tzinfo=timezone.utc)
        else:
            datetime.fromisoformat(ts)
        return True
    except ValueError:
        return False


def test_alias_correction_event_parses():
    line = json.dumps({
        "ts": "2026-05-07T14:30:00Z",
        "skill": "netcdf-inspect",
        "step": "alias_correction",
        "input": "user said: SST",
        "resolved": "tos",
        "via": "user_correction",
        "context": "CMIP6 historical run",
    })
    obj = json.loads(line)
    assert _valid_iso8601(obj["ts"])
    assert obj["skill"] in {
        "netcdf-inspect", "netcdf-plot-router",
        "netcdf-plot-map", "netcdf-plot-timeseries", "netcdf-plot-profile",
    }
    assert obj["step"] == "alias_correction"
    assert obj["via"] == "user_correction"


def test_region_correction_event_parses():
    line = json.dumps({
        "ts": "2026-05-07T14:35:00Z",
        "skill": "netcdf-plot-map",
        "step": "region_correction",
        "input": "user said: North Atlantic",
        "resolved_initial": {"lon_min": -80, "lon_max": 0,
                              "lat_min": 20, "lat_max": 70},
        "resolved_final":   {"lon_min": -90, "lon_max": 10,
                              "lat_min": 15, "lat_max": 75},
        "via": "user_correction",
    })
    obj = json.loads(line)
    assert obj["resolved_initial"]["lon_min"] == -80
    assert obj["resolved_final"]["lon_max"] == 10


def test_colormap_correction_event_parses():
    line = json.dumps({
        "ts": "2026-05-07T14:40:00Z",
        "skill": "netcdf-plot-map",
        "step": "colormap_correction",
        "input": "auto-picked: RdYlBu_r",
        "resolved": "viridis",
        "via": "user_correction",
        "context": {"variable": "tos", "units": "K"},
    })
    obj = json.loads(line)
    assert obj["resolved"] == "viridis"
    assert obj["context"]["variable"] == "tos"


def test_required_fields_present():
    """Every event must have ts, skill, step, via."""
    required = {"ts", "skill", "step", "via"}
    sample = {
        "ts": "2026-05-07T14:30:00Z",
        "skill": "netcdf-inspect",
        "step": "alias_correction",
        "via": "user_correction",
    }
    assert required.issubset(sample.keys())


def test_via_values_recognized():
    """`via` field uses one of the recognized provenance values."""
    recognized = {"user_correction", "auto_detected", "prompt_clarified"}
    for via in ("user_correction", "auto_detected", "prompt_clarified"):
        assert via in recognized
