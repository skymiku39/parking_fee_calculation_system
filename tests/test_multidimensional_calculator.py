"""
多維度標籤停車計算器測試
"""

import unittest
import sys
import os
from datetime import datetime, date

# 添加項目根目錄到路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from src.domain.multidimensional_calculator import (
        MultidimensionalParkingCalculator,
        TimeSegmentType,
        HolidayType,
        DateCategory,
    )
except ImportError as e:
    print(f"導入錯誤: {e}")
    sys.exit(1)


class TestMultidimensionalCalculator(unittest.TestCase):
    """多維度標籤計算器測試類"""

    def setUp(self):
        """設置測試環境"""
        try:
            self.calculator = MultidimensionalParkingCalculator(
                "config/multidimensional_rate_plans.json"
            )
        except Exception as e:
            print(f"初始化計算器失敗: {e}")
            self.calculator = None

    def test_calculator_initialization(self):
        """測試計算器初始化"""
        self.assertIsNotNone(self.calculator, "計算器初始化失敗")
        self.assertTrue(
            len(self.calculator.rate_plan_templates) > 0, "沒有載入費率範本"
        )

    def test_date_category_detection(self):
        """測試日期類別判斷"""
        if not self.calculator:
            self.skipTest("計算器未初始化")

        # 測試平日
        weekday = date(2024, 12, 19)  # 週四
        self.assertEqual(
            self.calculator.get_date_category(weekday), DateCategory.WEEKDAY
        )

        # 測試週末
        weekend = date(2024, 12, 21)  # 週六
        self.assertEqual(
            self.calculator.get_date_category(weekend), DateCategory.WEEKEND
        )

        # 測試客製假日
        custom_holiday = date(2024, 12, 25)  # 聖誕節
        self.assertEqual(
            self.calculator.get_date_category(custom_holiday),
            DateCategory.CUSTOM_HOLIDAY,
        )

    def test_all_day_no_holiday_rate(self):
        """測試全天無假日費率"""
        if not self.calculator:
            self.skipTest("計算器未初始化")

        enter_time = datetime(2024, 12, 19, 10, 0)  # 週四上午10點
        exit_time = datetime(2024, 12, 19, 14, 30)  # 週四下午2點30分

        result = self.calculator.calculate_parking_fee(
            enter_time, exit_time, "全天_無假日費率"
        )

        self.assertIsNotNone(result)
        self.assertGreater(result.total_amount, 0)
        self.assertEqual(result.time_segment_type, "全天")
        self.assertEqual(result.holiday_type, "無假日費率")
        self.assertEqual(result.date_category, DateCategory.WEEKDAY)

    def test_two_segment_weekend_rate(self):
        """測試兩段週末費率"""
        if not self.calculator:
            self.skipTest("計算器未初始化")

        # 週六停車（跨日夜時段）
        enter_time = datetime(2024, 12, 21, 20, 0)  # 週六晚上8點
        exit_time = datetime(2024, 12, 22, 2, 0)  # 週日凌晨2點

        result = self.calculator.calculate_parking_fee(
            enter_time, exit_time, "兩段_六日費率"
        )

        self.assertIsNotNone(result)
        self.assertGreater(result.total_amount, 0)
        self.assertEqual(result.time_segment_type, "兩段")
        self.assertEqual(result.holiday_type, "六日費率")
        self.assertEqual(result.date_category, DateCategory.WEEKEND)

        # 應該有兩個時段的明細
        day_segments = [s for s in result.session_details if s["duration"] > 0]
        self.assertGreaterEqual(len(day_segments), 1)

    def test_four_segment_national_holiday_rate(self):
        """測試四段國定假日費率"""
        if not self.calculator:
            self.skipTest("計算器未初始化")

        # 聖誕節停車（客製假日）
        enter_time = datetime(2024, 12, 25, 9, 0)  # 上午9點
        exit_time = datetime(2024, 12, 25, 17, 0)  # 下午5點

        result = self.calculator.calculate_parking_fee(
            enter_time, exit_time, "四段_國定假費率"
        )

        self.assertIsNotNone(result)
        self.assertGreater(result.total_amount, 0)
        self.assertEqual(result.time_segment_type, "四段")
        self.assertEqual(result.holiday_type, "國定假費率")
        self.assertEqual(result.date_category, DateCategory.CUSTOM_HOLIDAY)

        # 應該有多個時段的明細
        active_segments = [s for s in result.session_details if s["duration"] > 0]
        self.assertGreaterEqual(len(active_segments), 2)

    def test_cross_midnight_calculation(self):
        """測試跨日計算"""
        if not self.calculator:
            self.skipTest("計算器未初始化")

        # 跨日停車測試
        enter_time = datetime(2024, 12, 19, 21, 0)  # 週四晚上9點
        exit_time = datetime(2024, 12, 20, 3, 0)  # 週五凌晨3點

        result = self.calculator.calculate_parking_fee(
            enter_time, exit_time, "兩段_六日費率"
        )

        self.assertIsNotNone(result)
        self.assertGreater(result.total_amount, 0)

        # 檢查跨日時段計算
        total_duration = sum(s["duration"] for s in result.session_details)
        expected_duration = 6 * 60  # 6小時 = 360分鐘
        self.assertEqual(total_duration, expected_duration)

    def test_dimension_combinations(self):
        """測試維度組合"""
        if not self.calculator:
            self.skipTest("計算器未初始化")

        combinations = self.calculator.get_dimension_combinations()
        self.assertIsInstance(combinations, list)
        self.assertGreater(len(combinations), 0)

        # 檢查組合結構
        for combo in combinations:
            self.assertIn("combination_id", combo)
            self.assertIn("label", combo)
            self.assertIn("time_segment", combo)
            self.assertIn("holiday_type", combo)
            self.assertIn("total_variants", combo)

    def test_available_templates(self):
        """測試可用範本"""
        if not self.calculator:
            self.skipTest("計算器未初始化")

        templates = self.calculator.get_available_templates()
        self.assertIsInstance(templates, dict)
        self.assertGreater(len(templates), 0)

        # 檢查必要的範本
        expected_templates = ["全天_無假日費率", "兩段_六日費率", "四段_國定假費率"]

        for template_id in expected_templates:
            self.assertIn(template_id, templates)

    def test_calculation_result_structure(self):
        """測試計算結果結構"""
        if not self.calculator:
            self.skipTest("計算器未初始化")

        enter_time = datetime(2024, 12, 19, 10, 0)
        exit_time = datetime(2024, 12, 19, 14, 0)

        result = self.calculator.calculate_parking_fee(
            enter_time, exit_time, "兩段_六日費率"
        )

        # 檢查結果結構完整性
        self.assertTrue(hasattr(result, "total_amount"))
        self.assertTrue(hasattr(result, "original_amount"))
        self.assertTrue(hasattr(result, "date_category"))
        self.assertTrue(hasattr(result, "applied_rate_plan"))
        self.assertTrue(hasattr(result, "time_segment_type"))
        self.assertTrue(hasattr(result, "holiday_type"))
        self.assertTrue(hasattr(result, "session_details"))
        self.assertTrue(hasattr(result, "calculation_summary"))
        self.assertTrue(hasattr(result, "dimension_tags"))

        # 檢查維度標籤
        self.assertIsInstance(result.dimension_tags, list)
        self.assertGreater(len(result.dimension_tags), 0)

    def test_time_slot_duration_calculation(self):
        """測試時段時間計算"""
        if not self.calculator:
            self.skipTest("計算器未初始化")

        # 測試正常時段
        start_time = datetime(2024, 12, 19, 10, 0)
        end_time = datetime(2024, 12, 19, 12, 0)

        duration = self.calculator.calculate_slot_duration(
            start_time, end_time, "08:00", "22:00"
        )

        self.assertEqual(duration, 120)  # 2小時 = 120分鐘

        # 測試跨日時段
        start_time = datetime(2024, 12, 19, 23, 0)
        end_time = datetime(2024, 12, 20, 1, 0)

        duration = self.calculator.calculate_slot_duration(
            start_time, end_time, "22:00", "08:00"
        )

        self.assertEqual(duration, 120)  # 2小時 = 120分鐘

    def test_progressive_fee_calculation(self):
        """測試累進費率計算"""
        if not self.calculator:
            self.skipTest("計算器未初始化")

        progressive_rates = [
            {"start_min": 0, "end_min": 60, "unit_minutes": 30, "unit_price": 25},
            {"start_min": 60, "end_min": 120, "unit_minutes": 30, "unit_price": 35},
            {"start_min": 120, "end_min": None, "unit_minutes": 30, "unit_price": 40},
        ]

        # 測試90分鐘停車（跨兩個累進區間）
        fee, details = self.calculator.calculate_progressive_fee(90, progressive_rates)

        # 前60分鐘：2單位 × 25 = 50元
        # 後30分鐘：1單位 × 35 = 35元
        # 總計：85元
        expected_fee = 2 * 25 + 1 * 35  # 85元
        self.assertEqual(fee, expected_fee)
        self.assertEqual(len(details), 2)  # 應該有兩個計費區間


def run_multidimensional_tests():
    """運行多維度標籤測試"""
    print("=== 多維度標籤停車計算器測試 ===\n")

    # 創建測試套件
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMultidimensionalCalculator)

    # 運行測試
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 顯示測試結果摘要
    print(f"\n=== 測試結果摘要 ===")
    print(f"總測試數: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失敗: {len(result.failures)}")
    print(f"錯誤: {len(result.errors)}")

    if result.failures:
        print(f"\n失敗的測試:")
        for test, traceback in result.failures:
            print(f"- {test}")

    if result.errors:
        print(f"\n錯誤的測試:")
        for test, traceback in result.errors:
            print(f"- {test}")

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_multidimensional_tests()
    sys.exit(0 if success else 1)
