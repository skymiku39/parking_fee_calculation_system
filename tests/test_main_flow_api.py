import json
from pathlib import Path
from unittest.mock import patch

from app import app

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_public_api_surface_keeps_only_current_calendar_sync_route():
    routes = {rule.rule for rule in app.url_map.iter_rules()}

    expected_routes = {
        "/api/calculate",
        "/api/plans",
        "/api/rate_plans",
        "/api/rate_plans/export",
        "/api/rate_plans/load/<path:plan_id>",
        "/api/rate_plans/preview",
        "/api/rate_plans/save",
        "/api/rate_plans/<path:plan_id>",
        "/api/mdp/templates",
        "/api/mdp/templates/<template_id>",
        "/api/mdp/templates/save",
        "/api/mdp/export",
        "/api/mdp/preview",
        "/api/enhanced/segments/validate",
        "/api/multidimensional/combinations",
        "/api/calendar",
        "/api/calendar/generate_weekends",
        "/api/calendar/sync_official_v2",
        "/api/system/config",
        "/api/system/version",
        "/static/openapi.yaml",
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
    assert any(plan["type"] == "multidimensional" for plan in plans_payload["plans"])
    assert plans_payload.get("user_defined_count", 0) >= 1

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

    mock_calendar = {
        "national_holidays": [{"date": "2026-01-01", "name": "開國紀念日"}],
        "festival_holidays": [{"date": "2026-02-17", "name": "春節"}],
        "custom_workdays": ["2026-02-14"],
    }
    with patch(
        "src.web.calendar._fetch_taiwan_cdn_holidays",
        return_value=mock_calendar,
    ):
        sync_response = client.post(
            "/api/calendar/sync_official_v2",
            json={"year": 2026, "source": "gov_tw"},
        )
    assert sync_response.status_code == 200
    sync_payload = sync_response.get_json()
    assert sync_payload["success"] is True
    assert sync_payload["synced_year"] == 2026
    assert sync_payload["added_national"] == 1
    assert sync_payload["added_festival"] == 1
    assert sync_payload["added_workdays"] == 1

    saved_calendar = json.loads(
        (tmp_path / "system_calendar.json").read_text(encoding="utf-8")
    )
    assert saved_calendar["description"] == "test calendar"
    assert "weekend_holidays" in saved_calendar
    assert saved_calendar["national_holidays"][0]["date"] == "2026-01-01"
    assert saved_calendar["festival_holidays"][0]["date"] == "2026-02-17"
    assert "2026-02-14" in saved_calendar["custom_workdays"]


def test_rate_plan_designer_no_longer_points_to_legacy_bulk_export():
    content = (REPO_ROOT / "src" / "web" / "templates" / "rate_plan_designer.html").read_text(
        encoding="utf-8"
    )

    assert "/api/rate_plans/export_all" not in content
    assert "convertLegacyPlanToMDP" not in content
    assert "archivedLegacyPlanToMDP" not in content
    assert "legacyImportTemplateFromFile" not in content
    assert "isMDPTemplatePayload" in content
