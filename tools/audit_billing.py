"""一次性計費稽核：掃描所有方案不變量與 MDP 日上限對照。"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.system import SmartParkingSystem
from src.domain.multidimensional_calculator import MultidimensionalParkingCalculator


def main() -> int:
    config_dir = ROOT / "config"
    system = SmartParkingSystem(base_path=config_dir)
    mdp = MultidimensionalParkingCalculator(
        str(config_dir / "multidimensional_rate_plans.json")
    )
    issues: list[tuple[str, str]] = []

    with open(config_dir / "user_defined_plans.json", encoding="utf-8") as f:
        plans = json.load(f).get("plans", {})

    print("=== 自訂方案（active）===")
    for pid, plan in plans.items():
        if not plan.get("active", True):
            print(f"  SKIP inactive: {pid}")
            continue
        ent = datetime(2025, 6, 20, 8, 0)
        ext = datetime(2025, 6, 20, 20, 0)
        r = system.calculate_parking_fee(ent, ext, pid)
        if not r.get("success"):
            issues.append((pid, str(r.get("error"))))
            print(f"  FAIL {pid}: {r.get('error')}")
            continue
        total = int(r["total_amount"])
        orig = int(r.get("original_amount", total))
        dsum = sum(int(s.get("amount", 0) or 0) for s in r.get("session_details", []))
        cap = r.get("cap_applied")
        ok = dsum == total and orig >= total and cap == (orig > total)
        if not ok:
            issues.append((pid, f"dsum={dsum} total={total} orig={orig} cap={cap}"))
        print(
            f"  [{'OK' if ok else 'WARN'}] {pid}: "
            f"total={total} orig={orig} cap={cap} segs={len(r.get('session_details', []))}"
        )

    print("\n=== MDP 範本 ===")
    with open(config_dir / "multidimensional_rate_plans.json", encoding="utf-8") as f:
        templates = {t["template_id"]: t for t in json.load(f).get("templates", [])}

    mdp_cases = {
        "全天_無假日": [
            ("同日", datetime(2024, 12, 19, 8, 0), datetime(2024, 12, 19, 20, 0), 200),
            ("跨兩日", datetime(2024, 12, 19, 0, 0), datetime(2024, 12, 21, 0, 0), None),
        ],
        "二段_平日假日": [
            ("兩個平日", datetime(2024, 12, 18, 0, 0), datetime(2024, 12, 20, 0, 0), None),
            ("週末跨夜", datetime(2024, 12, 21, 20, 0), datetime(2024, 12, 22, 2, 0), None),
        ],
        "多時段_完整假日": [
            ("平日全日", datetime(2024, 12, 19, 0, 0), datetime(2024, 12, 20, 0, 0), 300),
            ("週六全日", datetime(2024, 12, 21, 0, 0), datetime(2024, 12, 22, 0, 0), 360),
            ("節慴全日", datetime(2024, 12, 25, 0, 0), datetime(2024, 12, 26, 0, 0), 540),
            ("週六 08-22", datetime(2024, 12, 21, 8, 0), datetime(2024, 12, 21, 22, 0), 360),
            ("中午邊界", datetime(2024, 12, 19, 11, 30), datetime(2024, 12, 19, 12, 30), None),
        ],
    }

    for tid, runs in mdp_cases.items():
        tpl = templates.get(tid, {})
        print(f"-- {tid} ({tpl.get('holiday_type', '')}) --")
        for label, ent, ext, cap_cfg in runs:
            r = mdp.calculate_parking_fee(ent, ext, tid)
            dsum = sum(s["fee"] for s in r.session_details)
            inv_ok = dsum == r.total_amount and r.original_amount >= r.total_amount
            cap_ok = r.total_amount <= cap_cfg if cap_cfg else True
            ok = inv_ok and cap_ok
            if not ok:
                issues.append((tid, label))
            cap_s = f" cap_cfg={cap_cfg}" if cap_cfg else ""
            print(
                f"  [{'OK' if ok else 'FAIL'}] {label}: "
                f"total={r.total_amount} orig={r.original_amount}{cap_s}"
            )

    print("\n=== 摘要 ===")
    if issues:
        print(f"發現 {len(issues)} 項問題:")
        for item in issues:
            print(f"  - {item[0]}: {item[1]}")
        return 1
    print("全部通過")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
