"""
智能停車費率計算系統 - 精簡啟動程式
職責：建立 Flask 應用、註冊藍圖與頁面路由
"""

import os
import sys
import logging
from pathlib import Path
from flask import Flask, render_template, redirect, url_for
from src.core.utils import DEFAULT_DATETIME_DISPLAY_FORMAT

# 讓 Flask 在 PyInstaller 打包後也能正確找到模板與靜態資源
_BASE_DIR = Path(getattr(sys, "_MEIPASS", os.getcwd()))
_TEMPLATE_DIR = (_BASE_DIR / "templates").as_posix()
_STATIC_DIR = (_BASE_DIR / "static").as_posix()

app = Flask(__name__, template_folder=_TEMPLATE_DIR, static_folder=_STATIC_DIR)
app.config["JSON_AS_ASCII"] = False

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

# 藍圖註冊
from src.web.calc import calc_bp
from src.web.mdp import mdp_bp
from src.web.calendar import calendar_bp
from src.web.misc import misc_bp
from src.web.system import system_bp

app.register_blueprint(calc_bp)
app.register_blueprint(mdp_bp)
app.register_blueprint(calendar_bp)
app.register_blueprint(misc_bp)
app.register_blueprint(system_bp)


@app.route("/")
def index():
    from src.web.calc import get_all_available_plans
    from src.core.context import parking_system

    plans = get_all_available_plans()
    system_config = parking_system.system_config
    return render_template("index.html", rate_plans=plans, system_config=system_config)


@app.route("/system_settings")
def system_settings_page():
    return render_template("system_settings.html")


@app.route("/rate_plan_designer")
def rate_plan_designer():
    return render_template("rate_plan_designer.html")


@app.route("/plan_manager")
def plan_manager_page():
    return render_template("plan_manager.html")


@app.route("/calendar_manager")
def calendar_manager_page():
    return render_template("calendar_manager.html")


@app.route("/settlement_center")
def settlement_center():
    return redirect(url_for("index"))


if __name__ == "__main__":
    if not os.path.exists("templates"):
        os.makedirs("templates")
    if not os.path.exists("log"):
        os.makedirs("log")
    app.run(debug=True, host="0.0.0.0", port=5000)


