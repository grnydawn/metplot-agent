#!/usr/bin/env bash
# tests/mcp/netcdf_reader/integration/download_samples.sh
#
# Populate tests/mcp/netcdf_reader/integration/data/ with small real
# samples for integration testing. Replace these URLs with samples you
# have rights to. Files land in a gitignored directory.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)/data"
mkdir -p "$DIR"

# Replace with actual URLs you control or have rights to
# curl -L -o "$DIR/wrfout_sample.nc" "https://example.org/wrfout_small.nc"
# curl -L -o "$DIR/era5_t2m_sample.nc" "https://example.org/era5_t2m_small.nc"

echo "Edit this script with the URLs of your sample files,"
echo "then re-run to populate $DIR."
