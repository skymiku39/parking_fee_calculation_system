"""自訂方案 API 補充測試：匯出、錯誤分支與試算輸入驗證。"""


def test_export_user_plans_attachment(isolated_client):
    _, client, _ = isolated_client
    resp = client.get("/api/rate_plans/export")
    assert resp.status_code == 200
    assert "attachment" in resp.headers.get("Content-Disposition", "")


def test_load_unknown_plan_returns_404(isolated_client):
    _, client, _ = isolated_client
    resp = client.get("/api/rate_plans/load/不存在的方案")
    assert resp.status_code == 404
    assert resp.get_json()["code"] == "PLAN_NOT_FOUND"


def test_save_without_plan_object_returns_400(isolated_client):
    _, client, _ = isolated_client
    resp = client.post("/api/rate_plans/save", json={"plan_id": "x"})
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "INVALID_INPUT"


def test_save_without_plan_id_or_name_returns_400(isolated_client):
    _, client, _ = isolated_client
    resp = client.post(
        "/api/rate_plans/save",
        json={
            "plan": {
                "segment_type": "全天",
                "holiday_type": "無假日",
                "segments": [{"name": "全天", "start": "00:00", "end": "24:00"}],
            }
        },
    )
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "INVALID_INPUT"


def test_save_invalid_schema_returns_400(isolated_client):
    _, client, _ = isolated_client
    resp = client.post(
        "/api/rate_plans/save",
        json={
            "plan_id": "bad_plan",
            "plan": {
                "name": "bad_plan",
                "segment_type": "不存在的時段",
                "holiday_type": "無假日",
                "segments": [{"name": "全天", "start": "00:00", "end": "24:00"}],
            },
        },
    )
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "INVALID_CONFIG"


def test_delete_unknown_plan_returns_404(isolated_client):
    _, client, _ = isolated_client
    resp = client.delete("/api/rate_plans/不存在的方案")
    assert resp.status_code == 404
    assert resp.get_json()["code"] == "PLAN_NOT_FOUND"


def test_preview_missing_fields_returns_400(isolated_client):
    _, client, _ = isolated_client
    resp = client.post("/api/rate_plans/preview", json={})
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "INVALID_INPUT"


def test_preview_bad_datetime_returns_400(isolated_client):
    _, client, _ = isolated_client
    plan = client.get("/api/rate_plans/load/跨日測試方案").get_json()["plan"]
    resp = client.post(
        "/api/rate_plans/preview",
        json={
            "enter_time": "2025/06/20 10:00",
            "exit_time": "2025/06/20 12:00",
            "plan": plan,
        },
    )
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "INVALID_DATETIME_FORMAT"


def test_preview_invalid_range_returns_400(isolated_client):
    _, client, _ = isolated_client
    plan = client.get("/api/rate_plans/load/跨日測試方案").get_json()["plan"]
    resp = client.post(
        "/api/rate_plans/preview",
        json={
            "enter_time": "2025-06-20T12:00",
            "exit_time": "2025-06-20T10:00",
            "plan": plan,
        },
    )
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "INVALID_TIME_RANGE"
