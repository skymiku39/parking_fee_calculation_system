param(
  [switch]$SkipBuild,
  [switch]$SkipTag,
  [switch]$SkipZip
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
$TagName = "v$Version"

Write-Host "=== Release $TagName ==="

if (-not $SkipBuild) {
  Write-Host 'Running health checks ...'
  & (Join-Path $ScriptDir 'health_check.ps1') -NoInstall -NoCoverage
  & (Join-Path $ScriptDir 'build_exe.ps1')
}

$distDir = Join-Path $ProjectRoot 'dist\ParkingCalculator'
if (-not (Test-Path (Join-Path $distDir 'ParkingCalculator.exe'))) {
  throw "Missing executable: $distDir\ParkingCalculator.exe"
}

if (-not $SkipZip) {
  $releaseDir = Join-Path $ProjectRoot 'release'
  New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null
  $zipName = "ParkingCalculator-$Version-win64.zip"
  $zipPath = Join-Path $releaseDir $zipName
  if (Test-Path $zipPath) { Remove-Item -Force $zipPath }
  Compress-Archive -Path $distDir -DestinationPath $zipPath -Force
  Write-Host "Created: release\$zipName"
}

if (-not $SkipTag) {
  $existingTag = git tag -l $TagName 2>$null
  if ($existingTag) {
    Write-Warning "Git tag $TagName already exists; skipping tag creation."
  } else {
    git tag -a $TagName -m "Release $TagName"
    Write-Host "Created git tag: $TagName"
    Write-Host "Push with: git push origin $TagName"
  }
}

Write-Host ''
Write-Host 'Release artifacts:'
Write-Host "  dist\ParkingCalculator\"
if (-not $SkipZip) {
  Write-Host "  release\ParkingCalculator-$Version-win64.zip"
}
