#!/usr/bin/env python3
"""
停車費計算系統 DEMO 測試
驗證核心功能的正確性
"""

import sys
import os
from datetime import datetime

# 加入模組路徑
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import ParkingCalculator


def test_basic_calculation():
    """測試基本計算功能"""
    print("=" * 60)
    print("基本計算功能測試")
    print("=" * 60)

    calculator = ParkingCalculator()

    # 測試案例1：同日停車
    print("測試案例1：同日停車 (日間時段)")
    enter_time = datetime(2025, 6, 20, 10, 0)  # 週五 10:00
    exit_time = datetime(2025, 6, 20, 14, 0)  # 週五 14:00

    result = calculator.calculate_parking_fee(enter_time, exit_time, "萬華西園")

    if result["success"]:
        print(f"✓ 計算成功")
        print(f"  進場時間：{result['enter_time']}")
        print(f"  出場時間：{result['exit_time']}")
        print(f"  停車時長：{result['total_duration']}")
        print(f"  總費用：{result['total_amount']}元")
        print("  計費明細：")
        for detail in result["billing_details"]:
            print(
                f"    - {detail['period']}: {detail['duration']} | {detail['rate']} = {detail['amount']}元"
            )
    else:
        print(f"❌ 計算失敗：{result['error']}")

    print()


def test_cross_day_calculation():
    """測試跨日計算功能"""
    print("=" * 60)
    print("跨日計算功能測試")
    print("=" * 60)

    calculator = ParkingCalculator()

    # 測試案例2：跨日停車（週五晚上到週六早上）
    print("測試案例2：跨日停車 (週五晚上到週六早上)")
    enter_time = datetime(2025, 6, 20, 20, 0)  # 週五 20:00
    exit_time = datetime(2025, 6, 21, 8, 0)  # 週六 08:00

    result = calculator.calculate_parking_fee(enter_time, exit_time, "萬華西園")

    if result["success"]:
        print(f"✓ 計算成功")
        print(f"  進場時間：{result['enter_time']}")
        print(f"  出場時間：{result['exit_time']}")
        print(f"  停車時長：{result['total_duration']}")
        print(f"  總費用：{result['total_amount']}元")
        print("  計費明細：")
        for detail in result["billing_details"]:
            print(
                f"    - {detail['period']}: {detail['duration']} | {detail['rate']} = {detail['amount']}元"
            )

        # 驗證結果
        print("\n  結果驗證：")
        has_weekday = any(
            "平日" in detail["period"] for detail in result["billing_details"]
        )
        has_weekend = any(
            "假日" in detail["period"] for detail in result["billing_details"]
        )

        if has_weekday:
            print("    ✓ 正確識別平日時段")
        if has_weekend:
            print("    ✓ 正確識別假日時段")

        # 檢查夜間時段是否正確使用平日費率
        night_details = [d for d in result["billing_details"] if "夜間" in d["period"]]
        if night_details:
            night_detail = night_details[0]
            if "平日" in night_detail["period"]:
                print("    ✓ 夜間時段正確使用平日費率（基於週五開始）")
            else:
                print("    ❌ 夜間時段費率錯誤")
    else:
        print(f"❌ 計算失敗：{result['error']}")

    print()


def test_multi_day_calculation():
    """測試多日停車計算"""
    print("=" * 60)
    print("多日停車計算測試")
    print("=" * 60)

    calculator = ParkingCalculator()

    # 測試案例3：多日停車（週五到週一）
    print("測試案例3：多日停車 (週五下午到週一早上)")
    enter_time = datetime(2025, 6, 20, 16, 0)  # 週五 16:00
    exit_time = datetime(2025, 6, 23, 9, 0)  # 週一 09:00

    result = calculator.calculate_parking_fee(enter_time, exit_time, "萬華西園")

    if result["success"]:
        print(f"✓ 計算成功")
        print(f"  進場時間：{result['enter_time']}")
        print(f"  出場時間：{result['exit_time']}")
        print(f"  停車時長：{result['total_duration']}")
        print(f"  總費用：{result['total_amount']}元")
        print("  計費明細：")

        total_by_type = {"平日": 0, "假日": 0}

        for detail in result["billing_details"]:
            print(
                f"    - {detail['period']}: {detail['duration']} | {detail['rate']} = {detail['amount']}元"
            )

            # 統計各類型費用
            if "平日" in detail["period"]:
                total_by_type["平日"] += detail["amount"]
            elif "假日" in detail["period"]:
                total_by_type["假日"] += detail["amount"]

        print(f"\n  費用分析：")
        print(f"    平日費用：{total_by_type['平日']}元")
        print(f"    假日費用：{total_by_type['假日']}元")
        print(f"    總費用：{sum(total_by_type.values())}元")

        # 驗證時段上限
        print(f"\n  時段上限驗證：")
        for detail in result["billing_details"]:
            if "夜間" in detail["period"] and detail["amount"] == 50:
                print(f"    ✓ {detail['period']} 達到上限 (50元)")
            elif "日間平日" in detail["period"] and detail["amount"] == 300:
                print(f"    ✓ {detail['period']} 達到上限 (300元)")
            elif "日間假日" in detail["period"] and detail["amount"] == 400:
                print(f"    ✓ {detail['period']} 達到上限 (400元)")
    else:
        print(f"❌ 計算失敗：{result['error']}")

    print()


def test_segment_cap():
    """測試時段上限功能"""
    print("=" * 60)
    print("時段上限功能測試")
    print("=" * 60)

    calculator = ParkingCalculator()

    # 測試案例4：長時間停車觸發上限
    print("測試案例4：長時間停車 (觸發時段上限)")
    enter_time = datetime(2025, 6, 20, 7, 0)  # 週五 07:00
    exit_time = datetime(2025, 6, 20, 18, 0)  # 週五 18:00

    result = calculator.calculate_parking_fee(enter_time, exit_time, "萬華西園")

    if result["success"]:
        print(f"✓ 計算成功")
        print(f"  停車時長：{result['total_duration']} (11小時)")
        print(f"  總費用：{result['total_amount']}元")

        # 計算理論費用（無上限）
        total_minutes = 11 * 60  # 660分鐘
        theoretical_units = -(-total_minutes // 30)  # 向上取整到30分鐘單位
        theoretical_fee = theoretical_units * 30  # 30元/30分鐘

        print(f"  理論費用：{theoretical_fee}元 (無上限)")
        print(f"  實際費用：{result['total_amount']}元")

        if result["total_amount"] < theoretical_fee:
            print(
                f"  ✓ 時段上限生效，節省 {theoretical_fee - result['total_amount']}元"
            )
        else:
            print(f"  ❌ 時段上限未生效")
    else:
        print(f"❌ 計算失敗：{result['error']}")

    print()


def run_all_tests():
    """執行所有測試"""
    print("停車費計算系統 DEMO 測試開始")
    print("=" * 60)

    test_basic_calculation()
    test_cross_day_calculation()
    test_multi_day_calculation()
    test_segment_cap()

    print("=" * 60)
    print("所有測試完成")


if __name__ == "__main__":
    run_all_tests()
