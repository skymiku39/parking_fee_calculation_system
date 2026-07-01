"""src.core.utils 單元測試。"""

import pytest

from src.core.utils import (
    format_duration_display,
    get_rate_description,
    merge_system_config,
    parse_bool,
    parse_int,
    validate_and_normalize_system_config,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        (True, True),
        ("yes", True),
        ("OFF", False),
        ("maybe", None),
    ],
)
def test_parse_bool(value, expected):
    assert parse_bool(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        (True, None),
        (" 42 ", 42),
        ("x", None),
    ],
)
def test_parse_int(value, expected):
    assert parse_int(value) == expected


@pytest.mark.parametrize(
    ("minutes", "expected"),
    [
        (0, "0 minutes"),
        (30, "30 minutes"),
        (60, "60 minutes (1 hour)"),
        (90, "90 minutes (1 hour 30 minutes)"),
        (150, "150 minutes (2 hours 30 minutes)"),
    ],
)
def test_format_duration_display(minutes, expected):
    assert format_duration_display(minutes) == expected


def test_get_rate_description_variants():
    assert get_rate_description({}) == "No rate"
    assert get_rate_description({"progressive_enabled": True}) == "Progressive pricing"
    assert get_rate_description({"simple_rate": 30, "unit_time": 60}) == "30 / 60 minutes"


def test_merge_system_config_rejects_invalid_ui_settings():
    with pytest.raises(ValueError, match="ui_settings must be an object"):
        merge_system_config({}, {"ui_settings": "bad"})


def test_validate_and_normalize_system_config_without_env(monkeypatch):
    monkeypatch.delenv("PARK_UI_MAX_USER_PLANS_DISPLAY", raising=False)
    normalized = validate_and_normalize_system_config(
        {"ui_settings": {"max_user_plans_display": 7}},
        include_env_overrides=False,
    )
    assert normalized["ui_settings"]["max_user_plans_display"] == 7


def test_validate_and_normalize_system_config_env_overrides(monkeypatch):
    monkeypatch.setenv("PARK_CALC_PRECISION", "4")
    monkeypatch.setenv("PARK_UI_SHOW_ONLY_FEATURED", "on")
    normalized = validate_and_normalize_system_config({})
    assert normalized["calculation_precision"] == 4
    assert normalized["ui_settings"]["show_only_featured_user_plans"] is True


def test_validate_and_normalize_system_config_rejects_invalid_ui_settings():
    with pytest.raises(ValueError, match="ui_settings must be an object"):
        validate_and_normalize_system_config({"ui_settings": []})
