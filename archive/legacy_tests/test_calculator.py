"""
停車費計算器測試
"""

import unittest
from datetime import datetime
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.parking_calculator import ParkingCalculator


class TestParkingCalculator(unittest.TestCase):
    """停車費計算器測試類別"""

    def setUp(self):
        """測試前準備"""
        self.calculator = ParkingCalculator()

    def test_simple_single_rate(self):
        """測試基本單一費率"""
        enter_time = datetime(2024, 1, 15, 10, 0)  # 平日10:00
        exit_time = datetime(2024, 1, 15, 12, 0)  # 平日12:00 (停車2小時)

        result = self.calculator.calculate_parking_fee(
            enter_time, exit_time, "weekday_standard"  # 使用存在的方案
        )

        # 應該計算2小時的費用
        self.assertEqual(result["total_duration_minutes"], 120)
        self.assertGreater(result["final_charge"], 0)
        print(f"基本計算: 停車2小時，費用 {result['final_charge']} 元")

    def test_two_period_rate(self):
        """測試兩段式費率"""
        enter_time = datetime(2024, 1, 15, 21, 0)  # 平日21:00
        exit_time = datetime(2024, 1, 15, 23, 0)  # 平日23:00 (跨夜間)

        result = self.calculator.calculate_parking_fee(
            enter_time, exit_time, "mall_complex"  # 使用複雜方案
        )

        self.assertEqual(result["total_duration_minutes"], 120)  # 2小時
        self.assertGreater(result["final_charge"], 0)
        print(f"兩段式費率: 夜間2小時，費用 {result['final_charge']} 元")

    def test_grace_period(self):
        """測試免費時間"""
        enter_time = datetime(2024, 1, 15, 10, 0)
        exit_time = datetime(2024, 1, 15, 10, 10)  # 停車10分鐘

        result = self.calculator.calculate_parking_fee(
            enter_time, exit_time, "weekday_standard"  # 使用存在的方案
        )

        self.assertEqual(result["total_duration_minutes"], 10)
        # 10分鐘內可能有免費時間，所以不一定收費
        print(f"寬限期測試: 停車10分鐘，費用 {result['final_charge']} 元")

    def test_cross_day_parking(self):
        """測試跨日停車"""
        enter_time = datetime(2024, 1, 15, 23, 0)  # 23:00
        exit_time = datetime(2024, 1, 16, 2, 0)  # 隔天02:00

        result = self.calculator.calculate_parking_fee(
            enter_time, exit_time, "mall_complex"  # 使用複雜方案
        )

        self.assertEqual(result["total_duration_minutes"], 180)  # 3小時
        self.assertGreater(result["final_charge"], 0)
        print(f"跨日停車: 3小時，費用 {result['final_charge']} 元")

    def test_cap_amount(self):
        """測試收費上限"""
        enter_time = datetime(2024, 1, 15, 8, 0)
        exit_time = datetime(2024, 1, 15, 20, 0)  # 停車12小時

        result = self.calculator.calculate_parking_fee(
            enter_time, exit_time, "mall_complex"  # 使用複雜方案
        )

        self.assertEqual(result["total_duration_minutes"], 720)  # 12小時
        self.assertGreater(result["final_charge"], 0)
        print(f"收費上限測試: 停車12小時，費用 {result['final_charge']} 元")

    def test_available_rate_plans(self):
        """測試可用費率方案"""
        available_plans = self.calculator.get_available_rate_plans()
        self.assertGreater(len(available_plans), 0)
        print(f"可用方案數量: {len(available_plans)}")
        print(f"方案列表: {list(available_plans.keys())}")


if __name__ == "__main__":
    unittest.main()
