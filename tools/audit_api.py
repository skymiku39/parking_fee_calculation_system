"""API 端對端計費煙霧測試。"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from shutil import copy2

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import app
from src.core.system import SmartParkingSystem
import src.core.context as context_module
import src.web.calc as calc_module
import src.web.mdp as mdp_module


def main() -> int:
    td = Path(tempfile.mkdtemp())
    for fn in (
        "multidimensional_rate_plans.json",
        "system_config.json",
        "user_defined_plans.json",
        "system_calendar.json",
    ):
        src = ROOT / "config" / fn
        if src.exists():
            copy2(src, td / fn)

    system = SmartParkingSystem(base_path=td)
    for mod in (context_module, calc_module, mdp_module):
        setattr(mod, "parking_system", system)
    client = app.test_client()

    cases = [
        (
            "自訂 全天有上限",
            "POST",
            "/api/calculate",
            {
                "enter_time": "2025-06-20T08:00",
                "exit_time": "2025-06-20T20:00",
                "plan_id": "全天有上限",
            },
            {"total": 200, "cap": True},
        ),
        (
            "自訂 萬華西園 週末",
            "POST",
            "/api/calculate",
            {
                "enter_time": "2025-06-21T10:00",
                "exit_time": "2025-06-21T14:00",
                "plan_id": "萬華西園",
            },
            {"total": 320},
        ),
        (
            "MDP 多時段 週六",
            "POST",
            "/api/calculate",
            {
                "enter_time": "2024-12-21T08:00",
                "exit_time": "2024-12-21T22:00",
                "plan_id": "多時段_完整假日",
            },
            {"total": 360, "engine": "multidimensional"},
        ),
        (
            "MDP 多時段 節慴",
            "POST",
            "/api/calculate",
            {
                "enter_time": "2024-12-25T08:00",
                "exit_time": "2024-12-25T20:00",
                "plan_id": "多時段_完整假日",
            },
            {"total": 540, "engine": "multidimensional"},
        ),
    ]

    issues = []
    print("=== API E2E ===")
    for name, method, path, body, expect in cases:
        resp = client.post(path, json=body)
        payload = resp.get_json() or {}
        success = payload.get("success", resp.status_code == 200)
        total = payload.get("total_amount")
        if total is None and "result" in payload:
            total = payload["result"].get("total_amount")

        ok = resp.status_code == 200 and success
        if "total" in expect and total != expect["total"]:
            ok = False
        if "cap" in expect and payload.get("cap_applied") != expect["cap"]:
            ok = False
        if "engine" in expect and payload.get("calculation_engine") != expect["engine"]:
            ok = False

        if path == "/api/calculate":
            details = payload.get("session_details", [])
            dsum = sum(
                int(s.get("amount", 0) or s.get("fee", 0) or 0) for s in details
            )
            if dsum != total:
                ok = False
            extra = ""
            if payload.get("calculation_engine") == "multidimensional":
                extra = f" cat={payload.get('date_category')}"
            else:
                extra = f" cap={payload.get('cap_applied')}"
            print(
                f"  [{'OK' if ok else 'FAIL'}] {name}: "
                f"status={resp.status_code} total={total}{extra}"
            )
        else:
            print(f"  [{'OK' if ok else 'FAIL'}] {name}: status={resp.status_code} total={total}")

        if not ok:
            issues.append(name)

    print()
    if issues:
        print(f"API 失敗: {issues}")
        return 1
    print("API 全部通過")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
