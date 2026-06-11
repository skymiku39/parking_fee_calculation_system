"""全組合計費獨立驗證：自訂方案與 MDP 範本各場景 golden 值 + 結構不變量。"""

from datetime import datetime
from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.core.system import SmartParkingSystem
from src.domain.multidimensional_calculator import MultidimensionalParkingCalculator


def _detail_sum_user(payload: dict) -> int:
    return sum(int(s.get("amount", 0) or 0) for s in payload.get("session_details", []))


def _detail_sum_mdp(result) -> int:
    return sum(int(s.get("fee", 0) or 0) for s in result.session_details)


def assert_billing_invariants_user(payload: dict) -> None:
    assert payload.get("success") is True, payload.get("error")
    total = int(payload["total_amount"])
    original = int(payload.get("original_amount", total))
    detail_sum = _detail_sum_user(payload)
    assert detail_sum == total
    assert original >= total
    assert payload.get("cap_applied") == (original > total)


def assert_billing_invariants_mdp(result) -> None:
    total = int(result.total_amount)
    original = int(result.original_amount)
    detail_sum = _detail_sum_mdp(result)
    assert detail_sum == total
    assert original >= total


@pytest.fixture
def parking_system(tmp_path):
    from shutil import copy2

    data_dir = tmp_path
    data_dir.mkdir(parents=True, exist_ok=True)
    for filename in (
        "multidimensional_rate_plans.json",
        "system_config.json",
        "user_defined_plans.json",
    ):
        copy2(REPO_ROOT / "config" / filename, data_dir / filename)
    return SmartParkingSystem(base_path=data_dir)


@pytest.fixture
def mdp_calculator():
    return MultidimensionalParkingCalculator(
        str(REPO_ROOT / "config" / "multidimensional_rate_plans.json")
    )


def _calc_user(system: SmartParkingSystem, plan_id: str, enter: str, exit: str) -> dict:
    enter_time = datetime.strptime(enter, "%Y-%m-%dT%H:%M")
    exit_time = datetime.strptime(exit, "%Y-%m-%dT%H:%M")
    return system.calculate_parking_fee(enter_time, exit_time, plan_id)


def _calc_mdp(calculator: MultidimensionalParkingCalculator, template_id: str, enter: str, exit: str):
    enter_time = datetime.strptime(enter, "%Y-%m-%dT%H:%M")
    exit_time = datetime.strptime(exit, "%Y-%m-%dT%H:%M")
    return calculator.calculate_parking_fee(enter_time, exit_time, template_id)


# --- 自訂方案（10 個獨立案例）---


def test_plan_跨日測試方案_cross_midnight(parking_system):
    payload = _calc_user(parking_system, "跨日測試方案", "2025-06-20T21:00", "2025-06-21T03:00")
    assert_billing_invariants_user(payload)
    assert payload["total_amount"] == 120
    assert payload["cap_applied"] is False


def test_plan_全天無上限_same_day_short(parking_system):
    payload = _calc_user(parking_system, "全天無上限", "2025-06-20T10:00", "2025-06-20T14:00")
    assert_billing_invariants_user(payload)
    assert payload["total_amount"] == 120
    assert payload["total_amount"] == payload["original_amount"]


def test_plan_全天有上限_same_day_daily_cap(parking_system):
    payload = _calc_user(parking_system, "全天有上限", "2025-06-20T08:00", "2025-06-20T20:00")
    assert_billing_invariants_user(payload)
    assert payload["total_amount"] == 200
    assert payload["cap_applied"] is True


def test_plan_全天有上限_two_days_daily_cap(parking_system):
    payload = _calc_user(parking_system, "全天有上限", "2025-06-20T00:00", "2025-06-22T00:00")
    assert_billing_invariants_user(payload)
    assert payload["total_amount"] == 400
    assert payload["cap_applied"] is True


def test_plan_兩段無上限_cross_midnight(parking_system):
    payload = _calc_user(parking_system, "兩段無上限", "2025-06-20T21:00", "2025-06-21T03:00")
    assert_billing_invariants_user(payload)
    assert payload["total_amount"] == 120
    assert payload["total_amount"] == payload["original_amount"]


def test_plan_兩段有上限_two_days_daily_cap(parking_system):
    payload = _calc_user(parking_system, "兩段有上限", "2025-06-20T00:00", "2025-06-22T00:00")
    assert_billing_invariants_user(payload)
    assert payload["total_amount"] == 400
    assert payload["cap_applied"] is True


def test_plan_兩段有分段上限_segment_cap_day_only(parking_system):
    payload = _calc_user(parking_system, "兩段有分段上限", "2025-06-20T07:00", "2025-06-20T19:00")
    assert_billing_invariants_user(payload)
    assert payload["total_amount"] == 130
    assert payload["cap_applied"] is True
    assert payload["original_amount"] > payload["total_amount"]


def test_plan_全天累進費率無上限_progressive_same_day(parking_system):
    payload = _calc_user(
        parking_system, "全天累進費率無上限", "2025-06-20T10:00", "2025-06-20T15:00"
    )
    assert_billing_invariants_user(payload)
    assert payload["total_amount"] == 150
    assert payload["total_amount"] > 0


