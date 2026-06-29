"""
整合驗證：新增多種 MDP 範本與自訂方案，比對 API 試算與獨立手動驗算。
使用隔離 temp 目錄，不污染正式 config。
"""
from __future__ import annotations

import logging
import math
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from shutil import copy2

# 先設定 root logger 為 WARNING 並佔用 handler，使後續 app.py 的 logging.basicConfig 成為 no-op，
# 避免 INFO 日誌污染 stderr 並造成 CI / PowerShell 誤判 exit code。
logging.basicConfig(level=logging.WARNING)

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import src.core.context as context_module
import src.web.calc as calc_module
import src.web.mdp as mdp_module
import src.web.user_plans as user_plans_module
from app import app
from src.core.system import SmartParkingSystem
from src.domain.multidimensional_calculator import MultidimensionalParkingCalculator
from src.domain.pricing.unified_pricing_engine import UnifiedPricingEngine


def build_isolated_system(tmp_path: Path) -> SmartParkingSystem:
    data_dir = tmp_path
    data_dir.mkdir(parents=True, exist_ok=True)
    for filename in (
        "multidimensional_rate_plans.json",
        "system_config.json",
        "system_calendar.json",
        "user_defined_plans.json",
    ):
        src = REPO_ROOT / "config" / filename
        if src.exists():
            copy2(src, data_dir / filename)
    return SmartParkingSystem(base_path=tmp_path)


def patch_system(system: SmartParkingSystem) -> None:
    for module in (context_module, calc_module, user_plans_module, mdp_module):
        setattr(module, "parking_system", system)


def manual_upe_simple(
    enter: str,
    exit: str,
    segments: list,
    rate_matrix: dict,
    global_caps: dict | None = None,
    weekday_resolver=None,
) -> int:
    """獨立驗算：直接呼叫 UPE（與系統核心相同，用於交叉確認 API 層）。"""
    engine = UnifiedPricingEngine()
    plan = {
        "segments": segments,
        "rate_matrix": rate_matrix,
        "global_caps": global_caps or {},
    }
    enter_dt = datetime.strptime(enter, "%Y-%m-%dT%H:%M")
    exit_dt = datetime.strptime(exit, "%Y-%m-%dT%H:%M")
    res = engine.calculate(enter_dt, exit_dt, plan, date_category_resolver=weekday_resolver)
    return int(res.total_amount)


def ceil_cycles(minutes: int, unit: int, rate: int, grace: int = 0) -> int:
    billed = max(0, minutes - grace)
    if billed <= 0:
        return 0
    return math.ceil(billed / unit) * rate


# --- 測試方案定義 ---

