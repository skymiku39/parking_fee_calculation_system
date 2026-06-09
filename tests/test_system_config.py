import importlib
import json
from pathlib import Path
from shutil import copy2

import src.web.system as web_system_module
from app import app
from src.core.system import SmartParkingSystem
from src.core.utils import (
    DEFAULT_DATETIME_DISPLAY_FORMAT,
    merge_system_config,
    validate_and_normalize_system_config,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _build_isolated_system(tmp_path: Path) -> SmartParkingSystem:
    data_dir = tmp_path
    data_dir.mkdir(parents=True, exist_ok=True)
    copy2(REPO_ROOT / "config" / "multidimensional_rate_plans.json", data_dir)
    return SmartParkingSystem(base_path=data_dir)


def test_validate_and_normalize_system_config_handles_merge_and_env(monkeypatch):
    merged = merge_system_config(
        {
            "ui_settings": {
                "max_user_plans_display": 5,
                "show_only_featured_user_plans": False,
            }
        },
        {"ui_settings": {"show_only_featured_user_plans": "true"}},
    )

    monkeypatch.setenv("PARK_UI_MAX_USER_PLANS_DISPLAY", "8")
    normalized = validate_and_normalize_system_config(merged)

    assert normalized["datetime_display_format"] == DEFAULT_DATETIME_DISPLAY_FORMAT
    assert normalized["ui_settings"]["max_user_plans_display"] == 8
    assert normalized["ui_settings"]["show_only_featured_user_plans"] is True


def test_smart_parking_system_load_does_not_rewrite_system_config(tmp_path):
    data_dir = tmp_path
    data_dir.mkdir(parents=True, exist_ok=True)
    config_path = data_dir / "system_config.json"
    config_payload = {
        "system_mode": "multidimensional",
        "default_calculation_engine": "multidimensional",
        "enable_plan_switching": True,
        "enable_manual_override": True,
        "calculation_precision": 2,
        "currency_symbol": "NT$",
        "date_format": "%Y-%m-%d",
        "time_format": "%H:%M",
        "datetime_display_format": "%Y-%m-%d %H:%M",
        "system_timezone": "Asia/Taipei",
        "official_calendar_api": None,
        "ui_settings": {
            "max_user_plans_display": 3,
            "show_only_featured_user_plans": False,
        },
    }
    config_path.write_text(
        json.dumps(config_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    copy2(REPO_ROOT / "config" / "multidimensional_rate_plans.json", data_dir)

    before_content = config_path.read_text(encoding="utf-8")
    before_mtime = config_path.stat().st_mtime_ns

    system = SmartParkingSystem(base_path=data_dir)

    after_content = config_path.read_text(encoding="utf-8")
    after_mtime = config_path.stat().st_mtime_ns

    assert system.system_config["ui_settings"]["max_user_plans_display"] == 3
    assert after_content == before_content
    assert after_mtime == before_mtime


def test_system_config_api_merges_nested_settings_without_losing_existing_values(
    monkeypatch, tmp_path
):
    system = _build_isolated_system(tmp_path)
    monkeypatch.setattr(web_system_module, "parking_system", system)

    with app.test_client() as client:
        response = client.post(
            "/api/system/config",
            data=json.dumps(
                {"ui_settings": {"show_only_featured_user_plans": True}}
            ),
            content_type="application/json",
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert system.system_config["ui_settings"]["show_only_featured_user_plans"] is True
    assert system.system_config["ui_settings"]["max_user_plans_display"] == 50

    saved_config = json.loads(
        (tmp_path / "system_config.json").read_text(encoding="utf-8")
    )
    assert saved_config["ui_settings"]["show_only_featured_user_plans"] is True
    assert saved_config["ui_settings"]["max_user_plans_display"] == 50


def test_system_config_api_rejects_invalid_nested_config(monkeypatch, tmp_path):
    system = _build_isolated_system(tmp_path)
    monkeypatch.setattr(web_system_module, "parking_system", system)

    with app.test_client() as client:
        response = client.post(
            "/api/system/config",
            data=json.dumps({"ui_settings": {"max_user_plans_display": "many"}}),
            content_type="application/json",
        )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["success"] is False
    assert payload["code"] == "INVALID_CONFIG"


def test_reloading_app_does_not_modify_system_config_file():
    config_path = REPO_ROOT / "config" / "system_config.json"
    before_content = config_path.read_text(encoding="utf-8")
    before_mtime = config_path.stat().st_mtime_ns

    importlib.reload(importlib.import_module("app"))

    after_content = config_path.read_text(encoding="utf-8")
    after_mtime = config_path.stat().st_mtime_ns

    assert after_content == before_content
    assert after_mtime == before_mtime
