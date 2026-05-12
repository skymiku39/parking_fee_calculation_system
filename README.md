# 智能停車費率計算系統 v2.0

現代化的停車場收費管理解決方案

---

## 項目概覽

智能停車費率計算系統是一個功能完整的停車收費管理平台，採用**收費週期邏輯**和**多維度標籤系統**，為停車場提供精確、靈活的收費解決方案。

### 核心特色

- **收費週期邏輯**：符合真實停車場收費標準，按收費週期計算而非時段邊界切割
- **多維度標籤**：時段 x 假日 x 費率的靈活組合，支援 15 種標準配置
- **Web 管理界面**：直觀的用戶操作介面，響應式設計
- **配置驅動**：純 JSON 配置文件管理，無需修改代碼
- **完整測試**：pytest 自動化測試，品質保證

---

## 快速開始

### 環境要求

- **Python**：3.10+
- **套件管理**：[uv](https://docs.astral.sh/uv/)
- **操作系統**：Windows / Linux / macOS

### 安裝和啟動

```powershell
# 進入專案根目錄
cd parking_fee_calculation_system

# 一鍵啟動（自動安裝依賴並啟動伺服器）
./scripts/start.ps1

# 若已安裝依賴，略過安裝直接啟動
./scripts/start.ps1 -NoInstall

# 只安裝依賴，不啟動（CI / 自動化可用）
./scripts/start.ps1 -NoRun
```

啟動後開啟瀏覽器：`http://127.0.0.1:5000`

---

## 專案結構

```
parking_fee_calculation_system/
├── app.py                  # Flask 應用入口
├── pyproject.toml          # 專案定義與依賴（uv 管理）
│
├── src/                    # 核心程式碼
│   ├── core/               # 系統啟動、設定、工具
│   │   ├── context.py      # 全域系統單例
│   │   ├── system.py       # SmartParkingSystem 主類
│   │   ├── utils.py        # 共用工具函式
│   │   └── validation.py   # JSON Schema 驗證
│   ├── domain/             # 業務邏輯
│   │   ├── parking_calculator.py
│   │   ├── multidimensional_calculator.py
│   │   ├── rate_plan_manager.py
│   │   └── pricing/        # 統一計價引擎
│   └── web/                # Flask 藍圖（REST API）
│       ├── calc.py          # /api/calculate
│       ├── calendar.py      # /api/calendar/*
│       ├── mdp.py           # /api/mdp/*
│       ├── system.py        # /api/system/*
│       └── misc.py          # 靜態資源
│
├── config/                 # 執行期 JSON 設定檔
├── templates/              # Jinja HTML 模板
├── static/                 # 前端 CSS / JS
├── tests/                  # pytest 自動化測試
├── scripts/                # 啟動、打包、驗證腳本
├── api/contracts/          # OpenAPI 規格
├── docs/                   # 方案文件
└── archive/                # 封存（舊 demo、打包 spec）
```

---

## 主要功能

### 停車費計算

- **精確計算**：按收費週期邏輯計算，避免時段邊界錯誤
- **跨日處理**：正確處理跨日停車計算
- **多種費率**：支援固定費率、累進費率、全域上限等
- **假日識別**：自動區分平日和假日費率

### 多維度配置

- **時段設定**：全天、二段、三段、任意段多種選擇
- **假日類型**：無假日、六日假日、國定假日配置
- **費率矩陣**：視覺化的費率組合編輯器
- **即時預覽**：配置時即時預覽計費效果

### 方案管理

- **預設方案**：提供多種常用的費率方案
- **自訂方案**：用戶可創建和儲存自己的費率方案
- **方案匯入匯出**：支援方案的備份和分享

---

## 配置說明

主要配置文件位於 `config/` 目錄，詳見 [config/README.md](config/README.md)。

### 精選方案（UI 顯示）

- 全天統一：`全天_無假日費率`
- 兩段週末：`兩段_六日費率`
- 四段國定：`四段_國定假費率`

使用者自訂方案（`config/user_defined_plans.json`）亦會完整顯示。

### 進階 UI 設定

於 `config/system_config.json` → `ui_settings` 可調整：
- `max_user_plans_display`：顯示的用戶自訂方案最大數量（預設 5）
- `show_only_featured_user_plans`：僅顯示被標記為 featured 的用戶方案（預設 false）

---

## API 端點

| 端點 | 方法 | 用途 |
|------|------|------|
| `/api/calculate` | POST | 停車費計算 |
| `/api/plans` | GET | 獲取費率方案列表 |
| `/api/rate_plans/save` | POST | 儲存自訂方案 |
| `/api/system/config` | GET/POST | 系統配置管理 |
| `/api/mdp/templates` | GET | 多維度範本列表 |
| `/api/mdp/preview` | POST | 範本試算預覽 |

完整 API 規格：[api/contracts/openapi.yaml](api/contracts/openapi.yaml)

---

## 測試

```powershell
# 執行所有測試
uv run pytest

# 驗證設定檔格式
uv run python scripts/validate_configs.py
```

---

## 開發

```powershell
# 安裝所有依賴（含開發工具）
uv sync --group dev

# 執行測試並產出覆蓋率
uv run pytest --cov=src
```

---

## 許可證

本項目採用 MIT 許可證。
