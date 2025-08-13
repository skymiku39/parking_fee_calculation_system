param(
  [switch]$NoInstall,
  [switch]$NoRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# 專案根目錄（此腳本位於 scripts/ 底下）
$ProjectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $ProjectRoot

if (-not (Test-Path .venv)) {
  Write-Host '建立虛擬環境 .venv ...'
  python -m venv .venv
}

# 啟用虛擬環境
. .\.venv\Scripts\Activate.ps1

if (-not $NoInstall) {
  Write-Host '升級 pip 並安裝依賴 ...'
  python -m pip install -U pip
  pip install -r requirements.txt
}

if (-not $NoRun) {
  Write-Host '啟動 Flask 應用 ...'
  python app.py
}


