# 停車費系統術語對照表

本文件為 **canonical 術語** 的單一真相來源。實作定義見 [`src/domain/terminology.py`](../src/domain/terminology.py)。

## 假日類型 `holiday_type`

| Canonical | 已廢止 alias | 語意 |
|-----------|--------------|------|
| `無假日` | `無假日費率` | 不分平假日，rate_matrix 用 `統一` |
| `平日假日` | `六日費率` | 平日 vs 假日分價 |
| `完整假日` | `國定假費率` | 平日 / 假日 / 節慶日 三價 |

## 時段類型 `segment_type`

| Canonical | 已廢止 alias | 備註 |
|-----------|--------------|------|
| `全天` | — | |
| `二段` | `兩段` | |
| `三段` | — | |
| `多時段` | `四段`、`自訂` | MDP 四段/自訂併入多時段 |
| `任意段` | — | 自訂方案專用 |

欄位名統一使用 `segment_type`（廢止 `time_segment_type`）。

## 日期類別 `date_category`

rate_matrix 鍵名格式：`{區段名}_{date_category}`

| Canonical | 已廢止 alias |
|-----------|--------------|
| `統一` | — |
| `平日` | — |
| `假日` | `週末` |
| `節慶日` | `國定假日`、`客製假日` |

## 欄位名

| 概念 | Canonical | 已廢止 |
|------|-----------|--------|
| 時段清單 | `segments[]` | `time_slots` |
| 計費單位 | `unit_time` | `unit_minutes` |
| 單價 | `simple_rate` | `default_unit_price` |
| 時段寬限 | `grace_time` | `grace_minutes` + `grace_enabled` |
| 全域寬限 | `global_grace_time` | — |
| 區段上限 | `segment_cap_enabled/amount` | `cap_enabled/amount` |
| 日上限 | `daily_cap_enabled/amount` | — |
| 封頂順序 | `global_caps.cap_priority` | — |
| 方案 ID（API） | `plan_id` | `rate_plan_id` |
| MDP 範本 ID | `template_id` | 格式 `{segment_type}_{holiday_type}` |
| 總金額 | `total_amount` | `final_charge` |
| 明細 | `session_details` | `sessions` |

## 中文 UI 用語

| 概念 | 統一用語 |
|------|----------|
| 日上限 | 日上限 |
| 區段上限 | 區段上限 |
| 緩衝 | 寬限時間 |
| 週期 | 收費週期 |
| 產品名 | 智能停車費率計算系統 |
| 精選 | `featured: true` 或 tag `推薦` |

## MDP 範本 ID 遷移

| 舊 ID | 新 ID |
|-------|-------|
| `全天_無假日費率` | `全天_無假日` |
| `兩段_六日費率` | `二段_平日假日` |
| `四段_國定假費率` | `多時段_完整假日` |

API 短期仍接受舊 ID（透過 `resolve_template_id`）。

## 引擎差異說明

- **自訂方案**：使用 `UnifiedPricingEngine`，schema 以本文件為準。
- **MDP 多維度**：內部以 `weekday_plan` / `weekend_plan` / `national_holiday_plan` / `custom_holiday_plan` 組裝 `rate_matrix`；計費時依行事曆與 `dimension_configs.完整假日.custom_holidays` 選擇對應鍵。對外摘要仍顯示 canonical `date_category`（國定假與客製假皆可能顯示為 `節慶日`）。
- **Legacy**（`rate_plans.json`）：僅工具腳本使用，輸出欄位逐步對齊 `total_amount` / `session_details`。

## 計費引擎行為（UPE）

| 項目 | 規則 |
|------|------|
| 時段歸屬 | 半開區間 `[start, end)`：邊界時刻歸下一時段（例：12:00 歸下午） |
| 收費週期 | 以進場時間對齊 `unit_time` 週期起點 |
| 全域寬限 | 整次停車僅第一個計費週期扣一次 `global_grace_time` |
| 時段寬限 | 各 `rate_matrix` 格之 `grace_time`，無全域寬限時逐週期套用 |
| 封頂順序 | `global_caps.cap_priority`：`segment`（先區段後日）、`daily`（先日後區段）、`lower`／`higher`（兩種順序取較低／較高當週期費） |
| 日上限 | 按曆日累計；MDP 依計費鍵（平日/假日/國定假日/節慶日）取各子方案 `daily_cap_amount` |
| 未覆蓋時段 | 無對應 segment 的分鐘不計費（缺口視為免費） |
| rate_matrix 容錯 | 鍵名不符時 fallback：`{區段}_{類別}` → 統一 → 平日 → 假日 → 節慶日 → 國定假日 |

### 日上限與區段上限設計

兩種封頂解決不同層級的收費控制，可同時啟用。

| 類型 | 設定位置 | 累計範圍 | 用途 |
|------|----------|----------|------|
| **區段上限** | `rate_matrix` 各格 `segment_cap_enabled` / `segment_cap_amount`；MDP 為 `time_slots[].cap_enabled` / `cap_amount` | 單一**時段**在同一**曆日**內 | 限制上午、下午等個別時段當日最高收費 |
| **日上限** | 自訂方案 `global_caps.daily_cap_amount`；MDP 各子方案 `daily_cap_amount` | 當日**所有時段合計**（含跨午夜後歸屬當日的夜間分鐘） | 限制單日總停車費，跨日停車每日 00:00 重新累計 |

**計費順序（每個收費週期）**

1. 依 `unit_time` 與費率計算週期牌價（扣除寬限後）。
2. 若啟用區段上限，累計該時段當日費用不得超過 `segment_cap_amount`。
3. 若啟用日上限，累計當日總費用不得超過 `daily_cap_amount`。
4. 同時啟用兩者時，順序由 `global_caps.cap_priority` 決定（`segment` / `daily` / `lower` / `higher`）。

**設計建議**

- 日上限應 **≥ 同曆日各時段區段上限之和**，否則較晚時段（常為傍晚）可能在日上限用盡後顯示 **0 元**（牌價仍顯示，實收為封頂後結果）。
- MDP 範本應為每個日期類別子方案（`weekday_plan`、`weekend_plan` 等）分別設定日上限，與該類別矩陣費率一致。
- 試算明細中費用為 0 且非免費時段時，UI 會標示「（已達封頂）」。

### MDP 計費鍵與子方案

| 計費鍵（rate_matrix 後綴） | 子方案 | 典型來源 |
|---------------------------|--------|----------|
| `平日` | `weekday_plan` | 週一至週五 |
| `假日` | `weekend_plan` | 週六日 |
| `國定假日` | `national_holiday_plan` | `system_calendar.national_holidays` 等 |
| `節慶日` | `custom_holiday_plan` | `festival_holidays` 或 MDP `custom_holidays` |

### 已移除欄位

不再接受：`unit_pivot`、`global_caps.segment_caps_enabled`。區段封頂僅由 `rate_matrix` 各格之 `segment_cap_enabled` 控制。
