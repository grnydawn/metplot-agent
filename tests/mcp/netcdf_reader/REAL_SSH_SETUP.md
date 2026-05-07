# Real-SSH integration tests

These tests run only when `NCPLOT_REAL_SSH=1` is set. They verify that
the SSH path works against a real remote endpoint of your choosing.

## Setup

1. Pick a remote host you can SSH into. (Localhost SSH is fine — `sshd`
   on macOS / Linux works.)
2. Place a small NetCDF file on that remote (e.g., `/tmp/fixture.nc`).
   You can generate one with:

   ```python
   import xarray as xr, numpy as np
   ds = xr.Dataset(
       {"v": (("t", "lat", "lon"),
              np.random.default_rng(0).normal(size=(3, 5, 6)).astype("f4"))},
       coords={"t": np.array(["2024-01-01", "2024-01-02", "2024-01-03"], dtype="datetime64[D]"),
               "lat": np.linspace(-30, 30, 5), "lon": np.linspace(-60, 60, 6)},
       attrs={"Conventions": "CF-1.7"},
   )
   ds.to_netcdf("/tmp/fixture.nc")
   ```

3. Configure env vars. Either export inline:

   ```bash
   export NCPLOT_REAL_SSH=1
   export NCPLOT_REAL_SSH_HOST=localhost
   export NCPLOT_REAL_SSH_USER=$USER
   export NCPLOT_REAL_SSH_FIXTURE_PATH=/tmp/fixture.nc
   export NCPLOT_REAL_SSH_KEY_PATH=$HOME/.ssh/id_ed25519  # optional
   ```

   Or write `.env.test` at the repo root (gitignored):

   ```ini
   NCPLOT_REAL_SSH=1
   NCPLOT_REAL_SSH_HOST=localhost
   NCPLOT_REAL_SSH_USER=youngsung
   NCPLOT_REAL_SSH_FIXTURE_PATH=/tmp/fixture.nc
   NCPLOT_REAL_SSH_KEY_PATH=/home/youngsung/.ssh/id_ed25519
   ```

4. Run:

   ```bash
   pytest tests/mcp/netcdf_reader/integration/test_real_ssh.py -v -m real_ssh
   ```

## Notes

- If you want to test password auth, set `NCPLOT_REAL_SSH_PASSWORD` in
  `.env.test` (NEVER inline on the command line). The credential-redaction
  property tests verify the password never lands in test output or any
  cache file.
- The opt-in marker (`pytest -m real_ssh`) prevents these tests from
  running in CI by default.
- Localhost SSH is the easiest setup. macOS: System Preferences → Sharing
  → Remote Login. Linux: `sudo systemctl enable --now sshd`.
