import xarray as xr
from src.mcp.netcdf_reader.conventions.roms import (
    detect, extract_spatial_roms, extract_vertical_roms,
)


def test_roms_detected_from_s_rho(roms_file):
    ds = xr.open_dataset(roms_file)
    r = detect(ds, ds.attrs)
    assert r is not None
    assert r["primary"] == "ROMS"
    assert any("s_rho" in e or "Cs_r" in e for e in r["evidence"])
    ds.close()


def test_non_roms_returns_none(cf_3d_file):
    ds = xr.open_dataset(cf_3d_file)
    assert detect(ds, ds.attrs) is None
    ds.close()


def test_extract_spatial_roms_curvilinear(roms_file):
    ds = xr.open_dataset(roms_file)
    s = extract_spatial_roms(ds)
    assert s["coord_kind"] == "curvilinear"
    assert s["lat_name"] == "lat_rho"
    assert s["lon_name"] == "lon_rho"
    ds.close()


def test_extract_vertical_roms_sigma(roms_file):
    ds = xr.open_dataset(roms_file)
    v = extract_vertical_roms(ds)
    assert v["name"] == "s_rho"
    assert v["kind"] == "sigma"
    assert v["n"] == 3
    ds.close()
