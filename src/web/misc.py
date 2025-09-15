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
    minimal = (
        "openapi: 3.0.0\n"
        "info:\n"
        "  title: Parking API\n"
        "  version: 0.0.1\n"
        "paths:\n"
        "  /api/calculate:\n"
        "    post:\n"
        "      summary: 計算停車費用\n"
        "      requestBody:\n"
        "        required: true\n"
        "        content:\n"
        "          application/json:\n"
        "            schema:\n"
        "              type: object\n"
        "              properties:\n"
        "                enter_time: { type: string, example: '2025-09-01T08:00' }\n"
        "                exit_time:  { type: string, example: '2025-09-01T10:00' }\n"
        "                rate_plan_id: { type: string }\n"
        "                manual_adjustment: { type: integer, default: 0 }\n"
        "                context: { type: object }\n"
        "      responses:\n"
        "        '200':\n"
        "          description: 成功\n"
        "        '400':\n"
        "          description: 輸入錯誤\n"
        "  /api/plans:\n"
        "    get:\n"
        "      summary: 取得可用方案清單\n"
        "      responses:\n"
        "        '200': { description: 成功 }\n"
    )
    resp = misc_bp.response_class(minimal, mimetype="text/yaml")
    return resp, 200



