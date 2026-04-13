import json
import logging
import os
from datetime import datetime, timedelta, time
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union

from utils.config_validator import (
    validate_user_defined_plans_json,
    validate_multidimensional_config_json,
    ConfigValidationError,
)
from src.multidimensional_calculator import (
    MultidimensionalParkingCalculator,
)
from src.rate_plan_manager import RatePlanManager
from src.core.utils import (
    format_duration_display,
    get_rate_description,
    merge_system_config,
    validate_and_normalize_system_config,
)


logger = logging.getLogger(__name__)


class SmartParkingSystem:
    def __init__(self, base_path: Optional[Union[str, Path]] = None):
        self.base_path = Path(base_path) if base_path is not None else Path(".")
        self.rate_plan_manager = RatePlanManager(str(self.base_path / "config"))
        self.multidimensional_calculator: Optional[MultidimensionalParkingCalculator] = None
        self.system_config: Dict[str, Any] = {}
        self.persisted_system_config: Dict[str, Any] = {}

        self.load_system_config()
        self.init_multidimensional_calculator()

    def _config_path(self, *parts: str) -> Path:
        return self.base_path.joinpath(*parts)

    def load_system_config(self):
        try:
            config_path = self._config_path("config", "system_config.json")
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    file_cfg = json.load(f)
            else:
                file_cfg = {}

            self.persisted_system_config = validate_and_normalize_system_config(
                file_cfg,
                include_env_overrides=False,
            )
            self.system_config = validate_and_normalize_system_config(
                self.persisted_system_config
            )
        except Exception as e:
            logger.exception("載入系統配置失敗: %s", e)
            self.persisted_system_config = {}
            self.system_config = {}

    def save_system_config(self):
        try:
            config_path = self._config_path("config", "system_config.json")
            config_path.parent.mkdir(exist_ok=True)
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(self.persisted_system_config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.exception("Failed to save system config: %s", e)

    def update_system_config(self, new_config: Dict[str, Any]) -> Dict[str, Any]:
        merged_config = merge_system_config(self.persisted_system_config, new_config)
        self.persisted_system_config = validate_and_normalize_system_config(
            merged_config,
            include_env_overrides=False,
        )
        self.system_config = validate_and_normalize_system_config(
            self.persisted_system_config
        )
        self.save_system_config()
        return self.system_config

    def init_multidimensional_calculator(self):
        try:
            cfg_path = self._config_path("config", "multidimensional_rate_plans.json")
            if cfg_path.exists():
                with open(cfg_path, "r", encoding="utf-8") as f:
                    _cfg = json.load(f)
                validate_multidimensional_config_json(_cfg)

            self.multidimensional_calculator = MultidimensionalParkingCalculator(
                str(cfg_path)
            )
            logger.info("多維度標籤計算器載入成功")
        except Exception as e:
            logger.exception("多維度標籤計算器載入失敗: %s", e)

    # ====== 計算相關（包含舊用戶自訂方案能力，避免破壞既有行為） ======
    def calculate_parking_fee(
        self,
        enter_time: datetime,
        exit_time: datetime,
        plan_id: Optional[str] = None,
        manual_adjustment: int = 0,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        try:
            if not plan_id:
                raise ValueError("請提供 plan_id 或使用 plan_inline 進行即時試算")

            if self.is_user_defined_plan(plan_id):
                return self.calculate_with_user_defined_plan(
                    enter_time, exit_time, plan_id, manual_adjustment, context
                )
            else:
                return self.calculate_with_multidimensional(
                    enter_time, exit_time, plan_id, manual_adjustment, context
                )
        except Exception as e:
            return {"success": False, "error": str(e), "calculation_engine": "none"}

    def is_user_defined_plan(self, plan_id: str) -> bool:
        try:
            with open(self._config_path("config", "user_defined_plans.json"), "r", encoding="utf-8") as f:
                user_plans = json.load(f)
                return plan_id in user_plans.get("plans", {})
        except FileNotFoundError:
            return False

    def calculate_with_user_defined_plan(
        self,
        enter_time: datetime,
        exit_time: datetime,
        plan_id: str,
        manual_adjustment: int = 0,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        try:
            with open(self._config_path("config", "user_defined_plans.json"), "r", encoding="utf-8") as f:
                user_plans = json.load(f)
            try:
                validate_user_defined_plans_json(user_plans)
            except ConfigValidationError as ve:
                return {
                    "success": False,
                    "code": "INVALID_CONFIG",
                    "message": f"用戶方案配置不合法: {', '.join(ve.errors) if ve.errors else str(ve)}",
                }

            if plan_id not in user_plans.get("plans", {}):
                raise ValueError(f"找不到用戶自訂方案: {plan_id}")

            plan_data = user_plans["plans"][plan_id]
            result = self.calculate_fee_by_billing_cycles(
                enter_time=enter_time,
                exit_time=exit_time,
                plan_data=plan_data,
                manual_adjustment=manual_adjustment,
            )
            return result
        except Exception as e:
            return {
                "success": False,
                "error": f"用戶自訂方案計算失敗: {str(e)}",
                "calculation_engine": "user_defined_billing_cycle",
            }

    def calculate_fee_by_billing_cycles(
        self,
        enter_time: datetime,
        exit_time: datetime,
        plan_data: dict,
        manual_adjustment: int = 0,
    ) -> Dict[str, Any]:
        try:
            total_minutes = int((exit_time - enter_time).total_seconds() / 60)

            date_category = self.determine_date_category(
                enter_time, plan_data["holiday_type"]
            )

            global_grace_time = plan_data.get("global_grace_time", 0)

            segments = plan_data.get("segments", [])
            rate_matrix = plan_data.get("rate_matrix", {})

            if plan_data["segment_type"] == "全天":
                segment_key = f"全天_{date_category}"
                if segment_key in rate_matrix:
                    rate_config = rate_matrix[segment_key]
                    total_amount = self.calculate_segment_fee(
                        total_minutes, rate_config, global_grace_time
                    )
                    session_details = [
                        {
                            "period": f"{enter_time.strftime('%H:%M')}-{exit_time.strftime('%H:%M')}",
                            "duration": format_duration_display(total_minutes),
                            "rate": get_rate_description(rate_config),
                            "amount": total_amount,
                            "date": enter_time.strftime("%m-%d"),
                        }
                    ]
                    calculation_summary = f"全天費率 {total_minutes}分鐘"
                else:
                    total_amount = 0
                    session_details = []
                    calculation_summary = "無適用費率"
            else:
                billing_cycles, total_amount = self.generate_billing_cycles(
                    enter_time,
                    exit_time,
                    segments,
                    rate_matrix,
                    plan_data["holiday_type"],
                    global_grace_time,
                )
                session_details, calculation_summary = self.consolidate_billing_cycles(
                    billing_cycles, enter_time, plan_data["holiday_type"]
                )

            global_caps = plan_data.get("global_caps", {})
            cap_applied = False
            cap_amount = None
            original_amount = total_amount
            if global_caps.get("daily_cap_enabled") and global_caps.get(
                "daily_cap_amount"
            ):
                daily_cap = global_caps["daily_cap_amount"]
                if total_amount > daily_cap:
                    total_amount = daily_cap
                    cap_applied = True
                    cap_amount = daily_cap

            total_amount += manual_adjustment

            primary_date_category = self.determine_date_category(
                enter_time, plan_data["holiday_type"]
            )

            return {
                "success": True,
                "calculation_engine": "user_defined_billing_cycle",
                "total_amount": total_amount,
                "original_amount": original_amount,
                "manual_adjustment": manual_adjustment,
                "cap_applied": cap_applied,
                "cap_amount": cap_amount,
                "date_category": primary_date_category,
                "applied_rate_plan": plan_data["name"],
                "segment_type": plan_data["segment_type"],
                "holiday_type": plan_data["holiday_type"],
                "session_details": session_details,
                "calculation_summary": calculation_summary,
                "enter_time": enter_time,
                "exit_time": exit_time,
                "total_duration_minutes": total_minutes,
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"收費週期計算失敗: {str(e)}",
                "calculation_engine": "user_defined_billing_cycle",
            }

    def generate_billing_cycles(
        self,
        enter_time: datetime,
        exit_time: datetime,
        segments: List[dict],
        rate_matrix: dict,
        holiday_type: str,
        global_grace_time: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        billing_cycles: List[Dict[str, Any]] = []
        total_fee = 0
        current_time = enter_time
        global_grace_used = False
        segment_accumulated_fees: Dict[str, int] = {}

        while current_time < exit_time:
            current_segment = self.find_active_segment_at_time(current_time, segments)
            if not current_segment:
                current_time += timedelta(minutes=1)
                continue

            segment_date_category = self.determine_segment_date_category(
                current_time, current_segment, holiday_type
            )

            segment_key = f"{current_segment['name']}_{segment_date_category}"
            if segment_key not in rate_matrix:
                current_time = self.get_next_segment_boundary(current_time, current_segment)
                continue

            rate_config = rate_matrix[segment_key]
            unit_time = rate_config.get("unit_time", 60)
            cycle_end_time = current_time + timedelta(minutes=unit_time)
            actual_cycle_end = min(cycle_end_time, exit_time)
            cycle_minutes = int((actual_cycle_end - current_time).total_seconds() / 60)
            if cycle_minutes <= 0:
                break

            effective_grace_time = 0
            if not global_grace_used and global_grace_time > 0:
                effective_grace_time = global_grace_time
                global_grace_used = True
            elif rate_config.get("grace_time", 0) > 0:
                effective_grace_time = rate_config.get("grace_time", 0)

            cycle_fee = self.calculate_cycle_fee(
                cycle_minutes, rate_config, effective_grace_time
            )

            current_date = current_time.date().strftime("%Y-%m-%d")
            segment_key_for_cap = f"{current_date}_{current_segment['name']}_{segment_date_category}"
            if segment_key_for_cap not in segment_accumulated_fees:
                segment_accumulated_fees[segment_key_for_cap] = 0

            if rate_config.get("segment_cap_enabled", False):
                segment_cap = rate_config.get("segment_cap_amount", 0)
                if segment_cap > 0:
                    new_accumulated = segment_accumulated_fees[segment_key_for_cap] + cycle_fee
                    if new_accumulated > segment_cap:
                        cycle_fee = max(0, segment_cap - segment_accumulated_fees[segment_key_for_cap])

            segment_accumulated_fees[segment_key_for_cap] += cycle_fee

            cycle_info = {
                "start_time": current_time,
                "end_time": actual_cycle_end,
                "minutes": cycle_minutes,
                "segment_name": current_segment["name"],
                "rate_config": rate_config,
                "fee": cycle_fee,
                "time_range": f"{current_time.strftime('%H:%M')}-{actual_cycle_end.strftime('%H:%M')}",
                "display_duration": format_duration_display(cycle_minutes),
                "rate_description": get_rate_description(rate_config),
                "date_display": current_time.strftime("%m-%d"),
                "date_category": segment_date_category,
            }

            billing_cycles.append(cycle_info)
            total_fee += cycle_fee
            current_time = cycle_end_time
            if current_time >= exit_time:
                break

        return billing_cycles, total_fee

    def determine_segment_date_category(
        self, current_time: datetime, segment: dict, holiday_type: str
    ) -> str:
        segment_start = segment["start"]
        segment_end = segment["end"]
        if segment_start > segment_end or segment_end == "24:00":
            current_time_only = current_time.time()
            segment_start_time = datetime.strptime(segment_start, "%H:%M").time()
            if current_time_only >= segment_start_time:
                return self.determine_date_category(current_time, holiday_type)
            else:
                previous_day = current_time - timedelta(days=1)
                return self.determine_date_category(previous_day, holiday_type)
        else:
            return self.determine_date_category(current_time, holiday_type)

    def find_active_segment_at_time(
        self, check_time: datetime, segments: List[dict]
    ) -> Optional[dict]:
        check_time_only = check_time.time()
        for segment in segments:
            start_str = segment["start"]
            end_str = segment["end"]
            if end_str == "24:00":
                end_str = "00:00"
                is_fullday = start_str == "00:00"
            else:
                is_fullday = False
            start_time = datetime.strptime(start_str, "%H:%M").time()
            end_time = datetime.strptime(end_str, "%H:%M").time()
            if is_fullday:
                return segment
            elif start_time <= end_time:
                if start_time <= check_time_only <= end_time:
                    return segment
            else:
                if check_time_only >= start_time or check_time_only <= end_time:
                    return segment
        return None

    def get_next_segment_boundary(
        self, current_time: datetime, current_segment: dict
    ) -> datetime:
        end_str = current_segment["end"]
        if end_str == "24:00":
            end_str = "00:00"
        end_time = datetime.strptime(end_str, "%H:%M").time()
        if current_segment["start"] > current_segment["end"]:
            if current_time.time() >= datetime.strptime(current_segment["start"], "%H:%M").time():
                return datetime.combine(current_time.date() + timedelta(days=1), end_time)
            else:
                return datetime.combine(current_time.date(), end_time)
        else:
            return datetime.combine(current_time.date(), end_time)

    def calculate_cycle_fee(
        self, minutes: int, rate_config: dict, grace_time: int = 0
    ) -> int:
        if not rate_config:
            return 0
        unit_time = rate_config.get("unit_time", 60)
        billable_minutes = max(0, minutes - grace_time)
        if billable_minutes == 0:
            return 0
        billing_units = -(-billable_minutes // unit_time)
        if rate_config.get("progressive_enabled", False):
            total_fee = 0
            remaining_units = billing_units
            for rate_tier in rate_config.get("progressive_rates", []):
                tier_rate = rate_tier.get("rate", 0)
                tier_duration = rate_tier.get("duration_minutes", 60) // unit_time
                if remaining_units <= 0:
                    break
                units_in_tier = min(remaining_units, tier_duration)
                total_fee += units_in_tier * tier_rate
                remaining_units -= units_in_tier
            return total_fee
        else:
            simple_rate = rate_config.get("simple_rate", 0)
            return billing_units * simple_rate

    def consolidate_billing_cycles(
        self, billing_cycles: List[Dict[str, Any]], enter_time: datetime, holiday_type: str
    ) -> Tuple[List[Dict[str, Any]], str]:
        if not billing_cycles:
            return [], "無計費明細"
        sorted_cycles = sorted(billing_cycles, key=lambda x: x["start_time"])
        consolidated: List[Dict[str, Any]] = []
        current_group: Optional[Dict[str, Any]] = None
        for cycle in sorted_cycles:
            cycle_date_category = cycle.get(
                "date_category",
                self.determine_date_category(cycle["start_time"], holiday_type),
            )
            if current_group is None:
                current_group = {
                    "start_time": cycle["start_time"],
                    "end_time": cycle["end_time"],
                    "segment_name": cycle["segment_name"],
                    "rate_description": cycle["rate_description"],
                    "total_minutes": cycle["minutes"],
                    "total_fee": cycle["fee"],
                    "cycles_count": 1,
                    "date_category": cycle_date_category,
                }
            elif (
                current_group["end_time"] == cycle["start_time"]
                and current_group["segment_name"] == cycle["segment_name"]
                and current_group["rate_description"] == cycle["rate_description"]
                and current_group["date_category"] == cycle_date_category
            ):
                current_group["end_time"] = cycle["end_time"]
                current_group["total_minutes"] += cycle["minutes"]
                current_group["total_fee"] += cycle["fee"]
                current_group["cycles_count"] += 1
            else:
                consolidated.append(current_group)
                current_group = {
                    "start_time": cycle["start_time"],
                    "end_time": cycle["end_time"],
                    "segment_name": cycle["segment_name"],
                    "rate_description": cycle["rate_description"],
                    "total_minutes": cycle["minutes"],
                    "total_fee": cycle["fee"],
                    "cycles_count": 1,
                    "date_category": cycle_date_category,
                }
        if current_group:
            consolidated.append(current_group)

        session_details: List[Dict[str, Any]] = []
        calculation_summary_parts: List[str] = []
        for group in consolidated:
            start_time = group["start_time"]
            end_time = group["end_time"]
            group_date_category = group["date_category"]
            segment_label = f"{group['segment_name']}{group_date_category}"
            if start_time.date() != end_time.date():
                if group["cycles_count"] > 1 and end_time.time() != time(0, 0):
                    first_part = f"{start_time.strftime('%H:%M')}-00:00"
                    second_part = f"00:00-{end_time.strftime('%H:%M')}"
                    time_range = f"({first_part}, {second_part})"
                    period_display = f"{start_time.strftime('%m-%d')}~{end_time.strftime('%m-%d')} {segment_label} {time_range}"
                else:
                    period_display = f"{start_time.strftime('%m-%d')}~{end_time.strftime('%m-%d')} {segment_label} ({start_time.strftime('%H:%M')}-{end_time.strftime('%H:%M')})"
            else:
                period_display = f"{start_time.strftime('%m-%d')} {segment_label} ({start_time.strftime('%H:%M')}-{end_time.strftime('%H:%M')})"

            session_details.append(
                {
                    "period": period_display,
                    "duration": format_duration_display(group["total_minutes"]),
                    "rate": group["rate_description"],
                    "amount": group["total_fee"],
                    "segment_label": segment_label,
                    "cycles_count": group["cycles_count"],
                }
            )
            calculation_summary_parts.append(
                f"{segment_label}: {format_duration_display(group['total_minutes'])} × {group['rate_description']} = {group['total_fee']}元"
            )

        calculation_summary = " | ".join(calculation_summary_parts)
        return session_details, calculation_summary

    def get_rate_description(self, rate_config: dict) -> str:
        return get_rate_description(rate_config)

    def calculate_with_multidimensional(
        self,
        enter_time: datetime,
        exit_time: datetime,
        template_id: str,
        manual_adjustment: int = 0,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        try:
            result = self.multidimensional_calculator.calculate_parking_fee(
                enter_time, exit_time, template_id
            )
            return {
                "success": True,
                "calculation_engine": "multidimensional",
                "total_amount": result.total_amount + manual_adjustment,
                "original_amount": result.original_amount,
                "manual_adjustment": manual_adjustment,
                "date_category": result.date_category.value,
                "applied_rate_plan": result.applied_rate_plan,
                "time_segment_type": result.time_segment_type,
                "holiday_type": result.holiday_type,
                "session_details": result.session_details,
                "calculation_summary": result.calculation_summary,
                "dimension_tags": result.dimension_tags,
                "enter_time": enter_time,
                "exit_time": exit_time,
                "total_duration_minutes": int((exit_time - enter_time).total_seconds() / 60),
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"多維度計算失敗: {str(e)}",
                "calculation_engine": "multidimensional",
            }

    def format_duration_display(self, minutes: int) -> str:
        return format_duration_display(minutes)

    def determine_date_category(self, check_time: datetime, holiday_type: str) -> str:
        weekday = check_time.weekday()
        if holiday_type == "無假日":
            return "統一"
        elif holiday_type == "平日假日":
            return "平日" if weekday < 5 else "假日"
        elif holiday_type == "完整假日":
            if weekday < 5:
                return "平日"
            elif weekday == 5:
                return "假日"
            else:
                return "節慶日"
        else:
            return "統一"

    def calculate_segment_fee(self, minutes: int, rate_config: dict, global_grace_time: int = 0) -> int:
        if not rate_config:
            return 0
        unit_time = rate_config.get("unit_time", 60)
        if global_grace_time > 0:
            grace_time = global_grace_time
        else:
            grace_time = rate_config.get("grace_time", 0)
        billable_minutes = max(0, minutes - grace_time)
        if billable_minutes == 0:
            return 0
        billing_units = -(-billable_minutes // unit_time)
        if rate_config.get("progressive_enabled", False):
            total_fee = 0
            remaining_units = billing_units
            for rate_tier in rate_config.get("progressive_rates", []):
                tier_rate = rate_tier.get("rate", 0)
                tier_duration = rate_tier.get("duration_minutes", 60) // unit_time
                if remaining_units <= 0:
                    break
                units_in_tier = min(remaining_units, tier_duration)
                total_fee += units_in_tier * tier_rate
                remaining_units -= units_in_tier
            return total_fee
        else:
            simple_rate = rate_config.get("simple_rate", 0)
            return billing_units * simple_rate
