# src/mcp/netcdf_reader/adapter.py
"""Format-specific: NetCDFAdapter implements the FormatAdapter protocol
that lives at the seam between cycle 1's reader and a future _core/
package. See spec §11."""
from __future__ import annotations

from typing import Any

import xarray as xr

# Re-export FormatAdapter from the format-agnostic protocols module so that
# `from src.mcp.netcdf_reader.adapter import FormatAdapter` continues to work
# for any external caller, while internal format-agnostic modules (tools/*)
# can import it directly from protocols.py without crossing the seam.
from src.mcp.netcdf_reader.protocols import FormatAdapter

__all__ = ["FormatAdapter", "NetCDFAdapter"]


class NetCDFAdapter:
    name = "netcdf"
    supported_schemes = {"file", "http", "https", "s3", "ssh"}

    _NC_SUFFIXES = (".nc", ".nc4", ".cdf")

    def claims(self, path: str) -> bool:
        # Heuristic: any path ending in .nc / .nc4 / .cdf, or any non-store scheme path
        # whose path component ends in those suffixes.
        lowered = path.lower()
        for s in self._NC_SUFFIXES:
            if lowered.endswith(s):
                return True
            # also handle "...?query" or fragment after suffix
            if s + "?" in lowered or s + "#" in lowered:
                return True
        return False

    def expand(self, path: str) -> list[str]:
        # Format-agnostic glob expansion handled in paths.classify.
        # NetCDF specifics live in paths.multi_file (Task 30+).
        return [path]

    def open(
        self, paths: list[str], file_objects: list[Any] | None = None,
        ssh_config: dict[str, Any] | None = None,
    ) -> xr.Dataset:
        from src.mcp.netcdf_reader.paths.classify import classify, PathKind

        if file_objects:
            if len(file_objects) != 1:
                raise NotImplementedError("multi-file SSH not yet wired")
            return xr.open_dataset(file_objects[0], engine="h5netcdf",
                                   decode_times=True, chunks="auto")

        if len(paths) == 1:
            cls = classify(paths[0])
            if cls.kind == PathKind.SSH_REMOTE:
                from src.mcp.netcdf_reader.paths.ssh import (
                    SSHConfig, parse_ssh_config_for_host,
                    silent_auth_chain, connect_explicit, open_sftp_file,
                )
                assert cls.host is not None
                assert cls.remote_path is not None
                if ssh_config:
                    cfg = SSHConfig(
                        host=ssh_config.get("host") or cls.host,
                        port=ssh_config.get("port") or cls.port or 22,
                        user=ssh_config.get("user") or cls.user,
                    )
                    auth = ssh_config.get("auth", {})
                    method = auth.get("method")
                    if method == "password":
                        cfg.password = auth.get("password")
                    elif method == "identity_file":
                        cfg.identity_file = auth.get("identity_file")
                        cfg.passphrase = auth.get("passphrase")
                    client = connect_explicit(cfg)
                else:
                    cfg = parse_ssh_config_for_host(cls.host)
                    if cls.user:
                        cfg.user = cls.user
                    if cls.port:
                        cfg.port = cls.port
                    client, _attempts = silent_auth_chain(cfg)
                handle = open_sftp_file(client, cls.remote_path)
                return xr.open_dataset(handle, engine="h5netcdf",
                                       decode_times=True, chunks="auto")
            return xr.open_dataset(paths[0], decode_times=True, chunks="auto")

        from src.mcp.netcdf_reader.paths.multi_file import open_multi_file
        return open_multi_file(paths)

    def detect_conventions(self, ds: xr.Dataset, attrs: dict[str, Any]) -> dict[str, Any]:
        from src.mcp.netcdf_reader.conventions import cf as _cf
        from src.mcp.netcdf_reader.conventions import roms as _roms
        from src.mcp.netcdf_reader.conventions import wrf as _wrf
        # WRF and ROMS take precedence — they're more specific
        for det in (_wrf.detect(ds, attrs), _roms.detect(ds, attrs)):
            if det is not None:
                return det
        return _cf.detect(ds, attrs)
