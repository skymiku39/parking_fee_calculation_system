# Changelog

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
