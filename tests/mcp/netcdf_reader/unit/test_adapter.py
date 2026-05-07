# tests/mcp/netcdf_reader/unit/test_adapter.py
import xarray as xr
from src.mcp.netcdf_reader.adapter import NetCDFAdapter, FormatAdapter


def test_adapter_implements_protocol():
    a = NetCDFAdapter()
    assert isinstance(a, FormatAdapter)
    assert a.name == "netcdf"
    assert "file" in a.supported_schemes
    assert "ssh" in a.supported_schemes
    assert "http" in a.supported_schemes
    assert "https" in a.supported_schemes


def test_adapter_claims_nc_files(tmp_path):
    a = NetCDFAdapter()
    nc = tmp_path / "x.nc"
    nc.write_bytes(b"")
    assert a.claims(str(nc)) is True
    assert a.claims("https://example.org/x.nc") is True
    assert a.claims("ssh://h/x.nc") is True
    assert a.claims(str(tmp_path / "x.zarr")) is False
    assert a.claims(str(tmp_path / "x.grib2")) is False


def test_adapter_open_local_single(cf_3d_file):
    a = NetCDFAdapter()
    ds = a.open([str(cf_3d_file)])
    assert isinstance(ds, xr.Dataset)
    assert "tos" in ds.data_vars
    ds.close()
