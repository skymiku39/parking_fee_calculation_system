"""系統 API 測試：版本資訊與設定錯誤分支。"""

import json
import re
from pathlib import Path
from unittest.mock import patch


def test_system_version_endpoint(isolated_client):
    _, client, _ = isolated_client
    resp = client.get("/api/system/version")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["success"] is True

    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject.read_text(encoding="utf-8"), re.M)
    assert payload["version"] == match.group(1)
    assert payload["data_dir"]


def test_system_config_get_returns_current_config(isolated_client):
    _, client, _ = isolated_client
    resp = client.get("/api/system/config")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["success"] is True
    assert payload["config"]["system_mode"] == "multidimensional"


def test_system_config_rejects_non_object_payload(isolated_client):
    _, client, _ = isolated_client
    resp = client.post(
        "/api/system/config",
        data=json.dumps([]),
        content_type="application/json",
    )
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "INVALID_INPUT"


def test_system_config_internal_error_returns_500(isolated_client):
    _, client, _ = isolated_client
    with patch(
        "src.web.system.parking_system.update_system_config",
        side_effect=RuntimeError("disk full"),
    ):
        resp = client.post(
            "/api/system/config",
            data=json.dumps({"currency_symbol": "NT$"}),
            content_type="application/json",
        )
    assert resp.status_code == 500
    payload = resp.get_json()
    assert payload["code"] == "INTERNAL_ERROR"
    assert "disk full" in payload["message"]
