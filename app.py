"""
智能停車費率計算系統 - 精簡啟動程式
職責：建立 Flask 應用、註冊藍圖與頁面路由
"""

import logging
import os
import sys
from pathlib import Path

from flask import Flask, render_template


def _resolve_resource_dirs() -> tuple[str, str]:
    """Dev 用 src/web/*；PyInstaller 打包後用 bundle 內 templates/、static/。"""
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", os.getcwd()))
        return (base / "templates").as_posix(), (base / "static").as_posix()
    base = Path(__file__).resolve().parent
    return (
        (base / "src" / "web" / "templates").as_posix(),
        (base / "src" / "web" / "static").as_posix(),
    )


_TEMPLATE_DIR, _STATIC_DIR = _resolve_resource_dirs()

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
from src.web.calendar import calendar_bp
from src.web.mdp import mdp_bp
from src.web.misc import misc_bp
from src.web.system import system_bp
from src.web.user_plans import user_plans_bp

app.register_blueprint(calc_bp)
app.register_blueprint(mdp_bp)
app.register_blueprint(calendar_bp)
app.register_blueprint(misc_bp)
app.register_blueprint(system_bp)
app.register_blueprint(user_plans_bp)


@app.route("/")
def index():
    from src.core.context import parking_system
    from src.web.calc import get_all_available_plans

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


@app.route("/user_plan_designer")
def user_plan_designer_page():
    return render_template("user_plan_designer.html")


if __name__ == "__main__":
    if not os.path.exists("src/web/templates"):
        os.makedirs("src/web/templates")
    if not os.path.exists("log"):
        os.makedirs("log")
    debug = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true", "yes", "on")
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=debug, host="0.0.0.0", port=port)


