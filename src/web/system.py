from flask import Blueprint, jsonify, request

from src.core.context import parking_system
from src.web.utils import error_response


system_bp = Blueprint("system_bp", __name__)


@system_bp.route("/api/system/config", methods=["GET", "POST"])
def api_system_config():
    if request.method == "GET":
        return jsonify({"success": True, "config": parking_system.system_config})
    else:
        try:
            new_config = request.get_json() or {}
            if not isinstance(new_config, dict):
                return error_response(
                    code="INVALID_INPUT",
                    message="請提供正確的JSON物件",
                    http_status=400,
                )
            parking_system.system_config.update(new_config)
            parking_system.save_system_config()
            if new_config.get("system_mode"):
                parking_system.init_multidimensional_calculator()
            return jsonify({"success": True, "message": "系統配置已更新"})
        except Exception as e:
            return error_response(
                code="INTERNAL_ERROR", message=str(e), http_status=500
            )



