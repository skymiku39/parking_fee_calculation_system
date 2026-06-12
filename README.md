# 智能停車費率計算系統 v3.2

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
cd parking_fee_calculation_system

# 一鍵啟動（自動安裝依賴並啟動伺服器）
./tools/start.ps1

# 若已安裝依賴，略過安裝直接啟動
./tools/start.ps1 -NoInstall

# 只安裝依賴，不啟動（CI / 自動化可用）
./tools/start.ps1 -NoRun
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
│   ├── application/        # 應用服務（計費策略、自訂方案 UPE 橋接）
│   ├── core/               # 系統啟動、事件匯流排、Repository、工具
│   │   ├── context.py      # 全域 SmartParkingSystem 單例
│   │   ├── events.py       # Publish/Subscribe EventBus
│   │   ├── ports.py        # 抽象介面（DIP / ISP）
│   │   ├── repositories/   # JSON 設定持久化（SRP）
│   │   ├── subscribers/    # 事件訂閱者（日曆/MDP 重載）
│   │   ├── system.py       # Composition root
│   │   └── validation.py
│   ├── domain/             # 領域邏輯
│   │   ├── multidimensional_calculator.py
│   │   ├── terminology.py
│   │   └── pricing/        # UnifiedPricingEngine
│   └── web/                # Flask 藍圖 + 前端資源
│       ├── calc.py
│       ├── calendar.py
│       ├── mdp.py
│       ├── user_plans.py   # 自訂方案 CRUD API
│       ├── system.py
│       ├── templates/      # Jinja HTML
│       └── static/         # CSS / JS
│
├── config/                 # 執行期 JSON 設定檔（見 config/README.md）
├── archive/                # 已封存 legacy 程式與設定
├── docs/                   # 術語與設計文件（terminology.md）
├── tests/                  # pytest 自動化測試
└── tools/                  # 腳本、文件、API 規格
    ├── start.ps1
    ├── build_exe.ps1
    ├── launcher.py
    ├── openapi.yaml
    └── ...
```

---

## 架構設計（SOLID + Pub/Sub）

本專案採用分層架構，並以 in-process **Publish/Subscribe** 解耦「設定變更」與「執行時重載」：

| 原則 | 實作 |
|------|------|
| **S** 單一職責 | `repositories/` 只管 JSON 讀寫；`UserDefinedBillingService` 只管自訂方案計費 |
| **O** 開放封閉 | `fee_strategies.py` 以策略註冊計費引擎，新增方案類型無需改 `calculate_parking_fee` |
| **L** 里氏替換 | `FeeCalculationStrategy` 協定；各策略可互換 |
| **I** 介面隔離 | `ports.py` 定義 `ConfigRepository`、`DateCategoryResolver` 等窄介面 |
| **D** 依賴反轉 | Web 藍圖透過 `SmartParkingSystem` 公開 API 存取資料，不再直接寫 JSON 檔 |

**事件流（設定變更）**

```
calendar/mdp/system 儲存
  → SmartParkingSystem.publish(CalendarPersisted | MdpConfigSaved | …)
  → subscribers/runtime.py 訂閱
  → refresh_runtime_state() 重載日曆與 MDP 計算器
```

計費成功時另發布 `ParkingFeeCalculated`；`subscribers/audit.py` 訂閱並寫入應用日誌。

**共用領域邏輯**

- `domain/segment_utils.py`：時段邊界判斷（UPE 與自訂方案日期解析共用）
- `MultidimensionalParkingCalculator.calculate_with_inline_template()`：MDP 試算不修改已載入範本登錄表

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

- **MDP 內建模板**：3 個多維度精選方案（全天 / 兩段週末 / 四段國定）
- **自訂方案**：10 個範例方案，可透過 UI 新增、編輯、刪除、匯出
- **雙設計器**：MDP 模板用「MDP 設計器」，自訂方案用「自訂方案設計器」

---

## 使用教學

### 1. 價格試算（首頁 `/`）

1. 啟動服務後開啟 `http://127.0.0.1:5000`
2. 在「費率方案」下拉選單選擇方案（分為 **內建多維度模板** 與 **使用者自訂方案** 兩組）
3. 選擇自訂方案時，下方會顯示費率矩陣預覽
4. 設定進場 / 出場時間，按「計算停車費」
5. 結果會顯示總金額、計費引擎類型與分段明細

**試算範例（自訂方案）**

```json
POST /api/calculate
{
  "enter_time": "2025-06-20T10:00",
  "exit_time": "2025-06-20T12:00",
  "plan_id": "跨日測試方案"
}
```

回應中 `calculation_engine` 為 `user_defined_billing_cycle` 表示走自訂方案引擎。

### 2. 方案管理（`/plan_manager`）

| 類型 | 標記 | 編輯入口 | 匯出 |
|------|------|----------|------|
| MDP 模板 | `MDP` | `/rate_plan_designer` | `/api/mdp/export` |
| 自訂方案 | `自訂` | `/user_plan_designer` | `/api/rate_plans/export` |

