"""
多維度標籤停車費計算器
支援時段選擇（全天、兩段、多段）與假日類型（無假日、六日、國定假）的組合計算
"""

import json
import math
from datetime import datetime, date, time, timedelta
from typing import List, Dict, Optional, Tuple, Any, Union
from dataclasses import dataclass
from enum import Enum
import calendar


class TimeSegmentType(Enum):
    """時段類型枚舉"""

    ALL_DAY = "全天"
    TWO_SEGMENT = "兩段"
    THREE_SEGMENT = "三段"
    FOUR_SEGMENT = "四段"
    CUSTOM = "自訂"


class HolidayType(Enum):
    """假日類型枚舉"""

    NO_HOLIDAY_RATE = "無假日費率"
    WEEKEND_RATE = "六日費率"
    NATIONAL_HOLIDAY_RATE = "國定假費率"


class DateCategory(Enum):
    """日期類別枚舉"""

    WEEKDAY = "平日"
    WEEKEND = "週末"
    NATIONAL_HOLIDAY = "國定假日"
    CUSTOM_HOLIDAY = "客製假日"


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
    time_segment_type: TimeSegmentType
    holiday_type: HolidayType
    dimension_combination: str  # 例如: "四段_國定假費率"
    weekday_plan: Optional[Dict[str, Any]] = None
    weekend_plan: Optional[Dict[str, Any]] = None
    national_holiday_plan: Optional[Dict[str, Any]] = None
    custom_holiday_plan: Optional[Dict[str, Any]] = None
    unified_plan: Optional[Dict[str, Any]] = None  # 用於無假日費率的情況


@dataclass
class ParkingCalculationResult:
    """停車計算結果"""

    total_amount: int
    original_amount: int
    date_category: DateCategory
    applied_rate_plan: str
    time_segment_type: str
    holiday_type: str
    session_details: List[Dict[str, Any]]
    calculation_summary: str
    dimension_tags: List[str]