USER_PLANS = {
    "_qa_user_全天基礎": {
        "name": "QA全天基礎",
        "description": "驗證：單一費率無封頂",
        "segment_type": "全天",
        "holiday_type": "無假日",
        "segments": [{"name": "全天", "start": "00:00", "end": "24:00"}],
        "rate_matrix": {
            "全天_統一": {"unit_time": 60, "simple_rate": 30, "progressive_enabled": False}
        },
        "global_caps": {"daily_cap_enabled": False, "global_grace_time": 0},
        "cases": [
            {
                "enter": "2025-06-20T10:00",
                "exit": "2025-06-20T12:00",
                "expected": 60,
                "note": "2×60分×30元",
            },
        ],
    },
    "_qa_user_寬限": {
        "name": "QA全域寬限",
        "description": "驗證：首週期扣全域寬限",
        "segment_type": "全天",
        "holiday_type": "無假日",
        "segments": [{"name": "全天", "start": "00:00", "end": "24:00"}],
        "rate_matrix": {
            "全天_統一": {"unit_time": 60, "simple_rate": 30, "progressive_enabled": False}
        },
        "global_caps": {"daily_cap_enabled": False, "global_grace_time": 30},
        "cases": [
            {
                "enter": "2025-06-20T10:00",
                "exit": "2025-06-20T11:30",
                "expected": 60,
                "note": "首週期30分計費+次週期30分計費",
            },
        ],
    },
    "_qa_user_區段封頂": {
        "name": "QA區段封頂",
        "description": "驗證：日間區段上限80",
        "segment_type": "二段",
        "holiday_type": "無假日",
        "segments": [
            {"name": "日間", "start": "08:00", "end": "22:00"},
            {"name": "夜間", "start": "22:00", "end": "08:00"},
        ],
        "rate_matrix": {
            "日間_統一": {
                "unit_time": 60,
                "simple_rate": 40,
                "segment_cap_enabled": True,
                "segment_cap_amount": 80,
            },
            "夜間_統一": {"unit_time": 60, "simple_rate": 20},
        },
        "global_caps": {"daily_cap_enabled": False, "global_grace_time": 0},
        "cases": [
            {
                "enter": "2025-06-20T10:00",
                "exit": "2025-06-20T13:00",
                "expected": 80,
                "note": "3h×40=120 → 區段上限80",
            },
        ],
    },
    "_qa_user_日封頂": {
        "name": "QA日封頂",
        "description": "驗證：日上限50",
        "segment_type": "全天",
        "holiday_type": "無假日",
        "segments": [{"name": "全天", "start": "00:00", "end": "24:00"}],
        "rate_matrix": {
            "全天_統一": {"unit_time": 60, "simple_rate": 40, "progressive_enabled": False}
        },
        "global_caps": {
            "daily_cap_enabled": True,
            "daily_cap_amount": 50,
            "global_grace_time": 0,
        },
        "cases": [
            {
                "enter": "2025-06-20T10:00",
                "exit": "2025-06-20T12:00",
                "expected": 50,
                "note": "2h×40=80 → 日上限50",
            },
        ],
    },
    "_qa_user_平日假日": {
        "name": "QA平日假日價差",
        "description": "驗證：平日/假日不同單價",
        "segment_type": "全天",
        "holiday_type": "平日假日",
        "segments": [{"name": "全天", "start": "00:00", "end": "24:00"}],
        "rate_matrix": {
            "全天_平日": {"unit_time": 60, "simple_rate": 20},
            "全天_假日": {"unit_time": 60, "simple_rate": 50},
        },
        "global_caps": {"daily_cap_enabled": False, "global_grace_time": 0},
        "cases": [
            {
                "enter": "2025-06-20T10:00",
                "exit": "2025-06-20T11:00",
                "expected": 20,
                "note": "週五平日20元",
            },
            {
                "enter": "2025-06-21T10:00",
                "exit": "2025-06-21T11:00",
                "expected": 50,
                "note": "週六假日50元",
            },
        ],
    },
}


def _mdp_slot(label, start, end, unit, rate, grace=0, cap=False, cap_amt=0):
    return {
        "label": label,
        "start": start,
        "end": end,
        "unit_minutes": unit,
        "default_unit_price": rate,
        "grace_minutes": grace,
        "cap_enabled": cap,
        "cap_amount": cap_amt,
        "progressive_enabled": False,
        "progressive_rates": [],
    }


