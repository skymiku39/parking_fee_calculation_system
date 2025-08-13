param(
  [switch]$NoInstall,
  [switch]$NoRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# 專案根目錄（此腳本位於 scripts/ 底下）
# 兼容在部分環境下 $PSScriptRoot 未定義的情況
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

# 啟用虛擬環境
. .\.venv\Scripts\Activate.ps1

if (-not $NoInstall) {
  Write-Host '升級 pip 並安裝依賴 ...'
  # 確保 pip 可用並修復可能的破損安裝
  python -m ensurepip --upgrade
  python -m pip install --upgrade --force-reinstall pip setuptools wheel
  pip install -r requirements.txt
}

if (-not $NoRun) {
  Write-Host '啟動 Flask 應用 ...'
  python app.py
}


