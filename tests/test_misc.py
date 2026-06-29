"""雜項路由測試：OpenAPI 規格靜態提供。"""

from app import app


def test_serve_openapi_yaml_returns_spec():
    client = app.test_client()
    resp = client.get("/static/openapi.yaml")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "openapi" in body
    assert "/api/calculate" in body
