import xarray as xr

def test_cf_4d_fixture_opens(cf_4d_file):
    ds = xr.open_dataset(cf_4d_file)
    assert "ta" in ds.data_vars
    assert ds["ta"].shape == (3, 4, 19, 72)
    ds.close()

def test_cf_3d_fixture_opens(cf_3d_file):
    ds = xr.open_dataset(cf_3d_file)
    assert "tos" in ds.data_vars
    assert float(ds["lon"].max()) > 180  # 0..360 convention
    ds.close()

def test_multifile_fixture(cf_multifile_dir):
    files = sorted(cf_multifile_dir.glob("*.nc"))
    assert len(files) == 3


def test_wrf_fixture_opens(wrf_file):
    import xarray as xr
    ds = xr.open_dataset(wrf_file)
    assert "T2" in ds.data_vars
    assert "west_east_stag" in ds.dims
    ds.close()


def test_roms_fixture_opens(roms_file):
    import xarray as xr
    ds = xr.open_dataset(roms_file)
    assert "s_rho" in ds.dims
    assert ds["lat_rho"].ndim == 2
    ds.close()
