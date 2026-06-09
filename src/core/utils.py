from __future__ import annotations

import os
from copy import deepcopy
from typing import Any, Dict, Optional


DEFAULT_DATE_FORMAT = "%Y-%m-%d"
DEFAULT_TIME_FORMAT = "%H:%M"
DEFAULT_DATETIME_DISPLAY_FORMAT = "%Y-%m-%d %H:%M"

NAGER_BASE_URL = "https://date.nager.at/api/v3/PublicHolidays/{year}/TW"
TAIWAN_CALENDAR_CDN_URL = (
    "https://cdn.jsdelivr.net/gh/ruyut/TaiwanCalendar/data/{year}.json"
)

TRUE_SET = {"1", "true", "yes", "y", "on"}
FALSE_SET = {"0", "false", "no", "n", "off"}


def parse_bool(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    v = str(value).strip().lower()
    if v in TRUE_SET:
        return True
    if v in FALSE_SET:
        return False
    return None


def parse_int(value: Any) -> Optional[int]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(str(value).strip())
    except Exception:
        return None


def normalize_bool(value: Any, field_name: str) -> bool:
    parsed = parse_bool(value)
    if parsed is None:
        raise ValueError(f"{field_name} must be a boolean value")
    return parsed


def normalize_int(value: Any, field_name: str) -> int:
    parsed = parse_int(value)
    if parsed is None:
        raise ValueError(f"{field_name} must be an integer value")
    return parsed


def format_duration_display(minutes: int) -> str:
    if minutes <= 0:
        return "0 minutes"
    if minutes % 60 == 0:
        hours = minutes // 60
        unit = "hour" if hours == 1 else "hours"
        return f"{minutes} minutes ({hours} {unit})"

    hours = minutes // 60
    remaining_minutes = minutes % 60
    if hours == 0:
        return f"{minutes} minutes"
    if hours == 1:
        return f"{minutes} minutes (1 hour {remaining_minutes} minutes)"
    return f"{minutes} minutes ({hours} hours {remaining_minutes} minutes)"


def get_rate_description(rate_config: dict) -> str:
    if not rate_config:
        return "No rate"
    if rate_config.get("progressive_enabled", False):
        return "Progressive pricing"

    unit_time = rate_config.get("unit_time", 60)
    simple_rate = rate_config.get("simple_rate", 0)
    return f"{simple_rate} / {unit_time} minutes"


DEFAULT_SYSTEM_CONFIG: Dict[str, Any] = {
    "system_mode": "multidimensional",
    "default_calculation_engine": "multidimensional",
    "enable_plan_switching": True,
    "enable_manual_override": True,
    "calculation_precision": 2,
    "currency_symbol": "NT$",
    "date_format": DEFAULT_DATE_FORMAT,
    "time_format": DEFAULT_TIME_FORMAT,
    "datetime_display_format": DEFAULT_DATETIME_DISPLAY_FORMAT,
    "system_timezone": "Asia/Taipei",
    "official_calendar_api": None,
    "ui_settings": {
        "max_user_plans_display": 50,
        "show_only_featured_user_plans": False,
    },
}


def merge_system_config(
    base_config: Optional[Dict[str, Any]],
    patch_config: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    merged = deepcopy(base_config or {})
    patch_config = patch_config or {}

    for key, value in patch_config.items():
        if key == "ui_settings":
            if not isinstance(value, dict):
                raise ValueError("ui_settings must be an object")
            existing_ui = merged.get("ui_settings")
            if not isinstance(existing_ui, dict):
                existing_ui = {}
            merged["ui_settings"] = {**existing_ui, **value}
        else:
            merged[key] = value

    return merged


def validate_and_normalize_system_config(
    cfg: Dict[str, Any],
    env: Optional[Dict[str, Any]] = None,
    *,
    include_env_overrides: bool = True,
) -> Dict[str, Any]:
    config: Dict[str, Any] = deepcopy(DEFAULT_SYSTEM_CONFIG)
    cfg = cfg or {}

    for key in [
        "system_mode",
        "default_calculation_engine",
        "currency_symbol",
        "date_format",
        "time_format",
        "datetime_display_format",
        "system_timezone",
        "official_calendar_api",
    ]:
        if key in cfg and cfg[key] is not None:
            config[key] = cfg[key]

    for key in ["enable_plan_switching", "enable_manual_override"]:
        if key in cfg:
            config[key] = normalize_bool(cfg[key], key)

    if "calculation_precision" in cfg:
        config["calculation_precision"] = normalize_int(
            cfg["calculation_precision"], "calculation_precision"
        )

    ui_src = cfg.get("ui_settings", {})
    if ui_src is None:
        ui_src = {}
    if not isinstance(ui_src, dict):
        raise ValueError("ui_settings must be an object")

    ui_dst = deepcopy(DEFAULT_SYSTEM_CONFIG["ui_settings"])
    if "max_user_plans_display" in ui_src:
        ui_dst["max_user_plans_display"] = normalize_int(
            ui_src["max_user_plans_display"], "ui_settings.max_user_plans_display"
        )
    if "show_only_featured_user_plans" in ui_src:
        ui_dst["show_only_featured_user_plans"] = normalize_bool(
            ui_src["show_only_featured_user_plans"],
            "ui_settings.show_only_featured_user_plans",
        )
    config["ui_settings"] = ui_dst

    if not include_env_overrides:
        return config

    env = env or {}
    env_map = {
        "system_mode": os.getenv("PARK_SYS_MODE", env.get("system_mode")),
        "default_calculation_engine": os.getenv(
            "PARK_DEFAULT_ENGINE", env.get("default_calculation_engine")
        ),
        "currency_symbol": os.getenv(
            "PARK_CURRENCY_SYMBOL", env.get("currency_symbol")
        ),
        "system_timezone": os.getenv("PARK_TIMEZONE", env.get("system_timezone")),
        "official_calendar_api": os.getenv(
            "PARK_OFFICIAL_CAL_API", env.get("official_calendar_api")
        ),
    }
    for key, value in env_map.items():
        if value is not None:
            config[key] = value

    precision_env = os.getenv(
        "PARK_CALC_PRECISION", str(env.get("calculation_precision", ""))
    )
    if precision_env != "":
        config["calculation_precision"] = normalize_int(
            precision_env, "calculation_precision"
        )

    ui_max_env = os.getenv(
        "PARK_UI_MAX_USER_PLANS_DISPLAY",
        str(env.get("ui_max_user_plans_display", "")),
    )
    if ui_max_env != "":
        config["ui_settings"]["max_user_plans_display"] = normalize_int(
            ui_max_env, "ui_settings.max_user_plans_display"
        )

    ui_featured_env = os.getenv(
        "PARK_UI_SHOW_ONLY_FEATURED", str(env.get("ui_show_only_featured", ""))
    )
    if ui_featured_env != "":
        config["ui_settings"]["show_only_featured_user_plans"] = normalize_bool(
            ui_featured_env, "ui_settings.show_only_featured_user_plans"
        )

    return config
