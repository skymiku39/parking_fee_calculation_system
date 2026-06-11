# Changelog

## [3.2.0] - 2026-06-10

### Added

- 計費明細顯示牌價、封頂原因（區段上限／日上限）與計費週期說明
- 欄位懸停提示（`field-hints.js`）套用於設計器與方案管理
- MDP 設計器：依日期類別設定日上限並正確讀寫 `unified_plan`
- 整合驗證腳本 `tools/verify_integration_scenarios.py`
- `docs/terminology.md` 日上限與區段上限設計專節

### Changed

- 試算明細 UI：牌價合計 vs 封頂後實收、逐段 `billing_explanation`
- 修正 MDP 多時段完整假日日上限，避免傍晚時段 0 元

### Fixed

- MDP `unified_plan` 格式範本無法計費（載入邏輯支援設計器輸出）
- MDP 設計器刪除按鈕 `confirmDelete` 未綁定

## [3.1.0] - 2026-06-09

### Added

- UPE 完整實作 `cap_priority`（segment / daily / lower / higher）
- MDP 日上限依日期類別（`daily_caps_by_category`）獨立套用
- 方案設計器：同時有日上限與區段上限時可設定封頂順序
- 計費稽核工具：`tools/audit_billing.py`、`tools/audit_api.py`

### Changed

- 移除幽靈規格欄位 `unit_pivot`、`segment_caps_enabled`；驗證時直接拒絕
- 更新 `docs/terminology.md` 與 `config/user_defined_plans.json` 對齊引擎行為
- MDP 計費鍵區分 `國定假日` / `節慶日`，摘要 `original_amount` 語意修正

### Fixed

- MDP 多時段方案週末／節慶日日上限誤用平日值的問題
- 時段半開區間 `[start, end)` 邊界歸屬

## [3.0.0] - 2026-06-09

### Added

- 打包發佈流程：`tools/build_exe.ps1`、`tools/release.ps1`
- 外部資料目錄 `data/`（開發環境仍用 `config/`）
- `PARKING_DATA_DIR` 環境變數支援自訂資料路徑
- `GET /api/system/version` 查詢版本與資料目錄
- `src/core/paths.py`、`src/core/version.py` 集中管理路徑與版本

### Changed

- PyInstaller 僅內建 UI 資源；方案 JSON 放在 exe 旁 `data/` 供外部查看編輯
- 首次啟動時從內建範本複製缺少的 JSON（不覆蓋既有檔案）
