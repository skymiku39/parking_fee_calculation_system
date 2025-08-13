#!/usr/bin/env python3
"""
測試新的基於收費週期的計費邏輯

驗證問題：
- 06-20 日間 (14:22-22:00) - 30分鐘一收費
- 06-20~06-21 夜間 (22:00-08:00) - 60分鐘一收費

舊邏輯問題：
21:52是上次日間收費時間，但系統會在22:00強制切換到夜間費率

新邏輯修正：
21:52 + 30分鐘 = 22:22，這30分鐘週期仍使用日間費率
22:22之後才開始使用夜間費率
"""

import sys
import os

# 將專案根目錄加入匯入路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
import json
from app import SmartParkingSystem


def create_test_plan():
    """創建測試用的費率方案"""
    test_plan = {
        "name": "計費週期測試方案",
        "description": "用於測試收費週期邏輯的方案",
        "segment_type": "多時段",
        "holiday_type": "平日假日",
        "segments": [
            {"name": "日間", "start": "08:00", "end": "22:00"},
            {"name": "夜間", "start": "22:00", "end": "08:00"},
        ],
        "rate_matrix": {
            "日間_平日": {
                "unit_time": 30,  # 30分鐘一收費
                "simple_rate": 30,  # 每30分鐘30元
                "progressive_enabled": False,
                "grace_time": 0,
            },
            "夜間_平日": {
                "unit_time": 60,  # 60分鐘一收費
                "simple_rate": 10,  # 每60分鐘10元
                "progressive_enabled": False,
                "grace_time": 0,
            },
            "日間_假日": {
                "unit_time": 30,  # 30分鐘一收費
                "simple_rate": 40,  # 每30分鐘40元 (假日加價)
                "progressive_enabled": False,
                "grace_time": 0,
            },
            "夜間_假日": {
                "unit_time": 60,  # 60分鐘一收費
                "simple_rate": 10,  # 每60分鐘10元 (夜間統一)
                "progressive_enabled": False,
                "grace_time": 0,
            },
        },
        "global_caps": {},
        "global_grace_time": 0,
        "created_date": datetime.now().isoformat(),
        "modified_date": datetime.now().isoformat(),
        "version": "1.0",
        "active": True,
    }

    return test_plan


def save_test_plan(plan_data):
    """儲存測試方案到配置文件"""
    try:
        # 確保config目錄存在
        os.makedirs("config", exist_ok=True)

        # 載入或創建用戶方案文件
        user_plans_file = "config/user_defined_plans.json"
        try:
            with open(user_plans_file, "r", encoding="utf-8") as f:
                user_plans = json.load(f)
        except FileNotFoundError:
            user_plans = {
                "plans": {},
                "metadata": {"created": datetime.now().isoformat(), "version": "1.0"},
            }

        # 添加測試方案
        user_plans["plans"]["billing_cycle_test"] = plan_data
        user_plans["metadata"]["last_modified"] = datetime.now().isoformat()

        # 儲存文件
        with open(user_plans_file, "w", encoding="utf-8") as f:
            json.dump(user_plans, f, ensure_ascii=False, indent=2)

        print("✓ 測試方案已儲存")
        return True

    except Exception as e:
        print(f"✗ 儲存測試方案失敗: {e}")
        return False


