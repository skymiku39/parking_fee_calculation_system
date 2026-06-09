param(
  [string]$Port = "5000"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ($PSScriptRoot) {
  $ScriptDir = $PSScriptRoot
} else {
  $ScriptDir = Split-Path -Path $MyInvocation.MyCommand.Path -Parent
}
$ProjectRoot = Split-Path $ScriptDir -Parent
Set-Location $ProjectRoot

function Get-ProjectVersion {
  $pyproject = Join-Path $ProjectRoot 'pyproject.toml'
  $content = Get-Content $pyproject -Raw -Encoding UTF8
  if ($content -match '(?m)^version\s*=\s*"([^"]+)"') {
    return $Matches[1]
  }
  throw 'Cannot read version from pyproject.toml'
}

$Version = Get-ProjectVersion
$Version | Set-Content -Path (Join-Path $ProjectRoot 'VERSION') -Encoding UTF8 -NoNewline
Write-Host "Building ParkingCalculator v$Version ..."

Write-Host 'Sync dependencies (uv) ...'
uv sync --group dev

Write-Host 'Installing PyInstaller ...'
uv pip install pyinstaller

if (Test-Path build) { Remove-Item -Recurse -Force build }
if (Test-Path dist) { Remove-Item -Recurse -Force dist }

$addData = @()
if (Test-Path 'src/web/templates') {
  $addData += @('--add-data', 'src/web/templates;templates')
}
if (Test-Path 'src/web/static') {
  $addData += @('--add-data', 'src/web/static;static')
}
if (Test-Path 'config') {
  $addData += @('--add-data', 'config;defaults')
}
if (Test-Path 'VERSION') {
  $addData += @('--add-data', 'VERSION;.')
}

$pyinstallerArgs = @(
  '--noconfirm',
  '--clean',
  '--name', 'ParkingCalculator',
  '--paths', $ProjectRoot,
  '--collect-submodules', 'src',
  '--hidden-import', 'app',
  '--hidden-import', 'flask',
  '--hidden-import', 'jsonschema'
) + $addData + @(
  'tools\launcher.py'
)

Write-Host 'Running PyInstaller ...'
uv run pyinstaller @pyinstallerArgs

$distDir = Join-Path $ProjectRoot 'dist\ParkingCalculator'
$dataDir = Join-Path $distDir 'data'
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

$seedFiles = @(
  'system_config.json',
  'system_calendar.json',
  'multidimensional_rate_plans.json',
  'user_defined_plans.json'
)
foreach ($file in $seedFiles) {
  $src = Join-Path $ProjectRoot "config\$file"
  if (Test-Path $src) {
    Copy-Item $src (Join-Path $dataDir $file) -Force
  }
}

@"
ParkingCalculator v$Version
Build date: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
Data directory: .\data\
Port: set PORT environment variable (default 5000)
"@ | Set-Content -Path (Join-Path $distDir 'VERSION.txt') -Encoding UTF8

Write-Host ''
Write-Host "Build complete: dist\ParkingCalculator\ParkingCalculator.exe"
Write-Host "Version: $Version"
Write-Host 'External data: dist\ParkingCalculator\data\'
Write-Host "Run: `$env:PORT=$Port; .\dist\ParkingCalculator\ParkingCalculator.exe"
