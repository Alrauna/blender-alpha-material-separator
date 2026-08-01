# SPDX-License-Identifier: GPL-3.0-or-later
param(
    [string]$Blender = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
)

$ErrorActionPreference = 'Stop'

$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$OutputDirectory = Join-Path $RepositoryRoot '.packaged-releases'
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

& $Blender --factory-startup --command extension validate (Join-Path $RepositoryRoot 'addon')
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& $Blender --factory-startup --command extension build --source-dir (Join-Path $RepositoryRoot 'addon') --output-dir $OutputDirectory
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