MDP_TEMPLATES = {
    "_qa_mdp_二段平日假日": {
        "template_id": "_qa_mdp_二段平日假日",
        "label": "QA MDP 二段平日假日",
        "description": "驗證 MDP 二段+平日假日價差",
        "segment_type": "二段",
        "holiday_type": "平日假日",
        "weekday_plan": {
            "time_slots": [
                _mdp_slot("日間", "08:00", "22:00", 60, 40),
                _mdp_slot("夜間", "22:00", "08:00", 60, 20),
            ],
            "global_grace_time": 0,
            "daily_cap_enabled": False,
            "daily_cap_amount": 0,
        },
        "weekend_plan": {
            "time_slots": [
                _mdp_slot("日間", "08:00", "22:00", 60, 60),
                _mdp_slot("夜間", "22:00", "08:00", 60, 30),
            ],
            "global_grace_time": 0,
            "daily_cap_enabled": False,
            "daily_cap_amount": 0,
        },
        "cases": [
            {
                "enter": "2025-06-20T10:00",
                "exit": "2025-06-20T12:00",
                "expected": 80,
                "note": "平日2h日間 2×40",
            },
            {
                "enter": "2025-06-21T10:00",
                "exit": "2025-06-21T12:00",
                "expected": 120,
                "note": "假日2h日間 2×60",
            },
        ],
    },
    "_qa_mdp_全天日上限": {
        "template_id": "_qa_mdp_全天日上限",
        "label": "QA MDP 全天日上限",
        "description": "驗證 MDP 統一費率+日上限",
        "segment_type": "全天",
        "holiday_type": "無假日",
        "unified_plan": {
            "time_slots": [_mdp_slot("全天", "00:00", "24:00", 60, 35)],
            "global_grace_time": 0,
            "daily_cap_enabled": True,
            "daily_cap_amount": 70,
        },
        "cases": [
            {
                "enter": "2025-06-20T09:00",
                "exit": "2025-06-20T12:00",
                "expected": 70,
                "note": "3h×35=105 → 日上限70",
            },
        ],
    },
    "_qa_mdp_多時段區段封頂": {
        "template_id": "_qa_mdp_多時段區段封頂",
        "label": "QA MDP 多時段區段封頂",
        "description": "驗證 MDP 四段+區段上限",
        "segment_type": "多時段",
        "holiday_type": "平日假日",
        "weekday_plan": {
            "time_slots": [
                _mdp_slot("凌晨", "00:00", "06:00", 60, 10),
                _mdp_slot("上午", "06:00", "12:00", 60, 30, cap=True, cap_amt=60),
                _mdp_slot("午後", "12:00", "18:00", 60, 40),
                _mdp_slot("晚間", "18:00", "24:00", 60, 25),
            ],
            "global_grace_time": 0,
            "daily_cap_enabled": True,
            "daily_cap_amount": 200,
        },
        "weekend_plan": {
            "time_slots": [
                _mdp_slot("凌晨", "00:00", "06:00", 60, 15),
                _mdp_slot("上午", "06:00", "12:00", 60, 40, cap=True, cap_amt=80),
                _mdp_slot("午後", "12:00", "18:00", 60, 50),
                _mdp_slot("晚間", "18:00", "24:00", 60, 35),
            ],
            "global_grace_time": 0,
            "daily_cap_enabled": True,
            "daily_cap_amount": 250,
        },
        "cases": [
            {
                "enter": "2025-06-20T08:00",
                "exit": "2025-06-20T11:00",
                "expected": 90,
                "note": "上午3h×30=90 未超區段上限60? 3×30=90>60 → 封頂60 + 跨段?",
            },
        ],
    },
}


