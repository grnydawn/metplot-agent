# tests/mcp/plot_renderer/integration/test_image_diff_optional.py
"""Optional image-diff suite. Gated on `pytest --image-diff`.

Compares freshly rendered figures against committed PNGs in tests/golden/
using SSIM (scikit-image). Tolerance: SSIM >= 0.95.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.image_diff

GOLDEN_DIR = Path(__file__).resolve().parents[3] / "golden"
SSIM_THRESHOLD = 0.95


def _ssim(a_path: Path, b_path: Path) -> float:
    from skimage import io
    from skimage.metrics import structural_similarity as ssim
    a = io.imread(str(a_path), as_gray=True)
    b = io.imread(str(b_path), as_gray=True)
    if a.shape != b.shape:
        return 0.0
    score, _ = ssim(a, b, full=True, data_range=1.0)
    return float(score)


def _compare_or_regenerate(request, fresh: Path, golden: Path) -> None:
    if request.config.getoption("--regenerate-golden"):
        golden.parent.mkdir(parents=True, exist_ok=True)
        golden.write_bytes(fresh.read_bytes())
        pytest.skip(f"regenerated {golden.name}")
    if not golden.exists():
        pytest.fail(f"golden {golden.name} missing; run with --regenerate-golden")
    score = _ssim(fresh, golden)
    assert score >= SSIM_THRESHOLD, (
        f"SSIM {score:.3f} below {SSIM_THRESHOLD} for {golden.name}")


def test_golden_basic_map(request, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from src.mcp.plot_renderer.tools import render_map as rm
    if not rm._CARTOPY_OK:
        pytest.skip("cartopy not installed")
    spec = {"values": [[1.0, 2.0], [3.0, 4.0]],
            "lat": [0.0, 1.0], "lon": [0.0, 1.0],
            "projection": "Robinson",
            "output_path": str(tmp_path / "fresh.png")}
    env = rm.render_map(spec)
    assert env["ok"] is True
    _compare_or_regenerate(request,
                            tmp_path / "fresh.png",
                            GOLDEN_DIR / "basic_map_robinson.png")


def test_golden_timeseries_two_series(request, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from src.mcp.plot_renderer.tools.render_timeseries import render_timeseries
    spec = {"series": [
        {"values": [1.0, 2.0, 3.0], "time": ["2024-01-15", "2024-02-15", "2024-03-15"],
         "label": "A"},
        {"values": [3.0, 2.0, 1.0], "time": ["2024-01-15", "2024-02-15", "2024-03-15"],
         "label": "B"},
    ], "trendline": "linear",
       "output_path": str(tmp_path / "fresh.png")}
    env = render_timeseries(spec)
    assert env["ok"] is True
    _compare_or_regenerate(request,
                            tmp_path / "fresh.png",
                            GOLDEN_DIR / "timeseries_two_series.png")


def test_golden_profile_pressure(request, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from src.mcp.plot_renderer.tools.render_profile import render_profile
    spec = {"values": [288.0, 270.0, 250.0, 220.0, 200.0],
            "vertical": [1000.0, 700.0, 500.0, 250.0, 100.0],
            "vertical_units": "hPa",
            "output_path": str(tmp_path / "fresh.png")}
    env = render_profile(spec)
    assert env["ok"] is True
    _compare_or_regenerate(request,
                            tmp_path / "fresh.png",
                            GOLDEN_DIR / "profile_pressure.png")
