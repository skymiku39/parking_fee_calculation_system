"""
多維度標籤停車費計算器
支援時段選擇（全天、二段、多時段）與假日類型（無假日、平日假日、完整假日）的組合計算
"""

import json
import math
from datetime import datetime, date, time, timedelta
from typing import List, Dict, Optional, Tuple, Any, Union
from dataclasses import dataclass
from enum import Enum
from src.domain.pricing.unified_pricing_engine import UnifiedPricingEngine
from src.core.calendar_resolver import HolidayCalendar
from src.domain.terminology import (
    DateCategory,
    HolidayType,
    MdpPlanTier,
    SegmentType,
    TEMPLATE_ID_ALIASES,
    normalize_holiday_type,
    normalize_segment_type,
    normalize_template_id,
    resolve_template_id,
)
import calendar

# Backward-compatible re-exports
TimeSegmentType = SegmentType


@dataclass
class MultidimensionalTimeSlot:
    """多維度時段資料結構"""

    time_slot_id: str
    label: str
    start: str
    end: str
    unit_minutes: int
    grace_minutes: int
    grace_enabled: bool
    cap_enabled: bool
    cap_amount: int
    progressive_enabled: bool
    default_unit_price: int
    progressive_rates: List[Dict[str, Any]]
    date_category: DateCategory = DateCategory.WEEKDAY
    base_multiplier: float = 1.0


@dataclass
class MultidimensionalRatePlan:
    """多維度費率方案"""

    template_id: str
    label: str
    description: str
    segment_type: SegmentType
    holiday_type: HolidayType
    dimension_combination: str
    weekday_plan: Optional[Dict[str, Any]] = None
    weekend_plan: Optional[Dict[str, Any]] = None
    national_holiday_plan: Optional[Dict[str, Any]] = None
    custom_holiday_plan: Optional[Dict[str, Any]] = None
    unified_plan: Optional[Dict[str, Any]] = None

    @property
    def time_segment_type(self) -> SegmentType:
        return self.segment_type


@dataclass
class ParkingCalculationResult:
    """停車計算結果"""

    total_amount: int
    original_amount: int
    date_category: DateCategory
    applied_rate_plan: str
    segment_type: str
    holiday_type: str
    session_details: List[Dict[str, Any]]
    calculation_summary: str
    dimension_tags: List[str]

    @property
    def time_segment_type(self) -> str:
        return self.segment_type


