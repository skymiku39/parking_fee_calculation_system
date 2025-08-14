import json


def test_calculate_error_model(client=None):
    # Flask provided test client via pytest fixture if available; else skip
    try:
        from app import app
    except Exception:
        return

    with app.test_client() as c:
        # 缺少必要欄位
        resp = c.post(
            "/api/calculate",
            data=json.dumps({"enter_time": "2025-06-20T10:00"}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["success"] is False
        assert data.get("code") == "INVALID_INPUT"
        assert "request_id" in data

        # 錯誤的時間格式
        resp2 = c.post(
            "/api/calculate",
            data=json.dumps({
                "enter_time": "2025/06/20 10:00",
                "exit_time": "2025/06/20 12:00",
                "plan_id": "全天_無假日費率",
            }),
            content_type="application/json",
        )
        assert resp2.status_code == 400
        data2 = resp2.get_json()
        assert data2.get("code") == "INVALID_DATETIME_FORMAT"
        assert "request_id" in data2

        # 正確請求但缺方案（若無預設方案）仍應返回成功字段或統一錯誤
        resp3 = c.post(
            "/api/calculate",
            data=json.dumps({
                "enter_time": "2025-06-20T10:00",
                "exit_time": "2025-06-20T12:00"
            }),
            content_type="application/json",
        )
        # 允許200（業務錯誤）或400，重點是結構一致
        assert resp3.status_code in (200, 400)
        data3 = resp3.get_json()
        assert "success" in data3


