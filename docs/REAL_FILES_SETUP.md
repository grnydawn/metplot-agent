# Real-files integration setup

The plot-renderer real-files scaffold is OFF by default. Enable with:

    export NCPLOT_REAL_FILES=1
    pytest tests/mcp/plot_renderer/integration/test_real_files.py -v

It reads slice paths from a developer-local config:
`tests/integration/real_files.json` (gitignored).

## Config shape

```json
{
  "cf_slice":   "/data/cmip/tos_2024-09.nc",
  "wrf_slice":  "/data/wrf/wrfout_2024-09-15.nc",
  "roms_slice": "/data/roms/his_2024-09.nc",
  "variable_cf":   "tos",
  "variable_wrf":  "T2",
  "variable_roms": "temp"
}
```

The scaffold drives `read_slice`-shaped specs (cycle-1 contract) into
each of the three render tools. Asserts: no exceptions, PNG > 50 KB,
oracle's `nan_fraction < 1.0`.