def test_plan_萬華西園_weekday_short(parking_system):
    payload = _calc_user(parking_system, "萬華西園", "2025-06-18T10:00", "2025-06-18T14:00")
    assert_billing_invariants_user(payload)
    assert payload["total_amount"] == 240


def test_plan_萬華西園_weekend_short(parking_system):
    payload = _calc_user(parking_system, "萬華西園", "2025-06-21T10:00", "2025-06-21T14:00")
    assert_billing_invariants_user(payload)
    assert payload["total_amount"] == 320


def test_plan_全局寬裕時間測試_global_grace(parking_system):
    payload = _calc_user(
        parking_system, "全局寬裕時間測試", "2025-06-20T10:00", "2025-06-20T12:00"
    )
    assert_billing_invariants_user(payload)
    assert payload["total_amount"] == 60


def test_plan_billing_cycle_test_weekday_short(parking_system):
    payload = _calc_user(
        parking_system, "billing_cycle_test", "2025-06-18T10:00", "2025-06-18T12:00"
    )
    assert_billing_invariants_user(payload)
    assert payload["total_amount"] == 120


# --- MDP 範本（7 個獨立案例）---


def test_mdp_全天_無假日_same_day_daily_cap(mdp_calculator):
    result = _calc_mdp(mdp_calculator, "全天_無假日", "2024-12-19T08:00", "2024-12-19T20:00")
    assert_billing_invariants_mdp(result)
    assert result.total_amount == 200


def test_mdp_全天_無假日_two_days_daily_cap(mdp_calculator):
    result = _calc_mdp(mdp_calculator, "全天_無假日", "2024-12-19T00:00", "2024-12-21T00:00")
    assert_billing_invariants_mdp(result)
    assert result.total_amount == 400


def test_mdp_二段_平日假日_two_weekdays_daily_cap(mdp_calculator):
    result = _calc_mdp(mdp_calculator, "二段_平日假日", "2024-12-18T00:00", "2024-12-20T00:00")
    assert_billing_invariants_mdp(result)
    assert result.total_amount == 360


def test_mdp_二段_平日假日_weekend_cross_midnight(mdp_calculator):
    result = _calc_mdp(mdp_calculator, "二段_平日假日", "2024-12-21T20:00", "2024-12-22T02:00")
    assert_billing_invariants_mdp(result)
    assert result.total_amount == 144


def test_mdp_多時段_完整假日_weekend_daily_cap(mdp_calculator):
    result = _calc_mdp(mdp_calculator, "多時段_完整假日", "2024-12-21T08:00", "2024-12-21T22:00")
    assert_billing_invariants_mdp(result)
    assert result.total_amount == 420


def test_mdp_多時段_完整假日_festival_day_cap(mdp_calculator):
    result = _calc_mdp(mdp_calculator, "多時段_完整假日", "2024-12-25T08:00", "2024-12-25T20:00")
    assert_billing_invariants_mdp(result)
    assert result.total_amount == 540


def test_mdp_多時段_完整假日_two_weekdays_daily_cap(mdp_calculator):
    result = _calc_mdp(mdp_calculator, "多時段_完整假日", "2024-12-18T00:00", "2024-12-20T00:00")
    assert_billing_invariants_mdp(result)
    assert result.total_amount == 860


def test_mdp_多時段_完整假日_afternoon_only_no_morning_bleed(mdp_calculator):
    result = _calc_mdp(mdp_calculator, "多時段_完整假日", "2024-12-19T12:00", "2024-12-19T18:00")
    assert_billing_invariants_mdp(result)
    assert result.total_amount == 150
    assert len(result.session_details) == 1
    assert result.session_details[0]["label"] == "下午時段"


def test_mdp_多時段_完整假日_boundary_at_noon_splits_segments(mdp_calculator):
    result = _calc_mdp(mdp_calculator, "多時段_完整假日", "2024-12-19T11:30", "2024-12-19T12:30")
    assert_billing_invariants_mdp(result)
    assert result.total_amount == 55
    labels = [s["label"] for s in result.session_details]
    assert labels == ["上午時段", "下午時段"]
    assert sum(s["duration"] for s in result.session_details) == 60


def test_mdp_多時段_完整假日_evening_only_no_afternoon_bleed(mdp_calculator):
    result = _calc_mdp(mdp_calculator, "多時段_完整假日", "2024-12-19T18:00", "2024-12-19T22:00")
    assert_billing_invariants_mdp(result)
    assert result.total_amount == 120
    assert len(result.session_details) == 1
    assert result.session_details[0]["label"] == "傍晚時段"


def test_mdp_多時段_完整假日_full_weekday_evening_charges_after_night_morning_afternoon(
    mdp_calculator,
):
    """日上限須涵蓋四段區段上限之和，否則完整曆日傍晚會被日上限提前用盡。"""
    result = _calc_mdp(mdp_calculator, "多時段_完整假日", "2024-12-18T22:00", "2024-12-19T22:00")
    assert_billing_invariants_mdp(result)
    evening = [s for s in result.session_details if s["label"] == "傍晚時段"]
    assert evening
    assert sum(s["fee"] for s in evening) > 0
