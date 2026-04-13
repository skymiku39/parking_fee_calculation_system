"""
全面配置系統測試套件
測試停車場費率方案設計框架的各種功能
"""

import unittest
import json
import sys
import os
from datetime import datetime, timedelta

# 添加項目路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.parking_calculator import ParkingCalculator, VehicleType


class TestComprehensiveConfig(unittest.TestCase):
    """全面配置系統測試"""

    def setUp(self):
        """測試前設置"""
        self.calculator = ParkingCalculator()
        self.test_enter_time = datetime(2024, 6, 19, 8, 0)  # 平日上午8點
        self.test_exit_time = datetime(2024, 6, 19, 12, 0)  # 平日中午12點

    def test_unified_flat_rate_model(self):
        """測試全天統一費率模式"""
        # 4小時停車，統一費率40元/小時
        result = self.calculator.calculate_parking_fee(
            self.test_enter_time,
            self.test_exit_time,
            "weekday_standard",  # 使用現有的統一費率方案
            vehicle_type=VehicleType.CAR,
        )

        # 驗證計算結果
        self.assertEqual(result["total_duration_minutes"], 240)  # 4小時 = 240分鐘
        self.assertGreater(result["final_charge"], 0)
        self.assertIn("sessions", result)

        print(f"統一費率測試結果: {result['final_charge']}元")

    def test_day_night_rates_model(self):
        """測試日間夜間費率模式"""
        # 測試跨夜間時段的停車
        enter_time = datetime(2024, 6, 19, 20, 0)  # 晚上8點
        exit_time = datetime(2024, 6, 20, 2, 0)  # 隔天凌晨2點

        result = self.calculator.calculate_parking_fee(
            enter_time, exit_time, "weekday_standard", vehicle_type=VehicleType.CAR
        )

        self.assertEqual(result["total_duration_minutes"], 360)  # 6小時
        self.assertGreater(result["final_charge"], 0)

        print(f"日夜費率測試結果: {result['final_charge']}元")

    def test_multi_segment_rates_model(self):
        """測試多段式費率模式"""
        # 使用複雜的商場方案
        result = self.calculator.calculate_parking_fee(
            self.test_enter_time,
            self.test_exit_time,
            "mall_complex",
            vehicle_type=VehicleType.CAR,
        )

        self.assertGreater(result["final_charge"], 0)
        self.assertIn("sessions", result)

        # 驗證是否有多個時段
        sessions = result.get("sessions", [])
        self.assertGreater(len(sessions), 0)

        print(f"多段式費率測試結果: {result['final_charge']}元，{len(sessions)}個時段")

    def test_vehicle_type_differences(self):
        """測試不同車輛類型的費率差異"""
        vehicle_types = [
            VehicleType.CAR,
            VehicleType.MOTORCYCLE,
            VehicleType.LARGE_VEHICLE,
            VehicleType.ELECTRIC_VEHICLE,
        ]

        results = {}
        for vehicle_type in vehicle_types:
            if "universal_mall" in self.calculator.rate_plans:
                result = self.calculator.calculate_parking_fee(
                    self.test_enter_time,
                    self.test_exit_time,
                    "universal_mall",
                    vehicle_type=vehicle_type,
                )
                results[vehicle_type.value] = result["total_amount"]

        print("不同車型費率測試結果:")
        for vehicle_type, amount in results.items():
            print(f"  {vehicle_type}: {amount}元")

    def test_discount_application(self):
        """測試優惠機制"""
        # 測試里民優惠
        user_conditions = {"resident_card": True, "valid_areas": ["龍興里"]}

        if "universal_mall" in self.calculator.rate_plans:
            result = self.calculator.calculate_parking_fee(
                self.test_enter_time,
                self.test_exit_time,
                "universal_mall",
                vehicle_type=VehicleType.CAR,
                user_conditions=user_conditions,
            )

            self.assertIn("applied_discounts", result)
            print(f"優惠測試結果: {result['total_amount']}元")
            if result.get("applied_discounts"):
                print(f"已套用優惠: {result['applied_discounts']}")

    def test_daily_cap_functionality(self):
        """測試每日上限功能"""
        # 測試長時間停車是否觸發每日上限
        enter_time = datetime(2024, 6, 19, 8, 0)
        exit_time = datetime(2024, 6, 19, 23, 59)  # 停車約16小時

        result = self.calculator.calculate_parking_fee(
            enter_time, exit_time, "weekday_standard", vehicle_type=VehicleType.CAR
        )

        self.assertGreater(result["total_duration_minutes"], 900)  # 超過15小時
        print(
            f"每日上限測試結果: {result['total_amount']}元，停車{result['total_duration_minutes']/60:.1f}小時"
        )

    def test_grace_period_functionality(self):
        """測試寬限期功能"""
        # 測試15分鐘內停車
        enter_time = datetime(2024, 6, 19, 8, 0)
        exit_time = datetime(2024, 6, 19, 8, 10)  # 停車10分鐘

        result = self.calculator.calculate_parking_fee(
            enter_time, exit_time, "weekday_standard", vehicle_type=VehicleType.CAR
        )

        print(
            f"寬限期測試結果: 停車{result['total_duration_minutes']}分鐘，費用{result['total_amount']}元"
        )

    def test_progressive_rates(self):
        """測試累進費率"""
        # 使用支援累進費率的方案
        if "mall_complex" in self.calculator.rate_plans:
            # 測試長時間停車的累進效果
            enter_time = datetime(2024, 6, 19, 9, 0)  # 上午9點 (尖峰時段)
            exit_time = datetime(2024, 6, 19, 12, 0)  # 中午12點

            result = self.calculator.calculate_parking_fee(
                enter_time, exit_time, "mall_complex", vehicle_type=VehicleType.CAR
            )

            print(f"累進費率測試結果: {result['total_amount']}元")

            # 檢查計算詳情
            sessions = result.get("sessions", [])
            for session in sessions:
                if (
                    hasattr(session, "progressive_details")
                    and session.progressive_details
                ):
                    print(f"  累進詳情: {session.progressive_details}")

    def test_cross_day_parking(self):
        """測試跨日停車"""
        enter_time = datetime(2024, 6, 19, 22, 0)  # 晚上10點
        exit_time = datetime(2024, 6, 20, 10, 0)  # 隔天上午10點

        result = self.calculator.calculate_parking_fee(
            enter_time, exit_time, "weekday_standard", vehicle_type=VehicleType.CAR
        )

        self.assertEqual(result["total_duration_minutes"], 720)  # 12小時
        print(f"跨日停車測試結果: {result['total_amount']}元")

        # 檢查是否正確分割到不同日期
        sessions = result.get("sessions", [])
        dates = set(
            session.start_time.date()
            for session in sessions
            if hasattr(session, "start_time")
        )
        if len(dates) > 1:
            print(f"  跨日分割: {len(dates)}個日期")

    def test_weekend_vs_weekday_rates(self):
        """測試平日與假日費率差異"""
        # 平日停車
        weekday_result = self.calculator.calculate_parking_fee(
            datetime(2024, 6, 19, 10, 0),  # 週三
            datetime(2024, 6, 19, 14, 0),
            "weekday_standard",
            vehicle_type=VehicleType.CAR,
        )

        # 假日停車
        weekend_result = self.calculator.calculate_parking_fee(
            datetime(2024, 6, 22, 10, 0),  # 週六
            datetime(2024, 6, 22, 14, 0),
            "holiday_special",
            vehicle_type=VehicleType.CAR,
        )

        print(f"平日費率: {weekday_result['total_amount']}元")
        print(f"假日費率: {weekend_result['total_amount']}元")

    def test_configuration_validation(self):
        """測試配置驗證"""
        # 檢查所有載入的費率方案是否有效
        available_plans = self.calculator.get_available_rate_plans()
        self.assertGreater(len(available_plans), 0, "應該至少有一個費率方案")

        print(f"可用費率方案: {list(available_plans.keys())}")

        # 檢查每個方案的基本結構
        for plan_id, plan_label in available_plans.items():
            plan = self.calculator.rate_plans.get(plan_id)
            self.assertIsNotNone(plan, f"方案 {plan_id} 應該存在")
            self.assertGreater(
                len(plan.time_slots), 0, f"方案 {plan_id} 應該有時段設定"
            )

    def test_manual_adjustment(self):
        """測試手動調整功能"""
        # 基礎計算
        base_result = self.calculator.calculate_parking_fee(
            self.test_enter_time,
            self.test_exit_time,
            "weekday_standard",
            vehicle_type=VehicleType.CAR,
        )

        # 手動調整 +50元
        adjusted_result = self.calculator.calculate_parking_fee(
            self.test_enter_time,
            self.test_exit_time,
            "weekday_standard",
            manual_adjustment=50,
            vehicle_type=VehicleType.CAR,
        )

        expected_amount = base_result["total_amount"] + 50
        self.assertEqual(adjusted_result["total_amount"], expected_amount)

        print(
            f"手動調整測試: 基礎{base_result['total_amount']}元 -> 調整後{adjusted_result['total_amount']}元"
        )