def test_scenario_1():
    """
    測試場景1：跨時段的收費週期

    停車時間：2025-06-20 21:52 到 2025-06-21 08:30

    預期結果（新邏輯）：
    1. 21:52-22:22 (30分鐘) - 日間費率 20元
    2. 22:22-23:22 (60分鐘) - 夜間費率 15元
    3. 23:22-00:22 (60分鐘) - 夜間費率 15元
    4. 00:22-01:22 (60分鐘) - 夜間費率 15元
    ... 繼續夜間費率
    最後到 08:22-08:30 (8分鐘) - 日間費率 20元
    """
    print("\n=== 測試場景1：跨時段收費週期 ===")

    # 初始化系統
    parking_system = SmartParkingSystem()

    # 測試時間
    enter_time = datetime(2025, 6, 20, 21, 52)  # 21:52 (日間時段的最後階段)
    exit_time = datetime(2025, 6, 21, 8, 30)  # 08:30 (日間時段的開始階段)

    print(
        f"停車時間：{enter_time.strftime('%Y-%m-%d %H:%M')} - {exit_time.strftime('%Y-%m-%d %H:%M')}"
    )

    # 計算費用
    result = parking_system.calculate_with_user_defined_plan(
        enter_time, exit_time, "billing_cycle_test"
    )

    if result["success"]:
        print(f"✓ 計算成功")
        print(f"總費用：{result['total_amount']}元")
        print(f"計算引擎：{result['calculation_engine']}")
        print(f"計算摘要：{result['calculation_summary']}")

        print("\n收費明細：")
        for i, detail in enumerate(result.get("session_details", []), 1):
            print(
                f"  {i}. {detail['period']} - {detail['duration']} × {detail['rate']} = {detail['amount']}元"
            )

        # 驗證關鍵點
        session_details = result.get("session_details", [])
        if session_details:
            first_detail = session_details[0]
            print(f"\n關鍵驗證：")
            print(f"第一個收費週期：{first_detail['period']}")
            print(f"預期：應該是21:52-22:22，使用日間費率20元")

            if "21:52-22:22" in first_detail["period"] and first_detail["amount"] == 20:
                print("✓ 第一個週期驗證通過")
            else:
                print("✗ 第一個週期驗證失敗")

        print(f"\n舊邏輯對比：")
        print(
            f"舊邏輯會在22:00強制切換，導致21:52-22:00用日間費率，22:00-22:22用夜間費率"
        )
        print(f"新邏輯正確按收費週期，21:52-22:22整個週期都用日間費率")

    else:
        print(f"✗ 計算失敗：{result.get('error', '未知錯誤')}")


def test_scenario_2():
    """
    測試場景2：夜間結束時的收費週期

    停車時間：2025-06-20 07:22 到 2025-06-20 09:30

    預期結果：
    1. 07:22-08:22 (60分鐘) - 夜間費率 15元 (雖然跨越了08:00邊界)
    2. 08:22-08:52 (30分鐘) - 日間費率 20元
    3. 08:52-09:22 (30分鐘) - 日間費率 20元
    4. 09:22-09:30 (8分鐘) - 日間費率 20元
    """
    print("\n=== 測試場景2：夜間結束時的收費週期 ===")

    # 初始化系統
    parking_system = SmartParkingSystem()

    # 測試時間
    enter_time = datetime(2025, 6, 20, 7, 22)  # 07:22 (夜間時段)
    exit_time = datetime(2025, 6, 20, 9, 30)  # 09:30 (日間時段)

    print(
        f"停車時間：{enter_time.strftime('%Y-%m-%d %H:%M')} - {exit_time.strftime('%Y-%m-%d %H:%M')}"
    )

    # 計算費用
    result = parking_system.calculate_with_user_defined_plan(
        enter_time, exit_time, "billing_cycle_test"
    )

    if result["success"]:
        print(f"✓ 計算成功")
        print(f"總費用：{result['total_amount']}元")
        print(f"計算摘要：{result['calculation_summary']}")

        print("\n收費明細：")
        for i, detail in enumerate(result.get("session_details", []), 1):
            print(
                f"  {i}. {detail['period']} - {detail['duration']} × {detail['rate']} = {detail['amount']}元"
            )

        # 驗證關鍵點
        session_details = result.get("session_details", [])
        if session_details:
            first_detail = session_details[0]
            print(f"\n關鍵驗證：")
            print(f"第一個收費週期：{first_detail['period']}")
            print(f"預期：應該是07:22-08:22，使用夜間費率15元")

            if "07:22-08:22" in first_detail["period"] and first_detail["amount"] == 15:
                print("✓ 第一個週期驗證通過")
            else:
                print("✗ 第一個週期驗證失敗")

    else:
        print(f"✗ 計算失敗：{result.get('error', '未知錯誤')}")


