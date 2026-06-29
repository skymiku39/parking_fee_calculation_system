"""User-defined plan billing (Single Responsibility: UPE bridge for custom plans)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Tuple

from src.core.utils import format_duration_display
from src.domain.pricing.unified_pricing_engine import UnifiedPricingEngine

if TYPE_CHECKING:
    from src.core.ports import DateCategoryResolver


class UserDefinedBillingService:
    def __init__(self, date_resolver: DateCategoryResolver) -> None:
        self._date_resolver = date_resolver

    def build_upe_plan(self, plan_data: dict) -> Dict[str, Any]:
        global_caps = dict(plan_data.get("global_caps") or {})
        if plan_data.get("global_grace_time") is not None:
            global_caps["global_grace_time"] = plan_data.get("global_grace_time", 0)
        return {
            "segment_type": plan_data.get("segment_type"),
            "holiday_type": plan_data.get("holiday_type"),
            "segments": plan_data.get("segments", []),
            "rate_matrix": plan_data.get("rate_matrix", {}),
            "global_caps": global_caps,
        }

    def date_resolver_for_plan(self, plan_data: dict):
        holiday_type = plan_data["holiday_type"]
        segments = plan_data.get("segments", [])

        def resolver(dt: datetime) -> str:
            seg = self._date_resolver.find_active_segment_at_time(dt, segments)
            if seg:
                return self._date_resolver.determine_segment_date_category(
                    dt, seg, holiday_type
                )
            return self._date_resolver.determine_date_category(dt, holiday_type)

        return resolver

    def format_session_details(
        self, upe_details: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], str]:
        session_details: List[Dict[str, Any]] = []
        summary_parts: List[str] = []
        for detail in upe_details:
            label = detail.get("label", "時段")
            time_range = detail.get("time_range", "")
            if detail.get("progressive"):
                rate_desc = "累進費率"
            else:
                unit = detail.get("unit", 60)
                rate_desc = f"{detail.get('rate', 0)}元/{unit}分"
            period = f"{label} ({time_range})" if time_range else label
            duration_minutes = int(detail.get("duration", 0) or 0)
            fee = int(detail.get("fee", 0) or 0)
            raw_fee = int(detail.get("raw_fee", fee) or fee)
            billing_explanation = detail.get("billing_explanation") or ""
            session_details.append(
                {
                    "period": period,
                    "duration": format_duration_display(duration_minutes),
                    "rate": rate_desc,
                    "amount": fee,
                    "raw_amount": raw_fee,
                    "billing_explanation": billing_explanation,
                    "segment_label": label,
                }
            )
            if billing_explanation:
                summary_parts.append(
                    f"{label}: {format_duration_display(duration_minutes)} — {fee}元（{billing_explanation}）"
                )
            else:
                summary_parts.append(
                    f"{label}: {format_duration_display(duration_minutes)} × {rate_desc} = {fee}元"
                )
        calculation_summary = " | ".join(summary_parts) if summary_parts else "無計費明細"
        return session_details, calculation_summary

    def calculate(
        self,
        enter_time: datetime,
        exit_time: datetime,
        plan_data: dict,
        manual_adjustment: int = 0,
    ) -> Dict[str, Any]:
        try:
            total_minutes = int((exit_time - enter_time).total_seconds() / 60)
            upe_plan = self.build_upe_plan(plan_data)
            upe = UnifiedPricingEngine()
            res = upe.calculate(
                enter_time,
                exit_time,
                upe_plan,
                self.date_resolver_for_plan(plan_data),
            )
            if not res.success:
                raise ValueError(res.calculation_summary)

            session_details, calculation_summary = self.format_session_details(
                res.session_details
            )
            total_amount = res.total_amount
            original_amount = res.original_amount
            global_caps = upe_plan.get("global_caps", {})
            cap_applied = original_amount > total_amount
            cap_amount = None
            if cap_applied and global_caps.get("daily_cap_amount"):
                cap_amount = int(global_caps["daily_cap_amount"])

            total_amount += manual_adjustment
            primary_date_category = self._date_resolver.determine_date_category(
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
