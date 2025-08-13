#!/usr/bin/env python3
"""
跨日停車假日費率修正測試（簡化版）
"""

import sys
import os
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import SmartParkingSystem


def test_cross_day_holiday_rate_fix():
    parking_system = SmartParkingSystem()

    enter_time = datetime(2025, 6, 20, 15, 48)  # 週五
    exit_time = datetime(2025, 6, 21, 17, 48)  # 週六
    plan_id = "萬華西園"

    result = parking_system.calculate_parking_fee(enter_time, exit_time, plan_id)
    print("成功" if result.get("success") else result)


if __name__ == "__main__":
    test_cross_day_holiday_rate_fix()


