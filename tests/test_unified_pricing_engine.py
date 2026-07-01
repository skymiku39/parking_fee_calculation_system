"""UnifiedPricingEngine 單元測試（含每日上限）。"""

import sys
from datetime import datetime
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.core.validation import ConfigValidationError, validate_plan_v2_json
from src.domain.multidimensional_calculator import MultidimensionalParkingCalculator
from src.domain.pricing.unified_pricing_engine import UnifiedPricingEngine


def _all_day_plan_with_daily_cap(*, daily_cap_enabled: bool = True) -> dict:
    return {
        "segments": [{"name": "全天", "start": "00:00", "end": "24:00"}],
        "rate_matrix": {
            "全天_統一": {
                "unit_time": 60,
                "simple_rate": 30,
                "grace_time": 0,
                "progressive_enabled": False,
                "progressive_rates": [],
                "segment_cap_enabled": False,
                "segment_cap_amount": 0,
            }
        },
        "global_caps": {
            "daily_cap_enabled": daily_cap_enabled,
            "daily_cap_amount": 200 if daily_cap_enabled else 0,
            "global_grace_time": 15,
        },
    }


def _session_fee_sum(result) -> int:
    return sum(int(s.get("fee", 0) or 0) for s in result.session_details)


class TestUnifiedPricingEngineDailyCap:
  def test_same_day_over_cap_caps_total_and_details_match(self):
      engine = UnifiedPricingEngine()
      plan = _all_day_plan_with_daily_cap()
      enter = datetime(2025, 6, 20, 8, 0)
      exit = datetime(2025, 6, 20, 20, 0)

      result = engine.calculate(enter, exit, plan, lambda _dt: "統一")

      assert result.success is True
      assert result.total_amount == 200
      assert result.original_amount > result.total_amount
      assert _session_fee_sum(result) == result.total_amount

  def test_cross_day_over_cap_sums_per_day_caps(self):
      engine = UnifiedPricingEngine()
      plan = _all_day_plan_with_daily_cap()
      enter = datetime(2025, 6, 20, 0, 0)
      exit = datetime(2025, 6, 22, 0, 0)

      result = engine.calculate(enter, exit, plan, lambda _dt: "統一")

      assert result.success is True
      assert result.total_amount == 400
      assert _session_fee_sum(result) == result.total_amount

  def test_daily_cap_disabled_unchanged(self):
      engine = UnifiedPricingEngine()
      plan = _all_day_plan_with_daily_cap(daily_cap_enabled=False)
      enter = datetime(2025, 6, 20, 8, 0)
      exit = datetime(2025, 6, 20, 12, 0)

      result = engine.calculate(enter, exit, plan, lambda _dt: "統一")

      assert result.success is True
      assert result.total_amount == result.original_amount
      assert result.total_amount > 0

  def test_rate_matrix_key_fallback_to_unified(self):
      engine = UnifiedPricingEngine()
      plan = {
          "segments": [{"name": "全天", "start": "00:00", "end": "24:00"}],
          "rate_matrix": {
              "全天_平日": {
                  "unit_time": 60,
                  "simple_rate": 30,
                  "grace_time": 0,
                  "progressive_enabled": False,
                  "progressive_rates": [],
                  "segment_cap_enabled": False,
                  "segment_cap_amount": 0,
              }
          },
          "global_caps": {
              "daily_cap_enabled": False,
              "daily_cap_amount": 0,
              "global_grace_time": 0,
          },
      }
      enter = datetime(2025, 6, 20, 10, 0)
      exit = datetime(2025, 6, 20, 12, 0)

      result = engine.calculate(enter, exit, plan, lambda _dt: "統一")

      assert result.success is True
      assert result.total_amount == 60

  def test_segment_cap_only_per_segment_per_day(self):
      engine = UnifiedPricingEngine()
      plan = {
          "segments": [{"name": "日間", "start": "07:00", "end": "19:00"}],
          "rate_matrix": {
              "日間_統一": {
                  "unit_time": 60,
                  "simple_rate": 30,
                  "grace_time": 0,
                  "progressive_enabled": False,
                  "progressive_rates": [],
                  "segment_cap_enabled": True,
                  "segment_cap_amount": 100,
              }
          },
          "global_caps": {
              "daily_cap_enabled": False,
              "daily_cap_amount": 0,
              "global_grace_time": 0,
          },
      }
      enter = datetime(2025, 6, 20, 7, 0)
      exit = datetime(2025, 6, 20, 19, 0)

      result = engine.calculate(enter, exit, plan, lambda _dt: "統一")

      assert result.success is True
      assert result.total_amount == 100
      assert _session_fee_sum(result) == result.total_amount

  def test_segment_cap_then_daily_cap_same_day(self):
      engine = UnifiedPricingEngine()
      plan = {
          "segments": [
              {"name": "日間", "start": "07:00", "end": "18:00"},
              {"name": "夜間", "start": "18:00", "end": "07:00"},
          ],
          "rate_matrix": {
              "日間_統一": {
                  "unit_time": 60,
                  "simple_rate": 30,
                  "grace_time": 0,
                  "progressive_enabled": False,
                  "progressive_rates": [],
                  "segment_cap_enabled": True,
                  "segment_cap_amount": 100,
              },
              "夜間_統一": {
                  "unit_time": 60,
                  "simple_rate": 30,
                  "grace_time": 0,
                  "progressive_enabled": False,
                  "progressive_rates": [],
                  "segment_cap_enabled": True,
                  "segment_cap_amount": 100,
              },
          },
          "global_caps": {
              "daily_cap_enabled": True,
              "daily_cap_amount": 150,
              "global_grace_time": 0,
              "cap_priority": "segment",
          },
      }
      enter = datetime(2025, 6, 20, 7, 0)
      exit = datetime(2025, 6, 20, 23, 0)

      result = engine.calculate(enter, exit, plan, lambda _dt: "統一")

      assert result.success is True
      assert result.total_amount == 150
      assert result.original_amount == 480
      assert _session_fee_sum(result) == result.total_amount

  def test_cap_priority_daily_matches_segment_for_dual_caps(self):
      engine = UnifiedPricingEngine()
      base_plan = {
          "segments": [
              {"name": "日間", "start": "07:00", "end": "18:00"},
              {"name": "夜間", "start": "18:00", "end": "07:00"},
          ],
          "rate_matrix": {
              "日間_統一": {
                  "unit_time": 60,
                  "simple_rate": 30,
                  "grace_time": 0,
                  "progressive_enabled": False,
                  "progressive_rates": [],
                  "segment_cap_enabled": True,
                  "segment_cap_amount": 100,
              },
              "夜間_統一": {
                  "unit_time": 60,
                  "simple_rate": 30,
                  "grace_time": 0,
                  "progressive_enabled": False,
                  "progressive_rates": [],
                  "segment_cap_enabled": True,
                  "segment_cap_amount": 100,
              },
          },
      }
      enter = datetime(2025, 6, 20, 7, 0)
      exit = datetime(2025, 6, 20, 23, 0)

      seg_result = engine.calculate(
          enter,
          exit,
          {
              **base_plan,
              "global_caps": {
                  "daily_cap_enabled": True,
                  "daily_cap_amount": 150,
                  "global_grace_time": 0,
                  "cap_priority": "segment",
              },
          },
          lambda _dt: "統一",
      )
      daily_result = engine.calculate(
          enter,
          exit,
          {
              **base_plan,
              "global_caps": {
                  "daily_cap_enabled": True,
                  "daily_cap_amount": 150,
                  "global_grace_time": 0,
                  "cap_priority": "daily",
              },
          },
          lambda _dt: "統一",
      )

      assert seg_result.total_amount == 150
      assert daily_result.total_amount == 100

  def test_daily_caps_by_category_weekday_vs_holiday(self):
      engine = UnifiedPricingEngine()
      plan = {
          "segments": [{"name": "全天", "start": "00:00", "end": "24:00"}],
          "rate_matrix": {
              "全天_平日": {
                  "unit_time": 60,
                  "simple_rate": 30,
                  "grace_time": 0,
                  "progressive_enabled": False,
                  "progressive_rates": [],
                  "segment_cap_enabled": False,
                  "segment_cap_amount": 0,
              },
              "全天_假日": {
                  "unit_time": 60,
                  "simple_rate": 30,
                  "grace_time": 0,
                  "progressive_enabled": False,
                  "progressive_rates": [],
                  "segment_cap_enabled": False,
                  "segment_cap_amount": 0,
              },
          },
          "global_caps": {
              "daily_cap_enabled": True,
              "daily_cap_amount": 200,
              "global_grace_time": 0,
              "daily_caps_by_category": {
                  "平日": {"daily_cap_enabled": True, "daily_cap_amount": 200},
                  "假日": {"daily_cap_enabled": True, "daily_cap_amount": 300},
              },
          },
      }
      enter = datetime(2025, 6, 20, 0, 0)
      exit = datetime(2025, 6, 22, 0, 0)

      def resolver(dt):
          return "假日" if dt.weekday() >= 5 else "平日"

      result = engine.calculate(enter, exit, plan, resolver)

      assert result.success is True
      assert result.total_amount == 500  # 平日 200 + 假日 300
      assert _session_fee_sum(result) == result.total_amount

  def test_mdp_all_day_cross_midnight_daily_cap(self):
      calculator = MultidimensionalParkingCalculator(
          str(REPO_ROOT / "config" / "multidimensional_rate_plans.json")
      )
      enter = datetime(2024, 12, 19, 0, 0)
      exit = datetime(2024, 12, 21, 0, 0)

      result = calculator.calculate_parking_fee(enter, exit, "全天_無假日")

      assert result.total_amount == 400
      assert sum(s["fee"] for s in result.session_details) == result.total_amount


