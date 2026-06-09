"""
停車費率計算模組
支援多段時間段、累進費率、上限控制、緩衝時間等功能
完整支援功能開關系統，提供最大彈性
新增：車輛類型、優惠機制、動態定價支援
"""

import json
import math
from datetime import datetime, date, time, timedelta
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum


class VehicleType(Enum):
    """車輛類型枚舉"""

    CAR = "car"
    MOTORCYCLE = "motorcycle"
    LARGE_VEHICLE = "large_vehicle"
    ELECTRIC_VEHICLE = "electric_vehicle"
    BICYCLE = "bicycle"


class DiscountType(Enum):
    """優惠類型枚舉"""

    RESIDENT = "resident"
    DISABLED = "disabled"
    STUDENT = "student"
    EMPLOYEE = "employee"
    CONSUMPTION = "consumption"
    CREDIT_CARD = "credit_card"
    MEMBER = "member"
    TIME_BASED = "time_based"


@dataclass
class TimeSlot:
    """時間段資料結構（完整版）"""

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
    progressive_rates: List[Dict]
    custom_enabled: bool = False
    custom_config: Dict[str, Any] = None
    apply_on_festival: bool = True
    holiday_rate_multiplier: float = 1.0
    festival_rate_multiplier: float = 1.0


@dataclass
class DiscountRule:
    """優惠規則資料結構"""

    discount_id: str
    discount_type: DiscountType
    name: str
    description: str
    discount_value: float  # 折扣比例 (0-1) 或固定金額
    discount_mode: str  # "percentage" 或 "fixed_amount" 或 "free_hours"
    eligibility_conditions: Dict[str, Any]
    daily_limit: Optional[int] = None
    monthly_limit: Optional[int] = None
    max_discount_amount: Optional[int] = None
    stackable: bool = False
    priority: int = 0


@dataclass
class VehicleTypeConfig:
    """車輛類型配置"""

    vehicle_type: VehicleType
    rate_multiplier: float = 1.0
    daily_cap_multiplier: float = 1.0
    grace_period_multiplier: float = 1.0
    applicable_discounts: List[str] = None


@dataclass
class DynamicPricingConfig:
    """動態定價配置"""

    enabled: bool = False
    occupancy_thresholds: List[Dict[str, Any]] = None
    event_multipliers: Dict[str, float] = None
    weather_adjustments: Dict[str, float] = None
    time_based_adjustments: Dict[str, float] = None


@dataclass
class RatePlan:
    """費率方案資料結構（完整版 - 支援車輛類型和優惠）"""

    rate_plan_id: str
    label: str
    description: str
    date_type: str
    apply_on_holiday: bool
    daily_cap_enabled: bool
    daily_cap_amount: Optional[int]
    split_by_timeslot_enabled: bool
    split_by_day_enabled: bool
    night_cross_day_split: bool
    enable_zero_fee: bool
    round_up_enabled: bool
    skip_fee_when_total_free: bool
    manual_override_enabled: bool
    time_slots: List[TimeSlot]
    vehicle_type_configs: List[VehicleTypeConfig] = None
    discount_rules: List[DiscountRule] = None
    dynamic_pricing: DynamicPricingConfig = None


@dataclass
class ParkingSession:
    """停車時段計算結果（詳細版）"""

    time_slot_id: str
    label: str
    start_time: datetime
    end_time: datetime
    duration_minutes: int
    original_amount: int
    final_amount: int
    is_free_period: bool
    is_capped: bool
    calculation_details: str
    progressive_details: List[Dict]


@dataclass
class SplitInterval:
    """停車時間切割區間"""

    start_time: datetime
    end_time: datetime
    duration_minutes: int
    date_type: str
    rate_plan_id: str
    time_slot_id: str