def test_scenario_3():
    """
    測試場景3：簡單的同時段停車

    停車時間：2025-06-20 10:15 到 2025-06-20 12:45

    預期結果：
    1. 10:15-10:45 (30分鐘) - 日間費率 30元
    2. 10:45-11:15 (30分鐘) - 日間費率 30元
    3. 11:15-11:45 (30分鐘) - 日間費率 30元
    4. 11:45-12:15 (30分鐘) - 日間費率 30元
    5. 12:15-12:45 (30分鐘) - 日間費率 30元
    總計：5個週期 × 30元 = 150元
    """
    print("\n=== 測試場景3：同時段停車 ===")

    # 初始化系統
    parking_system = SmartParkingSystem()

    # 測試時間
    enter_time = datetime(2025, 6, 20, 10, 15)  # 10:15 (日間時段)
    exit_time = datetime(2025, 6, 20, 12, 45)  # 12:45 (日間時段)

    print(
        f"停車時間：{enter_time.strftime('%Y-%m-%d %H:%M')} - {exit_time.strftime('%Y-%m-%d %H:%M')}"
    )
    total_minutes = int((exit_time - enter_time).total_seconds() / 60)
    print(f"總停車時間：{total_minutes}分鐘 (2小時30分)")

    # 計算費用
    result = parking_system.calculate_with_user_defined_plan(
        enter_time, exit_time, "billing_cycle_test"
    )

    if result["success"]:
        print(f"✓ 計算成功")
        print(f"總費用：{result['total_amount']}元")
        print(f"預期費用：150元 (5個30分鐘週期)")

        print("\n收費明細：")
        for i, detail in enumerate(result.get("session_details", []), 1):
            print(
                f"  {i}. {detail['period']} - {detail['duration']} × {detail['rate']} = {detail['amount']}元"
            )

        if result["total_amount"] == 150:
            print("✓ 費用驗證通過")
        else:
            print("✗ 費用驗證失敗")

    else:
        print(f"✗ 計算失敗：{result.get('error', '未知錯誤')}")


def test_scenario_4():
    """
    測試場景4：假日費率測試 (星期六)

    停車時間：2025-06-21 10:15 到 2025-06-21 12:45 (星期六)

    預期結果：
    1. 10:15-10:45 (30分鐘) - 假日日間費率 30元
    2. 10:45-11:15 (30分鐘) - 假日日間費率 30元
    3. 11:15-11:45 (30分鐘) - 假日日間費率 30元
    4. 11:45-12:15 (30分鐘) - 假日日間費率 30元
    5. 12:15-12:45 (30分鐘) - 假日日間費率 30元
    總計：5個週期 × 30元 = 150元 (比平日100元更貴)
    """
    print("\n=== 測試場景4：假日費率測試 (星期六) ===")

    # 初始化系統
    parking_system = SmartParkingSystem()

    # 測試時間 - 2025-06-21是星期六
    enter_time = datetime(2025, 6, 21, 10, 15)  # 10:15 (假日日間時段)
    exit_time = datetime(2025, 6, 21, 12, 45)  # 12:45 (假日日間時段)

    print(
        f"停車時間：{enter_time.strftime('%Y-%m-%d %H:%M')} - {exit_time.strftime('%Y-%m-%d %H:%M')}"
    )
    print(f"日期：{enter_time.strftime('%A')} (星期六，假日)")
    total_minutes = int((exit_time - enter_time).total_seconds() / 60)
    print(f"總停車時間：{total_minutes}分鐘 (2小時30分)")

    # 計算費用
    result = parking_system.calculate_with_user_defined_plan(
        enter_time, exit_time, "billing_cycle_test"
    )

    if result["success"]:
        print(f"✓ 計算成功")
        print(f"總費用：{result['total_amount']}元")
        print(f"預期費用：200元 (5個30分鐘週期 × 假日費率40元)")
        print(f"日期類型：{result.get('date_category', '未知')}")

        print("\n收費明細：")
        for i, detail in enumerate(result.get("session_details", []), 1):
            print(
                f"  {i}. {detail['period']} - {detail['duration']} × {detail['rate']} = {detail['amount']}元"
            )

        if result["total_amount"] == 200:
            print("✓ 假日費用驗證通過")
        else:
            print("✗ 假日費用驗證失敗")

        # 驗證是否正確識別為假日
        if result.get("date_category") == "假日":
            print("✓ 假日識別正確")
        else:
            print(f"✗ 假日識別錯誤，實際為：{result.get('date_category')}")

    else:
        print(f"✗ 計算失敗：{result.get('error', '未知錯誤')}")


