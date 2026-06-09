import time as _pytime
import uuid
from datetime import datetime
from flask import Blueprint, jsonify, request

from src.core.context import parking_system
from src.domain.terminology import (
    normalize_holiday_type,
    normalize_segment_type,
    resolve_template_id,
)
from src.web.utils import error_response


mdp_bp = Blueprint("mdp_bp", __name__)


def _mdp_config_path():
    from pathlib import Path

    base_path = getattr(parking_system, "base_path", Path("."))
    return Path(base_path) / "multidimensional_rate_plans.json"


def _load_mdp_config(path=None) -> dict:
    import json
    from pathlib import Path

    p = _mdp_config_path() if path is None else Path(path)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_mdp_config(config_data: dict, path=None):
    import json
    from pathlib import Path
    from src.core.validation import validate_multidimensional_config_json

    try:
        validate_multidimensional_config_json(config_data)
    except Exception:
        pass
    p = _mdp_config_path() if path is None else Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(config_data, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        parking_system.init_multidimensional_calculator()
    except Exception:
        pass


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

        _save_mdp_config(cfg)
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
        _save_mdp_config(cfg)
        return jsonify({"success": True, "message": f"已刪除範本: {template_id}"})
    except Exception as e:
        return error_response("MDP_DELETE_ERROR", str(e), 500)


@mdp_bp.route("/api/mdp/export", methods=["GET"])
def api_mdp_export_config():
    from flask import send_from_directory
    import json
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
    start_ts = _pytime.perf_counter()
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

        temp_id = template.get("template_id") or f"inline_{int(_pytime.perf_counter()*1000)}"
        old = calc.rate_plan_templates.get(temp_id)
        try:
            from src.domain.multidimensional_calculator import MultidimensionalRatePlan
            from src.domain.terminology import SegmentType, HolidayType
            seg_raw = template.get("segment_type") or template.get("time_segment_type", "二段")
            hol_raw = template.get("holiday_type", "平日假日")
            plan_variants = {
                "weekday_plan": template.get("weekday_plan"),
                "weekend_plan": template.get("weekend_plan"),
                "national_holiday_plan": template.get("national_holiday_plan"),
                "custom_holiday_plan": template.get("custom_holiday_plan"),
                "unified_plan": template.get("unified_plan"),
            }
            if not any(plan_variants.values()) and template.get("time_slots"):
                flat_plan = {
                    "label": template.get("label", temp_id),
                    "time_slots": template.get("time_slots", []),
                    "daily_cap_enabled": bool(template.get("daily_cap_enabled", False)),
                    "daily_cap_amount": int(template.get("daily_cap_amount", 0) or 0),
                    "global_grace_time": int(template.get("global_grace_time", 0) or 0),
                    "global_caps": {
                        "daily_cap_enabled": bool(template.get("daily_cap_enabled", False)),
                        "daily_cap_amount": int(template.get("daily_cap_amount", 0) or 0),
                        "global_grace_time": int(template.get("global_grace_time", 0) or 0),
                    },
                }
                plan_variants = {key: flat_plan for key in plan_variants}
            rp = MultidimensionalRatePlan(
                template_id=temp_id,
                label=template.get("label", temp_id),
                description=template.get("description", ""),
                segment_type=SegmentType(normalize_segment_type(seg_raw)),
                holiday_type=HolidayType(normalize_holiday_type(hol_raw)),
                dimension_combination=temp_id,
                weekday_plan=plan_variants["weekday_plan"],
                weekend_plan=plan_variants["weekend_plan"],
                national_holiday_plan=plan_variants["national_holiday_plan"],
                custom_holiday_plan=plan_variants["custom_holiday_plan"],
                unified_plan=plan_variants["unified_plan"],
            )
            calc.rate_plan_templates[temp_id] = rp
            res = calc.calculate_parking_fee(enter_time, exit_time, temp_id)
        finally:
            if old is not None:
                calc.rate_plan_templates[temp_id] = old
            else:
                calc.rate_plan_templates.pop(temp_id, None)

        total_minutes = sum(d.get("duration", 0) for d in res.session_details)
        result = {
            "success": True,
            "total_amount": res.total_amount,
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



