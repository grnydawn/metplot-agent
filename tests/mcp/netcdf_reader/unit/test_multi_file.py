import numpy as np
import pytest
import xarray as xr

from src.mcp.netcdf_reader.paths.multi_file import (
    open_multi_file, MultiFileCombineError,
)


def test_open_multi_file_combines_by_coords(cf_multifile_dir):
    paths = sorted(str(p) for p in cf_multifile_dir.glob("*.nc"))
    ds = open_multi_file(paths)
    assert isinstance(ds, xr.Dataset)
    assert ds.sizes["time"] == 6  # 3 files × 2 timesteps
    ds.close()


def test_open_multi_file_falls_back_to_nested(tmp_path):
    """Files that can't combine by_coords because of attribute conflicts
    fall back to combine='nested' along the time dim."""
    out = tmp_path / "conflicting"; out.mkdir()
    for i in range(2):
        ds = xr.Dataset(
            {"v": (("time", "lat"), np.zeros((1, 3), dtype="float32"))},
            coords={"time": [np.datetime64(f"2024-09-0{i+1}")],
                    "lat": np.array([0, 1, 2], dtype="float32")},
            attrs={"history": f"created run {i}"},  # conflicting attr
        )
        ds.to_netcdf(out / f"f{i}.nc")
    files = sorted(str(p) for p in out.glob("*.nc"))
    ds_out = open_multi_file(files)
    assert ds_out.sizes["time"] == 2
    ds_out.close()


def test_open_multi_file_raises_on_unmergeable(tmp_path):
    """Files with completely incompatible structures raise."""
    out = tmp_path / "incompat"; out.mkdir()
    ds1 = xr.Dataset({"a": (("x",), np.array([1, 2, 3]))})
    ds2 = xr.Dataset({"b": (("y",), np.array([1, 2]))})
    ds1.to_netcdf(out / "1.nc")
    ds2.to_netcdf(out / "2.nc")
    with pytest.raises(MultiFileCombineError):
        open_multi_file([str(out / "1.nc"), str(out / "2.nc")])
