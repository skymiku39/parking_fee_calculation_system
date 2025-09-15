from __future__ import annotations

import os
from typing import Any, Dict, Optional


# ===== 常數 =====
DEFAULT_DATE_FORMAT = "%Y-%m-%d"
DEFAULT_TIME_FORMAT = "%H:%M"
DEFAULT_DATETIME_DISPLAY_FORMAT = "%Y年%m月%d日 %H:%M"

NAGER_BASE_URL = "https://date.nager.at/api/v3/PublicHolidays/{year}/TW"

TRUE_SET = {"1", "true", "yes", "y", "on"}


# ===== 基本工具 =====
def parse_bool(value: Optional[str]) -> Optional[bool]:
    if value is None:
        return None
    v = str(value).strip().lower()
    if v in TRUE_SET:
        return True
    if v in {"0", "false", "no", "n", "off"}:
        return False
    return None


def parse_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except Exception:
        return None


# ===== 顯示字串工具 =====
def format_duration_display(minutes: int) -> str:
    if minutes <= 0:
        return "0分鐘"
    if minutes % 60 == 0:
        hours = minutes // 60
        if hours == 1:
            return f"{minutes}分鐘 (1小時)"
        else:
            return f"{minutes}分鐘 ({hours}小時)"
    else:
        hours = minutes // 60
        remaining_minutes = minutes % 60
        if hours == 0:
            return f"{minutes}分鐘"
        elif hours == 1:
            return f"{minutes}分鐘 (1小時{remaining_minutes}分)"
        else:
            return f"{minutes}分鐘 ({hours}小時{remaining_minutes}分)"


def get_rate_description(rate_config: dict) -> str:
    if not rate_config:
        return "無費率"
    if rate_config.get("progressive_enabled", False):
        return "累進費率"
    unit_time = rate_config.get("unit_time", 60)
    simple_rate = rate_config.get("simple_rate", 0)
    if unit_time == 60:
        return f"{simple_rate}元/60分鐘"
    elif unit_time == 30:
        return f"{simple_rate}元/30分鐘"
    else:
        return f"{simple_rate}元/{unit_time}分鐘"


# ===== system_config 驗證與正規化 =====
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
    # 可選：政府資料來源 API
    "official_calendar_api": None,
    # UI 設定
    "ui_settings": {
        "max_user_plans_display": 50,
        "show_only_featured_user_plans": False,
    },
}


def validate_and_normalize_system_config(cfg: Dict[str, Any], env: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    config: Dict[str, Any] = {**DEFAULT_SYSTEM_CONFIG}
    cfg = cfg or {}

    # 基礎層級鍵值
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

    # 布林與整數
    for key in ["enable_plan_switching", "enable_manual_override"]:
        if key in cfg:
            config[key] = bool(cfg[key])
    if "calculation_precision" in cfg:
        try:
            config["calculation_precision"] = int(cfg["calculation_precision"])  # type: ignore
        except Exception:
            pass

    # UI 設定
    ui_src = cfg.get("ui_settings") if isinstance(cfg.get("ui_settings"), dict) else {}
    ui_dst = {**DEFAULT_SYSTEM_CONFIG["ui_settings"]}
    if "max_user_plans_display" in ui_src:
        try:
            ui_dst["max_user_plans_display"] = int(ui_src["max_user_plans_display"])  # type: ignore
        except Exception:
            pass
    if "show_only_featured_user_plans" in ui_src:
        ui_dst["show_only_featured_user_plans"] = bool(ui_src["show_only_featured_user_plans"])  # type: ignore
    config["ui_settings"] = ui_dst

    # 環境變數覆寫（統一於此）
    env = env or {}
    env_map = {
        "system_mode": os.getenv("PARK_SYS_MODE", env.get("system_mode")),
        "default_calculation_engine": os.getenv("PARK_DEFAULT_ENGINE", env.get("default_calculation_engine")),
        "currency_symbol": os.getenv("PARK_CURRENCY_SYMBOL", env.get("currency_symbol")),
        "system_timezone": os.getenv("PARK_TIMEZONE", env.get("system_timezone")),
        "official_calendar_api": os.getenv("PARK_OFFICIAL_CAL_API", env.get("official_calendar_api")),
    }
    for k, v in env_map.items():
        if v is not None:
            config[k] = v

    precision_env = os.getenv("PARK_CALC_PRECISION", env.get("calculation_precision"))
    pi = parse_int(precision_env) if isinstance(precision_env, str) else precision_env
    if isinstance(pi, int):
        config["calculation_precision"] = pi

    ui_max_env = os.getenv("PARK_UI_MAX_USER_PLANS_DISPLAY", None)
    ui_max_env = ui_max_env if ui_max_env is not None else env.get("ui_max_user_plans_display")
    ui_max_val = parse_int(ui_max_env) if isinstance(ui_max_env, str) else ui_max_env
    if isinstance(ui_max_val, int):
        config["ui_settings"]["max_user_plans_display"] = ui_max_val

    ui_featured_env = os.getenv("PARK_UI_SHOW_ONLY_FEATURED", None)
    ui_featured_env = ui_featured_env if ui_featured_env is not None else env.get("ui_show_only_featured")
    pb = parse_bool(ui_featured_env) if isinstance(ui_featured_env, str) else ui_featured_env
    if isinstance(pb, bool):
        config["ui_settings"]["show_only_featured_user_plans"] = pb

    return config



