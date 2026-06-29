from conftest import build_isolated_system

import src.web.user_plans as user_plans_module


def test_plans_api_includes_user_defined(isolated_client):
    system, client, _ = isolated_client
    response = client.get("/api/plans")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["user_defined_count"] >= 1
    types = {p["type"] for p in payload["plans"]}
    assert "multidimensional" in types
    assert "user_defined" in types


def test_load_user_defined_plan(isolated_client):
    _, client, _ = isolated_client
    response = client.get("/api/rate_plans/load/跨日測試方案")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["plan"]["name"] == "跨日測試方案"


def test_preview_user_defined_plan_returns_session_details(isolated_client):
    _, client, _ = isolated_client
    response = client.get("/api/rate_plans/load/跨日測試方案")
    plan = response.get_json()["plan"]
    preview_response = client.post(
        "/api/rate_plans/preview",
        json={
            "enter_time": "2025-06-20T10:00",
            "exit_time": "2025-06-20T14:00",
            "plan": plan,
        },
    )
    assert preview_response.status_code == 200
    payload = preview_response.get_json()
    assert payload["success"] is True
    assert payload["total_amount"] >= 0
    assert isinstance(payload.get("session_details"), list)
    assert len(payload["session_details"]) >= 1


def test_calculate_with_user_defined_plan(isolated_client):
    _, client, _ = isolated_client
    response = client.post(
        "/api/calculate",
        json={
            "enter_time": "2025-06-20T10:00",
            "exit_time": "2025-06-20T12:00",
            "plan_id": "跨日測試方案",
        },
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["calculation_engine"] == "user_defined_billing_cycle"


def test_save_and_delete_user_defined_plan(isolated_client):
    _, client, tmp_path = isolated_client
    new_plan = {
        "name": "API測試方案",
        "description": "由測試建立",
        "segment_type": "全天",
        "holiday_type": "無假日",
        "segments": [{"name": "全天", "start": "00:00", "end": "24:00"}],
        "rate_matrix": {
            "全天_統一": {
                "unit_time": 60,
                "simple_rate": 30,
                "progressive_enabled": False,
            }
        },
        "global_caps": {
            "daily_cap_enabled": False,
            "daily_cap_amount": None,
            "global_grace_time": 0,
        },
    }

    save_response = client.post(
        "/api/rate_plans/save",
        json={"plan_id": "api_test_plan", "plan": new_plan},
    )
    assert save_response.status_code == 200
    save_payload = save_response.get_json()
    assert save_payload["success"] is True

    calc_response = client.post(
        "/api/calculate",
        json={
            "enter_time": "2025-06-20T10:00",
            "exit_time": "2025-06-20T11:00",
            "plan_id": "api_test_plan",
        },
    )
    assert calc_response.status_code == 200
    assert calc_response.get_json()["success"] is True

    delete_response = client.delete("/api/rate_plans/api_test_plan")
    assert delete_response.status_code == 200

    calc_after_delete = client.post(
        "/api/calculate",
        json={
            "enter_time": "2025-06-20T10:00",
            "exit_time": "2025-06-20T11:00",
            "plan_id": "api_test_plan",
        },
    )
    assert calc_after_delete.status_code == 200
    assert calc_after_delete.get_json()["success"] is False


def test_featured_filter(tmp_path, monkeypatch):
    system = build_isolated_system(
        tmp_path,
        ui_settings={
            "show_only_featured_user_plans": True,
            "max_user_plans_display": 50,
        },
    )
    monkeypatch.setattr(user_plans_module, "parking_system", system)

    plans = system.list_user_defined_plans()
    assert plans
    assert all(p["featured"] for p in plans)


def test_rate_plans_list_all_query(isolated_client):
    _, client, _ = isolated_client
    response = client.get("/api/rate_plans?all=1")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["total"] >= 10
