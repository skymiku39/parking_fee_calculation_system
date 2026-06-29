param(
  [switch]$NoInstall,
  [switch]$NoCoverage
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
# 依賴各步驟的 exit code 判斷成敗；不要把原生指令寫到 stderr 的訊息（如 logging）當成終止錯誤
if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -Scope Global -ErrorAction SilentlyContinue) {
  $PSNativeCommandUseErrorActionPreference = $false
}

# 專案根目錄（此腳本位於 tools/ 底下）
if ($PSScriptRoot) {
  $ScriptDir = $PSScriptRoot
} else {
  $ScriptDir = Split-Path -Path $MyInvocation.MyCommand.Path -Parent
}
$ProjectRoot = Split-Path $ScriptDir -Parent
Set-Location $ProjectRoot

$failures = New-Object System.Collections.Generic.List[string]

function Invoke-Step {
  param(
    [string]$Name,
    [scriptblock]$Action
  )
  Write-Host ''
  Write-Host "=== $Name ===" -ForegroundColor Cyan
  & $Action
  if ($LASTEXITCODE -ne 0) {
    Write-Host "[FAIL] $Name (exit code $LASTEXITCODE)" -ForegroundColor Red
    $failures.Add($Name)
  } else {
    Write-Host "[OK] $Name" -ForegroundColor Green
  }
}

if (-not $NoInstall) {
  Invoke-Step '依賴同步 (uv sync)' { uv sync --group dev }
}

Invoke-Step '靜態檢查 (ruff)' { uv run ruff check . }

if ($NoCoverage) {
  Invoke-Step '單元/整合測試 (pytest)' { uv run pytest -q }
} else {
  Invoke-Step '單元/整合測試 + 覆蓋率 (pytest --cov)' { uv run pytest --cov=src --cov-report=term-missing }
}

Invoke-Step '設定檔驗證 (validate_configs)' { uv run python tools/validate_configs.py }

Invoke-Step '邊界驗證 (validate_time_boundaries)' { uv run python tools/validate_time_boundaries.py }

Invoke-Step '整合情境 (verify_integration_scenarios)' { uv run python tools/verify_integration_scenarios.py }

Write-Host ''
Write-Host '============================================================'
if ($failures.Count -gt 0) {
  Write-Host "健康檢查未通過，失敗項目：" -ForegroundColor Red
  foreach ($f in $failures) {
    Write-Host "  - $f" -ForegroundColor Red
  }
  exit 1
}

Write-Host '健康檢查全數通過' -ForegroundColor Green
exit 0
