param(
  [switch]$NoInstall,
  [switch]$NoRun,
  [switch]$Debug,
  [string]$Port = "5000"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# 專案根目錄（此腳本位於 tools/ 底下）
# 兼容在部分環境下 $PSScriptRoot 未定義的情況
if ($PSScriptRoot) {
  $ScriptDir = $PSScriptRoot
} else {
  $ScriptDir = Split-Path -Path $MyInvocation.MyCommand.Path -Parent
}
$ProjectRoot = Split-Path $ScriptDir -Parent
Set-Location $ProjectRoot

if (-not $NoInstall) {
  Write-Host '使用 uv 同步依賴 ...'
  uv sync --group dev
}

# 啟用虛擬環境
. .\.venv\Scripts\Activate.ps1

if (-not $NoRun) {
  Write-Host "檢查本機 http://127.0.0.1:$Port 是否已啟動..."
  $serverUp = $false
  try {
    $resp = Invoke-WebRequest -Uri "http://127.0.0.1:$Port" -TimeoutSec 1 -ErrorAction Stop
    $serverUp = $true
  } catch {}

  if ($serverUp) {
    Write-Host '服務已在執行，直接開啟瀏覽器'
    Start-Process "http://127.0.0.1:$Port"
  } else {
    Write-Host '未偵測到服務，啟動 Flask 應用 ...'
    $env:PORT = $Port
    if ($Debug) { $env:FLASK_DEBUG = '1' }
    $p = Start-Process -FilePath "python" -ArgumentList "app.py" -PassThru
    Start-Sleep -Seconds 2
    try {
      $null = Invoke-WebRequest -Uri "http://127.0.0.1:$Port" -TimeoutSec 5 -ErrorAction Stop
      Start-Process "http://127.0.0.1:$Port"
    } catch {
      Write-Host "服務啟動檢測逾時，但已在背景執行 (PID=$($p.Id))"
    }
  }
}


