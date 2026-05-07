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
