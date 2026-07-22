# SPDX-License-Identifier: GPL-3.0-or-later
param(
    [string]$Blender = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
)

$ErrorActionPreference = 'Stop'

& $Blender --factory-startup --background --python-exit-code 1 --python tests/blender/run_all.py
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
