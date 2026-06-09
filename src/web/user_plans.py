from datetime import datetime

from flask import Blueprint, jsonify, request, send_from_directory

from src.core.context import parking_system
from src.core.utils import format_duration_display
from src.core.validation import ConfigValidationError
from src.web.utils import error_response


user_plans_bp = Blueprint("user_plans_bp", __name__)


@user_plans_bp.route("/api/rate_plans", methods=["GET"])
def api_list_user_plans():
    try:
        apply_filters = request.args.get("all", "").lower() not in ("1", "true", "yes")
        plans = parking_system.list_user_defined_plans(apply_ui_filters=apply_filters)
        return jsonify(
            {
                "success": True,
                "plans": plans,
                "total": len(plans),
            }
        )
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e), http_status=500)


@user_plans_bp.route("/api/rate_plans/load/<path:plan_id>", methods=["GET"])
def api_load_user_plan(plan_id: str):
    try:
        plan = parking_system.get_user_defined_plan(plan_id)
        if not plan:
            return error_response(
                code="PLAN_NOT_FOUND",
                message=f"找不到自訂方案: {plan_id}",
                http_status=404,
            )
        return jsonify(
            {
                "success": True,
                "plan_id": plan_id,
                "plan": plan,
            }
        )
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e), http_status=500)


@user_plans_bp.route("/api/rate_plans/preview", methods=["POST"])
def api_preview_user_plan():
    try:
        payload = request.get_json() or {}
        enter_time_str = payload.get("enter_time")
        exit_time_str = payload.get("exit_time")
        plan_data = payload.get("plan")

        if not all([enter_time_str, exit_time_str, isinstance(plan_data, dict)]):
            return error_response(
                code="INVALID_INPUT",
                message="請提供 enter_time、exit_time 與 plan 物件",
                http_status=400,
            )

        try:
            enter_time = datetime.strptime(enter_time_str, "%Y-%m-%dT%H:%M")
            exit_time = datetime.strptime(exit_time_str, "%Y-%m-%dT%H:%M")
        except ValueError:
            return error_response(
                code="INVALID_DATETIME_FORMAT",
                message="時間格式錯誤，請使用 YYYY-MM-DDTHH:MM",
                http_status=400,
            )

        if enter_time >= exit_time:
            return error_response(
                code="INVALID_TIME_RANGE",
                message="出場時間必須晚於進場時間",
                http_status=400,
            )

        result = parking_system.calculate_fee_by_billing_cycles(
            enter_time=enter_time,
            exit_time=exit_time,
            plan_data=plan_data,
        )
        if not result.get("success"):
            return error_response(
                code="PREVIEW_FAILED",
                message=result.get("error", "試算失敗"),
                http_status=400,
            )

        total_minutes = result.get("total_duration_minutes", 0)
        result["total_duration_display"] = format_duration_display(total_minutes)
        return jsonify(result)
    except ConfigValidationError as e:
        return error_response(
            code="INVALID_CONFIG",
            message=f"方案配置不合法: {', '.join(e.errors) if e.errors else str(e)}",
            http_status=400,
        )
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e), http_status=500)


@user_plans_bp.route("/api/rate_plans/save", methods=["POST"])
def api_save_user_plan():
    try:
        payload = request.get_json() or {}
        plan_id = payload.get("plan_id")
        plan_data = payload.get("plan")

        if not isinstance(plan_data, dict):
            return error_response(
                code="INVALID_INPUT",
                message="請提供 plan 物件",
                http_status=400,
            )

        if not plan_id:
            plan_id = plan_data.get("name") or plan_data.get("plan_id")
        if not plan_id:
            return error_response(
                code="INVALID_INPUT",
                message="請提供 plan_id 或 plan.name",
                http_status=400,
            )

        saved = parking_system.save_user_defined_plan(str(plan_id).strip(), plan_data)
        return jsonify(
            {
                "success": True,
                "message": "自訂方案已儲存",
                "plan_id": str(plan_id).strip(),
                "plan": saved,
            }
        )
    except ConfigValidationError as e:
        return error_response(
            code="INVALID_CONFIG",
            message=f"方案配置不合法: {', '.join(e.errors) if e.errors else str(e)}",
            http_status=400,
        )
    except ValueError as e:
        return error_response(code="INVALID_INPUT", message=str(e), http_status=400)
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e), http_status=500)


@user_plans_bp.route("/api/rate_plans/<path:plan_id>", methods=["DELETE"])
def api_delete_user_plan(plan_id: str):
    try:
        deleted = parking_system.delete_user_defined_plan(plan_id)
        if not deleted:
            return error_response(
                code="PLAN_NOT_FOUND",
                message=f"找不到自訂方案: {plan_id}",
                http_status=404,
            )
        return jsonify({"success": True, "message": f"已刪除方案: {plan_id}"})
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e), http_status=500)


@user_plans_bp.route("/api/rate_plans/export", methods=["GET"])
def api_export_user_plans():
    try:
        path = parking_system._user_plans_path()
        if path.exists():
            return send_from_directory(
                path.parent.as_posix(),
                path.name,
                as_attachment=True,
                download_name="user_defined_plans.json",
            )

        import json

        default_cfg = {"plans": {}, "metadata": {}}
        data = json.dumps(default_cfg, ensure_ascii=False, indent=2)
        resp = user_plans_bp.response_class(data, mimetype="application/json")
        resp.headers["Content-Disposition"] = (
            "attachment; filename=user_defined_plans.json"
        )
        return resp
    except Exception as e:
        return error_response(code="EXPORT_ERROR", message=str(e), http_status=500)
