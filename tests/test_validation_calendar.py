"""system_calendar.json Schema 驗證測試。"""

import pytest

from src.core.validation import ConfigValidationError, validate_system_calendar_json


def test_valid_calendar_passes():
    validate_system_calendar_json(
        {
            "description": "demo",
            "weekend_as_holiday": True,
            "custom_holidays": ["2026-01-01"],
            "custom_workdays": [],
            "festival_holidays": [{"date": "2026-02-17", "name": "春節"}],
            "national_holidays": ["2026-10-10"],
            "weekend_holidays": [],
        }
    )


def test_empty_calendar_passes():
    validate_system_calendar_json({})


def test_bad_date_format_rejected():
    with pytest.raises(ConfigValidationError):
        validate_system_calendar_json({"custom_holidays": ["2026/01/01"]})


def test_wrong_type_rejected():
    with pytest.raises(ConfigValidationError):
        validate_system_calendar_json({"weekend_as_holiday": "yes"})
