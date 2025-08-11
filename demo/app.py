#!/usr/bin/env python3
"""
停車費計算系統 - 精簡版
專注於核心功能：準確的跨日停車費計算
"""

from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta
import json
import os
from typing import Dict, List, Tuple, Optional

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False


class ParkingCalculator:
    """精簡版停車費計算器"""

    def __init__(self):
        self.rate_plans = self.load_rate_plans()

    def load_rate_plans(self) -> Dict:
        """載入費率方案"""
        try:
            with open("rate_plans.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return self.create_default_plans()

    def save_rate_plans(self):
        """儲存費率方案"""
        with open("rate_plans.json", "w", encoding="utf-8") as f:
            json.dump(self.rate_plans, f, ensure_ascii=False, indent=2)

    def create_default_plans(self) -> Dict:
        """創建預設費率方案"""
        default_plans = {
            "萬華西園": {
                "name": "萬華西園",
                "description": "二段式平日假日計費",
                "segments": [
                    {"name": "日間", "start": "07:00", "end": "18:00"},
                    {"name": "夜間", "start": "18:00", "end": "07:00"},
                ],
                "rates": {
                    "日間": {
                        "平日": {"rate": 30, "unit": 30, "cap": 300},
                        "假日": {"rate": 40, "unit": 30, "cap": 400},
                    },
                    "夜間": {
                        "平日": {"rate": 10, "unit": 60, "cap": 50},
                        "假日": {"rate": 10, "unit": 60, "cap": 50},
                    },
                },
                "holiday_mode": "weekday_weekend",  # 平日假日模式
            }
        }

        # 儲存預設方案
        os.makedirs("demo", exist_ok=True)
        with open("demo/rate_plans.json", "w", encoding="utf-8") as f:
            json.dump(default_plans, f, ensure_ascii=False, indent=2)

        return default_plans

    def get_date_type(self, dt: datetime, holiday_mode: str) -> str:
        """確定日期類型"""
        weekday = dt.weekday()  # 0=Monday, 6=Sunday

        if holiday_mode == "weekday_weekend":
            return "平日" if weekday < 5 else "假日"
        else:
            return "統一"

    def find_segment(self, time_obj: datetime, segments: List[Dict]) -> Optional[Dict]:
        """找出時間點所屬的時段"""
        current_time = time_obj.time()

        for segment in segments:
            start = datetime.strptime(segment["start"], "%H:%M").time()
            end = datetime.strptime(segment["end"], "%H:%M").time()

            if start <= end:
                # 同日時段 (如 07:00-18:00)
                if start <= current_time <= end:
                    return segment
            else:
                # 跨日時段 (如 18:00-07:00)
                if current_time >= start or current_time <= end:
                    return segment

        return None

    def get_segment_date_type(
        self, dt: datetime, segment: Dict, holiday_mode: str
    ) -> str:
        """
        獲取時段的日期類型
        對於跨日時段，使用時段開始時的日期類型
        """
        start_time = datetime.strptime(segment["start"], "%H:%M").time()
        end_time = datetime.strptime(segment["end"], "%H:%M").time()
        current_time = dt.time()

        # 判斷是否為跨日時段
        if start_time > end_time:
            # 跨日時段
            if current_time >= start_time:
                # 在時段前半部分，使用當天日期
                return self.get_date_type(dt, holiday_mode)
            else:
                # 在時段後半部分，使用前一天日期
                prev_day = dt - timedelta(days=1)
                return self.get_date_type(prev_day, holiday_mode)
        else:
            # 非跨日時段
            return self.get_date_type(dt, holiday_mode)

    def calculate_segment_fee(self, minutes: int, rate_config: Dict) -> int:
        """計算單個時段的費用"""
        if minutes <= 0:
            return 0

        rate = rate_config["rate"]
        unit = rate_config["unit"]
        cap = rate_config.get("cap", 0)

        # 計算計費單位數（向上取整）
        units = -(-minutes // unit)

        # 計算費用
        fee = units * rate

        # 應用上限
        if cap > 0 and fee > cap:
            fee = cap

        return fee

    def calculate_parking_fee(
        self, enter_time: datetime, exit_time: datetime, plan_id: str
    ) -> Dict:
        """計算停車費用"""
        try:
            if plan_id not in self.rate_plans:
                return {"success": False, "error": f"找不到費率方案: {plan_id}"}

            plan = self.rate_plans[plan_id]
            segments = plan["segments"]
            rates = plan["rates"]
            holiday_mode = plan["holiday_mode"]

            # 生成計費明細
            billing_details = []
            total_fee = 0
            current_time = enter_time

            # 按日期和時段分組計算
            daily_segments = {}  # {date: {segment_name: minutes}}

            while current_time < exit_time:
                # 找出當前時段
                segment = self.find_segment(current_time, segments)
                if not segment:
                    current_time += timedelta(minutes=1)
                    continue

                # 計算到下一個邊界的時間
                next_boundary = self.get_next_boundary(current_time, segment, exit_time)
                duration_minutes = int(
                    (next_boundary - current_time).total_seconds() / 60
                )

                if duration_minutes > 0:
                    # 獲取日期類型
                    date_type = self.get_segment_date_type(
                        current_time, segment, holiday_mode
                    )

                    # 按日期分組累計時間
                    date_key = current_time.date().strftime("%Y-%m-%d")
                    segment_key = f"{segment['name']}_{date_type}"

                    if date_key not in daily_segments:
                        daily_segments[date_key] = {}
                    if segment_key not in daily_segments[date_key]:
                        daily_segments[date_key][segment_key] = {
                            "minutes": 0,
                            "segment_name": segment["name"],
                            "date_type": date_type,
                            "start_time": current_time,
                            "end_time": current_time,
                        }

                    daily_segments[date_key][segment_key]["minutes"] += duration_minutes
                    daily_segments[date_key][segment_key]["end_time"] = next_boundary

                current_time = next_boundary

            # 計算各時段費用
            for date_str, segments_data in daily_segments.items():
                for segment_key, segment_data in segments_data.items():
                    segment_name = segment_data["segment_name"]
                    date_type = segment_data["date_type"]
                    minutes = segment_data["minutes"]
                    start_time = segment_data["start_time"]
                    end_time = segment_data["end_time"]

                    # 獲取費率配置
                    rate_config = rates[segment_name][date_type]

                    # 計算費用
                    fee = self.calculate_segment_fee(minutes, rate_config)
                    total_fee += fee

                    # 生成明細
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()

                    # 處理跨日顯示
                    if start_time.date() != end_time.date():
                        period_display = f"{start_time.strftime('%m-%d')}~{end_time.strftime('%m-%d')} {segment_name}{date_type} ({start_time.strftime('%H:%M')}-{end_time.strftime('%H:%M')})"
                    else:
                        period_display = f"{date_obj.strftime('%m-%d')} {segment_name}{date_type} ({start_time.strftime('%H:%M')}-{end_time.strftime('%H:%M')})"

                    billing_details.append(
                        {
                            "period": period_display,
                            "duration": self.format_duration(minutes),
                            "rate": f"{rate_config['rate']}元/{rate_config['unit']}分鐘",
                            "amount": fee,
                            "date": date_str,
                            "segment": segment_name,
                            "date_type": date_type,
                        }
                    )

            # 按時間順序排序
            billing_details.sort(key=lambda x: (x["date"], x["segment"]))

            return {
                "success": True,
                "total_amount": total_fee,
                "plan_name": plan["name"],
                "billing_details": billing_details,
                "enter_time": enter_time.strftime("%Y-%m-%d %H:%M"),
                "exit_time": exit_time.strftime("%Y-%m-%d %H:%M"),
                "total_duration": self.format_duration(
                    int((exit_time - enter_time).total_seconds() / 60)
                ),
            }

        except Exception as e:
            return {"success": False, "error": f"計算錯誤: {str(e)}"}

    def get_next_boundary(
        self, current_time: datetime, segment: Dict, exit_time: datetime
    ) -> datetime:
        """獲取下一個時間邊界"""
        # 計算時段結束時間
        end_time_str = segment["end"]
        end_time = datetime.strptime(end_time_str, "%H:%M").time()

        # 判斷是否跨日
        start_time = datetime.strptime(segment["start"], "%H:%M").time()
        if start_time > end_time:  # 跨日時段
            if current_time.time() >= start_time:
                # 當前在跨日時段前半部分，結束時間是明天
                segment_end = datetime.combine(
                    current_time.date() + timedelta(days=1), end_time
                )
            else:
                # 當前在跨日時段後半部分，結束時間是今天
                segment_end = datetime.combine(current_time.date(), end_time)
        else:
            # 同日時段
            segment_end = datetime.combine(current_time.date(), end_time)
            if segment_end <= current_time:
                segment_end += timedelta(days=1)

        # 計算到午夜的時間（用於日期切換）
        next_midnight = datetime.combine(
            current_time.date() + timedelta(days=1), datetime.min.time()
        )

        # 返回最近的邊界時間
        return min(segment_end, next_midnight, exit_time)

    def format_duration(self, minutes: int) -> str:
        """格式化時間顯示"""
        if minutes < 60:
            return f"{minutes}分鐘"

        hours = minutes // 60
        remaining_minutes = minutes % 60

        if remaining_minutes == 0:
            return f"{minutes}分鐘 ({hours}小時)"
        else:
            return f"{minutes}分鐘 ({hours}小時{remaining_minutes}分)"


# 初始化計算器
calculator = ParkingCalculator()


@app.route("/")
def index():
    """主頁面"""
    return render_template("index.html", rate_plans=list(calculator.rate_plans.keys()))


@app.route("/rate_editor")
def rate_editor():
    """費率編輯器頁面"""
    return render_template("rate_editor.html")


@app.route("/api/calculate", methods=["POST"])
def calculate():
    """計算API"""
    try:
        data = request.get_json()

        enter_time_str = data.get("enter_time")
        exit_time_str = data.get("exit_time")
        plan_id = data.get("plan_id")

        if not all([enter_time_str, exit_time_str, plan_id]):
            return jsonify({"success": False, "error": "請填寫完整資訊"})

        # 解析時間
        enter_time = datetime.strptime(enter_time_str, "%Y-%m-%dT%H:%M")
        exit_time = datetime.strptime(exit_time_str, "%Y-%m-%dT%H:%M")

        if enter_time >= exit_time:
            return jsonify({"success": False, "error": "出場時間必須晚於進場時間"})

        # 計算費用
        result = calculator.calculate_parking_fee(enter_time, exit_time, plan_id)

        return jsonify(result)

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/plans")
def get_plans():
    """獲取費率方案"""
    return jsonify({"success": True, "plans": calculator.rate_plans})


@app.route("/api/plans/<plan_id>")
def get_plan(plan_id):
    """獲取單個費率方案"""
    if plan_id in calculator.rate_plans:
        return jsonify({"success": True, "plan": calculator.rate_plans[plan_id]})
    else:
        return jsonify({"success": False, "error": "方案不存在"})


@app.route("/api/plans/save", methods=["POST"])
def save_plan():
    """儲存費率方案"""
    try:
        data = request.get_json()

        plan_name = data.get("name")
        if not plan_name:
            return jsonify({"success": False, "error": "方案名稱不能為空"})

        # 構建方案資料
        plan_data = {
            "name": plan_name,
            "description": data.get("description", ""),
            "segments": data.get("segments", []),
            "rates": data.get("rates", {}),
            "holiday_mode": data.get("holiday_mode", "weekday_weekend"),
        }

        # 儲存方案
        calculator.rate_plans[plan_name] = plan_data
        calculator.save_rate_plans()

        return jsonify({"success": True, "message": f"方案 '{plan_name}' 儲存成功"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/plans/delete/<plan_id>", methods=["DELETE"])
def delete_plan(plan_id):
    """刪除費率方案"""
    try:
        if plan_id in calculator.rate_plans:
            del calculator.rate_plans[plan_id]
            calculator.save_rate_plans()
            return jsonify({"success": True, "message": f"方案 '{plan_id}' 刪除成功"})
        else:
            return jsonify({"success": False, "error": "方案不存在"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/test_plan", methods=["POST"])
def test_plan():
    """測試費率方案"""
    try:
        data = request.get_json()

        plan_data = data.get("plan_data")
        enter_time_str = data.get("enter_time")
        exit_time_str = data.get("exit_time")

        if not all([plan_data, enter_time_str, exit_time_str]):
            return jsonify({"success": False, "error": "測試資料不完整"})

        # 解析時間
        enter_time = datetime.strptime(enter_time_str, "%Y-%m-%dT%H:%M")
        exit_time = datetime.strptime(exit_time_str, "%Y-%m-%dT%H:%M")

        # 創建臨時計算器
        temp_calculator = ParkingCalculator()
        temp_calculator.rate_plans = {"test": plan_data}

        # 計算費用
        result = temp_calculator.calculate_parking_fee(enter_time, exit_time, "test")

        return jsonify(result)

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)
