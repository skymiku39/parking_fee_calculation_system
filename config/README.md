# 設定檔說明

本目錄存放系統執行期的 JSON 設定檔。

## 檔案一覽

| 檔案 | 用途 | 是否接入 UI/API |
|------|------|----------------|
| `system_config.json` | 全域系統參數（UI 設定、假日 API 等） | 是（系統設定頁） |
| `system_calendar.json` | 自訂假日日曆（國定假、節慶、補班日） | 是（日曆管理頁 + **計費引擎讀取**） |
| `multidimensional_rate_plans.json` | 多維度費率範本（3 個精選 MDP 方案） | 是 |
| `user_defined_plans.json` | 使用者自訂收費週期方案 | 是（完整 CRUD） |

> Legacy 設定（`rate_plans.json`、`universal_rate_plans.json`、`system_templates.json`）已移至 [`archive/v2_legacy/config/`](../archive/v2_legacy/config/)。

## system_config.json — UI 顯示控制

```json
"ui_settings": {
  "max_user_plans_display": 5,
  "show_only_featured_user_plans": false
}
```

- `max_user_plans_display`：首頁「價格試算」下拉選單中，自訂方案最多顯示幾筆（精選優先排序）
- `show_only_featured_user_plans`：設為 `true` 時只顯示 `featured: true` 或 tags 含 `推薦` 的方案

可透過 `/system_settings` 頁面或 `POST /api/system/config` 修改。

## user_defined_plans.json — 自訂方案格式

每個方案需包含：

- `name`、`segment_type`、`holiday_type`、`segments`（至少 1 段）
- `rate_matrix`：鍵名為 `{區段名}_{日期類別}`，例如 `日間_統一`、`日間_平日`
- `global_caps`：日上限（`daily_cap_enabled` / `daily_cap_amount`）、全域寬限（`global_grace_time`）

管理方式：

- **UI**：方案管理 → 編輯 / 自訂方案設計器
- **API**：`GET/POST/DELETE /api/rate_plans/*`
- **驗證**：`uv run python tools/validate_configs.py`

## system_calendar.json — 假日日曆

計費引擎會讀取此檔判斷日期類別：

| 欄位 | 影響 |
|------|------|
| `custom_workdays` | 強制視為平日（補班日） |
| `festival_holidays` | 節慶日（自訂方案 `完整假日`）/ MDP 客製假日 |
| `national_holidays` | 國定假日（自訂方案 `完整假日` 視為節慶日；MDP 用國定假費率） |
| `custom_holidays` | 一般假日 |
| `weekend_as_holiday` | 週六日是否視為假日 |

建議流程：日曆管理頁 →「同步官方假日」→ 手動新增節慶日 → 儲存。儲存後計費會立即套用。

## multidimensional_rate_plans.json — MDP 模板

由 MDP 方案設計器（`/rate_plan_designer`）管理，API 前綴為 `/api/mdp/*`。

與自訂方案一致：皆使用 `segment_type` + `holiday_type`（`無假日` / `平日假日` / `完整假日`）。詳見 [docs/terminology.md](../docs/terminology.md)。

`dimension_configs.完整假日.custom_holidays` 為 MDP 內建客製假日清單（與 `system_calendar.json` 合併判定）；計費時國定假走 `national_holiday_plan`（鍵 `國定假日`），客製假走 `custom_holiday_plan`（鍵 `節慶日`），日上限亦各自獨立。

**日上限設計**：`daily_cap_amount` 應 ≥ 同一曆日內各時段 `cap_amount` 之和（含跨午夜夜間在該曆日計費的部分），否則較晚時段（常為傍晚）會在日上限用盡後顯示 0 元。

## 計費驗證工具

```bash
uv run pytest
uv run python tools/validate_configs.py
uv run python tools/validate_time_boundaries.py
uv run python tools/audit_billing.py
uv run python tools/audit_api.py
```