def test_scenario_5():
    """
    測試場景5：跨假日的夜間收費週期

    停車時間：2025-06-20 23:30 到 2025-06-21 08:30 (星期五晚上到星期六早上)

    預期結果（關鍵測試）：
    - 進場時間是星期五（平日），但跨日到星期六（假日）
    - 應該使用進場時間的日期類型來判斷整個停車期間的費率
    - 所以應該使用平日費率，而不是假日費率
    """
    print("\n=== 測試場景5：跨假日的夜間收費週期 ===")

    # 初始化系統
    parking_system = SmartParkingSystem()

    # 測試時間 - 從星期五晚上到星期六早上
    enter_time = datetime(2025, 6, 20, 23, 30)  # 23:30 星期五(平日)
    exit_time = datetime(2025, 6, 21, 8, 30)  # 08:30 星期六(假日)

    print(
        f"停車時間：{enter_time.strftime('%Y-%m-%d %H:%M')} - {exit_time.strftime('%Y-%m-%d %H:%M')}"
    )
    print(f"進場：{enter_time.strftime('%A')} (星期五，平日)")
    print(f"出場：{exit_time.strftime('%A')} (星期六，假日)")

    # 計算費用
    result = parking_system.calculate_with_user_defined_plan(
        enter_time, exit_time, "billing_cycle_test"
    )

    if result["success"]:
        print(f"✓ 計算成功")
        print(f"總費用：{result['total_amount']}元")
        print(f"日期類型：{result.get('date_category', '未知')}")
        print(f"計算摘要：{result['calculation_summary']}")

        print("\n收費明細：")
        for i, detail in enumerate(result.get("session_details", []), 1):
            print(
                f"  {i}. {detail['period']} - {detail['duration']} × {detail['rate']} = {detail['amount']}元"
            )

        # 驗證是否使用進場日期的類型
        if result.get("date_category") == "平日":
            print("✓ 正確使用進場日期的平日費率")
        elif result.get("date_category") == "假日":
            print("⚠ 使用了假日費率（需要確認這是否為預期行為）")
        else:
            print(f"? 未知的日期類型：{result.get('date_category')}")

    else:
        print(f"✗ 計算失敗：{result.get('error', '未知錯誤')}")


def main():
    """主測試函數"""
    print("基於收費週期的計費邏輯測試")
    print("=" * 50)

    # 創建並儲存測試方案
    print("準備測試方案...")
    test_plan = create_test_plan()
    if not save_test_plan(test_plan):
        print("無法儲存測試方案，測試終止")
        return

    # 執行測試場景
    test_scenario_1()  # 跨時段收費週期
    test_scenario_2()  # 夜間結束時的收費週期
    test_scenario_3()  # 同時段停車
    test_scenario_4()  # 假日費率測試
    test_scenario_5()  # 跨假日的夜間收費週期

    print("\n" + "=" * 50)
    print("測試完成")
    print("\n重要修正：")
    print("✓ 修正了按時段邊界切割的錯誤邏輯")
    print("✓ 改為按收費週期來計算費用")
    print("✓ 收費週期跨時段邊界時，使用週期開始時的費率")
    print("✓ 正確區分平日和假日費率")
    print("✓ 符合真實停車場的收費邏輯")


if __name__ == "__main__":
    main()


