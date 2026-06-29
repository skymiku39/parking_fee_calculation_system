import uuid
from datetime import datetime

from flask import Blueprint, jsonify, request

from src.core.context import parking_system
from src.domain.terminology import (
    normalize_holiday_type,
    normalize_segment_type,
)
from src.web.utils import error_response

mdp_bp = Blueprint("mdp_bp", __name__)


def _mdp_config_path():
    return parking_system.mdp_config_path


def _load_mdp_config() -> dict:
    return parking_system.load_mdp_config()


def _save_mdp_config(config_data: dict, *, template_id=None, action: str = "save"):
    parking_system.save_mdp_config(
        config_data,
        template_id=template_id,
        action=action,
    )


@mdp_bp.route("/api/mdp/templates", methods=["GET"])
def api_mdp_list_templates():
    try:
        cfg = _load_mdp_config()
        templates = cfg.get("rate_plan_templates", [])
        items = []
        for t in templates:
            seg = t.get("segment_type") or t.get("time_segment_type")
            items.append({
                "template_id": t.get("template_id"),
                "plan_id": t.get("template_id"),
                "label": t.get("label"),
                "description": t.get("description"),
                "segment_type": seg,
                "holiday_type": t.get("holiday_type"),
            })
        return jsonify({"success": True, "templates": items, "total": len(items)})
    except Exception as e:
        return error_response("MDP_LIST_ERROR", str(e), 500)


@mdp_bp.route("/api/mdp/templates/<template_id>", methods=["GET"])
def api_mdp_get_template(template_id: str):
    try:
        cfg = _load_mdp_config()
        templates = cfg.get("rate_plan_templates", [])
        for t in templates:
            if t.get("template_id") == template_id:
                return jsonify({"success": True, "template": t})
        return error_response("MDP_NOT_FOUND", "找不到指定範本", 404)
    except Exception as e:
        return error_response("MDP_GET_ERROR", str(e), 500)


@mdp_bp.route("/api/mdp/templates/save", methods=["POST"])
def api_mdp_save_template():
    try:
        payload = request.get_json() or {}
        tpl = payload.get("template") or {}
        seg = tpl.get("segment_type") or tpl.get("time_segment_type")
        required = ["template_id", "label", "description", "holiday_type"]
        for k in required:
            if not tpl.get(k):
                return error_response("INVALID_INPUT", f"缺少必要欄位: {k}", 400)
        if not seg:
            return error_response("INVALID_INPUT", "缺少必要欄位: segment_type", 400)
        tpl["segment_type"] = normalize_segment_type(seg)
        tpl["holiday_type"] = normalize_holiday_type(tpl["holiday_type"])
        tpl.pop("time_segment_type", None)

        cfg = _load_mdp_config()
        templates = cfg.setdefault("rate_plan_templates", [])
        updated = False
        for i, t in enumerate(templates):
            if t.get("template_id") == tpl["template_id"]:
                templates[i] = tpl
                updated = True
                break
        if not updated:
            templates.append(tpl)

        _save_mdp_config(cfg, template_id=tpl["template_id"], action="save")
        return jsonify({"success": True, "message": "範本已儲存", "template_id": tpl["template_id"]})
    except Exception as e:
        return error_response("MDP_SAVE_ERROR", str(e), 500)


@mdp_bp.route("/api/mdp/templates/<template_id>", methods=["DELETE"])
def api_mdp_delete_template(template_id: str):
    try:
        cfg = _load_mdp_config()
        templates = cfg.get("rate_plan_templates", [])
        new_list = [t for t in templates if t.get("template_id") != template_id]
        if len(new_list) == len(templates):
            return error_response("MDP_NOT_FOUND", "方案不存在", 404)
        cfg["rate_plan_templates"] = new_list
        _save_mdp_config(cfg, template_id=template_id, action="delete")
        return jsonify({"success": True, "message": f"已刪除範本: {template_id}"})
    except Exception as e:
        return error_response("MDP_DELETE_ERROR", str(e), 500)


