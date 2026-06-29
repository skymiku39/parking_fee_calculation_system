import json
import sys
from pathlib import Path
from shutil import copy2

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

CONFIG_FILES = (
    "multidimensional_rate_plans.json",
    "system_config.json",
    "system_calendar.json",
    "user_defined_plans.json",
)


def build_isolated_system(tmp_path: Path, **system_config_overrides):
    """以 tmp_path 為資料目錄建立隔離的 SmartParkingSystem，避免污染正式 config/。"""
    from src.core.system import SmartParkingSystem

    data_dir = tmp_path
    data_dir.mkdir(parents=True, exist_ok=True)
    for filename in CONFIG_FILES:
        source = REPO_ROOT / "config" / filename
        if source.exists():
            copy2(source, data_dir / filename)

    if system_config_overrides:
        cfg_path = data_dir / "system_config.json"
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        cfg.update(system_config_overrides)
        if "ui_settings" in system_config_overrides:
            cfg["ui_settings"] = {
                **cfg.get("ui_settings", {}),
                **system_config_overrides["ui_settings"],
            }
        cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    return SmartParkingSystem(base_path=data_dir)

@pytest.fixture
def isolated_system(tmp_path):
    """提供隔離的 SmartParkingSystem 實例。"""
    return build_isolated_system(tmp_path)


@pytest.fixture
def isolated_client(tmp_path, monkeypatch):
    """提供 (system, Flask test client, data_dir)，並將各 web 藍圖綁定到隔離系統。"""
    import src.core.context as context_module
    import src.web.calc as calc_module
    import src.web.calendar as calendar_module
    import src.web.mdp as mdp_module
    import src.web.system as system_module
    import src.web.user_plans as user_plans_module
    from app import app

    system = build_isolated_system(tmp_path)
    for module in (
        context_module,
        calc_module,
        calendar_module,
        mdp_module,
        system_module,
        user_plans_module,
    ):
        monkeypatch.setattr(module, "parking_system", system)

    return system, app.test_client(), tmp_path
