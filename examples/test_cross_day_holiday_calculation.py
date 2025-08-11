"""
測試跨日假日計費邏輯
驗證6/21(假日)進場的跨日停車是否正確使用假日費率
"""

import sys
import os

# 將專案根目錄加入匯入路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from app import SmartParkingSystem


def test_cross_day_holiday_scenario():
    """
    測試場景：6/21(星期六,假日)進場的多日停車

    停車時間：2025-06-21 15:26 - 2025-06-23 17:26

    預期：因為進場日期是6/21(假日)，整個停車期間都應該使用假日費率

    期望的計費明細：
    06-21 日間假日 (15:26-18:26) - 180分鐘 (3小時) × 40元/30分鐘 = 240元
    06-21~06-22 夜間假日 (18:26-07:26) - 780分鐘 (13小時) × 10元/60分鐘 = 130元
    06-22 日間假日 (07:26-18:26) - 660分鐘 (11小時) × 40元/30分鐘 = 880元
    06-22~06-23 夜間假日 (18:26-07:26) - 780分鐘 (13小時) × 10元/60分鐘 = 130元
    06-23 日間假日 (07:26-17:26) - 600分鐘 (10小時) × 40元/30分鐘 = 800元
    """
    print("測試跨日假日計費邏輯")
    print("=" * 50)

    # 初始化系統
    parking_system = SmartParkingSystem()

    # 測試時間 - 從6/21(星期六,假日)進場
    enter_time = datetime(2025, 6, 21, 15, 26)  # 2025-06-21 15:26 (星期六)
    exit_time = datetime(2025, 6, 23, 17, 26)  # 2025-06-23 17:26 (星期一)

    print(
        f"停車時間：{enter_time.strftime('%Y-%m-%d %H:%M')} - {exit_time.strftime('%Y-%m-%d %H:%M')}"
    )
    print(f"進場日期：{enter_time.strftime('%A')} (星期六，假日)")
    print(f"出場日期：{exit_time.strftime('%A')} (星期一，平日)")
    print(f"預期：因為進場日期是假日，整個停車期間都應該使用假日費率")

    # 計算費用
    result = parking_system.calculate_with_user_defined_plan(
        enter_time, exit_time, "billing_cycle_test"
    )

    if result["success"]:
        print(f"\n✓ 計算成功")
        print(f"總費用：{result['total_amount']}元")
        print(f"日期類型：{result.get('date_category', '未知')}")
        print(f"計算摘要：{result['calculation_summary']}")

        print("\n實際計費明細：")
        for i, detail in enumerate(result.get("session_details", []), 1):
            print(f"  {i}. {detail['period']}")
            print(f"     {detail['duration']} | {detail['rate']}")
            print(f"     {detail['amount']} 元")
            print()
    else:
        print(f"✗ 計算失敗：{result.get('error', '未知錯誤')}")


if __name__ == "__main__":
    test_cross_day_holiday_scenario()


