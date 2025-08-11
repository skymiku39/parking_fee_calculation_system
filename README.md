# 智能停車費率計算系統 v2.0

🚗 **現代化的停車場收費管理解決方案**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.0+-green.svg)](https://flask.palletsprojects.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen.svg)](CHANGELOG.md)

---

## 🎯 項目概覽

智能停車費率計算系統是一個功能完整的停車收費管理平台，採用**收費週期邏輯**和**多維度標籤系統**，為停車場提供精確、靈活的收費解決方案。

### ⭐ 核心特色

- 🎯 **收費週期邏輯**：符合真實停車場收費標準，按收費週期計算而非時段邊界切割
- 🏷️ **多維度標籤**：時段 × 假日 × 費率的靈活組合，支援15種標準配置
- 🌐 **Web管理界面**：直觀的用戶操作介面，響應式設計
- 🔧 **配置驅動**：純JSON配置文件管理，無需修改代碼
- 📊 **結算分析**：完整的收費統計和分析功能
- 🧪 **完整測試**：85%測試覆蓋率，品質保證

---

## 🚀 快速開始

### 環境要求

- **Python版本**：3.8 或更高版本
- **操作系統**：Windows / Linux / macOS
- **硬體需求**：2GB RAM，1GB 存儲空間
- **瀏覽器**：Chrome, Firefox, Safari, Edge（現代瀏覽器）

### 安裝和啟動（唯一方式）

請使用 PowerShell 啟動腳本，這是唯一且推薦的啟動方式：

```powershell
# 1. 進入專案根目錄
cd parking_fee_calculation_system

# 2. 一鍵啟動（自動建立虛擬環境並安裝依賴）
./scripts/start.ps1

# 若已安裝依賴且只想啟動（略過安裝）
./scripts/start.ps1 -NoInstall
```

啟動後，開啟瀏覽器：`http://127.0.0.1:5000`

### 首次使用

1. **計算停車費**：在主頁面輸入進場和出場時間
2. **選擇費率方案**：選擇適合的費率方案（預設有多種選項）
   - UI 僅顯示三個精選內建方案與你的自訂方案；若自訂方案過多，UI 會依系統設定限制顯示數量。
3. **查看結果**：系統會顯示詳細的計費明細和總費用
4. **自訂配置**：可在設定頁面自訂費率配置

---

## 🏗️ 系統架構

### 核心組件

```
停車費計算系統
├── app.py                 # Flask Web 應用主程式（仍可直接執行）
├── scripts/
│   └── start.ps1          # 唯一啟動腳本（PowerShell）
├── src/                   # 核心計算引擎
│   ├── engines/                      # 新的標準匯入路徑
│   │   ├── parking_calculator.py
│   │   ├── multidimensional_calculator.py
│   │   └── enhanced_multidimensional_calculator.py
│   ├── managers/
│   │   └── rate_plan_manager.py
│   ├── parking_calculator.py          # 舊路徑（保留向後相容）
│   ├── multidimensional_calculator.py # 舊路徑（保留向後相容）
│   └── rate_plan_manager.py           # 舊路徑（保留向後相容）
├── templates/             # Web 界面模板
├── config/               # 配置文件
├── tests/                # 單元測試
├── examples/             # 範例腳本（非單元測試）
└── log/                  # 系統日誌和報告
```

### 技術棧

- **後端**：Python Flask + JSON配置管理
- **前端**：HTML5 + CSS3 + JavaScript + Bootstrap 5
- **測試**：unittest + pytest
- **文檔**：Markdown + 技術報告

---

## 📋 主要功能

### 1. 停車費計算

- **精確計算**：按收費週期邏輯計算，避免時段邊界錯誤
- **跨日處理**：正確處理跨日停車計算
- **多種費率**：支援固定費率、累進費率、全域上限等
- **假日識別**：自動區分平日和假日費率

### 2. 多維度配置

- **時段設定**：全天、二段、三段、任意段多種選擇
- **假日類型**：無假日、六日假日、國定假日配置
- **費率矩陣**：視覺化的費率組合編輯器
- **即时預覽**：配置時即時預覽計費效果

### 3. 方案管理

- **預設方案**：提供多種常用的費率方案
- **自訂方案**：用戶可創建和儲存自己的費率方案
- **方案匯入匯出**：支援方案的備份和分享
- **版本管理**：方案修改歷史記錄

### 4. 系統管理

- **統一配置**：系統級參數集中管理
- **日曆管理**：假日日期自訂配置
- **結算中心**：收費統計和分析報表
- **API服務**：完整的RESTful API接口

---

## 📊 使用場景

### 適用停車場類型

- **商業大樓**：多時段差異化收費
- **住宅社區**：住戶優惠、訪客收費
- **商場購物中心**：消費折扣、時段定價
- **醫院機場**：長時間停車上限控制
- **路邊停車**：分時段差異化收費
- **活動場所**：臨時活動特殊定價

### 收費模式支援

- **按時計費**：15分鐘、30分鐘、60分鐘等
- **累進費率**：超時遞增費率
- **全日上限**：每日最高收費金額
- **會員優惠**：VIP用戶差異化定價
- **假日加價**：節假日特殊費率
- **免費時間**：停車優惠時間設定

---

## 🔧 配置說明

### 主要配置文件

| 文件 | 用途 | 說明 |
|------|------|------|
| `config/system_config.json` | 系統設定 | 全域參數配置 |
| `config/user_defined_plans.json` | 用戶方案 | 自訂費率方案 |
| `config/multidimensional_rate_plans.json` | 多維度配置 | 標準模板與精選方案 |

### 精選方案版本（UI 僅顯示以下內建選項）

- 全天統一：`全天_無假日費率`
- 兩段週末：`兩段_六日費率`
- 四段國定：`四段_國定假費率`

說明：
- 使用者自訂（`config/user_defined_plans.json`）的方案仍會完整顯示。
- 其餘內建模板保留於配置中以供擴充，但不於 UI 列出，避免選項過多造成困惑。

#### 進階設定
- 於 `config/system_config.json` → `ui_settings` 可調整：
  - `max_user_plans_display`: 顯示的用戶自訂方案最大數量（預設 5）
  - `show_only_featured_user_plans`: 僅顯示被標記為 featured 的用戶方案（預設 false）

### 費率配置範例

```json
{
  "plan_name": "標準商業大樓",
  "description": "平日假日差異化收費",
  "rate_matrix": {
    "日間_平日": {
      "unit_time": 30,
      "simple_rate": 20,
      "grace_time": 15
    },
    "日間_假日": {
      "unit_time": 30,
      "simple_rate": 30,
      "grace_time": 15
    }
  }
}
```

---

## 🧪 測試驗證

### 測試覆蓋範圍

- **核心計算邏輯**：收費週期、時段判斷、費用計算
- **多維度系統**：標籤組合、矩陣配置、方案管理
- **Web界面功能**：頁面載入、API調用、用戶交互
- **邊界情況**：跨日計算、異常處理、資料驗證

### 運行測試

```bash
# 運行所有測試
python -m pytest tests/ -v

# 運行特定測試
python tests/test_calculator.py
python examples/test_billing_cycle_fix.py
```

---

## 📖 API文檔

### 主要API端點

| 端點 | 方法 | 用途 |
|------|------|------|
| `/api/calculate` | POST | 停車費計算 |
| `/api/plans` | GET | 獲取費率方案列表 |
| `/api/rate_plans/save` | POST | 儲存自訂方案 |
| `/api/system/config` | GET/POST | 系統配置管理 |

### 計算API使用範例

```javascript
// 計算停車費
fetch('/api/calculate', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    entry_time: '2024-06-20 21:52',
    exit_time: '2024-06-21 08:30',
    rate_plan: 'test_billing_cycle'
  })
}).then(response => response.json())
  .then(data => console.log(data));
```

---

## 🎯 重要修正說明

### 收費週期邏輯修正

本系統解決了傳統停車收費系統的重大邏輯錯誤：

**❌ 舊邏輯問題:**
```
停車 21:52-22:22，時段邊界 22:00
錯誤：21:52-22:00用日間費率，22:00-22:22用夜間費率
```

**✅ 新邏輯正確:**
```
停車 21:52-22:22，收費週期 30分鐘
正確：21:52-22:22整個週期使用日間費率
```

**核心原理：**
- 按收費週期（如30分鐘）劃分時間
- 每個週期開始時確定適用費率
- 週期跨時段邊界時，使用週期開始時的費率
- 確保收費週期的完整性和邏輯一致性

---

## 📝 更新日誌

### v2.0 (2024-12)
- ✅ **重大修正**：實現正確的收費週期邏輯
- ✅ **功能增強**：完善假日費率功能
- ✅ **界面優化**：修正多個前端顯示問題
- ✅ **測試完善**：新增收費週期專項測試
- ✅ **文檔更新**：完整的技術文檔體系

### v1.0 (2024-06)
- ✅ 基礎停車費計算功能
- ✅ 多維度標籤系統
- ✅ Web管理界面
- ✅ 用戶自訂方案

---

## 🤝 技術支援

### 問題回報

如果您遇到問題，請：

1. **檢查日誌**：查看 `log/` 目錄中的錯誤日誌
2. **查看文檔**：參考 `log/` 目錄中的技術報告
3. **運行測試**：執行測試套件檢查系統狀態
4. **提交Issue**：在GitHub上提交詳細的問題報告

### 常見問題

**Q: 系統啟動失敗？**
A: 檢查Python版本（需3.8+）和依賴安裝（`pip install -r requirements.txt`）

**Q: 計算結果不正確？**
A: 檢查費率方案配置，確認時段設定和費率參數

**Q: 無法儲存自訂方案？**
A: 檢查 `config/` 目錄寫入權限和檔案格式

### 開發指南

1. **代碼規範**：遵循PEP 8 Python代碼規範
2. **測試要求**：新功能需添加對應測試用例
3. **文檔更新**：重要修改需更新相關文檔
4. **向後兼容**：確保配置文件向後兼容

---

## 📄 許可證

本項目採用 MIT 許可證 - 詳見 [LICENSE](LICENSE) 文件。

---

## 👥 貢獻者

- **主要開發**：AI 助手
- **系統設計**：智能停車系統開發團隊
- **測試驗證**：品質保證團隊
- **文檔編寫**：技術文檔團隊

---

## 🔗 相關資源

- **項目主頁**：[GitHub Repository](https://github.com/your-org/parking_fee_calculation_system)
- **技術文檔**：[log/](log/) 目錄中的詳細報告
- **API文檔**：[API Documentation](docs/api.md)
- **用戶手冊**：[User Guide](docs/user_guide.md)

---

**最後更新**：2024年12月  
**當前版本**：v2.0  
**系統狀態**：🟢 生產就緒

*智能停車費率計算系統 - 讓停車收費更精確、更靈活、更智能！* 