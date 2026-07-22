# SPDX-License-Identifier: GPL-3.0-or-later
param(
    [string]$Blender = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
)

$ErrorActionPreference = 'Stop'
$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$Output = Join-Path $RepositoryRoot '.test-output\benchmarks\baseline.json'

& $Blender --factory-startup --background --python-exit-code 1 `
    --python (Join-Path $RepositoryRoot 'tests\blender\run_benchmarks.py') `
    -- --output $Output
exit $LASTEXITCODE
