import json
import logging
import os
from datetime import datetime, timedelta, time
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union

from src.core.validation import (
    validate_user_defined_plans_json,
    validate_multidimensional_config_json,
    validate_plan_v2_json,
    ConfigValidationError,
)
from src.domain.multidimensional_calculator import (
    MultidimensionalParkingCalculator,
)
from src.domain.pricing.unified_pricing_engine import UnifiedPricingEngine
from src.core.calendar_resolver import HolidayCalendar
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
        self.multidimensional_calculator: Optional[MultidimensionalParkingCalculator] = None
        self.system_config: Dict[str, Any] = {}
        self.persisted_system_config: Dict[str, Any] = {}
        self.holiday_calendar: Optional[HolidayCalendar] = None

        self.load_system_config()
        self.reload_holiday_calendar()
        self.init_multidimensional_calculator()

    def _config_path(self, *parts: str) -> Path:
        return self.base_path.joinpath(*parts)

    def load_system_config(self):
        try:
            config_path = self._config_path("system_config.json")
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
            config_path = self._config_path("system_config.json")
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

    def reload_holiday_calendar(self) -> None:
        try:
            self.holiday_calendar = HolidayCalendar(
                self._config_path("system_calendar.json")
            )
        except Exception as e:
            logger.exception("載入假日日曆失敗: %s", e)
            self.holiday_calendar = HolidayCalendar(
                self._config_path("system_calendar.json")
            )

    def init_multidimensional_calculator(self):
        try:
            cfg_path = self._config_path("multidimensional_rate_plans.json")
            if cfg_path.exists():
                with open(cfg_path, "r", encoding="utf-8") as f:
                    _cfg = json.load(f)
                validate_multidimensional_config_json(_cfg)

            calendar = self.holiday_calendar
            if calendar is None:
                self.reload_holiday_calendar()
                calendar = self.holiday_calendar

            self.multidimensional_calculator = MultidimensionalParkingCalculator(
                str(cfg_path),
                holiday_calendar=calendar,
            )
            logger.info("多維度標籤計算器載入成功")
        except Exception as e:
            logger.exception("多維度標籤計算器載入失敗: %s", e)

    def _user_plans_path(self) -> Path:
        return self._config_path("user_defined_plans.json")

    def load_user_defined_plans_config(self) -> Dict[str, Any]:
        path = self._user_plans_path()
        if not path.exists():
            return {"plans": {}, "metadata": {}}
        with open(path, "r", encoding="utf-8") as f:
            config_obj = json.load(f)
        validate_user_defined_plans_json(config_obj)
        return config_obj

    def _save_user_defined_plans_config(self, config_obj: Dict[str, Any]) -> None:
        validate_user_defined_plans_json(config_obj)
        path = self._user_plans_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config_obj, f, ensure_ascii=False, indent=2)

    @staticmethod
    def _is_plan_featured(plan_data: Dict[str, Any]) -> bool:
        if plan_data.get("featured") is True:
            return True
        tags = plan_data.get("tags") or []
        return "featured" in tags or "推薦" in tags

    def list_user_defined_plans(self, *, apply_ui_filters: bool = True) -> List[Dict[str, Any]]:
        try:
            config_obj = self.load_user_defined_plans_config()
        except (FileNotFoundError, ConfigValidationError):
            return []

        plans = config_obj.get("plans", {})
        items: List[Dict[str, Any]] = []
        for plan_id, plan_data in plans.items():
            if plan_data.get("active") is False:
                continue
            items.append(
                {
                    "rate_plan_id": plan_id,
                    "plan_id": plan_id,
                    "label": plan_data.get("name", plan_id),
                    "description": plan_data.get("description", ""),
                    "type": "user_defined",
                    "segment_type": plan_data.get("segment_type"),
                    "holiday_type": plan_data.get("holiday_type"),
                    "featured": self._is_plan_featured(plan_data),
                    "active": plan_data.get("active", True),
                }
            )

        if not apply_ui_filters:
            return sorted(items, key=lambda x: (not x["featured"], x["label"]))

        ui_settings = self.system_config.get("ui_settings") or {}
        if ui_settings.get("show_only_featured_user_plans"):
            items = [item for item in items if item["featured"]]

        items.sort(key=lambda x: (not x["featured"], x["label"]))
        max_display = ui_settings.get("max_user_plans_display")
        if isinstance(max_display, int) and max_display > 0:
            items = items[:max_display]
        return items

    def get_user_defined_plan(self, plan_id: str) -> Optional[Dict[str, Any]]:
        try:
            config_obj = self.load_user_defined_plans_config()
        except (FileNotFoundError, ConfigValidationError):
            return None
        return config_obj.get("plans", {}).get(plan_id)

    def save_user_defined_plan(self, plan_id: str, plan_data: Dict[str, Any]) -> Dict[str, Any]:
        if not plan_id or not str(plan_id).strip():
            raise ValueError("plan_id 不可為空")

        validate_plan_v2_json(plan_data)
        plan_id = str(plan_id).strip()

        try:
            config_obj = self.load_user_defined_plans_config()
        except FileNotFoundError:
            config_obj = {"plans": {}, "metadata": {}}
        except ConfigValidationError as exc:
            raise ValueError(
                f"現有自訂方案配置不合法: {', '.join(exc.errors) if exc.errors else str(exc)}"
            ) from exc

        plans = config_obj.setdefault("plans", {})
        now = datetime.now().isoformat()
        existing = plans.get(plan_id)
        if existing:
            plan_data.setdefault("created_date", existing.get("created_date", now))
        else:
            plan_data.setdefault("created_date", now)
        plan_data["modified_date"] = now
        plan_data.setdefault("version", "1.0")
        plan_data.setdefault("active", True)
        if "name" not in plan_data or not plan_data["name"]:
            plan_data["name"] = plan_id

        plans[plan_id] = plan_data
        metadata = config_obj.setdefault("metadata", {})
        metadata["last_modified"] = now
        metadata.setdefault("version", "1.0")

        self._save_user_defined_plans_config(config_obj)
        return plan_data

    def delete_user_defined_plan(self, plan_id: str) -> bool:
        try:
            config_obj = self.load_user_defined_plans_config()
        except (FileNotFoundError, ConfigValidationError):
            return False

        plans = config_obj.get("plans", {})
        if plan_id not in plans:
            return False

        del plans[plan_id]
        metadata = config_obj.setdefault("metadata", {})
        metadata["last_modified"] = datetime.now().isoformat()
        self._save_user_defined_plans_config(config_obj)
        return True

    def is_multidimensional_plan(self, plan_id: str) -> bool:
        calc = self.multidimensional_calculator
        if not calc:
            return False
        return plan_id in calc.rate_plan_templates

    def is_user_defined_plan(self, plan_id: str) -> bool:
        return self.get_user_defined_plan(plan_id) is not None

    # ====== 計算相關 ======
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

            if self.is_multidimensional_plan(plan_id):
                return self.calculate_with_multidimensional(
                    enter_time, exit_time, plan_id, manual_adjustment, context
                )
            if self.is_user_defined_plan(plan_id):
                return self.calculate_with_user_defined_plan(
                    enter_time, exit_time, plan_id, manual_adjustment, context
                )
            raise ValueError(f"找不到費率方案: {plan_id}")
        except Exception as e:
            return {"success": False, "error": str(e), "calculation_engine": "none"}

    def calculate_with_user_defined_plan(
        self,
        enter_time: datetime,
        exit_time: datetime,
        plan_id: str,
        manual_adjustment: int = 0,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        try:
            plan_data = self.get_user_defined_plan(plan_id)
            if not plan_data:
                raise ValueError(f"找不到用戶自訂方案: {plan_id}")

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

    def _build_upe_plan_from_user_defined(self, plan_data: dict) -> Dict[str, Any]:
        global_caps = dict(plan_data.get("global_caps") or {})
        if plan_data.get("global_grace_time") is not None:
            global_caps["global_grace_time"] = plan_data.get("global_grace_time", 0)
        return {
            "segment_type": plan_data.get("segment_type"),
            "holiday_type": plan_data.get("holiday_type"),
            "segments": plan_data.get("segments", []),
            "rate_matrix": plan_data.get("rate_matrix", {}),
            "global_caps": global_caps,
        }

    def _user_defined_date_resolver(self, plan_data: dict):
        holiday_type = plan_data["holiday_type"]
        segments = plan_data.get("segments", [])

        def resolver(dt: datetime) -> str:
            seg = self.find_active_segment_at_time(dt, segments)
            if seg:
                return self.determine_segment_date_category(dt, seg, holiday_type)
            return self.determine_date_category(dt, holiday_type)

        return resolver

    def _format_upe_session_details(
        self, upe_details: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], str]:
        session_details: List[Dict[str, Any]] = []
        summary_parts: List[str] = []
        for detail in upe_details:
            label = detail.get("label", "時段")
            time_range = detail.get("time_range", "")
            if detail.get("progressive"):
                rate_desc = "累進費率"
            else:
                unit = detail.get("unit", 60)
                rate_desc = f"{detail.get('rate', 0)}元/{unit}分"
            period = f"{label} ({time_range})" if time_range else label
            duration_minutes = int(detail.get("duration", 0) or 0)
            fee = int(detail.get("fee", 0) or 0)
            session_details.append(
                {
                    "period": period,
                    "duration": format_duration_display(duration_minutes),
                    "rate": rate_desc,
                    "amount": fee,
                    "segment_label": label,
                }
            )
            summary_parts.append(
                f"{label}: {format_duration_display(duration_minutes)} × {rate_desc} = {fee}元"
            )
        calculation_summary = " | ".join(summary_parts) if summary_parts else "無計費明細"
        return session_details, calculation_summary

    def calculate_fee_by_billing_cycles(
        self,
        enter_time: datetime,
        exit_time: datetime,
        plan_data: dict,
        manual_adjustment: int = 0,
    ) -> Dict[str, Any]:
        try:
            total_minutes = int((exit_time - enter_time).total_seconds() / 60)
            upe_plan = self._build_upe_plan_from_user_defined(plan_data)
            upe = UnifiedPricingEngine()
            res = upe.calculate(
                enter_time,
                exit_time,
                upe_plan,
                self._user_defined_date_resolver(plan_data),
            )
            if not res.success:
                raise ValueError(res.calculation_summary)

            session_details, calculation_summary = self._format_upe_session_details(
                res.session_details
            )
            total_amount = res.total_amount
            original_amount = res.original_amount
            global_caps = upe_plan.get("global_caps", {})
            cap_applied = original_amount > total_amount
            cap_amount = None
            if cap_applied and global_caps.get("daily_cap_amount"):
                cap_amount = int(global_caps["daily_cap_amount"])

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
                "segment_type": result.segment_type,
                "time_segment_type": result.segment_type,
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
        if self.holiday_calendar is None:
            self.reload_holiday_calendar()
        calendar = self.holiday_calendar
        if calendar is not None:
            return calendar.classify_user_defined_date(check_time.date(), holiday_type)

        weekday = check_time.weekday()
        if holiday_type == "無假日":
            return "統一"
        if holiday_type == "平日假日":
            return "平日" if weekday < 5 else "假日"
        if holiday_type == "完整假日":
            return "節慶日" if weekday == 6 else ("假日" if weekday == 5 else "平日")
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
