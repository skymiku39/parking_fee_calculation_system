"""雜項路由測試：OpenAPI 規格靜態提供。"""

from unittest.mock import patch

from app import app


def test_serve_openapi_yaml_returns_spec():
    client = app.test_client()
    resp = client.get("/static/openapi.yaml")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "openapi" in body
    assert "/api/calculate" in body
    assert "3.2.0" in body


def test_serve_openapi_yaml_fallback_when_file_missing():
    client = app.test_client()
    with patch("src.web.misc.Path") as mock_path_cls:
        mock_path = mock_path_cls.return_value
        mock_path.exists.return_value = False
        resp = client.get("/static/openapi.yaml")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "openapi: 3.0.0" in body
    assert "Parking API" in body
    assert resp.mimetype == "text/yaml"
