import json
import os
from typing import Dict, Any, List

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USER_PLANS_PATH = os.path.join(ROOT, "config", "user_defined_plans.json")
INVENTORY_PATH = os.path.join(ROOT, "log", "plan_inventory.json")


FEATURED_IDS = {"跨日測試方案", "萬華西園"}


def detect_progressive(rate_matrix: Dict[str, Any]) -> bool:
    for cfg in rate_matrix.values():
        if isinstance(cfg, dict) and cfg.get("progressive_enabled"):
            return True
    return False


def detect_segment_cap(rate_matrix: Dict[str, Any]) -> bool:
    for cfg in rate_matrix.values():
        if isinstance(cfg, dict) and cfg.get("segment_cap_enabled"):
            return True
    return False


def get_global_grace(plan: Dict[str, Any]) -> int:
    # 預設優先順序：頂層 > global_caps
    if isinstance(plan.get("global_grace_time"), int):
        return plan.get("global_grace_time")
    caps = plan.get("global_caps", {})
    if isinstance(caps.get("global_grace_time"), int):
        return caps.get("global_grace_time")
    return 0


def build_tags(plan_id: str, plan: Dict[str, Any]) -> List[str]:
    tags: List[str] = []

    # 時段、假日
    segment_type = plan.get("segment_type") or plan.get("segmentType") or ""
    holiday_type = plan.get("holiday_type") or plan.get("holidayType") or ""
    if segment_type:
        tags.append(segment_type)
    if holiday_type:
        tags.append(holiday_type)

    # 價格類型
    rate_matrix = plan.get("rate_matrix", {})
    tags.append("累進" if detect_progressive(rate_matrix) else "單一")

    # 上限類型
    caps = plan.get("global_caps", {})
    tags.append("日上限" if caps.get("daily_cap_enabled") else "無日上限")
    tags.append("分段上限" if detect_segment_cap(rate_matrix) else "無分段上限")

    # 寬裕時間
    grace = get_global_grace(plan)
    tags.append(f"全局寬裕:{grace}分" if grace and grace > 0 else "無全局寬裕")

    # 推薦
    if plan_id in FEATURED_IDS:
        tags.append("推薦")

    return tags


def organize():
    if not os.path.exists(USER_PLANS_PATH):
        print("user_defined_plans.json 不存在，跳過")
        return False

    with open(USER_PLANS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    plans = data.get("plans", {})
    inventory: List[Dict[str, Any]] = []

    for plan_id, plan in plans.items():
        tags = build_tags(plan_id, plan)
        plan["tags"] = sorted(list(set(tags)))
        if plan_id in FEATURED_IDS:
            plan["featured"] = True

        inventory.append(
            {
                "plan_id": plan_id,
                "name": plan.get("name", plan_id),
                "segment_type": plan.get("segment_type"),
                "holiday_type": plan.get("holiday_type"),
                "active": plan.get("active", True),
                "tags": plan.get("tags", []),
                "has_daily_cap": bool(plan.get("global_caps", {}).get("daily_cap_enabled")),
                "has_segment_cap": detect_segment_cap(plan.get("rate_matrix", {})),
                "progressive": detect_progressive(plan.get("rate_matrix", {})),
                "global_grace_time": get_global_grace(plan),
            }
        )

    os.makedirs(os.path.join(ROOT, "log"), exist_ok=True)

    # 回寫 plans（加上 tags/featured）
    with open(USER_PLANS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 輸出盤點檔
    with open(INVENTORY_PATH, "w", encoding="utf-8") as f:
        json.dump({"plans": inventory}, f, ensure_ascii=False, indent=2)

    # 更新 docs/plan_catalog.md 區塊（簡單覆蓋，避免注入）
    try:
        docs_dir = os.path.join(ROOT, "docs")
        os.makedirs(docs_dir, exist_ok=True)
        catalog_md = os.path.join(docs_dir, "plan_catalog.md")
        with open(catalog_md, "w", encoding="utf-8") as f:
            f.write("# 方案屬性清單（自動產生）\n\n")
            f.write("本清單依據 `log/plan_inventory.json` 產生，列出目前用戶自訂方案的關鍵屬性，方便檢視與比對。\n\n")
            f.write(
                "> 若要更新本表，請執行：\n>\n> ```powershell\n> python scripts/organize_plans.py\n> ```\n\n"
            )
            f.write("## 方案列表\n\n")
            f.write("```json\n")
            json.dump({"plans": inventory}, f, ensure_ascii=False, indent=2)
            f.write("\n``""\n")
    except Exception as e:
        print(f"更新 docs/plan_catalog.md 失敗: {e}")

    print(f"已更新: {USER_PLANS_PATH}")
    print(f"已產生: {INVENTORY_PATH}")
    return True


if __name__ == "__main__":
    organize()


