param(
  [string]$Port = "5000"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# 進入專案根目錄
if ($PSScriptRoot) {
  $ScriptDir = $PSScriptRoot
} else {
  $ScriptDir = Split-Path -Path $MyInvocation.MyCommand.Path -Parent
}
$ProjectRoot = Split-Path $ScriptDir -Parent
Set-Location $ProjectRoot

if (-not (Test-Path .venv)) {
  Write-Host '建立虛擬環境 .venv ...'
  python -m venv .venv
}
. .\.venv\Scripts\Activate.ps1

Write-Host '安裝/更新打包依賴 (pyinstaller)...'
python -m pip install --upgrade pip setuptools wheel
pip install pyinstaller

# 清理舊的 build/dist
if (Test-Path build) { Remove-Item -Recurse -Force build }
if (Test-Path dist) { Remove-Item -Recurse -Force dist }

Write-Host '開始打包 ...'

# 動態組合 add-data 參數（Windows 用分號 ; 分隔 src;dest）
$addData = @()
if (Test-Path "templates") { $addData += @('--add-data', 'templates;templates') }
if (Test-Path "static")    { $addData += @('--add-data', 'static;static') }
if (Test-Path "config")    { $addData += @('--add-data', 'config;config') }
if (Test-Path "templates/rate_plan_template.xlsx") { $addData += @('--add-data', 'templates/rate_plan_template.xlsx;templates') }

$argsList = @(
  '--noconfirm',
  '--clean',
  '--name', 'ParkingCalculator'
) + $addData + @(
  '--hidden-import', 'app',
  '--hidden-import', 'src.domain.rate_plan_manager',
  '--hidden-import', 'src.domain.pricing.unified_pricing_engine',
  'scripts\launcher.py'
)

& pyinstaller @argsList

Write-Host '打包完成。可執行檔位於 dist\ParkingCalculator\ParkingCalculator.exe'
Write-Host '提示：執行時可設定 PORT 環境變數變更埠號，例如：'
Write-Host '  set PORT=5001 && .\dist\ParkingCalculator\ParkingCalculator.exe'