@mdp_bp.route("/api/mdp/export", methods=["GET"])
def api_mdp_export_config():
    import json

    from flask import send_from_directory
    try:
        p = _mdp_config_path()
        if p.exists():
            return send_from_directory(p.parent.as_posix(), p.name, as_attachment=True, download_name="multidimensional_rate_plans.json")
        default_cfg = {"dimension_configs": {}, "rate_plan_templates": []}
        data = json.dumps(default_cfg, ensure_ascii=False, indent=2)
        resp = mdp_bp.response_class(data, mimetype="application/json")
        resp.headers["Content-Disposition"] = "attachment; filename=multidimensional_rate_plans.json"
        return resp
    except Exception as e:
        return error_response("MDP_EXPORT_ERROR", str(e), 500)


@mdp_bp.route("/api/mdp/preview", methods=["POST"])
def api_mdp_preview():
    request_id = str(uuid.uuid4())
    try:
        data = request.get_json() or {}
        enter_time_str = data.get("enter_time")
        exit_time_str = data.get("exit_time")
        template = data.get("template")
        if not (enter_time_str and exit_time_str and isinstance(template, dict)):
            return error_response(
                code="INVALID_INPUT",
                message="請提供 enter_time、exit_time 與 template 物件",
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

        calc = parking_system.multidimensional_calculator
        if not calc:
            return error_response(
                code="MDP_NOT_READY",
                message="多維度計算器尚未初始化",
                http_status=500,
                extra={"request_id": request_id},
            )

        res = calc.calculate_with_inline_template(enter_time, exit_time, template)

        total_minutes = sum(d.get("duration", 0) for d in res.session_details)
        result = {
            "success": True,
            "total_amount": res.total_amount,
            "original_amount": res.original_amount,
            "cap_applied": res.original_amount > res.total_amount,
            "total_duration_minutes": total_minutes,
            "total_duration_display": parking_system.format_duration_display(total_minutes),
            "session_details": res.session_details,
            "calculation_summary": res.calculation_summary,
        }
        return jsonify({"request_id": request_id, **result})
    except Exception as e:
        return error_response(
            code="INTERNAL_ERROR",
            message=f"試算錯誤: {str(e)}",
            http_status=500,
            extra={"request_id": request_id},
        )


@mdp_bp.route("/api/enhanced/segments/validate", methods=["POST"])
def api_validate_segments():
    try:
        payload = request.get_json() or {}
        segments = payload.get("segments", [])
        if not isinstance(segments, list) or not segments:
            return jsonify({"success": False, "message": "請提供 segments 陣列"})

        def to_min(hhmm: str) -> int:
            if hhmm == "24:00":
                return 24 * 60
            hh, mm = hhmm.split(":")
            return int(hh) * 60 + int(mm)

        intervals = []
        for s in segments:
            name = s.get("name")
            start = s.get("start")
            end = s.get("end")
            if not all([name, start, end]):
                return jsonify({"success": False, "message": f"區段缺少必要欄位: {s}"})
            a, b = to_min(start), to_min(end)
            if a == b:
                return jsonify({"success": False, "message": f"區段 '{name}' 開始與結束相同"})
            if a < b:
                intervals.append((a, b))
            else:
                intervals.append((a, 24 * 60))
                intervals.append((0, b))

        intervals.sort()
        merged = []
        for iv in intervals:
            if not merged or merged[-1][1] < iv[0]:
                merged.append([iv[0], iv[1]])
            else:
                if iv[0] < merged[-1][1] and iv[0] != merged[-1][1]:
                    return jsonify({"success": False, "message": "時間區段有重疊，請調整"})
                merged[-1][1] = max(merged[-1][1], iv[1])

        total_minutes = sum(b - a for a, b in merged)
        success = total_minutes == 24 * 60
        return jsonify({
            "success": success,
            "message": "覆蓋完整" if success else "尚未完整覆蓋 24 小時",
            "total_minutes": total_minutes,
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@mdp_bp.route("/api/multidimensional/combinations")
def api_get_dimension_combinations():
    try:
        if not parking_system.multidimensional_calculator:
            return error_response(
                code="ENGINE_NOT_READY",
                message="多維度計算器未初始化",
                http_status=500,
            )
        combinations = (
            parking_system.multidimensional_calculator.get_dimension_combinations()
        )
        return jsonify({"success": True, "combinations": combinations})
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e), http_status=500)



