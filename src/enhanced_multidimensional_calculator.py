"""
增強版多維度停車費計算器
實現嚴謹的時間區段連續性保障和多段式累進費率機制
支援真正的多維度陣列組合計算
"""

import json
import math
from datetime import datetime, date, time, timedelta
from typing import List, Dict, Optional, Tuple, Any, Union
from dataclasses import dataclass
from enum import Enum
import calendar


class SegmentType(Enum):
    """時間區段類型枚舉"""

    ALL_DAY = "全天"
    TWO_SEGMENT = "二段"
    THREE_SEGMENT = "三段"
    CUSTOM_SEGMENT = "任意段"


class HolidayType(Enum):
    """節假日類型枚舉"""

    NO_HOLIDAY = "無假日"
    WEEKDAY_WEEKEND = "平日假日"
    FULL_HOLIDAY = "完整假日"


class DateCategory(Enum):
    """日期類別枚舉"""

    WEEKDAY = "平日"
    WEEKEND = "假日"
    NATIONAL_HOLIDAY = "節慶日"


class CapType(Enum):
    """收費上限類型枚舉"""

    NONE = "none"
    DAILY = "daily"
    SEGMENT = "segment"


@dataclass
class ProgressiveRate:
    """累進費率階段"""

    stage: int
    time_range: str
    rate: int
    duration_minutes: int = 0  # 該階段的分鐘數


@dataclass
class TimeSegment:
    """時間區段定義"""

    name: str
    start: str  # HH:MM格式
    end: str  # HH:MM格式
    is_cross_day: bool = False  # 是否跨日


@dataclass
class RateConfig:
    """費率配置"""

    unit_time: int  # 計費單位時間(分鐘)
    grace_minutes: int  # 寬限時間
    progressive_rates: List[ProgressiveRate]
    cap_type: CapType
    cap_amount: int


@dataclass
class DimensionCombination:
    """維度組合定義"""

    segment_name: str
    holiday_type: str
    rate_config: RateConfig


@dataclass
class ValidationResult:
    """驗證結果"""

    is_valid: bool
    message: str
    details: List[str] = None


@dataclass
class CalculationResult:
    """計算結果"""

    total_amount: int
    original_amount: int
    applied_segments: List[Dict[str, Any]]
    rate_breakdown: List[Dict[str, Any]]
    cap_applied: bool = False
    cap_amount: int = 0
    calculation_summary: str = ""


