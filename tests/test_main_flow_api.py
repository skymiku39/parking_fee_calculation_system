import json
from pathlib import Path
from shutil import copy2
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app import app
import src.core.context as context_module
import src.web.calc as calc_module
import src.web.calendar as calendar_module
import src.web.mdp as mdp_module
import src.web.system as system_module
from src.core.system import SmartParkingSystem


def _build_isolated_system(tmp_path: Path) -> SmartParkingSystem:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    for filename in (
        "multidimensional_rate_plans.json",
        "system_config.json",
        "system_templates.json",
    ):
        copy2(REPO_ROOT / "config" / filename, config_dir / filename)
    return SmartParkingSystem(base_path=tmp_path)


@pytest.fixture
def isolated_client(tmp_path, monkeypatch):
    system = _build_isolated_system(tmp_path)
    for module in (
        context_module,
        calc_module,
        calendar_module,
        mdp_module,
        system_module,
    ):
        monkeypatch.setattr(module, "parking_system", system)

    return system, app.test_client(), tmp_path


def test_public_api_surface_keeps_only_current_calendar_sync_route():
    routes = {rule.rule for rule in app.url_map.iter_rules()}

    expected_routes = {
        "/api/calculate",
        "/api/plans",
        "/api/mdp/templates",
        "/api/mdp/templates/<template_id>",
        "/api/mdp/templates/save",
        "/api/mdp/export",
        "/api/mdp/preview",
        "/api/calendar",
        "/api/calendar/generate_weekends",
        "/api/calendar/sync_official_v2",
        "/api/system/config",
    }

    assert expected_routes.issubset(routes)
    assert "/api/calendar/sync_official" not in routes


def test_main_flow_endpoints_run_against_multidimensional_templates(isolated_client):
    system, client, _ = isolated_client
    first_template = next(iter(system.multidimensional_calculator.rate_plan_templates.values()))

    plans_response = client.get("/api/plans")
    assert plans_response.status_code == 200
    plans_payload = plans_response.get_json()
    assert plans_payload["success"] is True
    assert plans_payload["plans"]
    assert all(plan["type"] == "multidimensional" for plan in plans_payload["plans"])

    calculate_response = client.post(
        "/api/calculate",
        json={
            "enter_time": "2025-06-20T10:00",
            "exit_time": "2025-06-20T12:00",
            "plan_id": first_template.template_id,
        },
    )
    assert calculate_response.status_code == 200
    calculate_payload = calculate_response.get_json()
    assert calculate_payload["success"] is True
    assert calculate_payload["calculation_engine"] == "multidimensional"

    templates_response = client.get("/api/mdp/templates")
    assert templates_response.status_code == 200
    templates_payload = templates_response.get_json()
    assert templates_payload["success"] is True
    assert templates_payload["total"] >= 1

    template_response = client.get(f"/api/mdp/templates/{first_template.template_id}")
    assert template_response.status_code == 200
    template_payload = template_response.get_json()
    assert template_payload["success"] is True
    assert template_payload["template"]["template_id"] == first_template.template_id

    preview_response = client.post(
        "/api/mdp/preview",
        json={
            "enter_time": "2025-06-20T10:00",
            "exit_time": "2025-06-20T12:00",
            "template": template_payload["template"],
        },
    )
    assert preview_response.status_code == 200
    preview_payload = preview_response.get_json()
    assert preview_payload["success"] is True
    assert preview_payload["total_amount"] >= 0

    config_response = client.get("/api/system/config")
    assert config_response.status_code == 200
    config_payload = config_response.get_json()
    assert config_payload["success"] is True
    assert config_payload["config"]["system_mode"] == "multidimensional"


def test_calendar_endpoints_use_isolated_config_storage(isolated_client):
    _, client, tmp_path = isolated_client

    save_response = client.post(
        "/api/calendar",
        json={
            "description": "test calendar",
            "weekend_as_holiday": True,
            "custom_holidays": ["2026-02-02"],
            "custom_workdays": [],
            "festival_holidays": [],
            "national_holidays": [],
            "weekend_holidays": [],
            "lunar_festivals": [],
            "special_events": [],
        },
    )
    assert save_response.status_code == 200
    assert save_response.get_json()["success"] is True

    get_response = client.get("/api/calendar")
    assert get_response.status_code == 200
    get_payload = get_response.get_json()
    assert get_payload["success"] is True
    assert get_payload["calendar"]["description"] == "test calendar"

    weekend_response = client.post(
        "/api/calendar/generate_weekends",
        json={"year": 2026},
    )
    assert weekend_response.status_code == 200
    weekend_payload = weekend_response.get_json()
    assert weekend_payload["success"] is True
    assert weekend_payload["generated_year"] == 2026

    sync_response = client.post(
        "/api/calendar/sync_official_v2",
        json={"year": 2026, "source": "gov_tw"},
    )
    assert sync_response.status_code == 200
    sync_payload = sync_response.get_json()
    assert sync_payload["success"] is True
    assert sync_payload["synced_year"] == 2026

    saved_calendar = json.loads(
        (tmp_path / "config" / "system_calendar.json").read_text(encoding="utf-8")
    )
    assert saved_calendar["description"] == "test calendar"
    assert "weekend_holidays" in saved_calendar
    assert "national_holidays" in saved_calendar


def test_rate_plan_designer_no_longer_points_to_legacy_bulk_export():
    content = (REPO_ROOT / "templates" / "rate_plan_designer.html").read_text(
        encoding="utf-8"
    )

    assert "/api/rate_plans/export_all" not in content
    assert "convertLegacyPlanToMDP" not in content
    assert "isMDPTemplatePayload" in content
    assert "archivedLegacyPlanToMDP" in content