class MultidimensionalParkingCalculator:
    """多維度標籤停車費計算器"""

    def __init__(
        self,
        config_path: str = "config/multidimensional_rate_plans.json",
        holiday_calendar: Optional[HolidayCalendar] = None,
    ):
        """初始化多維度計算器"""
        self.config = {}
        self.rate_plan_templates = {}
        self.dimension_configs = {}
        self.custom_holidays = []
        self.holiday_calendar = holiday_calendar
        self._legacy_template_ids: Dict[str, str] = {}
        self.load_config(config_path)

    def load_config(self, config_path: str):
        """載入多維度配置"""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                self.config = json.load(f)

            self.dimension_configs = self.config.get("dimension_configs", {})
            metadata = self.config.get("metadata", {})
            self._legacy_template_ids = metadata.get("legacy_template_ids", {})
            self._legacy_template_ids.update(TEMPLATE_ID_ALIASES)

            self.rate_plan_templates = {}
            for template in self.config.get("rate_plan_templates", []):
                raw_id = template["template_id"]
                template_id = normalize_template_id(raw_id)
                seg_raw = template.get("segment_type") or template.get("time_segment_type", "全天")
                hol_raw = template.get("holiday_type", "無假日")
                plan = MultidimensionalRatePlan(
                    template_id=template_id,
                    label=template["label"],
                    description=template["description"],
                    segment_type=SegmentType(normalize_segment_type(seg_raw)),
                    holiday_type=HolidayType(normalize_holiday_type(hol_raw)),
                    dimension_combination=template_id,
                    weekday_plan=template.get("weekday_plan"),
                    weekend_plan=template.get("weekend_plan"),
                    national_holiday_plan=template.get("national_holiday_plan"),
                    custom_holiday_plan=template.get("custom_holiday_plan"),
                    unified_plan=template.get("rate_plan_id") and template or None,
                )
                self.rate_plan_templates[template_id] = plan
                if raw_id != template_id:
                    self.rate_plan_templates[raw_id] = plan
                for old_id, new_id in self._legacy_template_ids.items():
                    if new_id == template_id:
                        self.rate_plan_templates[old_id] = plan

            hol_types = self.dimension_configs.get("holiday_types", {}).get("types", {})
            full_holiday_cfg = (
                hol_types.get("完整假日")
                or hol_types.get("國定假費率")
                or {}
            )
            self.custom_holidays = full_holiday_cfg.get("custom_holidays", [])

        except Exception as e:
            print(f"載入多維度配置失敗: {e}")
            self.config = {}
            self.rate_plan_templates = {}

    def _resolve_template_id(self, template_id: str) -> str:
        resolved = resolve_template_id(template_id, self._legacy_template_ids)
        if resolved in self.rate_plan_templates:
            return resolved
        if template_id in self.rate_plan_templates:
            return template_id
        canonical = normalize_template_id(template_id)
        if canonical in self.rate_plan_templates:
            return canonical
        raise ValueError(f"找不到費率範本: {template_id}")

    def _mdp_billing_category(self, check_date: date, holiday_type: str) -> str:
        """UPE rate_matrix / 日上限查表用的日期類別鍵（可區分國定假）。"""
        hol = normalize_holiday_type(holiday_type)
        if hol == HolidayType.NO_HOLIDAY.value:
            return DateCategory.UNIFIED.value

        if self.holiday_calendar is not None:
            tier = self.holiday_calendar.get_mdp_plan_tier(
                check_date, hol, extra_custom_holidays=self.custom_holidays
            )
        else:
            dc = self.get_date_category(check_date, hol)
            if dc == DateCategory.UNIFIED:
                tier = MdpPlanTier.UNIFIED
            elif dc == DateCategory.FESTIVAL:
                tier = MdpPlanTier.CUSTOM_HOLIDAY
            elif dc == DateCategory.HOLIDAY:
                tier = MdpPlanTier.WEEKEND
            else:
                tier = MdpPlanTier.WEEKDAY

        if tier == MdpPlanTier.UNIFIED:
            return DateCategory.UNIFIED.value
        if tier == MdpPlanTier.WEEKDAY:
            return DateCategory.WEEKDAY.value
        if tier == MdpPlanTier.WEEKEND:
            return DateCategory.HOLIDAY.value
        if tier == MdpPlanTier.NATIONAL_HOLIDAY:
            return "國定假日"
        if tier == MdpPlanTier.CUSTOM_HOLIDAY:
            return DateCategory.FESTIVAL.value
        return DateCategory.WEEKDAY.value

    def get_date_category(
        self, check_date: date, holiday_type: Optional[str] = None
    ) -> DateCategory:
        """判斷 canonical 日期類別"""
        hol = normalize_holiday_type(holiday_type or HolidayType.NO_HOLIDAY.value)
        if self.holiday_calendar is not None:
            category = self.holiday_calendar.classify_date(
                check_date,
                hol,
                extra_custom_holidays=self.custom_holidays,
            )
            return DateCategory(category)

        date_str = check_date.strftime("%Y-%m-%d")
        if date_str in self.custom_holidays:
            return DateCategory.FESTIVAL
        if check_date.weekday() >= 5:
            return DateCategory.HOLIDAY
        return DateCategory.WEEKDAY

    def get_applicable_plan(
        self, template_id: str, check_date: date
    ) -> Dict[str, Any]:
        """根據範本ID和日期獲取適用的費率方案"""
        template_id = self._resolve_template_id(template_id)
        template = self.rate_plan_templates[template_id]

        if template.holiday_type == HolidayType.NO_HOLIDAY:
            if template.unified_plan:
                return template.unified_plan
            return template.weekday_plan

        if self.holiday_calendar is not None:
            tier = self.holiday_calendar.get_mdp_plan_tier(
                check_date,
                template.holiday_type.value,
                extra_custom_holidays=self.custom_holidays,
            )
        else:
            dc = self.get_date_category(check_date, template.holiday_type.value)
            if dc == DateCategory.UNIFIED:
                tier = MdpPlanTier.UNIFIED
            elif dc == DateCategory.FESTIVAL:
                tier = MdpPlanTier.CUSTOM_HOLIDAY
            elif dc == DateCategory.HOLIDAY:
                tier = MdpPlanTier.WEEKEND
            else:
                tier = MdpPlanTier.WEEKDAY

        if tier == MdpPlanTier.UNIFIED:
            return template.unified_plan or template.weekday_plan
        if tier == MdpPlanTier.WEEKDAY:
            return template.weekday_plan
        if tier == MdpPlanTier.WEEKEND:
            return template.weekend_plan or template.weekday_plan
        if tier == MdpPlanTier.NATIONAL_HOLIDAY:
            return (
                template.national_holiday_plan
                or template.weekend_plan
                or template.weekday_plan
            )
        if tier == MdpPlanTier.CUSTOM_HOLIDAY:
            return (
                template.custom_holiday_plan
                or template.national_holiday_plan
                or template.weekend_plan
                or template.weekday_plan
            )

        return template.weekday_plan

    def parse_time_string(self, time_str: str) -> time:
        """解析時間字串"""
        try:
            if time_str == "24:00":
                # 將 24:00 視為當日結束（避免 23:59:59 導致的少一分鐘問題）
                return time(23, 59, 59)
            hour, minute = map(int, time_str.split(":"))
            return time(hour, minute)
        except:
            return time(0, 0)

    def calculate_slot_duration(
        self, start_time: datetime, end_time: datetime, slot_start: str, slot_end: str
    ) -> int:
        """計算在特定時段內的停車時間（分鐘）"""
        slot_start_time = self.parse_time_string(slot_start)
        slot_end_time = self.parse_time_string(slot_end)

        # 處理跨日時段
        if slot_start_time > slot_end_time:
            # 跨日時段分為「當天晚間段」與「次日前段」兩部分
            total_minutes = 0

            # 當天晚間段：當天 slot_start ~ 次日 00:00
            day_slot_start = start_time.replace(
                hour=slot_start_time.hour, minute=slot_start_time.minute, second=0
            )
            next_midnight = datetime.combine(start_time.date() + timedelta(days=1), time(0, 0))

            # 與 [start_time, end_time] 取交集
            interval_start_1 = max(start_time, day_slot_start)
            interval_end_1 = min(end_time, next_midnight)
            if interval_end_1 > interval_start_1:
                total_minutes += int((interval_end_1 - interval_start_1).total_seconds() / 60)

            # 次日前段：次日 00:00 ~ 次日 slot_end
            next_day_start = next_midnight
            next_day_slot_end = datetime.combine(
                start_time.date() + timedelta(days=1),
                time(slot_end_time.hour, slot_end_time.minute, 0),
            )
            interval_start_2 = max(start_time, next_day_start)
            interval_end_2 = min(end_time, next_day_slot_end)
            if interval_end_2 > interval_start_2:
                total_minutes += int((interval_end_2 - interval_start_2).total_seconds() / 60)

            return total_minutes

        # 一般時段（不跨日）
        slot_start_dt = start_time.replace(
            hour=slot_start_time.hour, minute=slot_start_time.minute, second=0
        )
        slot_end_dt = start_time.replace(
            hour=slot_end_time.hour, minute=slot_end_time.minute, second=0
        )

        actual_start = max(start_time, slot_start_dt)
        actual_end = min(end_time, slot_end_dt)

        if actual_end <= actual_start:
            return 0

        return int((actual_end - actual_start).total_seconds() / 60)

    def calculate_progressive_fee(
        self, duration_minutes: int, progressive_rates: List[Dict]
    ) -> Tuple[int, List[Dict]]:
        """計算累進費率"""
        if not progressive_rates:
            return 0, []

        total_fee = 0
        calculation_details = []
        remaining_duration = duration_minutes

        for rate in progressive_rates:
            start_min = rate["start_min"]
            end_min = rate.get("end_min")
            unit_minutes = rate["unit_minutes"]
            unit_price = rate["unit_price"]

            if remaining_duration <= 0:
                break

            # 計算這個區間的時間
            if end_min is None:
                # 最後一個區間，使用剩餘所有時間
                applicable_duration = remaining_duration
            else:
                # 限制在區間範圍內
                if duration_minutes <= start_min:
                    continue
                applicable_duration = min(remaining_duration, end_min - start_min)

            if applicable_duration > 0:
                # 計算這個區間的費用
                units = math.ceil(applicable_duration / unit_minutes)
                interval_fee = units * unit_price
                total_fee += interval_fee

                calculation_details.append(
                    {
                        "interval": f"{start_min}-{end_min or '∞'}分鐘",
                        "duration": applicable_duration,
                        "units": units,
                        "unit_price": unit_price,
                        "interval_fee": interval_fee,
                    }
                )

                remaining_duration -= applicable_duration

        return total_fee, calculation_details

    def calculate_time_slot_fee(
        self, time_slot: Dict, duration_minutes: int
    ) -> Tuple[int, Dict]:
        """計算單一時段的費用"""
        if duration_minutes <= 0:
            return 0, {"duration": 0, "fee": 0, "is_free": True}

        # 檢查緩衝時間
        grace_minutes = time_slot.get("grace_minutes", 0)
        grace_enabled = time_slot.get("grace_enabled", False)

        if grace_enabled and duration_minutes <= grace_minutes:
            return 0, {
                "duration": duration_minutes,
                "fee": 0,
                "is_free": True,
                "reason": f"緩衝時間內免費 ({grace_minutes}分鐘)",
            }

        # 計算實際計費時間（扣除緩衝時間）
        billable_duration = duration_minutes - (grace_minutes if grace_enabled else 0)
        billable_duration = max(0, billable_duration)

        # 計算費用
        progressive_enabled = time_slot.get("progressive_enabled", False)
        progressive_rates = time_slot.get("progressive_rates", [])

        if progressive_enabled and progressive_rates:
            fee, calculation_details = self.calculate_progressive_fee(
                billable_duration, progressive_rates
            )
        else:
            # 一般計費
            unit_minutes = time_slot.get("unit_minutes", 60)
            unit_price = time_slot.get("default_unit_price", 0)
            units = math.ceil(billable_duration / unit_minutes)
            fee = units * unit_price
            calculation_details = [
                {
                    "duration": billable_duration,
                    "units": units,
                    "unit_price": unit_price,
                    "fee": fee,
                }
            ]

        # 檢查上限
        cap_enabled = time_slot.get("cap_enabled", False)
        cap_amount = time_slot.get("cap_amount", 0)
        is_capped = False

        if cap_enabled and cap_amount > 0 and fee > cap_amount:
            fee = cap_amount
            is_capped = True

        return fee, {
            "duration": duration_minutes,
            "billable_duration": billable_duration,
            "fee": fee,
            "is_free": fee == 0,
            "is_capped": is_capped,
            "cap_amount": cap_amount if is_capped else None,
            "calculation_details": calculation_details,
        }

    def _slot_to_upe_rate_config(self, slot: Dict[str, Any]) -> Dict[str, Any]:
        prog_rates = []
        for tier in slot.get("progressive_rates", []):
            start_min = int(tier.get("start_min", 0) or 0)
            end_min = tier.get("end_min")
            unit_minutes = int(tier.get("unit_minutes", slot.get("unit_minutes", 60)) or 60)
            if end_min is None:
                duration_minutes = unit_minutes
            else:
                duration_minutes = max(0, int(end_min - start_min))
            prog_rates.append(
                {
                    "duration_minutes": duration_minutes,
                    "rate": int(tier.get("unit_price", 0) or 0),
                    "unit_time": unit_minutes,
                }
            )
        return {
            "unit_time": int(slot.get("unit_minutes", 60) or 60),
            "simple_rate": int(slot.get("default_unit_price", 0) or 0),
            "grace_time": int(slot.get("grace_minutes", 0) or 0)
            if slot.get("grace_enabled", False)
            else 0,
            "progressive_enabled": bool(slot.get("progressive_enabled", False)),
            "progressive_rates": prog_rates,
            "segment_cap_enabled": bool(slot.get("cap_enabled", False)),
            "segment_cap_amount": int(slot.get("cap_amount", 0) or 0),
        }

    def _build_mdp_upe_plan(self, template) -> Dict[str, Any]:
        segments_map: Dict[str, Dict[str, str]] = {}
        rate_matrix: Dict[str, Any] = {}
        category_plans = [
            (DateCategory.UNIFIED.value, template.unified_plan),
            (DateCategory.WEEKDAY.value, template.weekday_plan),
            (DateCategory.HOLIDAY.value, template.weekend_plan),
        ]
        if template.national_holiday_plan:
            category_plans.append(("國定假日", template.national_holiday_plan))
        if template.custom_holiday_plan:
            category_plans.append(
                (DateCategory.FESTIVAL.value, template.custom_holiday_plan)
            )
        elif template.national_holiday_plan:
            category_plans.append(
                (DateCategory.FESTIVAL.value, template.national_holiday_plan)
            )
        for date_category, plan in category_plans:
            if not plan:
                continue
            for slot in plan.get("time_slots", []):
                seg_name = slot.get("label") or slot.get("time_slot_id")
                segments_map[seg_name] = {
                    "name": seg_name,
                    "start": slot.get("start", "00:00"),
                    "end": slot.get("end", "24:00"),
                }
                rate_matrix[f"{seg_name}_{date_category}"] = self._slot_to_upe_rate_config(
                    slot
                )

        base_plan = (
            template.weekday_plan
            or template.unified_plan
            or template.weekend_plan
            or {}
        )
        daily_caps_by_category: Dict[str, Dict[str, Any]] = {}
        for date_category, plan in category_plans:
            if not plan:
                continue
            daily_caps_by_category[date_category] = {
                "daily_cap_enabled": bool(plan.get("daily_cap_enabled", False)),
                "daily_cap_amount": int(plan.get("daily_cap_amount", 0) or 0),
            }
        global_caps = {
            "daily_cap_enabled": bool(base_plan.get("daily_cap_enabled", False)),
            "daily_cap_amount": int(base_plan.get("daily_cap_amount", 0) or 0),
            "global_grace_time": int(base_plan.get("global_grace_time", 0) or 0),
            "daily_caps_by_category": daily_caps_by_category,
        }
        return {
            "segments": list(segments_map.values()),
            "rate_matrix": rate_matrix,
            "global_caps": global_caps,
        }

    def _upe_details_to_mdp_sessions(
        self, upe_details: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        session_details: List[Dict[str, Any]] = []
        for detail in upe_details:
            if detail.get("progressive"):
                rate_desc = "累進費率"
            else:
                unit = detail.get("unit", 60)
                rate_desc = f"{detail.get('rate', 0)}元/{unit}分"
            time_range = detail.get("time_range", "-")
            parts = time_range.split("-")
            session_details.append(
                {
                    "label": detail.get("label"),
                    "start": parts[0] if parts else "",
                    "end": parts[-1] if parts else "",
                    "duration": detail.get("duration", 0),
                    "fee": detail.get("fee", 0),
                    "rate": rate_desc,
                    "unit_price": detail.get("rate", 0),
                }
            )
        return session_details

    def calculate_parking_fee(
        self, enter_time: datetime, exit_time: datetime, template_id: str
    ) -> ParkingCalculationResult:
        """計算停車費用（多維度版本）"""
        template_id = self._resolve_template_id(template_id)
        template = self.rate_plan_templates[template_id]

        park_date = enter_time.date()
        date_category = self.get_date_category(park_date, template.holiday_type.value)

        rate_plan = self.get_applicable_plan(template_id, park_date)

        if not rate_plan:
            raise ValueError("無法找到適用的費率方案")

        total_duration = int((exit_time - enter_time).total_seconds() / 60)
        upe_plan = self._build_mdp_upe_plan(template)
        upe = UnifiedPricingEngine()

        def _resolver(dt: datetime) -> str:
            return self._mdp_billing_category(
                dt.date(), template.holiday_type.value
            )

        res = upe.calculate(enter_time, exit_time, upe_plan, _resolver)
        if not res.success:
            raise ValueError(res.calculation_summary)

        total_fee = res.total_amount
        session_details = self._upe_details_to_mdp_sessions(res.session_details)
        global_caps = upe_plan.get("global_caps", {})
        is_daily_capped = res.original_amount > res.total_amount
        cap_note = (
            "依日期類別"
            if global_caps.get("daily_caps_by_category")
            else str(int(global_caps.get("daily_cap_amount", 0) or 0))
        )

        # 生成維度標籤
        dimension_tags = [
            template.segment_type.value,
            template.holiday_type.value,
            date_category.value,
            f"總時段數: {len([s for s in session_details if s['duration'] > 0])}",
        ]

        calculation_summary = f"""
多維度停車費計算結果 (週期基礎):
- 時段類型: {template.segment_type.value}
- 假日類型: {template.holiday_type.value}
- 日期類別: {date_category.value}
- 停車時間: {total_duration}分鐘
- 總費用: {total_fee}元（每日上限: {'是' if is_daily_capped else '否'} {cap_note}）
""".strip()

        return ParkingCalculationResult(
            total_amount=total_fee,
            original_amount=res.original_amount,
            date_category=date_category,
            applied_rate_plan=rate_plan.get("label", "未知"),
            segment_type=template.segment_type.value,
            holiday_type=template.holiday_type.value,
            session_details=session_details,
            calculation_summary=calculation_summary,
            dimension_tags=dimension_tags,
        )

    def get_available_templates(self) -> Dict[str, str]:
        """獲取可用的費率範本列表（僅 canonical template_id）"""
        templates = {}
        seen = set()
        for template_id, template in self.rate_plan_templates.items():
            if template_id != template.template_id:
                continue
            if template.template_id in seen:
                continue
            seen.add(template.template_id)
            templates[template.template_id] = (
                f"{template.label} ({template.segment_type.value} × {template.holiday_type.value})"
            )
        return templates

    def get_dimension_combinations(self) -> List[Dict[str, Any]]:
        """獲取所有可能的維度組合"""
        time_segments = self.dimension_configs.get("time_segments", {}).get("types", {})
        holiday_types = self.dimension_configs.get("holiday_types", {}).get("types", {})

        combinations = []
        for time_seg_name, time_seg_config in time_segments.items():
            for holiday_name, holiday_config in holiday_types.items():
                combination = {
                    "combination_id": f"{time_seg_name}_{holiday_name}",
                    "label": f"{time_seg_config['label']} × {holiday_config['label']}",
                    "time_segment": time_seg_name,
                    "holiday_type": holiday_name,
                    "total_variants": time_seg_config.get("segment_count", 1)
                    * holiday_config.get("holiday_multiplier", 1),
                    "description": f"{time_seg_config['description']} + {holiday_config['description']}",
                }
                combinations.append(combination)

        return combinations


def main():
    """測試多維度計算器"""
    calculator = MultidimensionalParkingCalculator()

    # 測試不同的維度組合
    test_cases = [
        {
            "template_id": "全天_無假日費率",
            "enter_time": datetime(2024, 12, 19, 10, 0),  # 週四
            "exit_time": datetime(2024, 12, 19, 14, 30),
            "description": "平日全天統一費率測試",
        },
        {
            "template_id": "兩段_六日費率",
            "enter_time": datetime(2024, 12, 21, 20, 0),  # 週六
            "exit_time": datetime(2024, 12, 22, 2, 0),  # 跨日到週日
            "description": "週末兩段費率跨日測試",
        },
        {
            "template_id": "四段_國定假費率",
            "enter_time": datetime(2024, 12, 25, 9, 0),  # 聖誕節 (客製假日)
            "exit_time": datetime(2024, 12, 25, 19, 0),
            "description": "客製假日四段費率測試",
        },
    ]

    print("=== 多維度標籤停車費計算系統測試 ===\n")

    # 顯示可用的維度組合
    print("可用的維度組合:")
    combinations = calculator.get_dimension_combinations()
    for combo in combinations:
        print(
            f"- {combo['label']}: {combo['description']} (變體數: {combo['total_variants']})"
        )

    print("\n" + "=" * 60 + "\n")

    # 測試計算
    for i, test_case in enumerate(test_cases, 1):
        print(f"測試案例 {i}: {test_case['description']}")
        print(f"進場時間: {test_case['enter_time']}")
        print(f"出場時間: {test_case['exit_time']}")
        print(f"使用範本: {test_case['template_id']}")

        try:
            result = calculator.calculate_parking_fee(
                test_case["enter_time"],
                test_case["exit_time"],
                test_case["template_id"],
            )

            print(f"\n{result.calculation_summary}")
            print(f"\n維度標籤: {', '.join(result.dimension_tags)}")
            print(f"\n時段明細:")
            for detail in result.session_details:
                if detail["duration"] > 0:
                    print(
                        f"  - {detail['label']}: {detail['duration']}分鐘 = {detail['fee']}元"
                    )

        except Exception as e:
            print(f"計算失敗: {e}")

        print("\n" + "-" * 60 + "\n")


if __name__ == "__main__":
    main()
