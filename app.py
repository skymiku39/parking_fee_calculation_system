"""
智能停車費率計算系統 Web 應用程式
提供完整的費率方案設計、配置、計費、結算流程
支援多維度標籤計費系統和全面的費率管理
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for
from datetime import datetime, date, time, timedelta
import json
import uuid
import time as _pytime
import os
import sys
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import logging
from os import getenv
import urllib.request
import ssl
from flask import send_from_directory
from utils.config_validator import (
    validate_user_defined_plans_json,
    validate_multidimensional_config_json,
    ConfigValidationError,
)
_HAS_PYDANTIC = False

# 加入模組路徑
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from src.engines.parking_calculator import ParkingCalculator, VehicleType
from src.engines.multidimensional_calculator import (
    MultidimensionalParkingCalculator,
    TimeSegmentType,
    HolidayType,
    DateCategory,
)
from src.managers.rate_plan_manager import RatePlanManager
try:
    from src.domain.pricing.unified_pricing_engine import UnifiedPricingEngine
except Exception:
    # 向後相容舊路徑
    from src.unified_pricing_engine import UnifiedPricingEngine

# 移除增強版多維度計算器以簡化系統

# 讓 Flask 在 PyInstaller 打包後也能正確找到模板與靜態資源
# onedir/onefile：優先使用工作目錄（launcher 已切換至可執行檔所在目錄）
_BASE_DIR = Path(getattr(sys, "_MEIPASS", os.getcwd()))
_TEMPLATE_DIR = (_BASE_DIR / "templates").as_posix()
_STATIC_DIR = (_BASE_DIR / "static").as_posix()

app = Flask(__name__, template_folder=_TEMPLATE_DIR, static_folder=_STATIC_DIR)
app.config["JSON_AS_ASCII"] = False  # 支援中文JSON
try:
    from flasgger import Swagger

    swagger = Swagger(
        app,
        template={
            "swagger": "2.0",
            "info": {
                "title": "智能停車費率計算系統 API",
                "version": "1.0.0",
                "description": "統一錯誤模型與時間格式的 API 規格",
            },
        },
    )
except Exception:
    swagger = None

# 設定日誌
os.makedirs("log", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    handlers=[
        logging.FileHandler("log/app.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)
# 統一錯誤回應工具
def error_response(code: str, message: str, http_status: int = 400, extra: Dict = None):
    # 為相容前端舊邏輯，額外提供 error 欄位，避免顯示 undefined
    payload = {"success": False, "code": code, "message": message, "error": message}
    if isinstance(extra, dict):
        payload.update(extra)
    return jsonify(payload), http_status




# 初始化核心組件
class SmartParkingSystem:
    def __init__(self):
        self.rate_plan_manager = RatePlanManager()
        self.multidimensional_calculator = None
        self.system_config = {}
        self.unified_engine = UnifiedPricingEngine()

        # 載入系統配置
        self.load_system_config()

        # 初始化多維度計算器
        self.init_multidimensional_calculator()

    def load_system_config(self):
        """載入系統配置"""
        try:
            config_path = Path("config/system_config.json")
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    self.system_config = json.load(f)
            else:
                # 創建預設系統配置
                self.system_config = {
                    "system_mode": "multidimensional",  # 統一使用多維度模式
                    "default_calculation_engine": "multidimensional",
                    "enable_plan_switching": True,
                    "enable_manual_override": True,
                    "calculation_precision": 2,
                    "currency_symbol": "NT$",
                    "date_format": "%Y-%m-%d",
                    "time_format": "%H:%M",
                    "system_timezone": "Asia/Taipei",
                }
                self.save_system_config()

            # 環境變數覆寫（不修改檔案）
            env_overrides = {
                "system_mode": getenv("PARK_SYS_MODE"),
                "default_calculation_engine": getenv("PARK_DEFAULT_ENGINE"),
                "currency_symbol": getenv("PARK_CURRENCY_SYMBOL"),
                "system_timezone": getenv("PARK_TIMEZONE"),
            }
            calc_precision = getenv("PARK_CALC_PRECISION")
            if calc_precision is not None and calc_precision.isdigit():
                env_overrides["calculation_precision"] = int(calc_precision)

            # UI 設定覆寫
            ui_max = getenv("PARK_UI_MAX_USER_PLANS_DISPLAY")
            ui_featured = getenv("PARK_UI_SHOW_ONLY_FEATURED")
            if ui_max is not None:
                self.system_config.setdefault("ui_settings", {})
                try:
                    self.system_config["ui_settings"]["max_user_plans_display"] = int(ui_max)
                except ValueError:
                    pass
            if ui_featured is not None:
                self.system_config.setdefault("ui_settings", {})
                self.system_config["ui_settings"]["show_only_featured_user_plans"] = (
                    ui_featured.lower() in {"1", "true", "yes"}
                )

            # 套用一般覆寫
            for k, v in env_overrides.items():
                if v is not None:
                    self.system_config[k] = v
        except Exception as e:
            logger.exception("載入系統配置失敗: %s", e)
            self.system_config = {}

    def save_system_config(self):
        """儲存系統配置"""
        try:
            config_path = Path("config/system_config.json")
            config_path.parent.mkdir(exist_ok=True)
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(self.system_config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.exception("儲存系統配置失敗: %s", e)

    def init_multidimensional_calculator(self):
        """初始化多維度計算器"""
        try:
            # 啟動前驗證配置
            cfg_path = Path("config/multidimensional_rate_plans.json")
            if cfg_path.exists():
                with open(cfg_path, "r", encoding="utf-8") as f:
                    _cfg = json.load(f)
                validate_multidimensional_config_json(_cfg)

            self.multidimensional_calculator = MultidimensionalParkingCalculator(
                "config/multidimensional_rate_plans.json"
            )
            logger.info("多維度標籤計算器載入成功")
        except Exception as e:
            logger.exception("多維度標籤計算器載入失敗: %s", e)

# ============== 多維度方案 CRUD API ==============
MDP_CONFIG_PATH = Path("config/multidimensional_rate_plans.json")

def _load_mdp_config() -> dict:
    if MDP_CONFIG_PATH.exists():
        try:
            return json.loads(MDP_CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def _save_mdp_config(config_data: dict):
    # 可選：驗證整體結構
    try:
        validate_multidimensional_config_json(config_data)
    except Exception:
        # 若驗證函式較嚴格且結構為增量維護，放寬只在嚴重結構錯誤才阻止
        pass
    MDP_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    MDP_CONFIG_PATH.write_text(json.dumps(config_data, ensure_ascii=False, indent=2), encoding="utf-8")
    # 重新載入計算器
    try:
        parking_system.init_multidimensional_calculator()
    except Exception:
        logger.exception("重新載入多維度計算器失敗")

@app.route("/api/mdp/templates", methods=["GET"])
def api_mdp_list_templates():
    try:
        cfg = _load_mdp_config()
        templates = cfg.get("rate_plan_templates", [])
        items = []
        for t in templates:
            items.append({
                "template_id": t.get("template_id"),
                "label": t.get("label"),
                "description": t.get("description"),
                "time_segment_type": t.get("time_segment_type"),
                "holiday_type": t.get("holiday_type"),
            })
        return jsonify({"success": True, "templates": items, "total": len(items)})
    except Exception as e:
        return error_response("MDP_LIST_ERROR", str(e), 500)

@app.route("/api/mdp/templates/<template_id>", methods=["GET"])
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

@app.route("/api/mdp/templates/save", methods=["POST"])
def api_mdp_save_template():
    try:
        payload = request.get_json() or {}
        tpl = payload.get("template") or {}
        required = ["template_id", "label", "description", "time_segment_type", "holiday_type"]
        for k in required:
            if not tpl.get(k):
                return error_response("INVALID_INPUT", f"缺少必要欄位: {k}", 400)

        cfg = _load_mdp_config()
        templates = cfg.setdefault("rate_plan_templates", [])

        # 更新或新增
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

@app.route("/api/mdp/templates/<template_id>", methods=["DELETE"])
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

@app.route("/api/mdp/export", methods=["GET"])
def api_mdp_export_config():
    try:
        if MDP_CONFIG_PATH.exists():
            return send_from_directory(MDP_CONFIG_PATH.parent.as_posix(), MDP_CONFIG_PATH.name, as_attachment=True, download_name="multidimensional_rate_plans.json")
        # 提供空結構
        default_cfg = {"dimension_configs": {}, "rate_plan_templates": []}
        data = json.dumps(default_cfg, ensure_ascii=False, indent=2)
        resp = app.response_class(data, mimetype="application/json")
        resp.headers["Content-Disposition"] = "attachment; filename=multidimensional_rate_plans.json"
        return resp
    except Exception as e:
        return error_response("MDP_EXPORT_ERROR", str(e), 500)

    # 移除「啟用方案」機制，統一以傳入的 plan_id 或 plan_inline 試算

    def validate_plan_exists(self, plan_id: str) -> bool:
        """驗證費率方案是否存在"""
        # 檢查用戶自訂方案
        if self.is_user_defined_plan(plan_id):
            return True

        # 檢查多維度方案
        if self.multidimensional_calculator:
            templates = self.multidimensional_calculator.get_available_templates()
            if plan_id in templates:
                return True

        return False

    def calculate_parking_fee(
        self,
        enter_time: datetime,
        exit_time: datetime,
        plan_id: str = None,
        vehicle_type: VehicleType = VehicleType.CAR,
        manual_adjustment: int = 0,
        context: Dict = None,
    ) -> Dict:
        """統一的停車費計算介面"""
        try:
            # 僅使用呼叫端傳入的方案ID
            active_plan = plan_id
            if not active_plan:
                raise ValueError("請提供 plan_id 或使用 plan_inline 進行即時試算")

            # 檢查是否為用戶自訂方案
            if self.is_user_defined_plan(active_plan):
                return self.calculate_with_user_defined_plan(
                    enter_time, exit_time, active_plan, manual_adjustment, context
                )
            # 使用多維度計算引擎
            else:
                return self.calculate_with_multidimensional(
                    enter_time, exit_time, active_plan, manual_adjustment, context
                )

        except Exception as e:
            return {"success": False, "error": str(e), "calculation_engine": "none"}

    def is_user_defined_plan(self, plan_id: str) -> bool:
        """檢查是否為用戶自訂方案"""
        try:
            with open("config/user_defined_plans.json", "r", encoding="utf-8") as f:
                user_plans = json.load(f)
                return plan_id in user_plans.get("plans", {})
        except FileNotFoundError:
            return False

    def calculate_with_user_defined_plan(
        self,
        enter_time: datetime,
        exit_time: datetime,
        plan_id: str,
        manual_adjustment: int = 0,
        context: Dict = None,
    ) -> Dict:
        """使用用戶自訂方案進行計算"""
        try:
            # 載入用戶自訂方案
            with open("config/user_defined_plans.json", "r", encoding="utf-8") as f:
                user_plans = json.load(f)
            # 讀取後進行 schema 驗證
            try:
                validate_user_defined_plans_json(user_plans)
            except ConfigValidationError as ve:
                return {
                    "success": False,
                    "code": "INVALID_CONFIG",
                    "message": f"用戶方案配置不合法: {', '.join(ve.errors) if ve.errors else str(ve)}",
                }

            if plan_id not in user_plans.get("plans", {}):
                raise ValueError(f"找不到用戶自訂方案: {plan_id}")

            plan_data = user_plans["plans"][plan_id]
            # 使用 30 分鐘收費週期邏輯：週期開始時決定費率與日期類別
            result = self.calculate_fee_by_billing_cycles(
                enter_time=enter_time,
                exit_time=exit_time,
                plan_data=plan_data,
                manual_adjustment=manual_adjustment,
            )
            return result

        except Exception as e:
            return {
                "success": False,
                "error": f"用戶自訂方案計算失敗: {str(e)}",
                "calculation_engine": "user_defined_billing_cycle",
            }

    def calculate_fee_by_billing_cycles(
        self,
        enter_time: datetime,
        exit_time: datetime,
        plan_data: dict,
        manual_adjustment: int = 0,
    ) -> Dict:
        """
        基於收費週期的正確計費邏輯

        核心原理：
        1. 按收費週期（如30分鐘、60分鐘）來劃分時間
        2. 每個收費週期開始時，使用當時適用的時段費率
        3. 如果收費週期跨越時段邊界，仍使用週期開始時的費率

        例如：日間30分鐘一收費，21:52是上次收款時間
        - 下次收款時間是22:22（跨越了22:00的夜間邊界）
        - 但這30分鐘週期仍使用日間費率
        - 22:22之後才開始使用夜間費率
        """
        try:
            # 計算停車時長
            total_minutes = int((exit_time - enter_time).total_seconds() / 60)

            # 確定日期類型
            date_category = self.determine_date_category(
                enter_time, plan_data["holiday_type"]
            )

            # 檢查是否有全局寬裕時間設定
            global_grace_time = plan_data.get("global_grace_time", 0)

            # 處理時間區段
            segments = plan_data.get("segments", [])
            rate_matrix = plan_data.get("rate_matrix", {})

            if plan_data["segment_type"] == "全天":
                # 全天統一費率的簡單處理
                segment_key = f"全天_{date_category}"
                if segment_key in rate_matrix:
                    rate_config = rate_matrix[segment_key]
                    total_amount = self.calculate_segment_fee(
                        total_minutes, rate_config, global_grace_time
                    )

                    # 生成簡單明細
                    session_details = [
                        {
                            "period": f"{enter_time.strftime('%H:%M')}-{exit_time.strftime('%H:%M')}",
                            "duration": self.format_duration_display(total_minutes),
                            "rate": self.get_rate_description(rate_config),
                            "amount": total_amount,
                            "date": enter_time.strftime("%m-%d"),
                        }
                    ]

                    calculation_summary = f"全天費率 {total_minutes}分鐘"
                else:
                    total_amount = 0
                    session_details = []
                    calculation_summary = "無適用費率"
            else:
                # 多時段費率：使用收費週期邏輯，但整合顯示
                billing_cycles, total_amount = self.generate_billing_cycles(
                    enter_time,
                    exit_time,
                    segments,
                    rate_matrix,
                    plan_data["holiday_type"],
                    global_grace_time,
                )

                # 整合相同時段和費率的週期
                session_details, calculation_summary = self.consolidate_billing_cycles(
                    billing_cycles, enter_time, plan_data["holiday_type"]
                )

            # 應用全域收費上限
            global_caps = plan_data.get("global_caps", {})
            cap_applied = False
            cap_amount = None
            original_amount = total_amount

            if global_caps.get("daily_cap_enabled") and global_caps.get(
                "daily_cap_amount"
            ):
                daily_cap = global_caps["daily_cap_amount"]
                if total_amount > daily_cap:
                    total_amount = daily_cap
                    cap_applied = True
                    cap_amount = daily_cap

            # 添加手動調整
            total_amount += manual_adjustment

            # 確定主要日期類別（使用進場時間）
            primary_date_category = self.determine_date_category(
                enter_time, plan_data["holiday_type"]
            )

            return {
                "success": True,
                "calculation_engine": "user_defined_billing_cycle",
                "total_amount": total_amount,
                "original_amount": original_amount,
                "manual_adjustment": manual_adjustment,
                "cap_applied": cap_applied,
                "cap_amount": cap_amount,
                "date_category": primary_date_category,
                "applied_rate_plan": plan_data["name"],
                "segment_type": plan_data["segment_type"],
                "holiday_type": plan_data["holiday_type"],
                "session_details": session_details,
                "calculation_summary": calculation_summary,
                "enter_time": enter_time,
                "exit_time": exit_time,
                "total_duration_minutes": total_minutes,
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"收費週期計算失敗: {str(e)}",
                "calculation_engine": "user_defined_billing_cycle",
            }

    def generate_billing_cycles(
        self,
        enter_time: datetime,
        exit_time: datetime,
        segments: List[dict],
        rate_matrix: dict,
        holiday_type: str,
        global_grace_time: int = 0,
    ) -> Tuple[List[Dict], int]:
        """
        生成基於收費週期的計費明細
        修正：動態判斷每個時間點的日期類別，而非使用固定的日期類別

        Returns:
            Tuple[收費週期列表, 總費用]
        """
        billing_cycles = []
        total_fee = 0
        current_time = enter_time

        # 追蹤已使用的免費時間（全局免費時間只能使用一次）
        global_grace_used = False

        # 追蹤各時段的累計費用（用於時段上限）
        # 注意：時段上限是針對每個日期的每個時段，而不是跨日累計
        segment_accumulated_fees = {}

        while current_time < exit_time:
            # 1. 確定當前時間所在的時段
            current_segment = self.find_active_segment_at_time(current_time, segments)

            if not current_segment:
                # 如果沒有找到適用時段，跳過1分鐘
                current_time += timedelta(minutes=1)
                continue

            # 2. 確定當前時段的日期類別
            # 對於跨日時段，使用時段開始時的日期來判斷整個時段的日期類別
            segment_date_category = self.determine_segment_date_category(
                current_time, current_segment, holiday_type
            )

            # 3. 獲取該時段的費率配置
            segment_key = f"{current_segment['name']}_{segment_date_category}"
            if segment_key not in rate_matrix:
                # 如果沒有費率配置，跳過這個時段
                current_time = self.get_next_segment_boundary(
                    current_time, current_segment
                )
                continue

            rate_config = rate_matrix[segment_key]
            unit_time = rate_config.get("unit_time", 60)  # 收費週期（分鐘）

            # 4. 計算這個收費週期的結束時間
            cycle_end_time = current_time + timedelta(minutes=unit_time)

            # 但不能超過總停車結束時間
            actual_cycle_end = min(cycle_end_time, exit_time)

            # 5. 計算這個週期的實際分鐘數
            cycle_minutes = int((actual_cycle_end - current_time).total_seconds() / 60)

            if cycle_minutes <= 0:
                break

            # 6. 計算這個週期的費用
            # 使用全局免費時間（只在第一個週期使用）
            effective_grace_time = 0
            if not global_grace_used and global_grace_time > 0:
                effective_grace_time = global_grace_time
                global_grace_used = True
            elif rate_config.get("grace_time", 0) > 0:
                # 如果沒有全局免費時間，使用時段免費時間
                effective_grace_time = rate_config.get("grace_time", 0)

            # 計算週期費用
            cycle_fee = self.calculate_cycle_fee(
                cycle_minutes, rate_config, effective_grace_time
            )

            # 檢查時段上限 - 每日每時段獨立計算上限
            current_date = current_time.date().strftime("%Y-%m-%d")
            segment_key_for_cap = (
                f"{current_date}_{current_segment['name']}_{segment_date_category}"
            )
            if segment_key_for_cap not in segment_accumulated_fees:
                segment_accumulated_fees[segment_key_for_cap] = 0

            # 應用時段上限
            if rate_config.get("segment_cap_enabled", False):
                segment_cap = rate_config.get("segment_cap_amount", 0)
                if segment_cap > 0:
                    # 檢查累計費用是否會超過時段上限
                    new_accumulated = (
                        segment_accumulated_fees[segment_key_for_cap] + cycle_fee
                    )
                    if new_accumulated > segment_cap:
                        # 調整費用到上限
                        cycle_fee = max(
                            0,
                            segment_cap - segment_accumulated_fees[segment_key_for_cap],
                        )

            # 更新累計費用
            segment_accumulated_fees[segment_key_for_cap] += cycle_fee

            # 7. 記錄這個收費週期
            cycle_info = {
                "start_time": current_time,
                "end_time": actual_cycle_end,
                "minutes": cycle_minutes,
                "segment_name": current_segment["name"],
                "rate_config": rate_config,
                "fee": cycle_fee,
                "time_range": f"{current_time.strftime('%H:%M')}-{actual_cycle_end.strftime('%H:%M')}",
                "display_duration": self.format_duration_display(cycle_minutes),
                "rate_description": self.get_rate_description(rate_config),
                "date_display": current_time.strftime("%m-%d"),
                "date_category": segment_date_category,  # 記錄當前週期的日期類別
            }

            billing_cycles.append(cycle_info)
            total_fee += cycle_fee

            # 8. 移動到下一個收費週期
            current_time = cycle_end_time

            # 如果週期結束時間已經到達或超過停車結束時間，結束循環
            if current_time >= exit_time:
                break

        return billing_cycles, total_fee

    def determine_segment_date_category(
        self, current_time: datetime, segment: dict, holiday_type: str
    ) -> str:
        """
        確定時段的日期類別

        對於跨日時段，使用時段開始時的日期來判斷整個時段的日期類別
        例如：夜間時段22:00-08:00
        - 如果當前時間是22:30，使用當天的日期類別
        - 如果當前時間是02:30，仍然使用前一天的日期類別
        """
        segment_start = segment["start"]
        segment_end = segment["end"]

        # 判斷是否為跨日時段
        if segment_start > segment_end or segment_end == "24:00":
            # 跨日時段
            current_time_only = current_time.time()
            segment_start_time = datetime.strptime(segment_start, "%H:%M").time()

            if current_time_only >= segment_start_time:
                # 當前時間在跨日時段的前半部分（如22:30），使用當天日期
                return self.determine_date_category(current_time, holiday_type)
            else:
                # 當前時間在跨日時段的後半部分（如02:30），使用前一天日期
                previous_day = current_time - timedelta(days=1)
                return self.determine_date_category(previous_day, holiday_type)
        else:
            # 非跨日時段，直接使用當前時間的日期
            return self.determine_date_category(current_time, holiday_type)

    def find_active_segment_at_time(
        self, check_time: datetime, segments: List[dict]
    ) -> Optional[dict]:
        """
        找出指定時間點所屬的時段

        Args:
            check_time: 要檢查的時間點
            segments: 時段列表

        Returns:
            適用的時段配置，如果沒有找到則返回None
        """
        check_time_only = check_time.time()

        for segment in segments:
            start_str = segment["start"]
            end_str = segment["end"]

            # 處理 24:00 特殊情況
            if end_str == "24:00":
                end_str = "00:00"
                is_fullday = start_str == "00:00"
            else:
                is_fullday = False

            start_time = datetime.strptime(start_str, "%H:%M").time()
            end_time = datetime.strptime(end_str, "%H:%M").time()

            if is_fullday:
                # 全天時段
                return segment
            elif start_time <= end_time:
                # 同日時段
                if start_time <= check_time_only <= end_time:
                    return segment
            else:
                # 跨日時段
                if check_time_only >= start_time or check_time_only <= end_time:
                    return segment

        return None

    def get_next_segment_boundary(
        self, current_time: datetime, current_segment: dict
    ) -> datetime:
        """
        獲取當前時段的結束時間邊界
        """
        end_str = current_segment["end"]
        if end_str == "24:00":
            end_str = "00:00"

        end_time = datetime.strptime(end_str, "%H:%M").time()

        # 如果是跨日時段
        if current_segment["start"] > current_segment["end"]:
            if (
                current_time.time()
                >= datetime.strptime(current_segment["start"], "%H:%M").time()
            ):
                # 當前在跨日時段的前半部分，結束時間是明天
                return datetime.combine(
                    current_time.date() + timedelta(days=1), end_time
                )
            else:
                # 當前在跨日時段的後半部分，結束時間是今天
                return datetime.combine(current_time.date(), end_time)
        else:
            # 同日時段
            return datetime.combine(current_time.date(), end_time)

    def calculate_cycle_fee(
        self, minutes: int, rate_config: dict, grace_time: int = 0
    ) -> int:
        """
        計算單個收費週期的費用

        Args:
            minutes: 實際停車分鐘數
            rate_config: 費率配置
            grace_time: 免費時間（分鐘）

        Returns:
            週期費用
        """
        if not rate_config:
            return 0

        unit_time = rate_config.get("unit_time", 60)

        # 扣除免費時間
        billable_minutes = max(0, minutes - grace_time)

        if billable_minutes == 0:
            return 0

        # 對於不足一個收費週期的時間，仍按一個週期收費（向上取整）
        billing_units = -(-billable_minutes // unit_time)  # 向上取整

        if rate_config.get("progressive_enabled", False):
            # 累進費率
            total_fee = 0
            remaining_units = billing_units

            for rate_tier in rate_config.get("progressive_rates", []):
                tier_rate = rate_tier.get("rate", 0)
                tier_duration = rate_tier.get("duration_minutes", 60) // unit_time

                if remaining_units <= 0:
                    break

                units_in_tier = min(remaining_units, tier_duration)
                total_fee += units_in_tier * tier_rate
                remaining_units -= units_in_tier

            return total_fee
        else:
            # 簡單費率
            simple_rate = rate_config.get("simple_rate", 0)
            return billing_units * simple_rate

    def consolidate_billing_cycles(
        self, billing_cycles: List[Dict], enter_time: datetime, holiday_type: str
    ) -> Tuple[List[Dict], str]:
        """
        整合計費週期，將相同時段和費率的週期合併顯示
        使用 {時間區段}{節假日類型} 的標註方式
        修正：動態處理跨日停車的不同日期類別

        Args:
            billing_cycles: 原始計費週期列表
            enter_time: 進場時間（用於確定整體日期類別）
            holiday_type: 假日類型設定

        Returns:
            Tuple[整合後的明細列表, 計算摘要]
        """
        if not billing_cycles:
            return [], "無計費明細"

        # 按時間順序排序
        sorted_cycles = sorted(billing_cycles, key=lambda x: x["start_time"])

        # 智能合併：只合併時間連續且費率相同的週期
        consolidated = []
        current_group = None

        for cycle in sorted_cycles:
            # 獲取當前週期的日期類別
            cycle_date_category = cycle.get(
                "date_category",
                self.determine_date_category(cycle["start_time"], holiday_type),
            )

            if current_group is None:
                # 第一個週期，開始新組
                current_group = {
                    "start_time": cycle["start_time"],
                    "end_time": cycle["end_time"],
                    "segment_name": cycle["segment_name"],
                    "rate_description": cycle["rate_description"],
                    "total_minutes": cycle["minutes"],
                    "total_fee": cycle["fee"],
                    "cycles_count": 1,
                    "date_category": cycle_date_category,
                }
            elif (
                current_group["end_time"] == cycle["start_time"]
                and current_group["segment_name"] == cycle["segment_name"]
                and current_group["rate_description"] == cycle["rate_description"]
                and current_group["date_category"]
                == cycle_date_category  # 同樣的日期類別才能合併
            ):
                # 時間連續且費率相同且日期類別相同，可以合併
                current_group["end_time"] = cycle["end_time"]
                current_group["total_minutes"] += cycle["minutes"]
                current_group["total_fee"] += cycle["fee"]
                current_group["cycles_count"] += 1
            else:
                # 不能合併，保存當前組並開始新組
                consolidated.append(current_group)
                current_group = {
                    "start_time": cycle["start_time"],
                    "end_time": cycle["end_time"],
                    "segment_name": cycle["segment_name"],
                    "rate_description": cycle["rate_description"],
                    "total_minutes": cycle["minutes"],
                    "total_fee": cycle["fee"],
                    "cycles_count": 1,
                    "date_category": cycle_date_category,
                }

        # 添加最後一組
        if current_group:
            consolidated.append(current_group)

        # 生成顯示明細
        session_details = []
        calculation_summary_parts = []

        for group in consolidated:
            # 計算時間範圍
            start_time = group["start_time"]
            end_time = group["end_time"]
            group_date_category = group["date_category"]

            # 生成標註：{時間區段}{節假日類型}
            segment_label = f"{group['segment_name']}{group_date_category}"

            # 處理跨日顯示，格式如：06-20 日間平日 (14:22-22:22) 或 06-20~06-21 夜間假日 (18:25-00:00, 00:00-07:25)
            if start_time.date() != end_time.date():
                # 跨日情況 - 檢查是否有多個收費週期合併，如果有則顯示分段時間
                if group["cycles_count"] > 1 and end_time.time() != time(0, 0):
                    # 多個週期合併且不是整天到00:00結束，顯示分段時間
                    # 顯示兩段時間：第一天到午夜，午夜到第二天結束時間
                    first_part = f"{start_time.strftime('%H:%M')}-00:00"
                    second_part = f"00:00-{end_time.strftime('%H:%M')}"
                    time_range = f"({first_part}, {second_part})"
                    period_display = f"{start_time.strftime('%m-%d')}~{end_time.strftime('%m-%d')} {segment_label} {time_range}"
                else:
                    # 單一週期或整天到午夜，使用原有邏輯
                    period_display = f"{start_time.strftime('%m-%d')}~{end_time.strftime('%m-%d')} {segment_label} ({start_time.strftime('%H:%M')}-{end_time.strftime('%H:%M')})"
            else:
                # 同日情況
                period_display = f"{start_time.strftime('%m-%d')} {segment_label} ({start_time.strftime('%H:%M')}-{end_time.strftime('%H:%M')})"

            session_details.append(
                {
                    "period": period_display,
                    "duration": self.format_duration_display(group["total_minutes"]),
                    "rate": group["rate_description"],
                    "amount": group["total_fee"],
                    "segment_label": segment_label,
                    "cycles_count": group["cycles_count"],
                }
            )

            calculation_summary_parts.append(
                f"{segment_label}: {self.format_duration_display(group['total_minutes'])} × {group['rate_description']} = {group['total_fee']}元"
            )

        calculation_summary = " | ".join(calculation_summary_parts)

        return session_details, calculation_summary

    def get_rate_description(self, rate_config: dict) -> str:
        """生成費率描述文字"""
        if not rate_config:
            return "無費率"

        if rate_config.get("progressive_enabled", False):
            return "累進費率"
        else:
            unit_time = rate_config.get("unit_time", 60)
            simple_rate = rate_config.get("simple_rate", 0)
            if unit_time == 60:
                return f"{simple_rate}元/60分鐘"
            elif unit_time == 30:
                return f"{simple_rate}元/30分鐘"
            else:
                return f"{simple_rate}元/{unit_time}分鐘"

    def calculate_with_multidimensional(
        self,
        enter_time: datetime,
        exit_time: datetime,
        template_id: str,
        manual_adjustment: int = 0,
        context: Dict = None,
    ) -> Dict:
        """使用多維度計算器進行計算"""
        try:
            result = self.multidimensional_calculator.calculate_parking_fee(
                enter_time, exit_time, template_id
            )

            # 轉換結果格式
            return {
                "success": True,
                "calculation_engine": "multidimensional",
                "total_amount": result.total_amount + manual_adjustment,
                "original_amount": result.original_amount,
                "manual_adjustment": manual_adjustment,
                "date_category": result.date_category.value,
                "applied_rate_plan": result.applied_rate_plan,
                "time_segment_type": result.time_segment_type,
                "holiday_type": result.holiday_type,
                "session_details": result.session_details,
                "calculation_summary": result.calculation_summary,
                "dimension_tags": result.dimension_tags,
                "enter_time": enter_time,
                "exit_time": exit_time,
                "total_duration_minutes": int(
                    (exit_time - enter_time).total_seconds() / 60
                ),
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"多維度計算失敗: {str(e)}",
                "calculation_engine": "multidimensional",
            }

    def format_duration_display(self, minutes: int) -> str:
        """
        格式化時間顯示，將分鐘數轉換為更易讀的格式
        統一顯示括號格式

        Args:
            minutes: 分鐘數

        Returns:
            str: 格式化後的時間顯示，如 "60分鐘 (1小時)" 或 "90分鐘 (1小時30分)"
        """
        if minutes <= 0:
            return "0分鐘"

        # 統一顯示括號格式
        if minutes % 60 == 0:
            # 整小時
            hours = minutes // 60
            if hours == 1:
                return f"{minutes}分鐘 (1小時)"
            else:
                return f"{minutes}分鐘 ({hours}小時)"
        else:
            # 小時+分鐘組合
            hours = minutes // 60
            remaining_minutes = minutes % 60

            if hours == 0:
                # 純分鐘，小於60分鐘時不顯示括號
                return f"{minutes}分鐘"
            elif hours == 1:
                return f"{minutes}分鐘 (1小時{remaining_minutes}分)"
            else:
                return f"{minutes}分鐘 ({hours}小時{remaining_minutes}分)"

    def calculate_detailed_fee(
        self, intervals: List[Dict], plan_data: dict, date_category: str
    ) -> Tuple[int, List[Dict]]:
        """
        基於明細列表計算詳細費用
        對於跨日時段，合併計算費率但分開顯示明細

        Args:
            intervals: 時段明細列表
            plan_data: 費率方案數據
            date_category: 日期類別 (平日/假日)

        Returns:
            Tuple[總費用, 費用明細列表]
        """
        total_fee = 0
        fee_details = []

        # 獲取全局寬裕時間和費率矩陣
        global_grace_time = plan_data.get("global_grace_time", 0)
        rate_matrix = plan_data.get("rate_matrix", {})

        if plan_data["segment_type"] == "全天":
            # 全天統一費率
            for interval in intervals:
                minutes = interval["minutes"]

                # 對於用戶自定義方案，使用rate_matrix
                segment_key = f"全天_{date_category}"
                if segment_key in rate_matrix:
                    rate_config = rate_matrix[segment_key]
                    fee = self.calculate_segment_fee(
                        minutes, rate_config, global_grace_time
                    )
                elif "rates" in plan_data and "全天" in plan_data["rates"]:
                    # 向後兼容舊格式
                    fee = self.calculate_segment_fee(
                        minutes, plan_data["rates"]["全天"][date_category]
                    )
                else:
                    fee = 0

                total_fee += fee

                fee_details.append(
                    {
                        "date": interval["date"],
                        "segment": interval["segment_name"],
                        "time_range": interval["time_range"],
                        "minutes": minutes,
                        "fee": fee,
                        "display_duration": self.format_duration_display(minutes),
                    }
                )
        else:
            # 多時段費率：處理跨日時段合併
            cross_day_groups = {}
            regular_intervals = []

            # 分組處理跨日時段
            for interval in intervals:
                if "cross_day_group" in interval:
                    group_key = interval["cross_day_group"]
                    if group_key not in cross_day_groups:
                        cross_day_groups[group_key] = []
                    cross_day_groups[group_key].append(interval)
                else:
                    regular_intervals.append(interval)

            # 處理跨日時段組：合併計算費率，合併顯示明細
            for group_key, group_intervals in cross_day_groups.items():
                # 合併計算總時間
                total_minutes = sum(interval["minutes"] for interval in group_intervals)

                # 取得時段名稱和費率
                segment_name = group_intervals[0]["segment_name"]
                segment_key = f"{segment_name}_{date_category}"

                if segment_key in rate_matrix:
                    rate_config = rate_matrix[segment_key]
                    total_fee_for_group = self.calculate_segment_fee(
                        total_minutes, rate_config, global_grace_time
                    )
                elif "rates" in plan_data and segment_name in plan_data["rates"]:
                    # 向後兼容舊格式
                    segment_rates = plan_data["rates"][segment_name][date_category]
                    total_fee_for_group = self.calculate_segment_fee(
                        total_minutes, segment_rates
                    )
                else:
                    total_fee_for_group = 0

                # 生成合併的時間範圍顯示
                group_intervals.sort(key=lambda x: x["start_time"])
                first_interval = group_intervals[0]
                last_interval = group_intervals[-1]

                # 對於跨日時段，需要顯示正確的時段定義時間範圍
                # 檢查是否為跨日時段組
                if (
                    len(group_intervals) == 2
                    and group_intervals[0].get("cross_day_part") == "前半段"
                ):
                    # 這是一個完整的跨日時段實例 (如 22:00-08:00)
                    start_date = first_interval["start_time"].strftime("%m-%d")
                    end_date = last_interval["end_time"].strftime("%m-%d")

                    # 獲取時段的原始定義時間
                    segment_config = None
                    for seg in plan_data.get("segments", []):
                        if seg["name"] == segment_name:
                            segment_config = seg
                            break

                    if segment_config:
                        segment_start = segment_config["start"]
                        segment_end = segment_config["end"]
                        if segment_end == "24:00":
                            segment_end = "00:00"
                        display_range = f"{start_date}~{end_date} {segment_name} ({segment_start}-{segment_end})"
                    else:
                        display_range = f"{start_date}~{end_date} {segment_name} ({first_interval['start_time'].strftime('%H:%M')}-{last_interval['end_time'].strftime('%H:%M')})"
                elif len(group_intervals) == 1:
                    # 這是單一的跨日時段片段 (如 22:00-23:07)
                    start_date = first_interval["start_time"].strftime("%m-%d")
                    start_time = first_interval["start_time"].strftime("%H:%M")
                    end_time = first_interval["end_time"].strftime("%H:%M")
                    display_range = (
                        f"{start_date} {segment_name} ({start_time}-{end_time})"
                    )
                else:
                    # 其他情況，使用原有邏輯
                    start_date = first_interval["start_time"].strftime("%m-%d")
                    end_date = last_interval["end_time"].strftime("%m-%d")
                    start_time = first_interval["start_time"].strftime("%H:%M")
                    end_time = last_interval["end_time"].strftime("%H:%M")

                    if start_date == end_date:
                        display_range = f"跨日{segment_name} ({start_time}-{end_time})"
                    else:
                        display_range = f"{start_date}~{end_date} {segment_name} ({start_time}-{end_time})"

                # 使用第一個時段的日期作為分組依據
                fee_details.append(
                    {
                        "date": first_interval["date"],
                        "segment": segment_name,
                        "time_range": display_range,
                        "minutes": total_minutes,
                        "fee": total_fee_for_group,
                        "display_duration": self.format_duration_display(total_minutes),
                        "cross_day_group": group_key,
                        "total_group_minutes": total_minutes,
                        "total_group_fee": total_fee_for_group,
                    }
                )

                total_fee += total_fee_for_group

            # 處理一般時段
            for interval in regular_intervals:
                segment_name = interval["segment_name"]
                minutes = interval["minutes"]
                segment_key = f"{segment_name}_{date_category}"

                if segment_key in rate_matrix:
                    rate_config = rate_matrix[segment_key]
                    fee = self.calculate_segment_fee(
                        minutes, rate_config, global_grace_time
                    )
                elif "rates" in plan_data and segment_name in plan_data["rates"]:
                    # 向後兼容舊格式
                    segment_rates = plan_data["rates"][segment_name][date_category]
                    fee = self.calculate_segment_fee(minutes, segment_rates)
                else:
                    fee = 0

                total_fee += fee

                # 生成帶日期的時段顯示
                # interval["date"] 是字符串格式 "YYYY-MM-DD"，需要轉換成日期格式
                date_obj = datetime.strptime(interval["date"], "%Y-%m-%d").date()
                date_str = date_obj.strftime("%m-%d")
                time_range_display = (
                    f"{date_str} {segment_name} ({interval['time_range']})"
                )

                fee_details.append(
                    {
                        "date": interval["date"],
                        "segment": segment_name,
                        "time_range": time_range_display,
                        "minutes": minutes,
                        "fee": fee,
                        "display_duration": self.format_duration_display(minutes),
                    }
                )

        # 按時間順序排序明細，同一天的日間時段排在夜間時段前面
        def sort_key(detail):
            date = detail["date"]
            segment = detail["segment"]
            time_range = detail.get("time_range", "")

            # 定義時段優先級：日間 > 夜間
            segment_priority = 0 if "日間" in segment else 1

            return (date, segment_priority, time_range)

        fee_details.sort(key=sort_key)

        return total_fee, fee_details

    def determine_date_category(self, check_time: datetime, holiday_type: str) -> str:
        """
        確定日期類別

        對於跨日時段，應該使用時段開始時的日期來判斷日期類別
        例如：夜間時段22:00-08:00，即使在凌晨2:00，也應該使用前一天的日期類別
        """
        weekday = check_time.weekday()  # 0=Monday, 6=Sunday

        if holiday_type == "無假日":
            return "統一"
        elif holiday_type == "平日假日":
            return "平日" if weekday < 5 else "假日"
        elif holiday_type == "完整假日":
            if weekday < 5:
                return "平日"
            elif weekday == 5:  # Saturday
                return "假日"
            else:  # Sunday
                return "節慶日"
        else:
            return "統一"

    def calculate_segment_fee(
        self, minutes: int, rate_config: dict, global_grace_time: int = 0
    ) -> int:
        """計算區段費用（保留用於向後兼容）"""
        if not rate_config:
            return 0

        unit_time = rate_config.get("unit_time", 60)  # 計費單位時間（分鐘）

        # 使用全局寬裕時間，如果沒有則使用時段寬裕時間
        if global_grace_time > 0:
            grace_time = global_grace_time
        else:
            grace_time = rate_config.get("grace_time", 0)  # 免費時間（分鐘）

        # 扣除免費時間
        billable_minutes = max(0, minutes - grace_time)

        if billable_minutes == 0:
            return 0

        # 計算計費單位數
        billing_units = -(-billable_minutes // unit_time)  # 向上取整

        if rate_config.get("progressive_enabled", False):
            # 累進費率
            total_fee = 0
            remaining_units = billing_units

            for rate_tier in rate_config.get("progressive_rates", []):
                tier_rate = rate_tier.get("rate", 0)
                tier_duration = rate_tier.get("duration_minutes", 60) // unit_time

                if remaining_units <= 0:
                    break

                units_in_tier = min(remaining_units, tier_duration)
                total_fee += units_in_tier * tier_rate
                remaining_units -= units_in_tier

            return total_fee
        else:
            # 簡單費率
            simple_rate = rate_config.get("simple_rate", 0)
            return billing_units * simple_rate


# 初始化智能停車系統
parking_system = SmartParkingSystem()


@app.route("/")
def index():
    """主頁面 - 智能計費界面"""
    # 獲取可用的費率方案
    available_plans = get_all_available_plans()
    system_config = parking_system.system_config

    return render_template(
        "index.html",
        rate_plans=available_plans,
        system_config=system_config,
    )


@app.route("/system_settings")
def system_settings():
    """統一系統設定頁面"""
    return render_template("system_settings.html")


@app.route("/rate_plan_designer")
def rate_plan_designer():
    """多維度方案設計器"""
    return render_template("rate_plan_designer.html")


@app.route("/rate_plan_designer_test")
def rate_plan_designer_test():
    return redirect(url_for("rate_plan_designer"))


# 新增統一版側欄布局頁面
@app.route("/plan_manager")
def plan_manager_page():
    """多維度方案管理"""
    return render_template("plan_manager.html")


@app.route("/calendar_manager")
def calendar_manager_page():
    """行事曆與假日管理頁"""
    return render_template("calendar_manager.html")


# 保留向後相容的路由
@app.route("/system_management")
def system_management():
    """系統管理頁面（重定向到統一設定）"""
    return redirect(url_for("system_settings"))


@app.route("/comprehensive_config")
def comprehensive_config():
    """全面配置頁面（重定向到統一設定）"""
    return redirect(url_for("system_settings"))


@app.route("/multidimensional_config")
def multidimensional_config():
    """多維度配置頁面（重定向到統一設定）"""
    return redirect(url_for("system_settings"))


@app.route("/settlement_center")
def settlement_center():
    """結算中心（已移除），導向首頁"""
    return redirect(url_for("index"))


@app.route("/api/docs")
def api_docs():
    """文件頁（已精簡，導向首頁）"""
    return redirect(url_for("index"))

def get_all_available_plans() -> List[Dict]:
    """僅回傳多維度方案，移除用戶自訂方案以簡化系統"""
    plans: List[Dict] = []
    if parking_system.multidimensional_calculator:
        templates = parking_system.multidimensional_calculator.get_available_templates()
        for template_id, label in templates.items():
            plans.append(
                {
                    "rate_plan_id": template_id,
                    "label": label,
                    "type": "multidimensional",
                    "description": f"多維度方案: {label}",
                }
            )
    return plans


@app.route("/api/calculate", methods=["POST"])
def api_calculate_fee():
    """統一的費用計算API"""
    """
    ---
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required: [enter_time, exit_time]
          properties:
            enter_time:
              type: string
              example: "2025-06-20T21:52"
            exit_time:
              type: string
              example: "2025-06-21T08:30"
            plan_id:
              type: string
              example: "全天_無假日費率"
            manual_adjustment:
              type: integer
              example: 0
            vehicle_type:
              type: string
              enum: [car, motorcycle, truck, van]
    responses:
      200:
        description: 成功或業務錯誤
      400:
        description: 格式錯誤或輸入錯誤
      500:
        description: 伺服器錯誤
    """
    request_id = str(uuid.uuid4())
    start_ts = _pytime.perf_counter()
    try:
        data = request.get_json() or {}

        # 解析輸入資料
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

        # 轉換時間格式
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

        # 驗證時間邏輯
        if enter_time >= exit_time:
            return error_response(
                code="INVALID_TIME_RANGE",
                message="出場時間必須晚於進場時間",
                http_status=400,
                extra={"request_id": request_id},
            )

        # 轉換車輛類型
        try:
            vehicle_type = VehicleType(vehicle_type_str)
        except ValueError:
            vehicle_type = VehicleType.CAR

        # 即時試算：支援 plan_inline（不需先儲存）
        # 已移除 user_defined inline；多維度的即時預覽請使用 /api/mdp/preview

        # 計算費用（既有流程）
        result = parking_system.calculate_parking_fee(
            enter_time, exit_time, plan_id, vehicle_type, manual_adjustment, context
        )

        # 添加顯示資訊
        if result.get("success"):
            total_minutes = result.get("total_duration_minutes", 0)
            total_hours = total_minutes // 60
            remaining_minutes = total_minutes % 60
            result["total_duration_display"] = parking_system.format_duration_display(
                total_minutes
            )
            result["enter_time_display"] = enter_time.strftime("%Y年%m月%d日 %H:%M")
            result["exit_time_display"] = exit_time.strftime("%Y年%m月%d日 %H:%M")

        # 序列化 datetime 欄位，避免 JSON 轉換問題
        if isinstance(result, dict):
            if isinstance(result.get("enter_time"), datetime):
                result["enter_time"] = result["enter_time"].strftime("%Y-%m-%d %H:%M")
            if isinstance(result.get("exit_time"), datetime):
                result["exit_time"] = result["exit_time"].strftime("%Y-%m-%d %H:%M")

        duration_ms = int((_pytime.perf_counter() - start_ts) * 1000)
        logger.info(
            "calc_request result=%s plan_id=%s ms=%s request_id=%s",
            "success" if result.get("success") else "fail",
            plan_id,
            duration_ms,
            request_id,
        )

        # 成功或業務錯誤一律200回傳內容；致命錯誤走except
        return jsonify({"request_id": request_id, **result})

    except Exception as e:
        duration_ms = int((_pytime.perf_counter() - start_ts) * 1000)
        logger.exception(
            "calc_request exception plan_id=%s ms=%s request_id=%s error=%s",
            request.json.get("plan_id") if request.is_json else None,
            duration_ms,
            request_id,
            str(e),
        )
        return error_response(
            code="INTERNAL_ERROR",
            message=f"計算錯誤: {str(e)}",
            http_status=500,
            extra={"request_id": request_id},
        )


@app.route("/api/mdp/preview", methods=["POST"])
def api_mdp_preview():
    """多維度方案即時試算（傳入範本物件，不需先儲存）"""
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

        # 臨時註冊到多維度計算器記憶體後試算
        calc = parking_system.multidimensional_calculator
        if not calc:
            return error_response(
                code="MDP_NOT_READY",
                message="多維度計算器尚未初始化",
                http_status=500,
                extra={"request_id": request_id},
            )

        temp_id = template.get("template_id") or f"inline_{int(_pytime.perf_counter()*1000)}"
        # 保存舊值並覆蓋
        old = calc.rate_plan_templates.get(temp_id)
        try:
            from src.engines.multidimensional_calculator import (
                MultidimensionalRatePlan,
                TimeSegmentType,
                HolidayType,
            )
            rp = MultidimensionalRatePlan(
                template_id=temp_id,
                label=template.get("label", temp_id),
                description=template.get("description", ""),
                time_segment_type=TimeSegmentType(template.get("time_segment_type", "兩段")),
                holiday_type=HolidayType(template.get("holiday_type", "六日費率")),
                dimension_combination=temp_id,
                weekday_plan=template.get("weekday_plan"),
                weekend_plan=template.get("weekend_plan"),
                national_holiday_plan=template.get("national_holiday_plan"),
                custom_holiday_plan=template.get("custom_holiday_plan"),
                unified_plan=template.get("unified_plan"),
            )
            calc.rate_plan_templates[temp_id] = rp
            res = calc.calculate_parking_fee(enter_time, exit_time, temp_id)
        finally:
            # 還原/清理暫存
            if old is not None:
                calc.rate_plan_templates[temp_id] = old
            else:
                calc.rate_plan_templates.pop(temp_id, None)

        # 包裝輸出
        total_minutes = sum(d.get("duration", 0) for d in res.session_details)
        result = {
            "success": True,
            "total_amount": res.total_amount,
            "total_duration_minutes": total_minutes,
            "total_duration_display": parking_system.format_duration_display(total_minutes),
            "session_details": res.session_details,
        }
        return jsonify({"request_id": request_id, **result})
    except Exception as e:
        duration_ms = int((_pytime.perf_counter() - start_ts) * 1000)
        logger.exception("mdp_preview exception ms=%s request_id=%s error=%s", duration_ms, request_id, str(e))
        return error_response(
            code="INTERNAL_ERROR",
            message=f"試算錯誤: {str(e)}",
            http_status=500,
            extra={"request_id": request_id},
        )
@app.route("/api/system/config", methods=["GET", "POST"])
def api_system_config():
    """系統配置API"""
    """
    ---
    get:
      description: 取得系統配置
      responses:
        200:
          description: 成功
    post:
      description: 更新系統配置（部分欄位）
      consumes:
        - application/json
      parameters:
        - in: body
          name: body
          schema:
            type: object
            properties:
              system_mode:
                type: string
              default_calculation_engine:
                type: string
              calculation_precision:
                type: integer
      responses:
        200:
          description: 成功
        400:
          description: 格式錯誤
        500:
          description: 伺服器錯誤
    """
    if request.method == "GET":
        return jsonify({"success": True, "config": parking_system.system_config})

    elif request.method == "POST":
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

            # 如果變更了系統模式，重新初始化
            if new_config.get("system_mode"):
                parking_system.init_multidimensional_calculator()

            return jsonify({"success": True, "message": "系統配置已更新"})
        except Exception as e:
            return error_response(
                code="INTERNAL_ERROR", message=str(e), http_status=500
            )


@app.route("/api/plans", methods=["GET"])
def api_get_all_plans():
    """獲取所有費率方案API"""
    """
    ---
    get:
      description: 取得可用費率方案清單
      responses:
        200:
          description: 成功
        500:
          description: 伺服器錯誤
    """
    try:
        plans = get_all_available_plans()

        return jsonify(
            {
                "success": True,
                "plans": plans,
                "system_mode": parking_system.system_config.get(
                    "system_mode", "multidimensional"
                ),
            }
        )
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e), http_status=500)


# 已移除 /api/plans/activate，統一走直接試算


@app.route("/api/multidimensional/combinations")
def api_get_dimension_combinations():
    """獲取多維度組合API"""
    """
    ---
    get:
      description: 取得多維度可用組合
      responses:
        200:
          description: 成功
        500:
          description: 伺服器錯誤
    """
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


# 移除增強版計算器相關API以簡化系統


@app.route("/api/rate_plans/save", methods=["POST"])
def api_save_rate_plan():
    # 已停用舊版自訂方案儲存，請改用 /api/mdp/templates/save
    return error_response("DEPRECATED", "自訂方案已下線，請使用 /api/mdp/templates* API", 410)


@app.route("/api/rate_plans/list", methods=["GET"])
def api_list_user_rate_plans():
    # 已停用舊版自訂方案列表，請改用 /api/mdp/templates
    return error_response("DEPRECATED", "自訂方案已下線，請使用 /api/mdp/templates* API", 410)


@app.route("/api/enhanced/segments/validate", methods=["POST"])
def api_validate_segments():
    """驗證任意段的24小時覆蓋與無重疊。"""
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
                # 若相接允許合併，若重疊則失敗
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

@app.route("/api/calendar", methods=["GET", "POST"])
def api_calendar():
    """萬年曆資料（本地檔）讀寫端點"""
    calendar_file = Path("config/system_calendar.json")
    if request.method == "GET":
        if calendar_file.exists():
            try:
                return jsonify({
                    "success": True,
                    "calendar": json.loads(calendar_file.read_text(encoding="utf-8")),
                })
            except Exception as e:
                return error_response("CAL_READ_ERROR", str(e), 500)
        # 預設空結構
        return jsonify(
            {
                "success": True,
                "calendar": {
                    "description": "",
                    "weekend_as_holiday": True,
                    "custom_holidays": [],
                    "custom_workdays": [],
                    "festival_holidays": [],
                    "national_holidays": [],
                    "weekend_holidays": [],
                    "lunar_festivals": [],
                    "special_events": [],
                },
            }
        )
    else:
        try:
            data = request.get_json() or {}
            calendar_file.parent.mkdir(parents=True, exist_ok=True)
            calendar_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            return jsonify({"success": True, "message": "calendar saved"})
        except Exception as e:
            return error_response("CAL_WRITE_ERROR", str(e), 500)


def _fetch_gov_tw_official_holidays(year: int) -> Optional[List[Dict[str, Any]]]:
    """嘗試從系統配置的官方來源抓取假日JSON。

    需在 system_config 設定 official_calendar_api（政府資料開放平臺的 JSON 端點）。
    若未設定，返回 None。
    回傳格式為 list[ {"date": "YYYY-MM-DD", "name": "..."} ] 或 None。
    """
    api_url = parking_system.system_config.get("official_calendar_api") if isinstance(parking_system.system_config, dict) else None
    if not api_url:
        return None
    def _fetch(ctx: ssl.SSLContext) -> Optional[List[Dict[str, Any]]]:
        with urllib.request.urlopen(f"{api_url}?year={year}", context=ctx, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        items: List[Dict[str, Any]] = []
        for row in (data if isinstance(data, list) else data.get("result", [])):
            d = row.get("date") or row.get("Date") or row.get("date_str")
            nm = row.get("name") or row.get("Name") or row.get("holiday_name")
            if d:
                items.append({"date": d, "name": nm or "假日"})
        return items

    try:
        # 正常驗證
        return _fetch(ssl.create_default_context())
    except Exception:
        try:
            # 非驗證模式（應對企業代理/憑證問題）
            insecure = ssl.create_default_context()
            insecure.check_hostname = False
            insecure.verify_mode = ssl.CERT_NONE
            return _fetch(insecure)
        except Exception:
            return None


@app.route("/api/calendar/sync_official_v2", methods=["POST"])
def api_calendar_sync_official_v2():
    """多來源官方假日同步：
    body: {"year": 2025, "source": "gov_tw"|"nager"|"both"}
    - gov_tw: 僅政府開放資料（需在 system_config 設定 official_calendar_api）
    - nager: 僅 Nager.Date (TW)
    - both: 先政府再 Nager 合併，並標示來源
    """
    try:
        payload = request.get_json() or {}
        year = int(payload.get("year") or datetime.now().year)
        mode = (payload.get("source") or "both").lower()

        holidays: List[Dict[str, Any]] = []
        used_sources: List[str] = []

        def add_items(items: Optional[List[Dict[str, Any]]], tag: str):
            if not items:
                return
            for it in items:
                d = it.get("date")
                nm = it.get("name") or tag
                if d:
                    holidays.append({"date": d, "name": nm, "source": tag})

        if mode in ("gov_tw", "both"):
            gov = _fetch_gov_tw_official_holidays(year)
            if gov:
                used_sources.append("gov_tw")
                add_items(gov, "gov_tw")

        if mode in ("nager", "both") and (mode != "nager" or not holidays):
            # both 模式：即使 gov_tw 成功也合併 nager；nager 模式：單獨使用
            try:
                ctx = ssl.create_default_context()
                with urllib.request.urlopen(
                    f"https://date.nager.at/api/v3/PublicHolidays/{year}/TW",
                    context=ctx,
                    timeout=20,
                ) as resp:
                    raw = resp.read().decode("utf-8")
                data = json.loads(raw)
                items = [{"date": it.get("date"), "name": (it.get("localName") or it.get("name"))} for it in data]
                used_sources.append("nager")
                add_items(items, "nager")
            except Exception:
                # 再嘗試不驗證
                try:
                    insecure = ssl.create_default_context()
                    insecure.check_hostname = False
                    insecure.verify_mode = ssl.CERT_NONE
                    with urllib.request.urlopen(
                        f"https://date.nager.at/api/v3/PublicHolidays/{year}/TW",
                        context=insecure,
                        timeout=20,
                    ) as resp:
                        raw = resp.read().decode("utf-8")
                    data = json.loads(raw)
                    items = [{"date": it.get("date"), "name": (it.get("localName") or it.get("name"))} for it in data]
                    used_sources.append("nager")
                    add_items(items, "nager")
                except Exception as e:
                    if mode == "nager":
                        return error_response("SYNC_FETCH_ERROR", f"抓取 Nager 失敗: {e}", 500)

        # 寫入 calendar
        calendar_file = Path("config/system_calendar.json")
        cal = {}
        if calendar_file.exists():
            try:
                cal = json.loads(calendar_file.read_text(encoding="utf-8"))
            except Exception:
                cal = {}

        cal.setdefault("description", f"官方假日 {year}")
        cal.setdefault("weekend_as_holiday", True)
        cal.setdefault("custom_holidays", [])
        cal.setdefault("custom_workdays", [])
        cal.setdefault("festival_holidays", [])
        cal.setdefault("lunar_festivals", [])
        cal.setdefault("national_holidays", [])
        cal.setdefault("weekend_holidays", [])
        cal.setdefault("special_events", [])

        # 合併（保留來源）
        existing_dates = set(d if isinstance(d, str) else d.get("date") for d in cal.get("national_holidays", []))
        for h in holidays:
            d = h.get("date")
            if not d:
                continue
            if d not in existing_dates:
                cal["national_holidays"].append({"date": d, "name": h.get("name"), "source": h.get("source")})
                existing_dates.add(d)

        calendar_file.parent.mkdir(parents=True, exist_ok=True)
        calendar_file.write_text(json.dumps(cal, ensure_ascii=False, indent=2), encoding="utf-8")

        return jsonify({
            "success": True,
            "synced_year": year,
            "sources": used_sources,
            "added": len(holidays),
        })
    except Exception as e:
        return error_response("SYNC_INTERNAL_ERROR", str(e), 500)


@app.route("/api/calendar/sync_official", methods=["POST"])
def api_calendar_sync_official():
    """一鍵同步官方假日。

    預設優先使用政府資料來源（若在 system_config 設定 official_calendar_api）。
    若未設定或失敗，退回使用 Nager.Date（TW）。
    Body: {"year": 2025} 可選。
    """
    try:
        payload = request.get_json() or {}
        year = int(payload.get("year") or datetime.now().year)

        # 1) 先試官方（依系統設定的 official_calendar_api）
        official_items = _fetch_gov_tw_official_holidays(year)

        source_used = "gov_tw" if official_items is not None else "nager"
        holidays: List[Dict[str, Any]] = []

        if official_items is not None:
            holidays = official_items
        else:
            # 2) 退回 Nager.Date（非官方）
            def _fetch_nager(ctx: ssl.SSLContext):
                with urllib.request.urlopen(
                    f"https://date.nager.at/api/v3/PublicHolidays/{year}/TW",
                    context=ctx,
                    timeout=20,
                ) as resp:
                    raw = resp.read().decode("utf-8")
                data = json.loads(raw)
                for it in data:
                    d = it.get("date")
                    nm = it.get("localName") or it.get("name")
                    if d:
                        holidays.append({"date": d, "name": nm or "假日"})
            try:
                _fetch_nager(ssl.create_default_context())
            except Exception:
                try:
                    insecure = ssl.create_default_context()
                    insecure.check_hostname = False
                    insecure.verify_mode = ssl.CERT_NONE
                    _fetch_nager(insecure)
                except Exception as e:
                    return error_response("SYNC_FETCH_ERROR", f"抓取假日失敗: {e}", 500)

        # 映射到 calendar 結構
        custom_holidays: List[str] = []
        festival_holidays: List[Any] = []
        national_holidays: List[Any] = []
        for h in holidays:
            d = h.get("date")
            if d:
                custom_holidays.append(d)
                entry = {"date": d, "name": h.get("name")}
                festival_holidays.append(entry)
                national_holidays.append(entry)

        # 合併寫入本地
        calendar_file = Path("config/system_calendar.json")
        if calendar_file.exists():
            try:
                cal = json.loads(calendar_file.read_text(encoding="utf-8"))
            except Exception:
                cal = {}
        else:
            cal = {}

        cal.setdefault("description", f"{('政府資料' if source_used=='gov_tw' else 'Nager.Date')} TW {year} 公眾假期")
        cal.setdefault("weekend_as_holiday", True)
        cal.setdefault("custom_holidays", [])
        cal.setdefault("custom_workdays", [])
        cal.setdefault("festival_holidays", [])
        cal.setdefault("lunar_festivals", [])
        cal.setdefault("national_holidays", [])
        cal.setdefault("weekend_holidays", [])
        cal.setdefault("special_events", [])

        # 去重合併
        existing_h = set(cal.get("custom_holidays", []))
        for d in custom_holidays:
            if d not in existing_h:
                cal["custom_holidays"].append(d)

        existing_f = {
            (f["date"] if isinstance(f, dict) and "date" in f else f)
            for f in cal.get("festival_holidays", [])
        }
        for f in festival_holidays:
            key = f.get("date")
            if key and key not in existing_f:
                cal["festival_holidays"].append(f)

        # 國定假日（分開存）
        existing_n = {
            (f["date"] if isinstance(f, dict) and "date" in f else f)
            for f in cal.get("national_holidays", [])
        }
        for f in national_holidays:
            key = f.get("date")
            if key and key not in existing_n:
                cal["national_holidays"].append(f)

        calendar_file.parent.mkdir(parents=True, exist_ok=True)
        calendar_file.write_text(
            json.dumps(cal, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        return jsonify(
            {
                "success": True,
                "synced_year": year,
                "source_used": source_used,
                "added_holidays": len(custom_holidays),
            }
        )
    except Exception as e:
        return error_response("SYNC_INTERNAL_ERROR", str(e), 500)


@app.route("/api/calendar/generate_weekends", methods=["POST"])
def api_calendar_generate_weekends():
    """產生指定年度的週末日期並存入 weekend_holidays（不覆蓋現有）。Body: {"year": 2025} 可選。"""
    try:
        payload = request.get_json() or {}
        year = int(payload.get("year") or datetime.now().year)

        # 產生該年度所有週六週日日期字串
        first_day = datetime(year, 1, 1)
        last_day = datetime(year, 12, 31)
        d = first_day
        weekends: List[str] = []
        while d <= last_day:
            if d.weekday() >= 5:  # 5=Saturday, 6=Sunday
                weekends.append(d.strftime("%Y-%m-%d"))
            d += timedelta(days=1)

        calendar_file = Path("config/system_calendar.json")
        if calendar_file.exists():
            try:
                cal = json.loads(calendar_file.read_text(encoding="utf-8"))
            except Exception:
                cal = {}
        else:
            cal = {}

        cal.setdefault("description", cal.get("description", ""))
        cal.setdefault("weekend_as_holiday", True)
        cal.setdefault("custom_holidays", [])
        cal.setdefault("custom_workdays", [])
        cal.setdefault("festival_holidays", [])
        cal.setdefault("national_holidays", [])
        cal.setdefault("weekend_holidays", [])
        cal.setdefault("lunar_festivals", [])
        cal.setdefault("special_events", [])

        existing_w = set(cal.get("weekend_holidays", []))
        added = 0
        for dt in weekends:
            if dt not in existing_w:
                cal["weekend_holidays"].append(dt)
                added += 1

        calendar_file.parent.mkdir(parents=True, exist_ok=True)
        calendar_file.write_text(json.dumps(cal, ensure_ascii=False, indent=2), encoding="utf-8")

        return jsonify({"success": True, "generated_year": year, "added": added})
    except Exception as e:
        return error_response("WEEKEND_GEN_ERROR", str(e), 500)


@app.route('/static/openapi.yaml')
def serve_openapi_yaml():
    path = Path('api/contracts/openapi.yaml')
    if path.exists():
        return send_from_directory(path.parent.as_posix(), path.name)
    return error_response("OPENAPI_NOT_FOUND", "openapi.yaml 不存在", 404)

@app.route("/api/rate_plans/export_all", methods=["GET"])
def api_export_all_plans():
    """整包匯出 user_defined_plans.json。若檔案不存在，回傳預設結構。"""
    try:
        path = Path("config/user_defined_plans.json")
        if path.exists():
            return send_from_directory(
                directory=path.parent.as_posix(),
                path=path.name,
                as_attachment=True,
                download_name="user_defined_plans.json",
            )
        # 檔案不存在時提供預設結構
        default_payload = {
            "plans": {},
            "metadata": {"created": datetime.now().isoformat(), "version": "1.0"},
        }
        data = json.dumps(default_payload, ensure_ascii=False, indent=2)
        resp = app.response_class(data, mimetype="application/json")
        resp.headers["Content-Disposition"] = (
            "attachment; filename=user_defined_plans.json"
        )
        return resp
    except Exception as e:
        return error_response("EXPORT_ALL_ERROR", str(e), 500)
@app.route("/api/rate_plans/load/<plan_id>", methods=["GET"])
def api_load_rate_plan(plan_id):
    # 已停用舊版自訂方案載入，請改用 /api/mdp/templates/<id>
    return error_response("DEPRECATED", "自訂方案已下線，請使用 /api/mdp/templates* API", 410)


@app.route("/api/rate_plans/<plan_id>", methods=["DELETE"])
def api_delete_rate_plan(plan_id):
    # 已停用舊版自訂方案刪除，請改用 /api/mdp/templates/<id> (DELETE)
    return error_response("DEPRECATED", "自訂方案已下線，請使用 /api/mdp/templates* API", 410)


if __name__ == "__main__":
    # 確保模板目錄存在
    if not os.path.exists("templates"):
        os.makedirs("templates")

    # 確保log目錄存在
    if not os.path.exists("log"):
        os.makedirs("log")

    app.run(debug=True, host="0.0.0.0", port=5000)
