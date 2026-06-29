from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

from src.domain.terminology import (
    DateCategory,
    HolidayType,
    MdpPlanTier,
    normalize_holiday_type,
)

DateEntry = Union[str, Dict[str, Any]]


def normalize_date_entry(entry: DateEntry) -> Optional[str]:
    if isinstance(entry, str):
        return entry.strip() or None
    if isinstance(entry, dict):
        value = entry.get("date")
        return str(value).strip() if value else None
    return None


def collect_dates(entries: Optional[List[DateEntry]]) -> Set[str]:
    result: Set[str] = set()
    for entry in entries or []:
        normalized = normalize_date_entry(entry)
        if normalized:
            result.add(normalized)
    return result


class HolidayCalendar:
    """讀取 system_calendar.json 並提供統一的日期類別判定。"""

    def __init__(self, calendar_path: Union[str, Path]):
        self.calendar_path = Path(calendar_path)
        self._data: Dict[str, Any] = {}
        self.reload()

    def reload(self) -> None:
        if self.calendar_path.exists():
            try:
                with open(self.calendar_path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception:
                self._data = {}
        else:
            self._data = {}

    @property
    def weekend_as_holiday(self) -> bool:
        return bool(self._data.get("weekend_as_holiday", True))

    @property
    def custom_workdays(self) -> Set[str]:
        return collect_dates(self._data.get("custom_workdays"))

    @property
    def custom_holidays(self) -> Set[str]:
        return collect_dates(self._data.get("custom_holidays"))

    @property
    def national_holidays(self) -> Set[str]:
        return collect_dates(self._data.get("national_holidays"))

    @property
    def festival_holidays(self) -> Set[str]:
        return collect_dates(self._data.get("festival_holidays"))

    def is_custom_workday(self, check_date: date) -> bool:
        return check_date.strftime("%Y-%m-%d") in self.custom_workdays

    def is_festival(self, check_date: date) -> bool:
        return check_date.strftime("%Y-%m-%d") in self.festival_holidays

    def is_national_holiday(self, check_date: date) -> bool:
        return check_date.strftime("%Y-%m-%d") in self.national_holidays

    def is_custom_holiday(self, check_date: date) -> bool:
        return check_date.strftime("%Y-%m-%d") in self.custom_holidays

    def is_weekend(self, check_date: date) -> bool:
        if self.is_custom_workday(check_date):
            return False
        if not self.weekend_as_holiday:
            return False
        return check_date.weekday() >= 5

    def _raw_mdp_tier(
        self,
        check_date: date,
        extra_custom_holidays: Optional[List[str]] = None,
    ) -> MdpPlanTier:
        """Internal MDP plan tier before collapsing to canonical date category."""
        date_str = check_date.strftime("%Y-%m-%d")
        extra_custom = set(extra_custom_holidays or [])

        if date_str in self.custom_workdays:
            return MdpPlanTier.WEEKDAY

        if date_str in extra_custom or date_str in self.festival_holidays:
            return MdpPlanTier.CUSTOM_HOLIDAY

        if date_str in self.national_holidays or date_str in self.custom_holidays:
            return MdpPlanTier.NATIONAL_HOLIDAY

        if self.is_weekend(check_date):
            return MdpPlanTier.WEEKEND

        return MdpPlanTier.WEEKDAY

    def classify_date(
        self,
        check_date: date,
        holiday_type: str,
        extra_custom_holidays: Optional[List[str]] = None,
    ) -> str:
        """
        統一日期類別判定，回傳 canonical：統一 | 平日 | 假日 | 節慶日
        """
        hol = normalize_holiday_type(holiday_type)

        if hol == HolidayType.NO_HOLIDAY.value:
            return DateCategory.UNIFIED.value

        tier = self._raw_mdp_tier(check_date, extra_custom_holidays)

        if hol == HolidayType.FULL_HOLIDAY.value:
            if tier in (MdpPlanTier.CUSTOM_HOLIDAY, MdpPlanTier.NATIONAL_HOLIDAY):
                return DateCategory.FESTIVAL.value
            if tier == MdpPlanTier.WEEKEND:
                return DateCategory.HOLIDAY.value
            return DateCategory.WEEKDAY.value

        if hol == HolidayType.WEEKDAY_WEEKEND.value:
            if tier != MdpPlanTier.WEEKDAY:
                return DateCategory.HOLIDAY.value
            return DateCategory.WEEKDAY.value

        return DateCategory.UNIFIED.value

    def get_mdp_plan_tier(
        self,
        check_date: date,
        holiday_type: str,
        extra_custom_holidays: Optional[List[str]] = None,
    ) -> MdpPlanTier:
        """Select internal MDP sub-plan key for rate lookup."""
        hol = normalize_holiday_type(holiday_type)

        if hol == HolidayType.NO_HOLIDAY.value:
            return MdpPlanTier.UNIFIED

        tier = self._raw_mdp_tier(check_date, extra_custom_holidays)

        if hol == HolidayType.WEEKDAY_WEEKEND.value:
            if tier in (
                MdpPlanTier.WEEKEND,
                MdpPlanTier.NATIONAL_HOLIDAY,
                MdpPlanTier.CUSTOM_HOLIDAY,
            ):
                return MdpPlanTier.WEEKEND
            return MdpPlanTier.WEEKDAY

        return tier

    def classify_user_defined_date(self, check_date: date, holiday_type: str) -> str:
        """Backward-compatible alias for user-defined billing cycle."""
        return self.classify_date(check_date, holiday_type)

    def classify_mdp_date(
        self,
        check_date: date,
        extra_custom_holidays: Optional[List[str]] = None,
    ) -> str:
        """
        Deprecated: returns English snake_case tier for legacy callers.
        Prefer get_mdp_plan_tier() or classify_date().
        """
        tier = self._raw_mdp_tier(check_date, extra_custom_holidays)
        return tier.value
