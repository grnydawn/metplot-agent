"""Bash + PowerShell wrapper templates for cycle-5 setup."""

SETUP_SH = '''\
#!/usr/bin/env bash
# ncplot setup wrapper. Runs tools/install_deps.py against the bundled
# mcp-servers/. See README.md for usage and flags.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DEPS="$SCRIPT_DIR/tools/install_deps.py"

if [ ! -f "$INSTALL_DEPS" ]; then
    echo "ERROR: tools/install_deps.py not found in $SCRIPT_DIR." >&2
    echo "       The plugin payload is incomplete; reinstall from a fresh build." >&2
    exit 2
fi

# Choose Python: VIRTUAL_ENV first, then python3.10+
if [ -n "${VIRTUAL_ENV:-}" ] && [ -x "${VIRTUAL_ENV}/bin/python" ]; then
    PYTHON_BIN="${VIRTUAL_ENV}/bin/python"
else
    for p in python3.12 python3.11 python3.10 python3 python; do
        if command -v "$p" >/dev/null 2>&1; then
            PYTHON_BIN="$p"
            break
        fi
    done
    if [ -z "${PYTHON_BIN:-}" ]; then
        echo "ERROR: no python3.10+ found on PATH." >&2
        exit 2
    fi
fi

exec "$PYTHON_BIN" "$INSTALL_DEPS" \\
    --mcp-servers-dir "$SCRIPT_DIR/mcp-servers" \\
    "$@"
'''

SETUP_PS1 = '''\
# ncplot setup wrapper (PowerShell). Runs tools/install_deps.py against the bundled
# mcp-servers/. See README.md for usage.
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$InstallDeps = Join-Path $ScriptDir "tools/install_deps.py"

if (-not (Test-Path $InstallDeps)) {
    Write-Error "tools/install_deps.py not found. Plugin payload is incomplete."
    exit 2
}

# Choose Python
if ($env:VIRTUAL_ENV -and (Test-Path "$env:VIRTUAL_ENV/Scripts/python.exe")) {
    $PythonBin = "$env:VIRTUAL_ENV/Scripts/python.exe"
} else {
    foreach ($p in @("python3.12", "python3.11", "python3.10", "python3", "python")) {
        $found = Get-Command $p -ErrorAction SilentlyContinue
        if ($found) { $PythonBin = $p; break }
    }
    if (-not $PythonBin) {
        Write-Error "No Python 3.10+ found on PATH."
        exit 2
    }
}

& $PythonBin $InstallDeps `
    --mcp-servers-dir "$ScriptDir/mcp-servers" `
    @args
'''
