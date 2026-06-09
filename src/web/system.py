from flask import Blueprint, jsonify, request

from src.core.context import parking_system
from src.core.paths import resolve_data_dir
from src.core.version import get_version
from src.web.utils import error_response


system_bp = Blueprint("system_bp", __name__)


@system_bp.route("/api/system/version", methods=["GET"])
def api_system_version():
    return jsonify(
        {
            "success": True,
            "version": get_version(),
            "data_dir": str(resolve_data_dir()),
        }
    )


@system_bp.route("/api/system/config", methods=["GET", "POST"])
def api_system_config():
    if request.method == "GET":
        return jsonify({"success": True, "config": parking_system.system_config})

    try:
        new_config = request.get_json()
        if not isinstance(new_config, dict):
            return error_response(
                code="INVALID_INPUT",
                message="System config payload must be a JSON object.",
                http_status=400,
            )

        parking_system.update_system_config(new_config)
        if "system_mode" in new_config:
            parking_system.init_multidimensional_calculator()

        return jsonify({"success": True, "message": "System config updated successfully."})
    except ValueError as e:
        return error_response(
            code="INVALID_CONFIG",
            message=str(e),
            http_status=400,
        )
    except Exception as e:
        return error_response(
            code="INTERNAL_ERROR",
            message=str(e),
            http_status=500,
        )
