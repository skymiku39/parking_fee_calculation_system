"""
停車場配置轉換工具
將全面的停車場費率配置轉換為系統可用的格式
"""

import json
from typing import Dict, List, Any
from datetime import datetime


class ConfigurationConverter:
    """配置轉換器"""

    def __init__(self):
        self.pricing_model_handlers = {
            "unified_flat_rate": self._convert_unified_flat_rate,
            "day_night_rates": self._convert_day_night_rates,
            "multi_segment_rates": self._convert_multi_segment_rates,
            "weekday_holiday_rates": self._convert_weekday_holiday_rates,
            "weekday_holiday_festival_rates": self._convert_weekday_holiday_festival_rates,
            "per_entry_rate": self._convert_per_entry_rate,
        }

    def convert_comprehensive_config(
        self, comprehensive_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        將全面配置轉換為系統可用格式

        Args:
            comprehensive_config: 全面配置數據

        Returns:
            系統可用的費率配置
        """
        parking_lot_info = comprehensive_config.get("parking_lot_info", {})
        pricing_model = comprehensive_config.get("pricing_model")

        # 基礎配置
        system_config = {
            "description": f"由全面配置轉換 - {parking_lot_info.get('lot_name', '未命名停車場')}",
            "version": "3.0",
            "converted_at": datetime.now().isoformat(),
            "rate_plans": [],
        }

        # 根據計費模式轉換
        if pricing_model in self.pricing_model_handlers:
            rate_plan = self.pricing_model_handlers[pricing_model](comprehensive_config)
            system_config["rate_plans"].append(rate_plan)
        else:
            raise ValueError(f"不支援的計費模式: {pricing_model}")

        return system_config

    def _convert_unified_flat_rate(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """轉換全天統一費率"""
        parking_info = config.get("parking_lot_info", {})

        return {
            "rate_plan_id": "unified_flat_rate",
            "label": "全天統一費率",
            "description": "24小時單一固定費率",
            "date_type": "all",
            "apply_on_holiday": True,
            "daily_cap_enabled": True,
            "daily_cap_amount": config.get("unified_daily_cap", 300),
            "split_by_timeslot_enabled": False,
            "split_by_day_enabled": False,
            "night_cross_day_split": False,
            "enable_zero_fee": True,
            "round_up_enabled": True,
            "skip_fee_when_total_free": True,
            "manual_override_enabled": True,
            "time_slots": [
                {
                    "time_slot_id": "all_day",
                    "label": "全日統一",
                    "start": "00:00",
                    "end": "24:00",
                    "unit_minutes": parking_info.get("min_billing_unit", 60),
                    "grace_minutes": parking_info.get("grace_period_minutes", 15),
                    "grace_enabled": True,
                    "cap_enabled": True,
                    "cap_amount": config.get("unified_daily_cap", 300),
                    "progressive_enabled": False,
                    "default_unit_price": config.get("unified_car_rate", 40),
                    "progressive_rates": [],
                }
            ],
            "vehicle_type_configs": self._convert_vehicle_type_configs(config),
            "discount_rules": self._convert_discount_rules(config),
            "monthly_rental_plans": self._convert_monthly_rental_plans(config),
            "dynamic_pricing": self._convert_dynamic_pricing_config(config),
        }

    def _convert_day_night_rates(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """轉換日間夜間費率"""
        parking_info = config.get("parking_lot_info", {})

        return {
            "rate_plan_id": "day_night_rates",
            "label": "日間夜間費率",
            "description": "區分日間與夜間的兩段式費率",
            "date_type": "all",
            "apply_on_holiday": True,
            "daily_cap_enabled": True,
            "daily_cap_amount": config.get("daily_cap", 350),
            "split_by_timeslot_enabled": True,
            "split_by_day_enabled": True,
            "night_cross_day_split": True,
            "enable_zero_fee": True,
            "round_up_enabled": True,
            "skip_fee_when_total_free": True,
            "manual_override_enabled": True,
            "time_slots": [
                {
                    "time_slot_id": "day",
                    "label": "日間時段",
                    "start": "07:00",
                    "end": "22:00",
                    "unit_minutes": parking_info.get("min_billing_unit", 60),
                    "grace_minutes": parking_info.get("grace_period_minutes", 15),
                    "grace_enabled": True,
                    "cap_enabled": True,
                    "cap_amount": config.get("day_cap", 250),
                    "progressive_enabled": False,
                    "default_unit_price": config.get("day_car_rate", 50),
                    "progressive_rates": [],
                },
                {
                    "time_slot_id": "night",
                    "label": "夜間時段",
                    "start": "22:00",
                    "end": "07:00",
                    "unit_minutes": parking_info.get("min_billing_unit", 60),
                    "grace_minutes": 0,
                    "grace_enabled": False,
                    "cap_enabled": True,
                    "cap_amount": config.get("night_cap", 100),
                    "progressive_enabled": False,
                    "default_unit_price": config.get("night_car_rate", 20),
                    "progressive_rates": [],
                },
            ],
            "vehicle_type_configs": self._convert_vehicle_type_configs(config),
            "discount_rules": self._convert_discount_rules(config),
            "monthly_rental_plans": self._convert_monthly_rental_plans(config),
            "dynamic_pricing": self._convert_dynamic_pricing_config(config),
        }

    def _convert_multi_segment_rates(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """轉換多段式費率"""
        time_slots = []
        time_slot_configs = config.get("time_slots", [])

        for i, slot_config in enumerate(time_slot_configs):
            time_slot = {
                "time_slot_id": f"segment_{i+1}",
                "label": slot_config.get("label", f"時段{i+1}"),
                "start": slot_config.get("start_time", "00:00"),
                "end": slot_config.get("end_time", "24:00"),
                "unit_minutes": slot_config.get("unit_minutes", 30),
                "grace_minutes": slot_config.get("grace_minutes", 0),
                "grace_enabled": slot_config.get("grace_enabled", True),
                "cap_enabled": slot_config.get("cap_enabled", True),
                "cap_amount": slot_config.get("cap_amount", 100),
                "progressive_enabled": slot_config.get("progressive_enabled", False),
                "default_unit_price": slot_config.get("unit_price", 30),
                "progressive_rates": slot_config.get("progressive_rates", []),
            }
            time_slots.append(time_slot)

        return {
            "rate_plan_id": "multi_segment_rates",
            "label": "多段式費率",
            "description": "按不同時段設定的複雜費率規則",
            "date_type": "all",
            "apply_on_holiday": True,
            "daily_cap_enabled": True,
            "daily_cap_amount": config.get("daily_cap", 400),
            "split_by_timeslot_enabled": True,
            "split_by_day_enabled": True,
            "night_cross_day_split": True,
            "enable_zero_fee": True,
            "round_up_enabled": True,
            "skip_fee_when_total_free": True,
            "manual_override_enabled": True,
            "time_slots": time_slots,
            "vehicle_type_configs": self._convert_vehicle_type_configs(config),
            "discount_rules": self._convert_discount_rules(config),
            "monthly_rental_plans": self._convert_monthly_rental_plans(config),
            "dynamic_pricing": self._convert_dynamic_pricing_config(config),
        }

    def _convert_weekday_holiday_rates(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """轉換平日假日費率"""
        return {
            "rate_plan_id": "weekday_holiday_rates",
            "label": "平日假日費率",
            "description": "區分平日與假日的差異化費率",
            "date_type": "weekday",
            "apply_on_holiday": False,
            "daily_cap_enabled": True,
            "daily_cap_amount": config.get("weekday_cap", 350),
            "holiday_cap_amount": config.get("holiday_cap", 500),
            "split_by_timeslot_enabled": False,
            "split_by_day_enabled": True,
            "night_cross_day_split": False,
            "enable_zero_fee": True,
            "round_up_enabled": True,
            "skip_fee_when_total_free": True,
            "manual_override_enabled": True,
            "time_slots": [
                {
                    "time_slot_id": "weekday",
                    "label": "平日費率",
                    "start": "00:00",
                    "end": "24:00",
                    "unit_minutes": 60,
                    "grace_minutes": 15,
                    "grace_enabled": True,
                    "cap_enabled": True,
                    "cap_amount": config.get("weekday_cap", 350),
                    "progressive_enabled": False,
                    "default_unit_price": config.get("weekday_rate", 30),
                    "progressive_rates": [],
                },
                {
                    "time_slot_id": "holiday",
                    "label": "假日費率",
                    "start": "00:00",
                    "end": "24:00",
                    "unit_minutes": 60,
                    "grace_minutes": 15,
                    "grace_enabled": True,
                    "cap_enabled": True,
                    "cap_amount": config.get("holiday_cap", 500),
                    "progressive_enabled": False,
                    "default_unit_price": config.get("holiday_rate", 70),
                    "progressive_rates": [],
                },
            ],
            "vehicle_type_configs": self._convert_vehicle_type_configs(config),
            "discount_rules": self._convert_discount_rules(config),
            "monthly_rental_plans": self._convert_monthly_rental_plans(config),
            "dynamic_pricing": self._convert_dynamic_pricing_config(config),
        }

    def _convert_weekday_holiday_festival_rates(
        self, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """轉換平日假日節慶費率"""
        rate_plan = self._convert_weekday_holiday_rates(config)
        rate_plan["rate_plan_id"] = "weekday_holiday_festival_rates"
        rate_plan["label"] = "平日假日節慶費率"
        rate_plan["description"] = "區分平日、假日與節慶假日的三段式費率"
        rate_plan["festival_cap_amount"] = config.get("festival_cap", 600)
        rate_plan["festival_holidays"] = config.get("festival_holidays", [])

        # 新增節慶假日時段
        festival_slot = {
            "time_slot_id": "festival",
            "label": "節慶假日費率",
            "start": "00:00",
            "end": "24:00",
            "unit_minutes": 60,
            "grace_minutes": 10,
            "grace_enabled": True,
            "cap_enabled": True,
            "cap_amount": config.get("festival_cap", 600),
            "progressive_enabled": False,
            "default_unit_price": config.get("festival_rate", 80),
            "progressive_rates": [],
        }
        rate_plan["time_slots"].append(festival_slot)

        return rate_plan

    def _convert_per_entry_rate(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """轉換計次收費"""
        return {
            "rate_plan_id": "per_entry_rate",
            "label": "計次收費",
            "description": "每次進出收取固定費用",
            "date_type": "all",
            "apply_on_holiday": True,
            "daily_cap_enabled": False,
            "split_by_timeslot_enabled": False,
            "split_by_day_enabled": False,
            "night_cross_day_split": False,
            "enable_zero_fee": True,
            "round_up_enabled": False,
            "skip_fee_when_total_free": True,
            "manual_override_enabled": True,
            "per_entry_fees": {
                "car": config.get("car_entry_fee", 0),
                "motorcycle": config.get("motorcycle_entry_fee", 20),
                "bicycle": config.get("bicycle_entry_fee", 5),
            },
            "vehicle_type_configs": self._convert_vehicle_type_configs(config),
            "discount_rules": self._convert_discount_rules(config),
            "monthly_rental_plans": self._convert_monthly_rental_plans(config),
        }

    def _convert_vehicle_type_configs(
        self, config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """轉換車輛類型配置"""
        vehicle_configs = []
        vehicle_type_data = config.get("vehicle_type_configs", [])

        for vehicle_config in vehicle_type_data:
            vehicle_type_config = {
                "vehicle_type": vehicle_config.get("vehicle_type", "car"),
                "rate_multiplier": vehicle_config.get("rate_multiplier", 1.0),
                "daily_cap_multiplier": vehicle_config.get("daily_cap_multiplier", 1.0),
                "grace_period_multiplier": vehicle_config.get(
                    "grace_period_multiplier", 1.0
                ),
                "applicable_discounts": vehicle_config.get("applicable_discounts", []),
            }
            vehicle_configs.append(vehicle_type_config)

        return vehicle_configs

    def _convert_discount_rules(self, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """轉換優惠規則"""
        discount_rules = []
        discount_data = config.get("discount_rules", [])

        for discount_config in discount_data:
            discount_rule = {
                "discount_id": discount_config.get("discount_id", ""),
                "discount_type": discount_config.get("discount_type", "percentage"),
                "name": discount_config.get("name", ""),
                "description": discount_config.get("description", ""),
                "discount_value": discount_config.get("discount_value", 0),
                "discount_mode": discount_config.get("discount_mode", "percentage"),
                "eligibility_conditions": discount_config.get(
                    "eligibility_conditions", {}
                ),
                "daily_limit": discount_config.get("daily_limit", 1),
                "monthly_limit": discount_config.get("monthly_limit"),
                "max_discount_amount": discount_config.get("max_discount_amount"),
                "stackable": discount_config.get("stackable", True),
                "priority": discount_config.get("priority", 5),
            }
            discount_rules.append(discount_rule)

        return discount_rules

    def _convert_monthly_rental_plans(
        self, config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """轉換月租方案"""
        monthly_plans = []
        plan_data = config.get("monthly_rental_plans", [])

        for plan_config in plan_data:
            monthly_plan = {
                "plan_id": plan_config.get("plan_id", ""),
                "name": plan_config.get("name", ""),
                "monthly_fee": plan_config.get("monthly_fee", {}),
                "access_hours": plan_config.get("access_hours", "24hours"),
                "eligibility_requirements": plan_config.get(
                    "eligibility_requirements", ""
                ),
                "deposit_required": plan_config.get("deposit_required", True),
                "deposit_amount": plan_config.get("deposit_amount", ""),
                "minimum_rental_period": plan_config.get("minimum_rental_period", 1),
            }
            monthly_plans.append(monthly_plan)

        return monthly_plans

    def _convert_dynamic_pricing_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """轉換動態定價配置"""
        dynamic_config = config.get("dynamic_pricing", {})

        if not dynamic_config.get("enabled", False):
            return {"enabled": False}

        return {
            "enabled": True,
            "occupancy_thresholds": dynamic_config.get("occupancy_thresholds", []),
            "event_multipliers": dynamic_config.get("event_multipliers", {}),
            "weather_adjustments": dynamic_config.get("weather_adjustments", {}),
            "time_based_adjustments": dynamic_config.get("time_based_adjustments", {}),
        }

    def generate_configuration_form_data(
        self, template_name: str = "comprehensive"
    ) -> Dict[str, Any]:
        """
        生成配置表單的預設數據

        Args:
            template_name: 模板名稱

        Returns:
            表單預設數據
        """
        if template_name == "comprehensive":
            return {
                "parking_lot_info": {
                    "lot_name": "範例停車場",
                    "lot_type": "commercial_complex",
                    "operating_hours": "24hours",
                    "min_billing_unit": 30,
                    "grace_period_minutes": 15,
                },
                "pricing_models": [
                    {
                        "id": "unified_flat_rate",
                        "name": "全天統一費率",
                        "description": "24小時使用相同費率，簡單易懂",
                    },
                    {
                        "id": "day_night_rates",
                        "name": "日間夜間費率",
                        "description": "區分日間與夜間的兩段式費率",
                    },
                    {
                        "id": "multi_segment_rates",
                        "name": "多段式費率",
                        "description": "按不同時段設定的複雜費率規則",
                    },
                    {
                        "id": "weekday_holiday_rates",
                        "name": "平日/假日費率",
                        "description": "區分平日與假日的差異化費率",
                    },
                    {
                        "id": "weekday_holiday_festival_rates",
                        "name": "平日/假日/節慶費率",
                        "description": "三段式費率，包含節慶假日特殊定價",
                    },
                    {
                        "id": "per_entry_rate",
                        "name": "計次收費",
                        "description": "每次進出收取固定費用",
                    },
                ],
                "default_vehicle_types": [
                    {"type": "car", "label": "汽車", "multiplier": 1.0},
                    {"type": "motorcycle", "label": "機車", "multiplier": 0.4},
                    {"type": "large_vehicle", "label": "大型車", "multiplier": 1.8},
                    {"type": "electric_vehicle", "label": "電動車", "multiplier": 0.7},
                    {"type": "bicycle", "label": "自行車", "multiplier": 0.1},
                ],
                "default_discount_types": [
                    {"id": "resident", "name": "里民優惠", "type": "percentage"},
                    {"id": "disabled", "name": "身心障礙優惠", "type": "free_hours"},
                    {"id": "consumption", "name": "消費折抵", "type": "free_hours"},
                    {"id": "credit_card", "name": "信用卡優惠", "type": "percentage"},
                    {
                        "id": "mobile_payment",
                        "name": "行動支付優惠",
                        "type": "free_hours",
                    },
                    {"id": "student", "name": "學生優惠", "type": "percentage"},
                    {"id": "member", "name": "會員優惠", "type": "fixed_amount"},
                ],
            }

        return {}


def main():
    """測試配置轉換器"""
    converter = ConfigurationConverter()

    # 測試全天統一費率轉換
    test_config = {
        "parking_lot_info": {
            "lot_name": "測試停車場",
            "lot_type": "commercial_complex",
            "operating_hours": "24hours",
            "min_billing_unit": 30,
            "grace_period_minutes": 15,
        },
        "pricing_model": "unified_flat_rate",
        "unified_car_rate": 40,
        "unified_motorcycle_rate": 10,
        "unified_daily_cap": 300,
        "vehicle_type_configs": [
            {
                "vehicle_type": "car",
                "rate_multiplier": 1.0,
                "daily_cap_multiplier": 1.0,
                "grace_period_multiplier": 1.0,
                "applicable_discounts": ["resident", "disabled"],
            }
        ],
        "discount_rules": [
            {
                "discount_id": "resident",
                "discount_type": "resident",
                "name": "里民優惠",
                "description": "設籍居民享8折優惠",
                "discount_value": 0.2,
                "discount_mode": "percentage",
                "eligibility_conditions": {"required_documents": ["resident_card"]},
                "daily_limit": 1,
                "stackable": True,
                "priority": 5,
            }
        ],
    }

    # 轉換配置
    system_config = converter.convert_comprehensive_config(test_config)

    # 輸出結果
    print("轉換結果:")
    print(json.dumps(system_config, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
