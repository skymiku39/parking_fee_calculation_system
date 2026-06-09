from datetime import datetime
import uuid
import time as _pytime
from flask import Blueprint, jsonify, request

from src.core.context import parking_system
from src.web.utils import error_response
from src.core.utils import format_duration_display, DEFAULT_DATETIME_DISPLAY_FORMAT


calc_bp = Blueprint("calc_bp", __name__)


def get_all_available_plans():
    plans = []
    if parking_system.multidimensional_calculator:
        templates = parking_system.multidimensional_calculator.get_available_templates()
        for template_id, label in templates.items():
            plans.append(
                {
                    "plan_id": template_id,
                    "rate_plan_id": template_id,
                    "label": label,
                    "type": "multidimensional",
                    "description": f"多維度方案: {label}",
                }
            )

    user_plans = parking_system.list_user_defined_plans()
    plans.extend(user_plans)
    return plans


@calc_bp.route("/api/calculate", methods=["POST"])
def api_calculate_fee():
    request_id = str(uuid.uuid4())
    start_ts = _pytime.perf_counter()
    try:
        data = request.get_json() or {}
        enter_time_str = data.get("enter_time")
        exit_time_str = data.get("exit_time")
        plan_id = data.get("rate_plan_id") or data.get("plan_id")
        manual_adjustment = int(data.get("manual_adjustment", 0))
        vehicle_type_str = data.get("vehicle_type", "car")
        context = data.get("context", {})

        if not all([enter_time_str, exit_time_str]):
            return error_response(
                code="INVALID_INPUT",
                message="請填寫完整的進場時間和出場時間",
                http_status=400,
                extra={"request_id": request_id},
            )

        try:
            enter_time = datetime.strptime(enter_time_str, "%Y-%m-%dT%H:%M")
            exit_time = datetime.strptime(exit_time_str, "%Y-%m-%dT%H:%M")
        except ValueError:
            return error_response(
                code="INVALID_DATETIME_FORMAT",
                message="時間格式錯誤，請使用 YYYY-MM-DDTHH:MM",
                http_status=400,
                extra={"request_id": request_id},
            )

        if enter_time >= exit_time:
            return error_response(
                code="INVALID_TIME_RANGE",
                message="出場時間必須晚於進場時間",
                http_status=400,
                extra={"request_id": request_id},
            )

        result = parking_system.calculate_parking_fee(
            enter_time, exit_time, plan_id, manual_adjustment, context
        )

        if result.get("success"):
            total_minutes = result.get("total_duration_minutes", 0)
            result["total_duration_display"] = format_duration_display(total_minutes)
            result["enter_time_display"] = enter_time.strftime(DEFAULT_DATETIME_DISPLAY_FORMAT)
            result["exit_time_display"] = exit_time.strftime(DEFAULT_DATETIME_DISPLAY_FORMAT)

        if isinstance(result, dict):
            if isinstance(result.get("enter_time"), datetime):
                result["enter_time"] = result["enter_time"].strftime("%Y-%m-%d %H:%M")
            if isinstance(result.get("exit_time"), datetime):
                result["exit_time"] = result["exit_time"].strftime("%Y-%m-%d %H:%M")

        return jsonify({"request_id": request_id, **result})
    except Exception as e:
        return error_response(
            code="INTERNAL_ERROR",
            message=f"計算錯誤: {str(e)}",
            http_status=500,
            extra={"request_id": request_id},
        )


@calc_bp.route("/api/plans", methods=["GET"])
def api_get_all_plans():
    try:
        plans = get_all_available_plans()
        user_defined_count = sum(1 for p in plans if p.get("type") == "user_defined")
        return jsonify(
            {
                "success": True,
                "plans": plans,
                "user_defined_count": user_defined_count,
                "system_mode": parking_system.system_config.get(
                    "system_mode", "multidimensional"
                ),
            }
        )
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e), http_status=500)


