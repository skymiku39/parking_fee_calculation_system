"""
多維度標籤停車計算器測試
"""

import unittest
import sys
import os
from datetime import datetime, date

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from src.domain.multidimensional_calculator import (
        MultidimensionalParkingCalculator,
        TimeSegmentType,
        HolidayType,
        DateCategory,
    )
    from src.domain.terminology import TEMPLATE_ID_ALIASES
except ImportError as e:
    print(f"導入錯誤: {e}")
    sys.exit(1)


CANONICAL_TEMPLATES = {
    "全天_無假日": "全天_無假日",
    "二段_平日假日": "二段_平日假日",
    "多時段_完整假日": "多時段_完整假日",
}


class TestMultidimensionalCalculator(unittest.TestCase):
    """多維度標籤計算器測試類"""

    def setUp(self):
        try:
            self.calculator = MultidimensionalParkingCalculator(
                "config/multidimensional_rate_plans.json"
            )
        except Exception as e:
            print(f"初始化計算器失敗: {e}")
            self.calculator = None

    def test_calculator_initialization(self):
        self.assertIsNotNone(self.calculator, "計算器初始化失敗")
        self.assertTrue(
            len(self.calculator.rate_plan_templates) > 0, "沒有載入費率範本"
        )

    def test_date_category_detection(self):
        if not self.calculator:
            self.skipTest("計算器未初始化")

        weekday = date(2024, 12, 19)
        self.assertEqual(
            self.calculator.get_date_category(weekday, "平日假日"),
            DateCategory.WEEKDAY,
        )

        weekend = date(2024, 12, 21)
        self.assertEqual(
            self.calculator.get_date_category(weekend, "平日假日"),
            DateCategory.HOLIDAY,
        )

        custom_holiday = date(2024, 12, 25)
        self.assertEqual(
            self.calculator.get_date_category(custom_holiday, "完整假日"),
            DateCategory.FESTIVAL,
        )

    def test_all_day_no_holiday_rate(self):
        if not self.calculator:
            self.skipTest("計算器未初始化")

        enter_time = datetime(2024, 12, 19, 10, 0)
        exit_time = datetime(2024, 12, 19, 14, 30)

        result = self.calculator.calculate_parking_fee(
            enter_time, exit_time, "全天_無假日"
        )

        self.assertIsNotNone(result)
        self.assertGreater(result.total_amount, 0)
        self.assertEqual(result.segment_type, "全天")
        self.assertEqual(result.holiday_type, "無假日")
        self.assertEqual(result.date_category, DateCategory.WEEKDAY)

    def test_legacy_template_id_alias(self):
        if not self.calculator:
            self.skipTest("計算器未初始化")

        enter_time = datetime(2024, 12, 19, 10, 0)
        exit_time = datetime(2024, 12, 19, 14, 30)
        result = self.calculator.calculate_parking_fee(
            enter_time, exit_time, "全天_無假日費率"
        )
        self.assertGreater(result.total_amount, 0)

    def test_two_segment_weekend_rate(self):
        if not self.calculator:
            self.skipTest("計算器未初始化")

        enter_time = datetime(2024, 12, 21, 20, 0)
        exit_time = datetime(2024, 12, 22, 2, 0)

        result = self.calculator.calculate_parking_fee(
            enter_time, exit_time, "二段_平日假日"
        )

        self.assertIsNotNone(result)
        self.assertGreater(result.total_amount, 0)
        self.assertEqual(result.segment_type, "二段")
        self.assertEqual(result.holiday_type, "平日假日")
        self.assertEqual(result.date_category, DateCategory.HOLIDAY)

        day_segments = [s for s in result.session_details if s["duration"] > 0]
        self.assertGreaterEqual(len(day_segments), 1)

    def test_multi_segment_full_holiday_rate(self):
        if not self.calculator:
            self.skipTest("計算器未初始化")

        enter_time = datetime(2024, 12, 25, 9, 0)
        exit_time = datetime(2024, 12, 25, 17, 0)

        result = self.calculator.calculate_parking_fee(
            enter_time, exit_time, "多時段_完整假日"
        )

        self.assertIsNotNone(result)
        self.assertGreater(result.total_amount, 0)
        self.assertEqual(result.segment_type, "多時段")
        self.assertEqual(result.holiday_type, "完整假日")
        self.assertEqual(result.date_category, DateCategory.FESTIVAL)

        active_segments = [s for s in result.session_details if s["duration"] > 0]
        self.assertGreaterEqual(len(active_segments), 2)

    def test_cross_midnight_calculation(self):
        if not self.calculator:
            self.skipTest("計算器未初始化")

        enter_time = datetime(2024, 12, 19, 21, 0)
        exit_time = datetime(2024, 12, 20, 3, 0)

        result = self.calculator.calculate_parking_fee(
            enter_time, exit_time, "二段_平日假日"
        )

        self.assertIsNotNone(result)
        self.assertGreater(result.total_amount, 0)

        total_duration = sum(s["duration"] for s in result.session_details)
        expected_duration = 6 * 60
        self.assertEqual(total_duration, expected_duration)

    def test_dimension_combinations(self):
        if not self.calculator:
            self.skipTest("計算器未初始化")

        combinations = self.calculator.get_dimension_combinations()
        self.assertIsInstance(combinations, list)
        self.assertGreater(len(combinations), 0)

        for combo in combinations:
            self.assertIn("combination_id", combo)
            self.assertIn("label", combo)
            self.assertIn("time_segment", combo)
            self.assertIn("holiday_type", combo)
            self.assertIn("total_variants", combo)

    def test_available_templates(self):
        if not self.calculator:
            self.skipTest("計算器未初始化")

        templates = self.calculator.get_available_templates()
        self.assertIsInstance(templates, dict)
        self.assertGreater(len(templates), 0)

        for template_id in CANONICAL_TEMPLATES:
            self.assertIn(template_id, templates)

    def test_calculation_result_structure(self):
        if not self.calculator:
            self.skipTest("計算器未初始化")

        enter_time = datetime(2024, 12, 19, 10, 0)
        exit_time = datetime(2024, 12, 19, 14, 0)

        result = self.calculator.calculate_parking_fee(
            enter_time, exit_time, "二段_平日假日"
        )

        self.assertTrue(hasattr(result, "total_amount"))
        self.assertTrue(hasattr(result, "original_amount"))
        self.assertTrue(hasattr(result, "date_category"))
        self.assertTrue(hasattr(result, "applied_rate_plan"))
        self.assertTrue(hasattr(result, "segment_type"))
        self.assertTrue(hasattr(result, "holiday_type"))
        self.assertTrue(hasattr(result, "session_details"))
        self.assertTrue(hasattr(result, "calculation_summary"))
        self.assertTrue(hasattr(result, "dimension_tags"))
        self.assertEqual(result.time_segment_type, result.segment_type)

        self.assertIsInstance(result.dimension_tags, list)
        self.assertGreater(len(result.dimension_tags), 0)

    def test_time_slot_duration_calculation(self):
        if not self.calculator:
            self.skipTest("計算器未初始化")

        start_time = datetime(2024, 12, 19, 10, 0)
        end_time = datetime(2024, 12, 19, 12, 0)

        duration = self.calculator.calculate_slot_duration(
            start_time, end_time, "08:00", "22:00"
        )
        self.assertEqual(duration, 120)

        start_time = datetime(2024, 12, 19, 23, 0)
        end_time = datetime(2024, 12, 20, 1, 0)

        duration = self.calculator.calculate_slot_duration(
            start_time, end_time, "22:00", "08:00"
        )
        self.assertEqual(duration, 120)

    def test_progressive_fee_calculation(self):
        if not self.calculator:
            self.skipTest("計算器未初始化")

        progressive_rates = [
            {"start_min": 0, "end_min": 60, "unit_minutes": 30, "unit_price": 25},
            {"start_min": 60, "end_min": 120, "unit_minutes": 30, "unit_price": 35},
            {"start_min": 120, "end_min": None, "unit_minutes": 30, "unit_price": 40},
        ]

        fee, details = self.calculator.calculate_progressive_fee(90, progressive_rates)
        expected_fee = 2 * 25 + 1 * 35
        self.assertEqual(fee, expected_fee)
        self.assertEqual(len(details), 2)


if __name__ == "__main__":
    unittest.main()