class EnhancedMultidimensionalCalculator:
    """增強版多維度停車費計算器"""

    def __init__(self):
        """初始化計算器"""
        self.segments: List[TimeSegment] = []
        self.holiday_type: HolidayType = HolidayType.NO_HOLIDAY
        self.rate_matrix: Dict[str, RateConfig] = {}
        self.custom_holidays: List[str] = []  # YYYY-MM-DD格式

    def set_time_segments(self, segments: List[Dict[str, str]]) -> ValidationResult:
        """設定時間區段並驗證24小時覆蓋完整性"""
        try:
            # 轉換為TimeSegment對象
            time_segments = []
            for seg in segments:
                segment = TimeSegment(
                    name=seg["name"],
                    start=seg["start"],
                    end=seg["end"],
                    is_cross_day=self._is_cross_day(seg["start"], seg["end"]),
                )
                time_segments.append(segment)

            # 驗證24小時覆蓋
            validation = self._validate_24hour_coverage(time_segments)
            if validation.is_valid:
                self.segments = time_segments

            return validation

        except Exception as e:
            return ValidationResult(
                is_valid=False, message=f"時間區段設定失敗: {str(e)}"
            )

    def _is_cross_day(self, start_time: str, end_time: str) -> bool:
        """判斷是否為跨日時段"""
        start_hour = int(start_time.split(":")[0])
        end_hour = int(end_time.split(":")[0])

        # 如果結束時間小於開始時間，則為跨日
        if end_hour < start_hour:
            return True
        elif end_hour == start_hour:
            start_min = int(start_time.split(":")[1])
            end_min = int(end_time.split(":")[1])
            return end_min < start_min
        return False

    def _validate_24hour_coverage(
        self, segments: List[TimeSegment]
    ) -> ValidationResult:
        """驗證時間區段是否完整覆蓋24小時"""
        if not segments:
            return ValidationResult(is_valid=False, message="至少需要一個時間區段")

        # 將所有時間轉換為分鐘數進行計算
        coverage = [False] * (24 * 60)  # 24小時 * 60分鐘
        details = []

        for segment in segments:
            start_minutes = self._time_to_minutes(segment.start)
            end_minutes = self._time_to_minutes(segment.end)

            if segment.is_cross_day:
                # 跨日處理：從開始時間到24:00，然後從00:00到結束時間
                # 先處理當日剩餘部分
                for i in range(start_minutes, 24 * 60):
                    if coverage[i]:
                        return ValidationResult(
                            is_valid=False,
                            message=f"時間區段重疊: {segment.name} 在 {self._minutes_to_time(i)}",
                        )
                    coverage[i] = True

                # 再處理次日開始部分
                for i in range(0, end_minutes):
                    if coverage[i]:
                        return ValidationResult(
                            is_valid=False,
                            message=f"時間區段重疊: {segment.name} 在 {self._minutes_to_time(i)}",
                        )
                    coverage[i] = True

                details.append(
                    f"{segment.name}: {segment.start}-24:00 + 00:00-{segment.end} (跨日)"
                )
            else:
                # 正常時段處理
                if end_minutes <= start_minutes:
                    return ValidationResult(
                        is_valid=False,
                        message=f"時間區段錯誤: {segment.name} 結束時間不能早於或等於開始時間",
                    )

                for i in range(start_minutes, end_minutes):
                    if coverage[i]:
                        return ValidationResult(
                            is_valid=False,
                            message=f"時間區段重疊: {segment.name} 在 {self._minutes_to_time(i)}",
                        )
                    coverage[i] = True

                details.append(f"{segment.name}: {segment.start}-{segment.end}")

        # 檢查是否有未覆蓋的時間
        uncovered_ranges = []
        start_gap = None

        for i, covered in enumerate(coverage):
            if not covered:
                if start_gap is None:
                    start_gap = i
            else:
                if start_gap is not None:
                    uncovered_ranges.append(
                        f"{self._minutes_to_time(start_gap)}-{self._minutes_to_time(i)}"
                    )
                    start_gap = None

        # 處理最後的空隙
        if start_gap is not None:
            uncovered_ranges.append(f"{self._minutes_to_time(start_gap)}-24:00")

        if uncovered_ranges:
            return ValidationResult(
                is_valid=False,
                message=f"時間覆蓋不完整，缺少時段: {', '.join(uncovered_ranges)}",
                details=details,
            )

        return ValidationResult(
            is_valid=True, message="時間區段覆蓋完整，無重疊", details=details
        )

    def _time_to_minutes(self, time_str: str) -> int:
        """將HH:MM格式時間轉換為分鐘數"""
        hours, minutes = map(int, time_str.split(":"))
        return hours * 60 + minutes

    def _minutes_to_time(self, minutes: int) -> str:
        """將分鐘數轉換為HH:MM格式"""
        hours = minutes // 60
        mins = minutes % 60
        return f"{hours:02d}:{mins:02d}"

    def set_holiday_type(self, holiday_type: str, custom_holidays: List[str] = None):
        """設定節假日類型"""
        self.holiday_type = HolidayType(holiday_type)
        if custom_holidays:
            self.custom_holidays = custom_holidays

    def set_rate_config(
        self, segment_name: str, holiday_type: str, config: Dict[str, Any]
    ) -> bool:
        """設定特定維度組合的費率配置"""
        try:
            # 轉換累進費率
            progressive_rates = []
            for i, rate_data in enumerate(config.get("progressiveRates", [])):
                progressive_rate = ProgressiveRate(
                    stage=rate_data.get("stage", i + 1),
                    time_range=rate_data.get("timeRange", f"第{i+1}階段"),
                    rate=rate_data.get("rate", 30),
                    duration_minutes=config.get(
                        "unitTime", 60
                    ),  # 預設每階段為一個單位時間
                )
                progressive_rates.append(progressive_rate)

            rate_config = RateConfig(
                unit_time=config.get("unitTime", 60),
                grace_minutes=config.get("graceMinutes", 15),
                progressive_rates=progressive_rates,
                cap_type=CapType(config.get("capType", "daily")),
                cap_amount=config.get("capAmount", 200),
            )

            combination_key = f"{segment_name}_{holiday_type}"
            self.rate_matrix[combination_key] = rate_config
            return True

        except Exception as e:
            print(f"設定費率配置失敗: {e}")
            return False

    def get_date_category(self, check_date: date) -> DateCategory:
        """判斷日期類別"""
        date_str = check_date.strftime("%Y-%m-%d")

        # 檢查是否為自訂節慶日
        if date_str in self.custom_holidays:
            return DateCategory.NATIONAL_HOLIDAY

        # 檢查是否為週末
        if check_date.weekday() >= 5:  # 5=週六, 6=週日
            return DateCategory.WEEKEND

        return DateCategory.WEEKDAY

    def calculate_parking_fee(
        self, enter_time: datetime, exit_time: datetime
    ) -> CalculationResult:
        """計算停車費用"""
        try:
            total_amount = 0
            original_amount = 0
            applied_segments = []
            rate_breakdown = []
            cap_applied = False
            cap_amount = 0

            # 判斷日期類別
            park_date = enter_time.date()
            date_category = self.get_date_category(park_date)

            # 獲取對應的節假日類型字串
            holiday_type_str = self._get_holiday_type_string(date_category)

            # 分時段計算費用
            for segment in self.segments:
                # 計算該時段的停車時長
                segment_duration = self._calculate_segment_duration(
                    enter_time, exit_time, segment
                )

                if segment_duration > 0:
                    # 獲取該時段的費率配置
                    combination_key = f"{segment.name}_{holiday_type_str}"
                    rate_config = self.rate_matrix.get(combination_key)

                    if rate_config:
                        # 計算該時段的費用
                        segment_fee, segment_breakdown = self._calculate_segment_fee(
                            segment_duration, rate_config
                        )

                        total_amount += segment_fee
                        original_amount += segment_fee

                        applied_segments.append(
                            {
                                "segment_name": segment.name,
                                "duration_minutes": segment_duration,
                                "fee": segment_fee,
                                "rate_config_key": combination_key,
                            }
                        )

                        rate_breakdown.extend(segment_breakdown)

            # 檢查上限
            if self.segments and total_amount > 0:
                # 使用第一個時段的上限配置（假設所有時段使用相同的上限設定）
                first_segment = self.segments[0]
                holiday_type_str = self._get_holiday_type_string(date_category)
                combination_key = f"{first_segment.name}_{holiday_type_str}"
                rate_config = self.rate_matrix.get(combination_key)

                if rate_config and rate_config.cap_type == CapType.DAILY:
                    if total_amount > rate_config.cap_amount:
                        cap_applied = True
                        cap_amount = rate_config.cap_amount
                        total_amount = rate_config.cap_amount

            # 生成計算摘要
            total_duration = int((exit_time - enter_time).total_seconds() / 60)
            calculation_summary = f"""
多維度累進費率計算結果:
- 停車時間: {total_duration}分鐘
- 日期類別: {date_category.value}
- 適用時段: {len(applied_segments)}個
- 原始費用: {original_amount}元
- 實際費用: {total_amount}元
- 上限適用: {'是' if cap_applied else '否'}
""".strip()

            return CalculationResult(
                total_amount=total_amount,
                original_amount=original_amount,
                applied_segments=applied_segments,
                rate_breakdown=rate_breakdown,
                cap_applied=cap_applied,
                cap_amount=cap_amount,
                calculation_summary=calculation_summary,
            )

        except Exception as e:
            return CalculationResult(
                total_amount=0,
                original_amount=0,
                applied_segments=[],
                rate_breakdown=[],
                calculation_summary=f"計算失敗: {str(e)}",
            )

    def _get_holiday_type_string(self, date_category: DateCategory) -> str:
        """根據日期類別和系統設定獲取節假日類型字串"""
        if self.holiday_type == HolidayType.NO_HOLIDAY:
            return "統一費率"
        elif self.holiday_type == HolidayType.WEEKDAY_WEEKEND:
            if date_category == DateCategory.WEEKDAY:
                return "平日"
            else:
                return "假日"
        else:  # FULL_HOLIDAY
            return date_category.value

    def _calculate_segment_duration(
        self, enter_time: datetime, exit_time: datetime, segment: TimeSegment
    ) -> int:
        """計算在特定時段內的停車時長（分鐘）"""
        # 獲取停車日期
        park_date = enter_time.date()

        # 構建時段的開始和結束時間
        segment_start = datetime.combine(
            park_date, time(*map(int, segment.start.split(":")))
        )

        if segment.is_cross_day:
            # 跨日時段：結束時間在次日
            next_date = park_date + timedelta(days=1)
            segment_end = datetime.combine(
                next_date, time(*map(int, segment.end.split(":")))
            )
        else:
            segment_end = datetime.combine(
                park_date, time(*map(int, segment.end.split(":")))
            )

        # 計算重疊時間
        overlap_start = max(enter_time, segment_start)
        overlap_end = min(exit_time, segment_end)

        if overlap_start < overlap_end:
            return int((overlap_end - overlap_start).total_seconds() / 60)
        return 0

    def _calculate_segment_fee(
        self, duration_minutes: int, rate_config: RateConfig
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """計算時段費用，支援多段式累進費率"""
        if duration_minutes <= rate_config.grace_minutes:
            return 0, [{"description": "寬限時間內免費", "amount": 0}]

        # 扣除寬限時間
        billable_minutes = duration_minutes - rate_config.grace_minutes

        total_fee = 0
        breakdown = []
        remaining_minutes = billable_minutes

        # 按累進費率階段計算
        for stage, progressive_rate in enumerate(rate_config.progressive_rates):
            if remaining_minutes <= 0:
                break

            # 該階段的時長（預設為單位時間）
            stage_duration = progressive_rate.duration_minutes or rate_config.unit_time

            # 計算該階段的計費時間
            stage_billable_minutes = min(remaining_minutes, stage_duration)

            # 計算該階段的費用
            stage_units = math.ceil(stage_billable_minutes / rate_config.unit_time)
            stage_fee = stage_units * progressive_rate.rate

            total_fee += stage_fee
            remaining_minutes -= stage_billable_minutes

            breakdown.append(
                {
                    "stage": progressive_rate.stage,
                    "description": progressive_rate.time_range,
                    "duration_minutes": stage_billable_minutes,
                    "units": stage_units,
                    "unit_rate": progressive_rate.rate,
                    "amount": stage_fee,
                }
            )

        # 如果還有剩餘時間，使用最後一個階段的費率
        if remaining_minutes > 0 and rate_config.progressive_rates:
            last_rate = rate_config.progressive_rates[-1]
            overflow_units = math.ceil(remaining_minutes / rate_config.unit_time)
            overflow_fee = overflow_units * last_rate.rate

            total_fee += overflow_fee

            breakdown.append(
                {
                    "stage": "overflow",
                    "description": f"超過{last_rate.time_range}後",
                    "duration_minutes": remaining_minutes,
                    "units": overflow_units,
                    "unit_rate": last_rate.rate,
                    "amount": overflow_fee,
                }
            )

        return total_fee, breakdown

    def get_dimension_combinations(self) -> List[Dict[str, Any]]:
        """獲取所有維度組合"""
        combinations = []

        # 獲取節假日類型列表
        if self.holiday_type == HolidayType.NO_HOLIDAY:
            holiday_types = ["統一費率"]
        elif self.holiday_type == HolidayType.WEEKDAY_WEEKEND:
            holiday_types = ["平日", "假日"]
        else:  # FULL_HOLIDAY
            holiday_types = ["平日", "假日", "節慶日"]

        # 生成所有組合
        for segment in self.segments:
            for holiday_type in holiday_types:
                combination_key = f"{segment.name}_{holiday_type}"
                is_configured = combination_key in self.rate_matrix

                combinations.append(
                    {
                        "combination_id": combination_key,
                        "segment_name": segment.name,
                        "holiday_type": holiday_type,
                        "is_configured": is_configured,
                        "segment_time": f"{segment.start}-{segment.end}",
                        "is_cross_day": segment.is_cross_day,
                    }
                )

        return combinations

    def export_configuration(self) -> Dict[str, Any]:
        """匯出完整配置"""
        return {
            "segments": [
                {
                    "name": seg.name,
                    "start": seg.start,
                    "end": seg.end,
                    "is_cross_day": seg.is_cross_day,
                }
                for seg in self.segments
            ],
            "holiday_type": self.holiday_type.value,
            "custom_holidays": self.custom_holidays,
            "rate_matrix": {
                key: {
                    "unit_time": config.unit_time,
                    "grace_minutes": config.grace_minutes,
                    "progressive_rates": [
                        {
                            "stage": rate.stage,
                            "time_range": rate.time_range,
                            "rate": rate.rate,
                            "duration_minutes": rate.duration_minutes,
                        }
                        for rate in config.progressive_rates
                    ],
                    "cap_type": config.cap_type.value,
                    "cap_amount": config.cap_amount,
                }
                for key, config in self.rate_matrix.items()
            },
        }

    def import_configuration(self, config: Dict[str, Any]) -> bool:
        """匯入配置"""
        try:
            # 匯入時間區段
            segments_data = config.get("segments", [])
            segments = [
                TimeSegment(
                    name=seg["name"],
                    start=seg["start"],
                    end=seg["end"],
                    is_cross_day=seg.get("is_cross_day", False),
                )
                for seg in segments_data
            ]

            validation = self._validate_24hour_coverage(segments)
            if not validation.is_valid:
                print(f"時間區段驗證失敗: {validation.message}")
                return False

            self.segments = segments

            # 匯入節假日設定
            self.holiday_type = HolidayType(config.get("holiday_type", "NO_HOLIDAY"))
            self.custom_holidays = config.get("custom_holidays", [])

            # 匯入費率矩陣
            rate_matrix_data = config.get("rate_matrix", {})
            self.rate_matrix = {}

            for key, rate_data in rate_matrix_data.items():
                progressive_rates = [
                    ProgressiveRate(
                        stage=rate["stage"],
                        time_range=rate["time_range"],
                        rate=rate["rate"],
                        duration_minutes=rate.get("duration_minutes", 60),
                    )
                    for rate in rate_data.get("progressive_rates", [])
                ]

                rate_config = RateConfig(
                    unit_time=rate_data.get("unit_time", 60),
                    grace_minutes=rate_data.get("grace_minutes", 15),
                    progressive_rates=progressive_rates,
                    cap_type=CapType(rate_data.get("cap_type", "daily")),
                    cap_amount=rate_data.get("cap_amount", 200),
                )

                self.rate_matrix[key] = rate_config

            return True

        except Exception as e:
            print(f"匯入配置失敗: {e}")
            return False


def main():
    """測試增強版多維度計算器"""
    calculator = EnhancedMultidimensionalCalculator()

    print("=== 增強版多維度停車費計算器測試 ===\n")

    # 測試1: 設定時間區段
    print("1. 設定時間區段")
    segments = [
        {"name": "日間", "start": "07:00", "end": "18:00"},
        {"name": "夜間", "start": "18:00", "end": "07:00"},
    ]

    validation = calculator.set_time_segments(segments)
    print(f"驗證結果: {validation.message}")
    if validation.details:
        for detail in validation.details:
            print(f"  - {detail}")

    # 測試2: 設定節假日類型
    print("\n2. 設定節假日類型")
    calculator.set_holiday_type("平日假日")
    print("已設定為平日/假日差別費率")

    # 測試3: 設定費率配置
    print("\n3. 設定費率配置")

    # 日間平日費率
    day_weekday_config = {
        "unitTime": 60,
        "graceMinutes": 15,
        "progressiveRates": [
            {"stage": 1, "timeRange": "第1小時", "rate": 30},
            {"stage": 2, "timeRange": "第2小時", "rate": 40},
            {"stage": 3, "timeRange": "第3小時以上", "rate": 50},
        ],
        "capType": "daily",
        "capAmount": 200,
    }

    calculator.set_rate_config("日間", "平日", day_weekday_config)
    calculator.set_rate_config(
        "夜間",
        "平日",
        {
            "unitTime": 60,
            "graceMinutes": 15,
            "progressiveRates": [
                {"stage": 1, "timeRange": "第1小時", "rate": 20},
                {"stage": 2, "timeRange": "第2小時以上", "rate": 30},
            ],
            "capType": "daily",
            "capAmount": 150,
        },
    )

    print("已設定日間和夜間的平日費率")

    # 測試4: 計算停車費
    print("\n4. 計算停車費")
    enter_time = datetime(2024, 12, 19, 14, 30)  # 週四下午2:30
    exit_time = datetime(2024, 12, 19, 17, 45)  # 週四下午5:45

    result = calculator.calculate_parking_fee(enter_time, exit_time)

    print(f"進場時間: {enter_time}")
    print(f"出場時間: {exit_time}")
    print(f"總費用: {result.total_amount}元")
    print(f"原始費用: {result.original_amount}元")
    print(f"上限適用: {'是' if result.cap_applied else '否'}")

    print("\n適用時段:")
    for segment in result.applied_segments:
        print(
            f"  - {segment['segment_name']}: {segment['duration_minutes']}分鐘 = {segment['fee']}元"
        )

    print("\n費率明細:")
    for breakdown in result.rate_breakdown:
        print(
            f"  - {breakdown['description']}: {breakdown['duration_minutes']}分鐘 = {breakdown['amount']}元"
        )

    print(f"\n{result.calculation_summary}")

    # 測試5: 匯出配置
    print("\n5. 匯出配置")
    config = calculator.export_configuration()
    print("配置已匯出，包含:")
    print(f"  - 時間區段: {len(config['segments'])}個")
    print(f"  - 費率矩陣: {len(config['rate_matrix'])}個組合")
    print(f"  - 節假日類型: {config['holiday_type']}")


if __name__ == "__main__":
    main()
