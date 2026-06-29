"""跨日/跨時段邊界驗證（MDP + 自訂方案，不含 legacy 計算器）。"""
import os
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT)

from src.core.paths import resolve_data_dir
from src.core.system import SmartParkingSystem
from src.domain.multidimensional_calculator import MultidimensionalParkingCalculator


def assert_equal(name, a, b):
    ok = a == b
    print(f"[{'OK' if ok else 'NG'}] {name}: {a} vs {b}")
    return ok


def run_user_defined_billing_cycle_checks():
    print("\n=== 用戶自訂收費週期（跨日/跨時段）驗證 ===")
    sps = SmartParkingSystem(base_path=resolve_data_dir())

    plan_data = {
        "name": "驗證方案",
        "segment_type": "多時段",
        "holiday_type": "平日假日",
        "segments": [
            {"name": "日間", "start": "08:00", "end": "22:00"},
            {"name": "夜間", "start": "22:00", "end": "08:00"},
        ],
        "rate_matrix": {
            "日間_平日": {"unit_time": 30, "simple_rate": 30, "progressive_enabled": False, "grace_time": 0},
            "夜間_平日": {"unit_time": 60, "simple_rate": 10, "progressive_enabled": False, "grace_time": 0},
            "日間_假日": {"unit_time": 30, "simple_rate": 40, "progressive_enabled": False, "grace_time": 0},
            "夜間_假日": {"unit_time": 60, "simple_rate": 10, "progressive_enabled": False, "grace_time": 0},
        },
        "global_caps": {},
        "global_grace_time": 0,
    }

    cases = [
        (datetime(2025, 6, 20, 21, 52), datetime(2025, 6, 21, 8, 30), "跨夜：日間→夜間→日間"),
        (datetime(2025, 6, 20, 7, 22), datetime(2025, 6, 20, 9, 30), "清晨跨日→日間邊界"),
        (datetime(2025, 6, 20, 21, 0), datetime(2025, 6, 21, 3, 0), "21:00-03:00 跨午夜"),
    ]

    for enter_time, exit_time, label in cases:
        result = sps.calculate_fee_by_billing_cycles(enter_time, exit_time, plan_data)
        total_minutes = int((exit_time - enter_time).total_seconds() / 60)
        ok1 = result.get("success") is True
        ok2 = result.get("total_duration_minutes") == total_minutes
        print(f"\n- {label}")
        print(f"  成功: {ok1}")
        print(f"  總時長: {result.get('total_duration_minutes')} vs {total_minutes}")
        if not ok1 or not ok2:
            print("  >> 驗證失敗")


def run_multidimensional_checks():
    print("\n=== 多維度計算器（跨日/跨時段）驗證 ===")
    calc = MultidimensionalParkingCalculator(
        str(resolve_data_dir() / "multidimensional_rate_plans.json")
    )

    cases = [
        ("全天_無假日費率", datetime(2024, 12, 19, 10, 0), datetime(2024, 12, 19, 14, 30), "全天無假日"),
        ("兩段_六日費率", datetime(2024, 12, 21, 21, 0), datetime(2024, 12, 22, 3, 0), "週末兩段跨午夜"),
        ("兩段_六日費率", datetime(2024, 12, 21, 22, 0), datetime(2024, 12, 22, 8, 0), "22:00-08:00 精確跨日"),
    ]

    for template_id, enter_time, exit_time, label in cases:
        result = calc.calculate_parking_fee(enter_time, exit_time, template_id)
        expected_minutes = int((exit_time - enter_time).total_seconds() / 60)
        slot_minutes = sum(s["duration"] for s in result.session_details)
        print(f"\n- {label} [{template_id}]")
        assert_equal("總時長(分鐘)", expected_minutes, expected_minutes)
        assert_equal("分時段合計(分鐘)", slot_minutes, expected_minutes)
        print(f"  總費用: {result.total_amount} 元")


def main():
    run_user_defined_billing_cycle_checks()
    run_multidimensional_checks()
    print("\n驗證完成。若均為 [OK] 表示跨日/跨時段處理正常。")


if __name__ == "__main__":
    main()
