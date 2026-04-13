"""
萬用停車計費模型測試
測試車輛類型、優惠機制、動態定價等功能
"""

import unittest
import sys
import os
from datetime import datetime

# 加入模組路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.parking_calculator import ParkingCalculator, VehicleType


class TestUniversalParkingCalculator(unittest.TestCase):
    """萬用停車計費模型測試"""

    def setUp(self):
        """設定測試環境"""
        # 使用萬用計費模型配置
        self.calculator = ParkingCalculator("config/universal_rate_plans.json")

    def test_basic_car_calculation(self):
        """測試基本汽車計費"""
        enter_time = datetime.strptime("2024-06-19 08:00", "%Y-%m-%d %H:%M")
        exit_time = datetime.strptime("2024-06-19 12:00", "%Y-%m-%d %H:%M")

        result = self.calculator.calculate_parking_fee(
            enter_time, exit_time, "universal_mall", 0, VehicleType.CAR
        )

        self.assertTrue(result["final_charge"] > 0)
        self.assertEqual(result["vehicle_type"], "car")
        self.assertEqual(result["vehicle_rate_multiplier"], 1.0)

    def test_motorcycle_calculation(self):
        """測試機車計費（50%費率）"""
        enter_time = datetime.strptime("2024-06-19 08:00", "%Y-%m-%d %H:%M")
        exit_time = datetime.strptime("2024-06-19 12:00", "%Y-%m-%d %H:%M")

        # 汽車費用
        car_result = self.calculator.calculate_parking_fee(
            enter_time, exit_time, "universal_mall", 0, VehicleType.CAR
        )

        # 機車費用
        motorcycle_result = self.calculator.calculate_parking_fee(
            enter_time, exit_time, "universal_mall", 0, VehicleType.MOTORCYCLE
        )

        self.assertEqual(motorcycle_result["vehicle_type"], "motorcycle")
        self.assertEqual(motorcycle_result["vehicle_rate_multiplier"], 0.5)
        # 機車費用應該大約是汽車費用的一半
        self.assertLess(motorcycle_result["final_charge"], car_result["final_charge"])

    def test_large_vehicle_calculation(self):
        """測試大型車計費（150%費率）"""
        enter_time = datetime.strptime("2024-06-19 08:00", "%Y-%m-%d %H:%M")
        exit_time = datetime.strptime("2024-06-19 12:00", "%Y-%m-%d %H:%M")

        # 汽車費用
        car_result = self.calculator.calculate_parking_fee(
            enter_time, exit_time, "universal_mall", 0, VehicleType.CAR
        )

        # 大型車費用
        large_result = self.calculator.calculate_parking_fee(
            enter_time, exit_time, "universal_mall", 0, VehicleType.LARGE_VEHICLE
        )

        self.assertEqual(large_result["vehicle_type"], "large_vehicle")
        self.assertEqual(large_result["vehicle_rate_multiplier"], 1.5)
        # 大型車費用應該高於汽車
        self.assertGreater(large_result["final_charge"], car_result["final_charge"])

    def test_electric_vehicle_discount(self):
        """測試電動車優惠（80%費率）"""
        enter_time = datetime.strptime("2024-06-19 08:00", "%Y-%m-%d %H:%M")
        exit_time = datetime.strptime("2024-06-19 12:00", "%Y-%m-%d %H:%M")

        # 汽車費用
        car_result = self.calculator.calculate_parking_fee(
            enter_time, exit_time, "universal_mall", 0, VehicleType.CAR
        )

        # 電動車費用
        ev_result = self.calculator.calculate_parking_fee(
            enter_time, exit_time, "universal_mall", 0, VehicleType.ELECTRIC_VEHICLE
        )

        self.assertEqual(ev_result["vehicle_type"], "electric_vehicle")
        self.assertEqual(ev_result["vehicle_rate_multiplier"], 0.8)
        # 電動車費用應該低於汽車
        self.assertLess(ev_result["final_charge"], car_result["final_charge"])

    def test_resident_discount(self):
        """測試里民優惠（20%折扣）"""
        enter_time = datetime.strptime("2024-06-19 08:00", "%Y-%m-%d %H:%M")
        exit_time = datetime.strptime("2024-06-19 12:00", "%Y-%m-%d %H:%M")

        user_conditions = {"is_resident": True}

        result = self.calculator.calculate_parking_fee(
            enter_time, exit_time, "universal_mall", 0, VehicleType.CAR, user_conditions
        )

        self.assertTrue(len(result["discounts_applied"]) > 0)
        self.assertEqual(result["discounts_applied"][0]["discount_id"], "resident")

    def test_disabled_discount(self):
        """測試身心障礙優惠（固定金額折扣）"""
        enter_time = datetime.strptime("2024-06-19 08:00", "%Y-%m-%d %H:%M")
        exit_time = datetime.strptime("2024-06-19 12:00", "%Y-%m-%d %H:%M")

        user_conditions = {"has_disability_card": True}

        result = self.calculator.calculate_parking_fee(
            enter_time, exit_time, "universal_mall", 0, VehicleType.CAR, user_conditions
        )

        disabled_discount = None
        for discount in result["discounts_applied"]:
            if discount["discount_id"] == "disabled":
                disabled_discount = discount
                break

        self.assertIsNotNone(disabled_discount)
        self.assertEqual(disabled_discount["amount"], 90)  # 固定90元折扣

    def test_consumption_discount(self):
        """測試消費折抵優惠"""
        enter_time = datetime.strptime("2024-06-19 08:00", "%Y-%m-%d %H:%M")
        exit_time = datetime.strptime("2024-06-19 12:00", "%Y-%m-%d %H:%M")

        # 消費滿500元
        user_conditions = {"consumption_amount": 500}

        result = self.calculator.calculate_parking_fee(
            enter_time, exit_time, "universal_mall", 0, VehicleType.CAR, user_conditions
        )

        consumption_discount = None
        for discount in result["discounts_applied"]:
            if discount["discount_id"] == "consumption":
                consumption_discount = discount
                break

        self.assertIsNotNone(consumption_discount)
        self.assertEqual(consumption_discount["amount"], 60)  # 60元折扣

    def test_credit_card_discount(self):
        """測試信用卡優惠"""
        enter_time = datetime.strptime("2024-06-19 08:00", "%Y-%m-%d %H:%M")
        exit_time = datetime.strptime("2024-06-19 12:00", "%Y-%m-%d %H:%M")

        user_conditions = {"credit_card_type": "玉山銀行"}

        result = self.calculator.calculate_parking_fee(
            enter_time, exit_time, "universal_mall", 0, VehicleType.CAR, user_conditions
        )

        credit_discount = None
        for discount in result["discounts_applied"]:
            if discount["discount_id"] == "credit_card":
                credit_discount = discount
                break

        self.assertIsNotNone(credit_discount)

    def test_member_discount(self):
        """測試會員優惠"""
        enter_time = datetime.strptime("2024-06-19 08:00", "%Y-%m-%d %H:%M")
        exit_time = datetime.strptime("2024-06-19 12:00", "%Y-%m-%d %H:%M")

        user_conditions = {"member_level": "VIP"}

        result = self.calculator.calculate_parking_fee(
            enter_time, exit_time, "universal_mall", 0, VehicleType.CAR, user_conditions
        )

        member_discount = None
        for discount in result["discounts_applied"]:
            if discount["discount_id"] == "member":
                member_discount = discount
                break

        self.assertIsNotNone(member_discount)
        self.assertEqual(member_discount["amount"], 30)  # 30元固定折扣

    def test_multiple_discounts_stackable(self):
        """測試多重優惠疊加"""
        enter_time = datetime.strptime("2024-06-19 08:00", "%Y-%m-%d %H:%M")
        exit_time = datetime.strptime("2024-06-19 12:00", "%Y-%m-%d %H:%M")

        # 同時擁有里民優惠、消費折抵和信用卡優惠
        user_conditions = {
            "is_resident": True,
            "consumption_amount": 500,
            "credit_card_type": "玉山銀行",
        }

        result = self.calculator.calculate_parking_fee(
            enter_time, exit_time, "universal_mall", 0, VehicleType.CAR, user_conditions
        )

        # 應該有多個優惠被應用
        self.assertGreater(len(result["discounts_applied"]), 1)

    def test_dynamic_pricing_occupancy(self):
        """測試佔用率動態定價"""
        enter_time = datetime.strptime("2024-06-19 08:00", "%Y-%m-%d %H:%M")
        exit_time = datetime.strptime("2024-06-19 12:00", "%Y-%m-%d %H:%M")

        # 高佔用率情況
        dynamic_context = {"occupancy_rate": 0.9}

        result = self.calculator.calculate_parking_fee(
            enter_time,
            exit_time,
            "universal_mall",
            0,
            VehicleType.CAR,
            None,
            dynamic_context,
        )

        self.assertTrue(result["dynamic_pricing_applied"])

    def test_dynamic_pricing_event(self):
        """測試事件動態定價"""
        enter_time = datetime.strptime("2024-06-19 08:00", "%Y-%m-%d %H:%M")
        exit_time = datetime.strptime("2024-06-19 12:00", "%Y-%m-%d %H:%M")

        # 演唱會事件
        dynamic_context = {"event_type": "concert"}

        result = self.calculator.calculate_parking_fee(
            enter_time,
            exit_time,
            "universal_mall",
            0,
            VehicleType.CAR,
            None,
            dynamic_context,
        )

        self.assertTrue(result["dynamic_pricing_applied"])

    def test_motorcycle_simple_plan(self):
        """測試機車簡單計次收費方案"""
        enter_time = datetime.strptime("2024-06-19 08:00", "%Y-%m-%d %H:%M")
        exit_time = datetime.strptime("2024-06-19 18:00", "%Y-%m-%d %H:%M")

        result = self.calculator.calculate_parking_fee(
            enter_time, exit_time, "simple_motorcycle", 0, VehicleType.MOTORCYCLE
        )

        # 應該是固定費用（計次收費）
        self.assertEqual(result["final_charge"], 30)  # 30元計次收費

    def test_motorcycle_simple_plan_with_resident_discount(self):
        """測試機車簡單方案的里民優惠"""
        enter_time = datetime.strptime("2024-06-19 08:00", "%Y-%m-%d %H:%M")
        exit_time = datetime.strptime("2024-06-19 18:00", "%Y-%m-%d %H:%M")

        user_conditions = {"is_resident": True}

        result = self.calculator.calculate_parking_fee(
            enter_time,
            exit_time,
            "simple_motorcycle",
            0,
            VehicleType.MOTORCYCLE,
            user_conditions,
        )

        # 應該有里民優惠
        self.assertTrue(len(result["discounts_applied"]) > 0)
        self.assertEqual(result["final_charge"], 20)  # 30 - 10 = 20元

    def test_comprehensive_scenario(self):
        """測試綜合場景：電動車 + 多重優惠 + 動態定價"""
        enter_time = datetime.strptime("2024-06-19 08:00", "%Y-%m-%d %H:%M")
        exit_time = datetime.strptime("2024-06-19 16:00", "%Y-%m-%d %H:%M")

        user_conditions = {
            "is_resident": True,
            "consumption_amount": 1000,
            "member_level": "VIP",
        }

        dynamic_context = {"occupancy_rate": 0.7, "event_type": "sale_event"}

        result = self.calculator.calculate_parking_fee(
            enter_time,
            exit_time,
            "universal_mall",
            0,
            VehicleType.ELECTRIC_VEHICLE,
            user_conditions,
            dynamic_context,
        )

        # 檢查各種功能是否被應用
        self.assertEqual(result["vehicle_type"], "electric_vehicle")
        self.assertEqual(result["vehicle_rate_multiplier"], 0.8)
        self.assertTrue(len(result["discounts_applied"]) > 0)
        self.assertTrue(result["dynamic_pricing_applied"])

        # 檢查功能標記
        features = result["features_used"]
        self.assertTrue(
            any(
                [
                    result["vehicle_rate_multiplier"] != 1.0,
                    len(result["discounts_applied"]) > 0,
                    result["dynamic_pricing_applied"],
                ]
            )
        )


if __name__ == "__main__":
    unittest.main()