class ParkingCalculator:
    """停車費計算器（完整版 - 支援萬用計費模型）"""

    def __init__(self, config_path: str = "config/rate_plans.json"):
        """初始化計算器並載入設定"""
        self.rate_plans = {}
        self.holiday_calendar = {}
        self.load_config(config_path)

    def load_config(self, config_path: str):
        """載入費率設定檔"""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            # 載入費率方案
            for plan_data in config["rate_plans"]:
                time_slots = []
                for slot_data in plan_data["time_slots"]:
                    # 確保所有必要字段都存在，提供預設值
                    time_slot = TimeSlot(
                        time_slot_id=slot_data.get(
                            "time_slot_id", slot_data.get("slot_id", "")
                        ),
                        label=slot_data.get("label", ""),
                        start=slot_data.get("start", "00:00"),
                        end=slot_data.get("end", "24:00"),
                        unit_minutes=slot_data.get("unit_minutes", 60),
                        grace_minutes=slot_data.get("grace_minutes", 0),
                        grace_enabled=slot_data.get("grace_enabled", True),
                        cap_enabled=slot_data.get("cap_enabled", True),
                        cap_amount=slot_data.get("cap_amount", 0),
                        progressive_enabled=slot_data.get("progressive_enabled", False),
                        default_unit_price=slot_data.get(
                            "default_unit_price", slot_data.get("unit_price", 0)
                        ),
                        progressive_rates=slot_data.get("progressive_rates", []),
                        custom_enabled=slot_data.get("custom_enabled", False),
                        custom_config=slot_data.get("custom_config", None),
                        apply_on_festival=slot_data.get("apply_on_festival", True),
                        holiday_rate_multiplier=slot_data.get(
                            "holiday_rate_multiplier", 1.0
                        ),
                        festival_rate_multiplier=slot_data.get(
                            "festival_rate_multiplier", 1.0
                        ),
                    )
                    time_slots.append(time_slot)

                # 載入車輛類型配置
                vehicle_type_configs = []
                if "vehicle_type_configs" in plan_data:
                    for config_data in plan_data["vehicle_type_configs"]:
                        vehicle_config = VehicleTypeConfig(
                            vehicle_type=VehicleType(config_data["vehicle_type"]),
                            rate_multiplier=config_data.get("rate_multiplier", 1.0),
                            daily_cap_multiplier=config_data.get(
                                "daily_cap_multiplier", 1.0
                            ),
                            grace_period_multiplier=config_data.get(
                                "grace_period_multiplier", 1.0
                            ),
                            applicable_discounts=config_data.get(
                                "applicable_discounts", []
                            ),
                        )
                        vehicle_type_configs.append(vehicle_config)

                # 載入優惠規則
                discount_rules = []
                if "discount_rules" in plan_data:
                    for discount_data in plan_data["discount_rules"]:
                        discount_rule = DiscountRule(
                            discount_id=discount_data["discount_id"],
                            discount_type=DiscountType(discount_data["discount_type"]),
                            name=discount_data["name"],
                            description=discount_data["description"],
                            discount_value=discount_data["discount_value"],
                            discount_mode=discount_data["discount_mode"],
                            eligibility_conditions=discount_data.get(
                                "eligibility_conditions", {}
                            ),
                            daily_limit=discount_data.get("daily_limit"),
                            monthly_limit=discount_data.get("monthly_limit"),
                            max_discount_amount=discount_data.get(
                                "max_discount_amount"
                            ),
                            stackable=discount_data.get("stackable", False),
                            priority=discount_data.get("priority", 0),
                        )
                        discount_rules.append(discount_rule)

                # 載入動態定價配置
                dynamic_pricing = None
                if "dynamic_pricing" in plan_data:
                    dp_data = plan_data["dynamic_pricing"]
                    dynamic_pricing = DynamicPricingConfig(
                        enabled=dp_data.get("enabled", False),
                        occupancy_thresholds=dp_data.get("occupancy_thresholds", []),
                        event_multipliers=dp_data.get("event_multipliers", {}),
                        weather_adjustments=dp_data.get("weather_adjustments", {}),
                        time_based_adjustments=dp_data.get(
                            "time_based_adjustments", {}
                        ),
                    )

                rate_plan = RatePlan(
                    rate_plan_id=plan_data["rate_plan_id"],
                    label=plan_data["label"],
                    description=plan_data["description"],
                    date_type=plan_data["date_type"],
                    apply_on_holiday=plan_data.get("apply_on_holiday", True),
                    daily_cap_enabled=plan_data.get("daily_cap_enabled", False),
                    daily_cap_amount=plan_data.get("daily_cap_amount"),
                    split_by_timeslot_enabled=plan_data.get(
                        "split_by_timeslot_enabled", True
                    ),
                    split_by_day_enabled=plan_data.get("split_by_day_enabled", True),
                    night_cross_day_split=plan_data.get("night_cross_day_split", True),
                    enable_zero_fee=plan_data.get("enable_zero_fee", True),
                    round_up_enabled=plan_data.get("round_up_enabled", True),
                    skip_fee_when_total_free=plan_data.get(
                        "skip_fee_when_total_free", True
                    ),
                    manual_override_enabled=plan_data.get(
                        "manual_override_enabled", True
                    ),
                    time_slots=time_slots,
                    vehicle_type_configs=vehicle_type_configs,
                    discount_rules=discount_rules,
                    dynamic_pricing=dynamic_pricing,
                )

                self.rate_plans[rate_plan.rate_plan_id] = rate_plan

            # 載入假日設定
            self.holiday_calendar = config.get("holiday_calendar", {})

        except Exception as e:
            raise Exception(f"載入設定檔失敗: {e}")

    def load_rate_plans(self, config_path: str = "config/rate_plans.json"):
        """重新載入費率方案設定"""
        self.rate_plans = {}
        self.load_config(config_path)

    def is_holiday(self, check_date: date) -> bool:
        """判斷是否為假日"""
        date_str = check_date.strftime("%Y-%m-%d")

        # 檢查自訂工作日（優先級最高）
        if date_str in self.holiday_calendar.get("custom_workdays", []):
            return False

        # 檢查自訂假日
        if date_str in self.holiday_calendar.get("custom_holidays", []):
            return True

        # 檢查是否為週末
        if self.holiday_calendar.get("weekend_as_holiday", True):
            if check_date.weekday() >= 5:  # 週六日
                return True

        return False

    def is_festival(self, check_date: date) -> bool:
        """判斷是否為節慶日"""
        date_str = check_date.strftime("%Y-%m-%d")

        # 檢查節慶假日列表
        festival_days = self.holiday_calendar.get("festival_holidays", [])
        if date_str in festival_days:
            return True

        # 檢查農曆節日（如果有設定的話）
        lunar_festivals = self.holiday_calendar.get("lunar_festivals", [])
        if self._check_lunar_festival(check_date, lunar_festivals):
            return True

        return False

    def _check_lunar_festival(
        self, check_date: date, lunar_festivals: List[Dict]
    ) -> bool:
        """檢查農曆節日（簡化實現）"""
        # 這裡可以整合第三方農曆計算庫
        # 目前先返回False，待後續實現
        return False

    def get_date_type(self, check_date: date) -> str:
        """取得日期類型（增強版）"""
        if self.is_festival(check_date):
            return "festival"
        elif self.is_holiday(check_date):
            return "holiday"
        else:
            return "weekday"

    def parse_time_string(self, time_str: str) -> time:
        """解析時間字串"""
        if time_str == "24:00":
            return time(23, 59, 59)
        hour, minute = map(int, time_str.split(":"))
        return time(hour, minute)

    def get_applicable_rate_plan(
        self, check_date: date, rate_plan_id: str = None
    ) -> Optional[RatePlan]:
        """取得適用的費率方案（增強版 - 支援節慶日）"""
        date_type = self.get_date_type(check_date)
        is_festival = date_type == "festival"
        is_holiday = date_type == "holiday"
        is_weekday = date_type == "weekday"

        if rate_plan_id:
            # 指定方案ID
            if rate_plan_id in self.rate_plans:
                plan = self.rate_plans[rate_plan_id]
                # 檢查方案是否適用於當前日期類型
                if (
                    (is_festival and plan.apply_on_holiday)
                    or (is_holiday and plan.apply_on_holiday)
                    or (is_weekday and plan.date_type == "weekday")
                ):
                    return plan
            return None
        else:
            # 自動選擇方案 - 優先順序：節慶 > 假日 > 平日
            # 首先查找專門的節慶方案
            if is_festival or is_holiday:
                for plan in self.rate_plans.values():
                    if plan.date_type == "holiday" and plan.apply_on_holiday:
                        return plan

            # 查找平日方案
            if is_weekday:
                for plan in self.rate_plans.values():
                    if plan.date_type == "weekday":
                        return plan

            return None

    def split_parking_duration_advanced(
        self, enter_time: datetime, exit_time: datetime, rate_plan: RatePlan
    ) -> List[SplitInterval]:
        """進階停車時間切分（支援所有功能開關）- 每個時段分別產生明細"""
        intervals = []
        current_time = enter_time

        while current_time < exit_time:
            current_date = current_time.date()

            # 取得適用的費率方案
            applicable_plan = self.get_applicable_rate_plan(
                current_date, rate_plan.rate_plan_id
            )
            if not applicable_plan:
                applicable_plan = rate_plan

            # 如果不依時段切分，使用全天時段
            if not applicable_plan.split_by_timeslot_enabled:
                # 找全天時段或第一個時段
                time_slot = None
                for slot in applicable_plan.time_slots:
                    if slot.start == "00:00" and slot.end in ["24:00", "23:59"]:
                        time_slot = slot
                        break
                if not time_slot and applicable_plan.time_slots:
                    time_slot = applicable_plan.time_slots[0]

                if time_slot:
                    # 全天時段：按日期分別計算（換日算一次明細）
                    if applicable_plan.split_by_day_enabled:
                        next_day = datetime.combine(
                            current_date + timedelta(days=1), time(0, 0)
                        )
                        session_end = min(exit_time, next_day)
                    else:
                        session_end = exit_time

                    duration = int((session_end - current_time).total_seconds() / 60)
                    intervals.append(
                        SplitInterval(
                            start_time=current_time,
                            end_time=session_end,
                            duration_minutes=duration,
                            date_type=self.get_date_type(current_date),
                            rate_plan_id=applicable_plan.rate_plan_id,
                            time_slot_id=time_slot.time_slot_id,
                        )
                    )
                    current_time = session_end
                else:
                    # 沒有時段定義，跳到隔天
                    current_time = datetime.combine(
                        current_date + timedelta(days=1), time(0, 0)
                    )
            else:
                # 依時段切分 - 每個時段都要分別產生明細
                daily_intervals = []

                # 為當天的每個時段生成區間
                for time_slot in applicable_plan.time_slots:
                    start_time_obj = self.parse_time_string(time_slot.start)
                    end_time_obj = self.parse_time_string(time_slot.end)

                    # 處理跨日時段
                    if time_slot.start > time_slot.end:  # 跨日時段
                        if applicable_plan.night_cross_day_split:
                            # 拆分跨日時段為兩個部分
                            # 第一部分：當天的後半段（從start到午夜）
                            if current_time.time() <= time(23, 59):
                                slot_start = datetime.combine(
                                    current_date, start_time_obj
                                )
                                slot_end = datetime.combine(
                                    current_date + timedelta(days=1), time(0, 0)
                                )

                                session_start = max(current_time, slot_start)
                                session_end = min(exit_time, slot_end)

                                if session_start < session_end:
                                    duration = int(
                                        (session_end - session_start).total_seconds()
                                        / 60
                                    )
                                    daily_intervals.append(
                                        SplitInterval(
                                            start_time=session_start,
                                            end_time=session_end,
                                            duration_minutes=duration,
                                            date_type=self.get_date_type(
                                                session_start.date()
                                            ),
                                            rate_plan_id=applicable_plan.rate_plan_id,
                                            time_slot_id=time_slot.time_slot_id,
                                        )
                                    )

                            # 第二部分：隔天的前半段（從午夜到end）- 只有當停車時間跨日時才處理
                            next_date = current_date + timedelta(days=1)
                            if exit_time.date() >= next_date:
                                slot_start = datetime.combine(next_date, time(0, 0))
                                slot_end = datetime.combine(next_date, end_time_obj)

                                session_start = max(current_time, slot_start)
                                session_end = min(exit_time, slot_end)

                                if session_start < session_end:
                                    duration = int(
                                        (session_end - session_start).total_seconds()
                                        / 60
                                    )
                                    daily_intervals.append(
                                        SplitInterval(
                                            start_time=session_start,
                                            end_time=session_end,
                                            duration_minutes=duration,
                                            date_type=self.get_date_type(
                                                session_start.date()
                                            ),
                                            rate_plan_id=applicable_plan.rate_plan_id,
                                            time_slot_id=time_slot.time_slot_id,
                                        )
                                    )
                        else:
                            # 不拆分跨日時段 - 生成完整的跨日區間
                            # 根據當前時間判斷屬於跨日時段的哪一部分
                            if current_time.time() >= start_time_obj:
                                # 當前時間在跨日時段的起始部分
                                slot_start = datetime.combine(
                                    current_date, start_time_obj
                                )
                                slot_end = datetime.combine(
                                    current_date + timedelta(days=1), end_time_obj
                                )
                            elif current_time.time() <= end_time_obj:
                                # 當前時間在跨日時段的結束部分
                                slot_start = datetime.combine(
                                    current_date - timedelta(days=1), start_time_obj
                                )
                                slot_end = datetime.combine(current_date, end_time_obj)
                            else:
                                continue

                            session_start = max(current_time, slot_start)
                            session_end = min(exit_time, slot_end)

                            if session_start < session_end:
                                duration = int(
                                    (session_end - session_start).total_seconds() / 60
                                )
                                daily_intervals.append(
                                    SplitInterval(
                                        start_time=session_start,
                                        end_time=session_end,
                                        duration_minutes=duration,
                                        date_type=self.get_date_type(
                                            session_start.date()
                                        ),
                                        rate_plan_id=applicable_plan.rate_plan_id,
                                        time_slot_id=time_slot.time_slot_id,
                                    )
                                )
                    else:
                        # 同日時段
                        slot_start = datetime.combine(current_date, start_time_obj)
                        slot_end = datetime.combine(current_date, end_time_obj)

                        session_start = max(current_time, slot_start)
                        session_end = min(exit_time, slot_end)

                        if session_start < session_end:
                            duration = int(
                                (session_end - session_start).total_seconds() / 60
                            )
                            daily_intervals.append(
                                SplitInterval(
                                    start_time=session_start,
                                    end_time=session_end,
                                    duration_minutes=duration,
                                    date_type=self.get_date_type(session_start.date()),
                                    rate_plan_id=applicable_plan.rate_plan_id,
                                    time_slot_id=time_slot.time_slot_id,
                                )
                            )

                # 將當天的區間按時間順序排序並加入結果
                daily_intervals.sort(key=lambda x: x.start_time)
                intervals.extend(daily_intervals)

                # 更新當前時間到下一個未處理的時間點
                if daily_intervals:
                    # 找到最後處理的時間點
                    last_end_time = max(
                        interval.end_time for interval in daily_intervals
                    )
                    current_time = last_end_time

                    # 如果還沒處理完當天，繼續處理
                    if current_time.date() == current_date and current_time < exit_time:
                        # 跳到隔天開始
                        current_time = datetime.combine(
                            current_date + timedelta(days=1), time(0, 0)
                        )
                else:
                    # 如果當天沒有任何匹配的時段，跳到隔天
                    current_time = datetime.combine(
                        current_date + timedelta(days=1), time(0, 0)
                    )

        return intervals

    def calculate_progressive_rate_advanced(
        self,
        duration_minutes: int,
        progressive_rates: List[Dict],
        round_up_enabled: bool,
    ) -> Tuple[int, List[Dict]]:
        """進階累進費率計算"""
        total_amount = 0
        details = []

        for rate_tier in progressive_rates:
            start_min = rate_tier["start_min"]
            end_min = rate_tier["end_min"]
            unit_minutes = rate_tier["unit_minutes"]
            unit_price = rate_tier["unit_price"]

            # 計算這一階段的時間
            if end_min is None:
                tier_duration = max(0, duration_minutes - start_min)
            else:
                tier_duration = max(0, min(duration_minutes, end_min) - start_min)

            if tier_duration > 0:
                # 計算單位數
                if round_up_enabled:
                    units = math.ceil(tier_duration / unit_minutes)
                else:
                    units = tier_duration / unit_minutes

                tier_amount = int(units * unit_price)
                total_amount += tier_amount

                end_display = f"{end_min}分" if end_min else "以上"
                details.append(
                    {
                        "tier_range": f"{start_min}-{end_display}",
                        "duration": tier_duration,
                        "units": units,
                        "unit_price": unit_price,
                        "amount": tier_amount,
                    }
                )

        return total_amount, details

    def calculate_slot_fee_advanced(
        self,
        time_slot: TimeSlot,
        duration_minutes: int,
        rate_plan: RatePlan,
        session_date: date = None,
    ) -> ParkingSession:
        """進階時段費用計算（支援假日節慶日費率調整）"""

        # 檢查緩衝時間
        is_free_period = False
        if time_slot.grace_enabled and duration_minutes <= time_slot.grace_minutes:
            if rate_plan.enable_zero_fee:
                is_free_period = True

        # 如果在免費時段內
        if is_free_period:
            return ParkingSession(
                time_slot_id=time_slot.time_slot_id,
                label=time_slot.label,
                start_time=datetime.now(),  # 會被後續設定
                end_time=datetime.now(),  # 會被後續設定
                duration_minutes=duration_minutes,
                original_amount=0,
                final_amount=0,
                is_free_period=True,
                is_capped=False,
                calculation_details=f"免費時段（{time_slot.grace_minutes}分鐘內）",
                progressive_details=[],
            )

        # 檢查假日和節慶日狀態，並決定費率倍數
        rate_multiplier = 1.0
        date_type_description = "平日"

        date_type = self.get_date_type(session_date)

        if date_type == "weekend":
            # 週末不需要特殊處理，使用預設倍數
            date_type_description = "週末"

        if date_type == "festival":
            # 檢查時段是否適用於節慶日
            if time_slot.apply_on_festival:
                rate_multiplier = time_slot.festival_rate_multiplier
                date_type_description = "節慶日"
            else:
                # 不適用節慶日時，使用假日費率（因為方案層級已經控制假日適用性）
                if self.is_holiday(session_date):
                    rate_multiplier = time_slot.holiday_rate_multiplier
                    date_type_description = "假日"
        elif date_type == "holiday":
            # 假日費率（方案層級已經控制了適用性，所以直接應用）
            rate_multiplier = time_slot.holiday_rate_multiplier
            date_type_description = "假日"

        # 計算原始費用
        original_amount = 0
        progressive_details = []
        calculation_details = ""

        if time_slot.progressive_enabled and time_slot.progressive_rates:
            # 累進費率計算
            original_amount, progressive_details = (
                self.calculate_progressive_rate_advanced(
                    duration_minutes,
                    time_slot.progressive_rates,
                    rate_plan.round_up_enabled,
                )
            )
            calculation_details = f"累進費率計算，共{len(progressive_details)}階段"
        else:
            # 單一費率計算
            # 特例：若 unit_minutes >= 1440（計次/每日），至少收一單位
            base_price = time_slot.default_unit_price
            if time_slot.unit_minutes >= 1440:
                units = 1
            else:
                if rate_plan.round_up_enabled:
                    units = math.ceil(duration_minutes / time_slot.unit_minutes)
                else:
                    units = duration_minutes / time_slot.unit_minutes

            original_amount = int(units * base_price)
            calculation_details = f"單一費率：{duration_minutes}分鐘 ÷ {time_slot.unit_minutes}分鐘 × {base_price}元（單位數：{units}）"

        # 應用假日/節慶日費率調整
        if rate_multiplier != 1.0:
            original_amount = int(original_amount * rate_multiplier)
            calculation_details += (
                f"，{date_type_description}費率調整（×{rate_multiplier}）"
            )

        # 檢查上限
        final_amount = original_amount
        is_capped = False

        if time_slot.cap_enabled and time_slot.cap_amount > 0:
            adjusted_cap = int(time_slot.cap_amount * rate_multiplier)
            if original_amount > adjusted_cap:
                final_amount = adjusted_cap
                is_capped = True
                calculation_details += f"，觸發上限（{adjusted_cap}元）"

        # 處理自定義配置
        if time_slot.custom_enabled and time_slot.custom_config:
            final_amount = self._apply_custom_config(
                final_amount, time_slot.custom_config, session_date
            )
            calculation_details += "，套用自定義配置"

        return ParkingSession(
            time_slot_id=time_slot.time_slot_id,
            label=time_slot.label,
            start_time=datetime.now(),  # 會被後續設定
            end_time=datetime.now(),  # 會被後續設定
            duration_minutes=duration_minutes,
            original_amount=original_amount,
            final_amount=final_amount,
            is_free_period=is_free_period,
            is_capped=is_capped,
            calculation_details=calculation_details,
            progressive_details=progressive_details,
        )

    def _apply_custom_config(
        self, amount: int, custom_config: Dict[str, Any], session_date: date = None
    ) -> int:
        """應用自定義配置"""
        if not custom_config:
            return amount

        # 支援的自定義配置類型
        config_type = custom_config.get("type", "none")

        if config_type == "fixed_discount":
            # 固定折扣
            discount = custom_config.get("discount", 0)
            return max(0, amount - discount)

        elif config_type == "percentage_discount":
            # 百分比折扣
            discount_rate = custom_config.get("discount_rate", 0)
            return max(0, int(amount * (1 - discount_rate)))

        elif config_type == "time_based":
            # 時間基礎調整
            if session_date:
                hour = datetime.now().hour
                time_adjustments = custom_config.get("time_adjustments", {})
                for time_range, multiplier in time_adjustments.items():
                    start_hour, end_hour = map(int, time_range.split("-"))
                    if start_hour <= hour < end_hour:
                        return int(amount * multiplier)

        elif config_type == "conditional":
            # 條件式調整
            conditions = custom_config.get("conditions", [])
            for condition in conditions:
                if self._check_custom_condition(condition, session_date):
                    multiplier = condition.get("multiplier", 1.0)
                    return int(amount * multiplier)

        return amount

    def _check_custom_condition(
        self, condition: Dict[str, Any], session_date: date = None
    ) -> bool:
        """檢查自定義條件"""
        condition_type = condition.get("type", "none")

        if condition_type == "date_range" and session_date:
            start_date = datetime.strptime(
                condition.get("start_date", "1900-01-01"), "%Y-%m-%d"
            ).date()
            end_date = datetime.strptime(
                condition.get("end_date", "2100-12-31"), "%Y-%m-%d"
            ).date()
            return start_date <= session_date <= end_date

        elif condition_type == "weekday" and session_date:
            target_weekdays = condition.get("weekdays", [])
            return session_date.weekday() in target_weekdays

        return False

    def calculate_parking_fee(
        self,
        enter_time: datetime,
        exit_time: datetime,
        rate_plan_id: str,
        manual_adjustment: int = 0,
        vehicle_type: VehicleType = VehicleType.CAR,
        user_conditions: Dict[str, Any] = None,
        dynamic_context: Dict[str, Any] = None,
    ) -> Dict:
        """完整停車費計算（支援所有功能開關，包含車輛類型、優惠和動態定價）"""
        try:
            if rate_plan_id not in self.rate_plans:
                raise ValueError(f"找不到費率方案: {rate_plan_id}")

            rate_plan = self.rate_plans[rate_plan_id]

            # 取得車輛類型配置
            vehicle_config = self.get_vehicle_type_config(rate_plan, vehicle_type)

            # 計算總停車時長
            total_duration = int((exit_time - enter_time).total_seconds() / 60)

            # 切分停車時間
            split_intervals = self.split_parking_duration_advanced(
                enter_time, exit_time, rate_plan
            )

            # 計算各時段費用
            parking_sessions = []
            daily_totals = {}  # 用於計算每日封頂

            for interval in split_intervals:
                # 找到對應的時段定義
                applicable_plan = self.get_applicable_rate_plan(
                    interval.start_time.date(), interval.rate_plan_id
                )
                if not applicable_plan:
                    applicable_plan = rate_plan

                time_slot = None
                for slot in applicable_plan.time_slots:
                    if slot.time_slot_id == interval.time_slot_id:
                        time_slot = slot
                        break

                if time_slot:
                    session = self.calculate_slot_fee_advanced(
                        time_slot,
                        interval.duration_minutes,
                        applicable_plan,
                        interval.start_time.date(),
                    )
                    session.start_time = interval.start_time
                    session.end_time = interval.end_time
                    parking_sessions.append(session)

                    # 累計每日費用（用於每日封頂計算）
                    session_date = interval.start_time.date().strftime("%Y-%m-%d")
                    if session_date not in daily_totals:
                        daily_totals[session_date] = 0
                    daily_totals[session_date] += session.final_amount

            # 應用每日封頂
            if rate_plan.daily_cap_enabled and rate_plan.daily_cap_amount:
                for session_date, daily_total in daily_totals.items():
                    if daily_total > rate_plan.daily_cap_amount:
                        # 計算需要調整的比例
                        adjustment_ratio = rate_plan.daily_cap_amount / daily_total
                        # 調整該日所有時段的費用
                        for session in parking_sessions:
                            if (
                                session.start_time.date().strftime("%Y-%m-%d")
                                == session_date
                            ):
                                session.final_amount = int(
                                    session.final_amount * adjustment_ratio
                                )
                                session.calculation_details += (
                                    f"，套用每日封頂（{rate_plan.daily_cap_amount}元）"
                                )

            # 計算總費用
            total_charge = sum(session.final_amount for session in parking_sessions)

            # 應用車輛類型倍數
            if vehicle_config and vehicle_config.rate_multiplier != 1.0:
                total_charge = int(total_charge * vehicle_config.rate_multiplier)

            # 應用動態定價
            if dynamic_context:
                total_charge = self.apply_dynamic_pricing(
                    rate_plan, total_charge, dynamic_context
                )

            # 應用優惠折扣
            discount_details = []
            if user_conditions:
                total_charge, discount_details = self.calculate_discounts(
                    rate_plan, total_charge, vehicle_type, user_conditions
                )

            # 檢查是否跳過全免費情況
            if rate_plan.skip_fee_when_total_free and total_charge == 0:
                final_charge = 0
            else:
                final_charge = total_charge

            # 手動調整
            if rate_plan.manual_override_enabled and manual_adjustment != 0:
                final_charge += manual_adjustment

            # 組織結果
            session_rows = [
                {
                    "time_slot_id": session.time_slot_id,
                    "label": session.label,
                    "start_time": session.start_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "end_time": session.end_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "duration_minutes": session.duration_minutes,
                    "duration": session.duration_minutes,
                    "original_amount": session.original_amount,
                    "final_amount": session.final_amount,
                    "fee": session.final_amount,
                    "amount": session.final_amount,
                    "is_free_period": session.is_free_period,
                    "is_capped": session.is_capped,
                    "calculation_details": session.calculation_details,
                    "progressive_details": session.progressive_details,
                }
                for session in parking_sessions
            ]

            result = {
                "enter_time": enter_time.strftime("%Y-%m-%d %H:%M:%S"),
                "exit_time": exit_time.strftime("%Y-%m-%d %H:%M:%S"),
                "total_duration_minutes": total_duration,
                "rate_plan_id": rate_plan_id,
                "plan_id": rate_plan_id,
                "rate_plan_label": rate_plan.label,
                "session_details": session_rows,
                "sessions": session_rows,
                "total_charge": total_charge,
                "manual_adjustment": manual_adjustment,
                "total_amount": final_charge,
                "final_charge": final_charge,
                "daily_cap_applied": rate_plan.daily_cap_enabled,
                "vehicle_type": vehicle_type.value,
                "vehicle_rate_multiplier": (
                    vehicle_config.rate_multiplier if vehicle_config else 1.0
                ),
                "discounts_applied": discount_details,
                "dynamic_pricing_applied": bool(
                    dynamic_context
                    and rate_plan.dynamic_pricing
                    and rate_plan.dynamic_pricing.enabled
                ),
                "features_used": {
                    "progressive_rates": any(
                        session.progressive_details for session in parking_sessions
                    ),
                    "grace_period": any(
                        session.is_free_period for session in parking_sessions
                    ),
                    "amount_capping": any(
                        session.is_capped for session in parking_sessions
                    ),
                    "daily_capping": rate_plan.daily_cap_enabled,
                    "manual_adjustment": manual_adjustment != 0,
                },
            }

            return result

        except Exception as e:
            raise Exception(f"計算停車費用失敗: {str(e)}")

    def get_available_rate_plans(self) -> Dict[str, str]:
        """取得可用的費率方案清單"""
        return {plan_id: plan.label for plan_id, plan in self.rate_plans.items()}

    def get_vehicle_type_config(
        self, rate_plan: RatePlan, vehicle_type: VehicleType
    ) -> Optional[VehicleTypeConfig]:
        """取得指定車輛類型的配置"""
        if not rate_plan.vehicle_type_configs:
            return None

        for config in rate_plan.vehicle_type_configs:
            if config.vehicle_type == vehicle_type:
                return config
        return None

    def calculate_discounts(
        self,
        rate_plan: RatePlan,
        base_amount: int,
        vehicle_type: VehicleType = VehicleType.CAR,
        user_conditions: Dict[str, Any] = None,
    ) -> Tuple[int, List[Dict]]:
        """計算優惠折扣"""
        if not rate_plan.discount_rules or not user_conditions:
            return base_amount, []

        applicable_discounts = []
        total_discount = 0
        discount_details = []

        # 取得適用於該車輛類型的優惠
        vehicle_config = self.get_vehicle_type_config(rate_plan, vehicle_type)
        allowed_discounts = (
            vehicle_config.applicable_discounts if vehicle_config else None
        )

        # 按優先級排序優惠規則
        sorted_discounts = sorted(
            rate_plan.discount_rules, key=lambda x: x.priority, reverse=True
        )

        for discount in sorted_discounts:
            # 檢查是否適用於該車輛類型
            if allowed_discounts and discount.discount_id not in allowed_discounts:
                continue

            # 檢查優惠條件
            if self.check_discount_eligibility(discount, user_conditions):
                discount_amount = 0

                if discount.discount_mode == "percentage":
                    discount_amount = int(base_amount * discount.discount_value)
                elif discount.discount_mode == "fixed_amount":
                    discount_amount = int(discount.discount_value)
                elif discount.discount_mode == "free_hours":
                    # 免費時數處理 - 這裡簡化為固定金額
                    discount_amount = int(discount.discount_value)

                # 檢查優惠上限
                if discount.max_discount_amount:
                    discount_amount = min(discount_amount, discount.max_discount_amount)

                if discount.stackable:
                    total_discount += discount_amount
                else:
                    total_discount = max(total_discount, discount_amount)

                discount_details.append(
                    {
                        "discount_id": discount.discount_id,
                        "name": discount.name,
                        "amount": discount_amount,
                        "mode": discount.discount_mode,
                    }
                )

        final_amount = max(0, base_amount - total_discount)
        return final_amount, discount_details

    def check_discount_eligibility(
        self, discount: DiscountRule, user_conditions: Dict[str, Any]
    ) -> bool:
        """檢查優惠資格"""
        if not user_conditions:
            return False

        conditions = discount.eligibility_conditions

        # 檢查居民資格
        if discount.discount_type == DiscountType.RESIDENT:
            return user_conditions.get("is_resident", False)

        # 檢查身心障礙資格
        elif discount.discount_type == DiscountType.DISABLED:
            return user_conditions.get("has_disability_card", False)

        # 檢查學生資格
        elif discount.discount_type == DiscountType.STUDENT:
            return user_conditions.get("is_student", False)

        # 檢查員工資格
        elif discount.discount_type == DiscountType.EMPLOYEE:
            return user_conditions.get("is_employee", False)

        # 檢查消費條件
        elif discount.discount_type == DiscountType.CONSUMPTION:
            required_amount = conditions.get("min_consumption", 0)
            actual_amount = user_conditions.get("consumption_amount", 0)
            return actual_amount >= required_amount

        # 檢查信用卡條件
        elif discount.discount_type == DiscountType.CREDIT_CARD:
            required_cards = conditions.get("accepted_cards", [])
            user_card = user_conditions.get("credit_card_type", "")
            return user_card in required_cards

        # 檢查會員資格
        elif discount.discount_type == DiscountType.MEMBER:
            required_level = conditions.get("min_member_level", "")
            user_level = user_conditions.get("member_level", "")
            return user_level == required_level

        return False

    def apply_dynamic_pricing(
        self, rate_plan: RatePlan, base_amount: int, context: Dict[str, Any] = None
    ) -> int:
        """應用動態定價"""
        if not rate_plan.dynamic_pricing or not rate_plan.dynamic_pricing.enabled:
            return base_amount

        multiplier = 1.0

        # 佔用率調整
        if context and rate_plan.dynamic_pricing.occupancy_thresholds:
            occupancy_rate = context.get("occupancy_rate", 0)
            for threshold in rate_plan.dynamic_pricing.occupancy_thresholds:
                if occupancy_rate >= threshold.get("threshold", 0):
                    multiplier = threshold.get("multiplier", 1.0)

        # 事件調整
        if context and rate_plan.dynamic_pricing.event_multipliers:
            event_type = context.get("event_type")
            if event_type in rate_plan.dynamic_pricing.event_multipliers:
                multiplier *= rate_plan.dynamic_pricing.event_multipliers[event_type]

        # 天氣調整
        if context and rate_plan.dynamic_pricing.weather_adjustments:
            weather = context.get("weather")
            if weather in rate_plan.dynamic_pricing.weather_adjustments:
                multiplier *= rate_plan.dynamic_pricing.weather_adjustments[weather]

        return int(base_amount * multiplier)


def main():
    """測試主程式"""
    calculator = ParkingCalculator()

    # 測試案例
    enter_time = datetime.strptime("2024-06-19 07:45", "%Y-%m-%d %H:%M")
    exit_time = datetime.strptime("2024-06-19 12:30", "%Y-%m-%d %H:%M")

    result = calculator.calculate_parking_fee(enter_time, exit_time, "weekday_standard")

    print("=== 停車費計算結果 ===")
    print(f"進場時間: {result['enter_time']}")
    print(f"出場時間: {result['exit_time']}")
    print(f"停車時長: {result['total_duration_minutes']} 分鐘")
    print(f"費率方案: {result['rate_plan_label']}")
    print(f"最終費用: {result['final_charge']} 元")

    print("\n=== 計費明細 ===")
    for session in result["sessions"]:
        print(f"時段: {session['label']}")
        print(f"  時間: {session['start_time']} ~ {session['end_time']}")
        print(f"  時長: {session['duration_minutes']} 分鐘")
        print(f"  費用: {session['final_amount']} 元")
        print(f"  詳情: {session['calculation_details']}")


if __name__ == "__main__":
    main()