- **新增 MDP 模板**：方案管理 →「新增 MDP 模板」
- **新增自訂方案**：方案管理 →「新增自訂方案」
- **刪除 / 下載**：各方案卡片上的操作按鈕

### 3. 自訂方案設計器（`/user_plan_designer`）

適用於 `config/user_defined_plans.json` 格式的收費週期方案。

1. 填寫方案 ID、名稱、時段類型、假日類型
2. 設定時間區段（可用「驗證」確認 24 小時覆蓋）
3. 在費率矩陣填入各時段 × 日期類別的單價
4. 按「儲存」寫入設定檔
5. 可用「試算」按鈕即時驗證

欄位與假日類型對照見 [docs/terminology.md](docs/terminology.md) 與 [config/README.md](config/README.md)。

### 4. MDP 設計器（`/rate_plan_designer`）

適用於 `config/multidimensional_rate_plans.json` 的多維度模板，假日類型為「無假日 / 平日假日 / 完整假日」（與自訂方案一致）。術語詳見 [docs/terminology.md](docs/terminology.md)。

### 5. 日曆與假日（`/calendar_manager`）

流程：同步官方假日 → 手動新增節慶日 / 補班日 → 儲存。日曆欄位與計費對應見 [config/README.md](config/README.md#system_calendarjson--假日日曆)。

### 6. 系統設定（`/system_settings`）

調整首頁自訂方案顯示（`ui_settings`）見 [config/README.md](config/README.md#system_configjson--ui-顯示控制)。

---

## 配置說明

主要配置文件位於 `config/` 目錄，詳見 [config/README.md](config/README.md)。  
方案分組與推薦清單見 [tools/plan_groups.md](tools/plan_groups.md)。

### 內建 MDP 模板（首頁固定顯示 3 個）

- 全天統一：`全天_無假日`
- 二段平日假日：`二段_平日假日`
- 多時段完整假日：`多時段_完整假日`（舊 ID `四段_國定假費率` 仍可透過 API alias 使用）

### 自訂方案（`user_defined_plans.json`）

首頁依 `ui_settings` 顯示（預設最多 5 個）；方案管理頁可查看全部。  
推薦入門方案：`跨日測試方案`（驗證跨日）、`萬華西園`（平日假日差價）。

---

## API 端點

| 端點 | 方法 | 用途 |
|------|------|------|
| `/api/calculate` | POST | 停車費計算（支援 MDP 模板與自訂方案） |
| `/api/plans` | GET | 獲取可用方案列表（含多維度模板與自訂方案） |
| `/api/rate_plans` | GET | 自訂方案列表 |
| `/api/rate_plans/load/<plan_id>` | GET | 讀取單一自訂方案 |
| `/api/rate_plans/save` | POST | 儲存自訂方案 |
| `/api/rate_plans/<plan_id>` | DELETE | 刪除自訂方案 |
| `/api/rate_plans/export` | GET | 匯出自訂方案設定檔 |
| `/api/system/config` | GET/POST | 系統配置管理 |
| `/api/system/version` | GET | 應用版本與資料目錄路徑 |
| `/api/mdp/templates` | GET | 多維度範本列表 |
| `/api/mdp/preview` | POST | 範本試算預覽 |

完整 API 規格：[tools/openapi.yaml](tools/openapi.yaml)

---

## 打包與發佈

版本號以 `pyproject.toml` 的 `version` 為唯一來源（目前 **3.2.0**）。

### 建置可執行檔

```powershell
./tools/build_exe.ps1
```

產出目錄：

```
dist/ParkingCalculator/
├── ParkingCalculator.exe    # 雙擊啟動（自動開瀏覽器）
├── data/                    # 外部可編輯的方案與設定（JSON）
│   ├── user_defined_plans.json
│   ├── multidimensional_rate_plans.json
│   ├── system_calendar.json
│   └── system_config.json
├── VERSION.txt
└── log/
```

- 開發環境仍使用 `config/`；打包後使用 exe 旁的 `data/`
- 可透過環境變數 `PARKING_DATA_DIR` 指定其他資料目錄
- 變更埠號：`$env:PORT=5001; .\ParkingCalculator.exe`

### 完整 Release（測試 + 打包 + ZIP + Git tag）

```powershell
./tools/release.ps1
```

會依序：執行 pytest → 打包 → 產生 `release/ParkingCalculator-{version}-win64.zip` → 建立 git tag `v{version}`。

發佈新版本時，先更新 `pyproject.toml` 的 `version`，再執行 `./tools/release.ps1`。

---

## 測試

```powershell
uv run pytest

# 驗證設定檔格式
uv run python tools/validate_configs.py
```

---

## 開發

```powershell
# 安裝所有依賴（含開發工具）
uv sync --group dev

# 執行測試並產出覆蓋率
uv run pytest --cov=src
```

歷史資料（舊 demo、報告等）已在 git tag `pre-reorganization` 中保留。

---

## 許可證

本項目採用 MIT 許可證。
