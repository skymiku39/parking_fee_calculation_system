# 封存資產說明

本目錄存放已退出執行期路徑的 legacy 程式、設定與工具，僅供歷史參考與遷移對照。

## 目錄結構

| 路徑 | 原位置 | 替代方案 |
|------|--------|----------|
| `v2_legacy/src/domain/parking_calculator.py` | `src/domain/parking_calculator.py` | `MultidimensionalParkingCalculator` + `UnifiedPricingEngine` |
| `v2_legacy/src/domain/rate_plan_manager.py` | `src/domain/rate_plan_manager.py` | `SmartParkingSystem` + `src/web/mdp.py` + `src/web/user_plans.py` |
| `v2_legacy/config/rate_plans.json` | `config/rate_plans.json` | `multidimensional_rate_plans.json` |
| `v2_legacy/config/universal_rate_plans.json` | `config/universal_rate_plans.json` | `multidimensional_rate_plans.json` |
| `v2_legacy/config/system_templates.json` | `config/system_templates.json` | `multidimensional_rate_plans.json` 的 `dimension_configs` |
| `tools/migrate_terminology.py` | `tools/migrate_terminology.py` | v3.1 術語遷移已完成，見 `docs/terminology.md` |
| `tools/validate_time_boundaries.py` | `tools/validate_time_boundaries.py` | 改以 `pytest` 與 `SmartParkingSystem` 驗證 |
| `tools/plan_catalog.md` | `tools/plan_catalog.md` | 改以 `tools/plan_groups.md` 手動維護 |

## 注意

- 請勿從 `archive/` import 至主程式；若需參考舊邏輯，請複製片段而非還原路徑。
- Git 歷史仍保留更早版本，本目錄為方便對照的靜態快照。