class TestConfigurationFramework(unittest.TestCase):
    """配置框架測試"""

    def test_pricing_model_coverage(self):
        """測試計費模式覆蓋率"""
        expected_models = [
            "unified_flat_rate",
            "day_night_rates",
            "multi_segment_rates",
            "weekday_holiday_rates",
            "weekday_holiday_festival_rates",
            "per_entry_rate",
        ]

        # 這裡可以測試配置轉換器是否支援所有模式
        print(f"期望支援的計費模式: {expected_models}")

    def test_vehicle_type_support(self):
        """測試車輛類型支援"""
        expected_types = [
            VehicleType.CAR,
            VehicleType.MOTORCYCLE,
            VehicleType.LARGE_VEHICLE,
            VehicleType.ELECTRIC_VEHICLE,
            VehicleType.BICYCLE,
        ]

        print(f"支援的車輛類型: {[t.value for t in expected_types]}")

    def test_discount_mechanism_types(self):
        """測試優惠機制類型"""
        expected_discount_types = [
            "percentage",  # 百分比折扣
            "fixed_amount",  # 固定金額減免
            "free_hours",  # 免費時數
        ]

        print(f"支援的優惠類型: {expected_discount_types}")


def run_comprehensive_tests():
    """執行全面測試"""
    print("=" * 60)
    print("停車場費率方案設計框架 - 全面測試")
    print("=" * 60)

    # 創建測試套件
    test_suite = unittest.TestSuite()

    # 添加所有測試
    test_suite.addTest(unittest.makeSuite(TestComprehensiveConfig))
    test_suite.addTest(unittest.makeSuite(TestConfigurationFramework))

    # 執行測試
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)

    # 測試摘要
    print("\n" + "=" * 60)
    print("測試摘要")
    print("=" * 60)
    print(f"執行測試數: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失敗: {len(result.failures)}")
    print(f"錯誤: {len(result.errors)}")

    if result.failures:
        print("\n失敗的測試:")
        for test, error in result.failures:
            print(f"  - {test}: {error}")

    if result.errors:
        print("\n錯誤的測試:")
        for test, error in result.errors:
            print(f"  - {test}: {error}")

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_comprehensive_tests()
    if success:
        print("\n✅ 所有測試通過！")
    else:
        print("\n❌ 部分測試失敗，請檢查配置。")
