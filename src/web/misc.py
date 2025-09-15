from pathlib import Path
from flask import Blueprint
from src.web.utils import error_response


misc_bp = Blueprint("misc_bp", __name__)


@misc_bp.route('/static/openapi.yaml')
def serve_openapi_yaml():
    from flask import send_from_directory
    path = Path('api/contracts/openapi.yaml')
    if path.exists():
        return send_from_directory(path.parent.as_posix(), path.name)
    # 提供最小化空白規格，避免 404 但仍提示未定義
    minimal = "openapi: 3.0.0\ninfo:\n  title: Parking API\n  version: 0.0.0\npaths: {}\n"
    resp = misc_bp.response_class(minimal, mimetype="text/yaml")
    return resp, 200