def test_user_defined_plan_daily_cap_via_api(isolated_client):
    _, client, _ = isolated_client

    response = client.post(
        "/api/calculate",
        json={
            "enter_time": "2025-06-20T08:00",
            "exit_time": "2025-06-20T20:00",
            "plan_id": "全天有上限",
        },
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["total_amount"] == 200
    assert payload["cap_applied"] is True
    detail_sum = sum(s.get("amount", 0) for s in payload.get("session_details", []))
    assert detail_sum == payload["total_amount"]


def test_reject_removed_plan_fields():
    with pytest.raises(ConfigValidationError, match="unit_pivot"):
        validate_plan_v2_json(
            {
                "name": "x",
                "segment_type": "全天",
                "holiday_type": "無假日",
                "segments": [{"name": "全天", "start": "00:00", "end": "24:00"}],
                "unit_pivot": "start",
            }
        )
    with pytest.raises(ConfigValidationError, match="segment_caps_enabled"):
        validate_plan_v2_json(
            {
                "name": "x",
                "segment_type": "全天",
                "holiday_type": "無假日",
                "segments": [{"name": "全天", "start": "00:00", "end": "24:00"}],
                "global_caps": {"segment_caps_enabled": True},
            }
        )


def test_user_defined_two_segment_daily_cap_cross_day_via_api(isolated_client):
    _, client, _ = isolated_client

    response = client.post(
        "/api/calculate",
        json={
            "enter_time": "2025-06-20T00:00",
            "exit_time": "2025-06-22T00:00",
            "plan_id": "兩段有上限",
        },
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["total_amount"] == 400
    assert payload["cap_applied"] is True
