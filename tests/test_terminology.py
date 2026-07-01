"""Tests for canonical terminology normalization."""

import json
from datetime import date
from pathlib import Path

import pytest

from src.domain.terminology import (
    DateCategory,
    HolidayType,
    MdpPlanTier,
    SegmentType,
    build_template_id,
    collect_deprecated_warnings,
    date_categories_for_holiday_type,
    mdp_plan_tier_to_date_category,
    migrate_rate_matrix_key,
    normalize_date_category,
    normalize_holiday_type,
    normalize_segment_type,
    normalize_template_id,
    resolve_template_id,
)


@pytest.fixture
def calendar_file(tmp_path: Path) -> Path:
    path = tmp_path / "system_calendar.json"
    path.write_text(
        json.dumps(
            {
                "weekend_as_holiday": True,
                "custom_workdays": ["2025-02-08"],
                "custom_holidays": ["2025-02-02"],
                "national_holidays": [{"date": "2025-01-01", "name": "元旦"}],
                "festival_holidays": [
                    {"date": "2025-12-25", "name": "聖誕節"},
                    {"date": "2025-02-14", "name": "情人節"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def test_normalize_holiday_type_aliases():
    assert normalize_holiday_type(None) == HolidayType.NO_HOLIDAY.value
    assert normalize_holiday_type("六日費率") == HolidayType.WEEKDAY_WEEKEND.value
    assert normalize_holiday_type("無假日費率") == HolidayType.NO_HOLIDAY.value
    assert normalize_holiday_type("國定假費率") == HolidayType.FULL_HOLIDAY.value
    assert normalize_holiday_type("平日假日") == HolidayType.WEEKDAY_WEEKEND.value
    assert normalize_holiday_type("未知類型") == "未知類型"


def test_normalize_segment_type_aliases():
    assert normalize_segment_type(None) == SegmentType.ALL_DAY.value
    assert normalize_segment_type("兩段") == SegmentType.TWO_SEGMENT.value
    assert normalize_segment_type("四段") == SegmentType.MULTI_SEGMENT.value
    assert normalize_segment_type("自訂") == SegmentType.MULTI_SEGMENT.value
    assert normalize_segment_type("未知段") == "未知段"


def test_normalize_date_category_aliases():
    assert normalize_date_category(None) == DateCategory.WEEKDAY.value
    assert normalize_date_category("週末") == DateCategory.HOLIDAY.value
    assert normalize_date_category("國定假日") == DateCategory.FESTIVAL.value
    assert normalize_date_category("客製假日") == DateCategory.FESTIVAL.value
    assert normalize_date_category("未知") == "未知"


def test_template_id_migration():
    assert normalize_template_id(None) == ""
    assert normalize_template_id("兩段_六日費率") == "二段_平日假日"
    assert build_template_id("兩段", "六日費率") == "二段_平日假日"
    assert resolve_template_id("全天_無假日費率") == "全天_無假日"
    assert resolve_template_id(None) == ""


def test_date_categories_for_holiday_type():
    assert date_categories_for_holiday_type("無假日") == [DateCategory.UNIFIED.value]
    assert date_categories_for_holiday_type("完整假日") == [
        DateCategory.WEEKDAY.value,
        DateCategory.HOLIDAY.value,
        DateCategory.FESTIVAL.value,
    ]
    assert date_categories_for_holiday_type("平日假日") == [
        DateCategory.WEEKDAY.value,
        DateCategory.HOLIDAY.value,
    ]


def test_mdp_plan_tier_to_date_category():
    assert (
        mdp_plan_tier_to_date_category(MdpPlanTier.UNIFIED, "無假日")
        == DateCategory.UNIFIED.value
    )
    assert (
        mdp_plan_tier_to_date_category(MdpPlanTier.WEEKDAY, "平日假日")
        == DateCategory.WEEKDAY.value
    )
    assert (
        mdp_plan_tier_to_date_category(MdpPlanTier.WEEKEND, "平日假日")
        == DateCategory.HOLIDAY.value
    )
    assert (
        mdp_plan_tier_to_date_category(MdpPlanTier.NATIONAL_HOLIDAY, "完整假日")
        == DateCategory.FESTIVAL.value
    )
    assert (
        mdp_plan_tier_to_date_category(MdpPlanTier.CUSTOM_HOLIDAY, "完整假日")
        == DateCategory.HOLIDAY.value
    )


def test_migrate_rate_matrix_key_without_suffix_separator():
    assert migrate_rate_matrix_key("flat") == "flat"


def test_migrate_rate_matrix_key():
    assert migrate_rate_matrix_key("日間_週末") == "日間_假日"
    assert migrate_rate_matrix_key("日間_國定假日") == "日間_節慶日"


def test_collect_deprecated_warnings():
    obj = {
        "rate_plan_templates": [
            {"template_id": "兩段_六日費率", "holiday_type": "六日費率", "time_segment_type": "兩段"}
        ]
    }
    warnings = collect_deprecated_warnings(obj)
    assert len(warnings) >= 3


def test_classify_date_unified(calendar_file):
    from src.core.calendar_resolver import HolidayCalendar

    cal = HolidayCalendar(calendar_file)
    assert cal.classify_date(date(2025, 2, 10), "無假日") == DateCategory.UNIFIED.value


def test_classify_date_full_holiday(calendar_file):
    from src.core.calendar_resolver import HolidayCalendar

    cal = HolidayCalendar(calendar_file)
    assert cal.classify_date(date(2025, 12, 25), "完整假日") == DateCategory.FESTIVAL.value
    assert cal.classify_date(date(2025, 2, 14), "平日假日") == DateCategory.HOLIDAY.value
    assert cal.classify_date(date(2025, 2, 8), "平日假日") == DateCategory.WEEKDAY.value