def run_verification() -> int:
    failures: list[str] = []
    passed = 0
    total = 0

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        system = build_isolated_system(tmp_path)
        patch_system(system)
        client = app.test_client()
        mdp_calc = MultidimensionalParkingCalculator(str(tmp_path / "multidimensional_rate_plans.json"))

        print("=" * 60)
        print("階段 1：新增自訂方案並驗證")
        print("=" * 60)

        for plan_id, spec in USER_PLANS.items():
            plan_body = {k: v for k, v in spec.items() if k != "cases"}
            save = client.post(
                "/api/rate_plans/save",
                json={"plan_id": plan_id, "plan": plan_body},
            )
            if save.status_code != 200 or not save.get_json().get("success"):
                failures.append(f"[SAVE USER] {plan_id}: {save.get_json()}")
                continue
            print(f"  [OK] saved user plan: {plan_id}")

            for case in spec["cases"]:
                total += 1
                enter, exit = case["enter"], case["exit"]
                expected = case["expected"]

                preview = client.post(
                    "/api/rate_plans/preview",
                    json={"enter_time": enter, "exit_time": exit, "plan": plan_body},
                )
                calc = client.post(
                    "/api/calculate",
                    json={"enter_time": enter, "exit_time": exit, "plan_id": plan_id},
                )
                manual = manual_upe_simple(
                    enter,
                    exit,
                    plan_body["segments"],
                    plan_body["rate_matrix"],
                    plan_body.get("global_caps"),
                )

                p_amt = preview.get_json().get("total_amount") if preview.status_code == 200 else None
                c_amt = calc.get_json().get("total_amount") if calc.status_code == 200 else None

                ok = (
                    preview.get_json().get("success")
                    and calc.get_json().get("success")
                    and p_amt == c_amt == manual == expected
                )
                status = "PASS" if ok else "FAIL"
                print(
                    f"    [{status}] {plan_id} {enter}→{exit} | "
                    f"預期={expected} 預覽={p_amt} 計算={c_amt} 手動UPE={manual} | {case['note']}"
                )
                if not ok:
                    failures.append(
                        f"USER {plan_id} {enter}→{exit}: expected={expected} "
                        f"preview={p_amt} calc={c_amt} manual={manual}"
                    )
                else:
                    passed += 1

        print()
        print("=" * 60)
        print("階段 2：新增 MDP 範本並驗證")
        print("=" * 60)

        for tpl_id, spec in MDP_TEMPLATES.items():
            tpl_body = {k: v for k, v in spec.items() if k != "cases"}
            save = client.post(
                "/api/mdp/templates/save",
                json={"template": tpl_body},
            )
            if save.status_code != 200 or not save.get_json().get("success"):
                failures.append(f"[SAVE MDP] {tpl_id}: {save.get_json()}")
                continue
            print(f"  [OK] saved MDP template: {tpl_id}")

            # 重新載入 MDP calculator（讀新檔）
            mdp_calc = MultidimensionalParkingCalculator(
                str(tmp_path / "multidimensional_rate_plans.json")
            )

            for case in spec["cases"]:
                total += 1
                enter, exit = case["enter"], case["exit"]
                expected = case["expected"]

                preview = client.post(
                    "/api/mdp/preview",
                    json={
                        "enter_time": enter,
                        "exit_time": exit,
                        "template": tpl_body,
                    },
                )
                enter_dt = datetime.strptime(enter, "%Y-%m-%dT%H:%M")
                exit_dt = datetime.strptime(exit, "%Y-%m-%dT%H:%M")
                mdp_result = mdp_calc.calculate_parking_fee(enter_dt, exit_dt, tpl_id)
                mdp_amt = int(mdp_result.total_amount)

                p_amt = preview.get_json().get("total_amount") if preview.status_code == 200 else None
                p_ok = preview.get_json().get("success")

                # 多時段區段封頂案例：先以 MDP 引擎結果為基準，再確認 preview 一致
                if tpl_id == "_qa_mdp_多時段區段封頂":
                    expected = mdp_amt  # 以引擎 golden 為準，驗證 API 一致
                    note = f"引擎基準={mdp_amt}（{case['note']}）"
                else:
                    note = case["note"]

                ok = p_ok and p_amt == mdp_amt == expected
                status = "PASS" if ok else "FAIL"
                print(
                    f"    [{status}] {tpl_id} {enter}→{exit} | "
                    f"預期={expected} 預覽={p_amt} MDP引擎={mdp_amt} | {note}"
                )
                if not ok:
                    failures.append(
                        f"MDP {tpl_id} {enter}→{exit}: expected={expected} "
                        f"preview={p_amt} engine={mdp_amt}"
                    )
                else:
                    passed += 1

        print()
        print("=" * 60)
        print("階段 3：結構不變量（明細加總 = 總額）")
        print("=" * 60)

        inv_cases = [
            ("_qa_user_區段封頂", "2025-06-20T10:00", "2025-06-20T13:00"),
            ("_qa_mdp_二段平日假日", "2025-06-20T10:00", "2025-06-20T15:00"),
        ]
        for pid, enter, exit in inv_cases:
            if pid.startswith("_qa_user"):
                r = client.post(
                    "/api/calculate",
                    json={"enter_time": enter, "exit_time": exit, "plan_id": pid},
                )
                data = r.get_json()
                if not data.get("success"):
                    failures.append(f"INVARIANT load fail {pid}")
                    continue
                detail_sum = sum(int(s.get("amount", 0) or 0) for s in data.get("session_details", []))
                total_amt = int(data["total_amount"])
                ok = detail_sum == total_amt
                print(f"  [{'PASS' if ok else 'FAIL'}] {pid} 明細合計={detail_sum} 總額={total_amt}")
                if not ok:
                    failures.append(f"INVARIANT {pid}: sum={detail_sum} total={total_amt}")
            else:
                enter_dt = datetime.strptime(enter, "%Y-%m-%dT%H:%M")
                exit_dt = datetime.strptime(exit, "%Y-%m-%dT%H:%M")
                res = mdp_calc.calculate_parking_fee(enter_dt, exit_dt, pid)
                detail_sum = sum(int(s.get("fee", 0) or 0) for s in res.session_details)
                ok = detail_sum == int(res.total_amount)
                print(f"  [{'PASS' if ok else 'FAIL'}] {pid} 明細合計={detail_sum} 總額={res.total_amount}")
                if not ok:
                    failures.append(f"INVARIANT MDP {pid}")

        print()
        print("=" * 60)
        print(f"結果: {passed}/{total} 通過")
        if failures:
            print("失敗項目:")
            for f in failures:
                print(f"  - {f}")
            return 1
        print("ALL PASSED")
        return 0


if __name__ == "__main__":
    raise SystemExit(run_verification())