class MultidimensionalParkingCalculator:
    """多維度標籤停車費計算器"""

    def __init__(self, config_path: str = "config/multidimensional_rate_plans.json"):
        """初始化多維度計算器"""
        self.config = {}
        self.rate_plan_templates = {}
        self.dimension_configs = {}
        self.custom_holidays = []
        self.load_config(config_path)

    def load_config(self, config_path: str):
        """載入多維度配置"""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                self.config = json.load(f)

            # 載入維度配置
            self.dimension_configs = self.config.get("dimension_configs", {})

            # 載入費率方案範本
            self.rate_plan_templates = {}
            for template in self.config.get("rate_plan_templates", []):
                template_id = template["template_id"]
                self.rate_plan_templates[template_id] = MultidimensionalRatePlan(
                    template_id=template_id,
                    label=template["label"],
                    description=template["description"],
                    time_segment_type=TimeSegmentType(template["time_segment_type"]),
                    holiday_type=HolidayType(template["holiday_type"]),
                    dimension_combination=template_id,
                    weekday_plan=template.get("weekday_plan"),
                    weekend_plan=template.get("weekend_plan"),
                    national_holiday_plan=template.get("national_holiday_plan"),
                    custom_holiday_plan=template.get("custom_holiday_plan"),
                    unified_plan=template.get("rate_plan_id") and template or None,
                )

            # 載入客製假日
            holiday_config = (
                self.dimension_configs.get("holiday_types", {})
                .get("types", {})
                .get("國定假費率", {})
            )
            self.custom_holidays = holiday_config.get("custom_holidays", [])

        except Exception as e:
            print(f"載入多維度配置失敗: {e}")
            self.config = {}
            self.rate_plan_templates = {}

    def get_date_category(self, check_date: date) -> DateCategory:
        """判斷日期類別"""
        # 檢查是否為客製假日
        date_str = check_date.strftime("%Y-%m-%d")
        if date_str in self.custom_holidays:
            return DateCategory.CUSTOM_HOLIDAY

        # 檢查是否為國定假日 (簡化版，實際應該使用完整的假日曆)
        national_holidays = [
            "01-01",  # 元旦
            "02-28",  # 和平紀念日
            "04-04",  # 兒童節
            "04-05",  # 清明節
            "05-01",  # 勞動節
            "10-10",  # 國慶日
        ]

        month_day = check_date.strftime("%m-%d")
        if month_day in national_holidays:
            return DateCategory.NATIONAL_HOLIDAY

        # 檢查是否為週末
        if check_date.weekday() >= 5:  # 5=週六, 6=週日
            return DateCategory.WEEKEND

        return DateCategory.WEEKDAY

    def get_applicable_plan(
        self, template_id: str, date_category: DateCategory
    ) -> Dict[str, Any]:
        """根據範本ID和日期類別獲取適用的費率方案"""
        if template_id not in self.rate_plan_templates:
            raise ValueError(f"找不到範本: {template_id}")

        template = self.rate_plan_templates[template_id]

        # 如果是統一費率（無假日費率）
        if template.holiday_type == HolidayType.NO_HOLIDAY_RATE:
            if template.unified_plan:
                return template.unified_plan
            return template.weekday_plan

        # 根據日期類別選擇對應的費率方案
        if date_category == DateCategory.WEEKDAY:
            return template.weekday_plan
        elif date_category == DateCategory.WEEKEND:
            return template.weekend_plan or template.weekday_plan
        elif date_category == DateCategory.NATIONAL_HOLIDAY:
            return (
                template.national_holiday_plan
                or template.weekend_plan
                or template.weekday_plan
            )
        elif date_category == DateCategory.CUSTOM_HOLIDAY:
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

    def calculate_parking_fee(
        self, enter_time: datetime, exit_time: datetime, template_id: str
    ) -> ParkingCalculationResult:
        """計算停車費用（多維度版本）"""
        if template_id not in self.rate_plan_templates:
            raise ValueError(f"找不到費率範本: {template_id}")

        template = self.rate_plan_templates[template_id]

        # 判斷日期類別
        park_date = enter_time.date()
        date_category = self.get_date_category(park_date)

        # 獲取適用的費率方案
        rate_plan = self.get_applicable_plan(template_id, date_category)

        if not rate_plan:
            raise ValueError("無法找到適用的費率方案")

        # 計算總停車時間
        total_duration = int((exit_time - enter_time).total_seconds() / 60)

        # 分時段計算費用
        time_slots = rate_plan.get("time_slots", [])
        session_details = []
        total_fee = 0

        for slot in time_slots:
            slot_duration = self.calculate_slot_duration(
                enter_time, exit_time, slot["start"], slot["end"]
            )

            if slot_duration > 0:
                slot_fee, slot_detail = self.calculate_time_slot_fee(
                    slot, slot_duration
                )
                total_fee += slot_fee

                session_details.append(
                    {
                        "time_slot_id": slot["time_slot_id"],
                        "label": slot["label"],
                        "start": slot["start"],
                        "end": slot["end"],
                        "duration": slot_duration,
                        "fee": slot_fee,
                        "details": slot_detail,
                    }
                )

        # 檢查每日上限
        daily_cap_enabled = rate_plan.get("daily_cap_enabled", False)
        daily_cap_amount = rate_plan.get("daily_cap_amount", 0)
        is_daily_capped = False

        if daily_cap_enabled and daily_cap_amount > 0 and total_fee > daily_cap_amount:
            total_fee = daily_cap_amount
            is_daily_capped = True

        # 生成維度標籤
        dimension_tags = [
            template.time_segment_type.value,
            template.holiday_type.value,
            date_category.value,
            f"總時段數: {len([s for s in session_details if s['duration'] > 0])}",
        ]

        # 計算摘要
        calculation_summary = f"""
多維度停車費計算結果:
- 時段類型: {template.time_segment_type.value}
- 假日類型: {template.holiday_type.value}  
- 日期類別: {date_category.value}
- 停車時間: {total_duration}分鐘
- 總費用: {total_fee}元
- 適用方案: {rate_plan.get('label', '未知')}
- 每日上限: {'是' if is_daily_capped else '否'} ({daily_cap_amount}元)
""".strip()

        return ParkingCalculationResult(
            total_amount=total_fee,
            original_amount=sum(detail["fee"] for detail in session_details),
            date_category=date_category,
            applied_rate_plan=rate_plan.get("label", "未知"),
            time_segment_type=template.time_segment_type.value,
            holiday_type=template.holiday_type.value,
            session_details=session_details,
            calculation_summary=calculation_summary,
            dimension_tags=dimension_tags,
        )

    def get_available_templates(self) -> Dict[str, str]:
        """獲取可用的費率範本列表"""
        templates = {}
        for template_id, template in self.rate_plan_templates.items():
            templates[template_id] = (
                f"{template.label} ({template.time_segment_type.value} × {template.holiday_type.value})"
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
