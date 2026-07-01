"""MDP 範本 API 測試：CRUD、匯出、時段驗證與試算錯誤分支。"""

import json


def _minimal_template(template_id: str = "_test_全天方案") -> dict:
    return {
        "template_id": template_id,
        "label": "測試全天方案",
        "description": "由測試建立",
        "holiday_type": "無假日",
        "segment_type": "全天",
        "daily_cap_enabled": False,
        "time_slots": [
            {
                "time_slot_id": "all_day",
                "label": "全天時段",
                "start": "00:00",
                "end": "24:00",
                "unit_minutes": 60,
                "grace_minutes": 0,
                "grace_enabled": False,
                "cap_enabled": False,
                "progressive_enabled": False,
                "default_unit_price": 30,
                "progressive_rates": [],
            }
        ],
    }


def test_list_templates_returns_seed_templates(isolated_client):
    _, client, _ = isolated_client
    resp = client.get("/api/mdp/templates")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["success"] is True
    assert payload["total"] >= 1


def test_get_unknown_template_returns_404(isolated_client):
    _, client, _ = isolated_client
    resp = client.get("/api/mdp/templates/不存在的範本")
    assert resp.status_code == 404
    assert resp.get_json()["code"] == "MDP_NOT_FOUND"


def test_save_then_get_then_delete_template(isolated_client):
    _, client, tmp_path = isolated_client
    template = _minimal_template()

    save_resp = client.post("/api/mdp/templates/save", json={"template": template})
    assert save_resp.status_code == 200
    assert save_resp.get_json()["success"] is True

    get_resp = client.get(f"/api/mdp/templates/{template['template_id']}")
    assert get_resp.status_code == 200
    assert get_resp.get_json()["template"]["template_id"] == template["template_id"]

    saved = json.loads((tmp_path / "multidimensional_rate_plans.json").read_text(encoding="utf-8"))
    assert any(t["template_id"] == template["template_id"] for t in saved["rate_plan_templates"])

    delete_resp = client.delete(f"/api/mdp/templates/{template['template_id']}")
    assert delete_resp.status_code == 200
    assert delete_resp.get_json()["success"] is True

    assert client.get(f"/api/mdp/templates/{template['template_id']}").status_code == 404


def test_save_template_missing_field_returns_400(isolated_client):
    _, client, _ = isolated_client
    template = _minimal_template()
    del template["label"]
    resp = client.post("/api/mdp/templates/save", json={"template": template})
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "INVALID_INPUT"


def test_save_template_missing_segment_returns_400(isolated_client):
    _, client, _ = isolated_client
    template = _minimal_template()
    del template["segment_type"]
    resp = client.post("/api/mdp/templates/save", json={"template": template})
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "INVALID_INPUT"


def test_delete_unknown_template_returns_404(isolated_client):
    _, client, _ = isolated_client
    resp = client.delete("/api/mdp/templates/不存在的範本")
    assert resp.status_code == 404
    assert resp.get_json()["code"] == "MDP_NOT_FOUND"


def test_export_returns_attachment(isolated_client):
    _, client, _ = isolated_client
    resp = client.get("/api/mdp/export")
    assert resp.status_code == 200
    assert "attachment" in resp.headers.get("Content-Disposition", "")


def test_export_returns_default_when_file_missing(isolated_client):
    _, client, tmp_path = isolated_client
    mdp_file = tmp_path / "multidimensional_rate_plans.json"
    if mdp_file.exists():
        mdp_file.unlink()

    resp = client.get("/api/mdp/export")
    assert resp.status_code == 200
    assert "attachment" in resp.headers.get("Content-Disposition", "")
    body = resp.get_data(as_text=True)
    assert "rate_plan_templates" in body


def test_segments_validate_full_coverage(isolated_client):
    _, client, _ = isolated_client
    resp = client.post(
        "/api/enhanced/segments/validate",
        json={"segments": [{"name": "全天", "start": "00:00", "end": "24:00"}]},
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["success"] is True
    assert payload["total_minutes"] == 24 * 60


def test_segments_validate_incomplete_coverage(isolated_client):
    _, client, _ = isolated_client
    resp = client.post(
        "/api/enhanced/segments/validate",
        json={"segments": [{"name": "日間", "start": "08:00", "end": "22:00"}]},
    )
    payload = resp.get_json()
    assert payload["success"] is False
    assert payload["total_minutes"] == 14 * 60


def test_segments_validate_overlap_rejected(isolated_client):
    _, client, _ = isolated_client
    resp = client.post(
        "/api/enhanced/segments/validate",
        json={
            "segments": [
                {"name": "A", "start": "00:00", "end": "13:00"},
                {"name": "B", "start": "12:00", "end": "24:00"},
            ]
        },
    )
    payload = resp.get_json()
    assert payload["success"] is False
    assert "重疊" in payload["message"]


def test_segments_validate_empty_returns_failure(isolated_client):
    _, client, _ = isolated_client
    resp = client.post("/api/enhanced/segments/validate", json={"segments": []})
    assert resp.get_json()["success"] is False


def test_combinations_endpoint(isolated_client):
    _, client, _ = isolated_client
    resp = client.get("/api/multidimensional/combinations")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["success"] is True
    assert isinstance(payload["combinations"], list)
    assert payload["combinations"]


def test_preview_missing_fields_returns_400(isolated_client):
    _, client, _ = isolated_client
    resp = client.post("/api/mdp/preview", json={"enter_time": "2025-06-20T10:00"})
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "INVALID_INPUT"


def test_preview_bad_datetime_returns_400(isolated_client):
    _, client, _ = isolated_client
    resp = client.post(
        "/api/mdp/preview",
        json={
            "enter_time": "2025/06/20 10:00",
            "exit_time": "2025/06/20 12:00",
            "template": _minimal_template(),
        },
    )
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "INVALID_DATETIME_FORMAT"


def test_preview_invalid_range_returns_400(isolated_client):
    _, client, _ = isolated_client
    resp = client.post(
        "/api/mdp/preview",
        json={
            "enter_time": "2025-06-20T12:00",
            "exit_time": "2025-06-20T10:00",
            "template": _minimal_template(),
        },
    )
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "INVALID_TIME_RANGE"
