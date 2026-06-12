from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from src.domain.segment_utils import find_active_segment_at


@dataclass
class UnifiedEngineResult:
    success: bool
    total_amount: int
    original_amount: int
    session_details: List[Dict[str, Any]]
    calculation_summary: str


class UnifiedPricingEngine:
    """
    Unified Pricing Engine (UPE)

    支援：
    - 以收費週期為核心的切片（unit_time），跨日與時段邊界依週期起點規則
    - 全域免費時間（global_grace_time）與時段免費時間（grace_time or grace_enabled/grace_minutes）
    - 區段上限（segment_cap_enabled / segment_cap_amount）每日累計
    - 全域每日上限（global_caps.daily_cap_enabled / daily_cap_amount）
    - MDP 可依日期類別設定日上限（global_caps.daily_caps_by_category）
    - 封頂順序由 global_caps.cap_priority 控制（segment|daily|lower|higher）
    - 收費週期以進場時間對齊 unit_time 起點
    - 累進費率（progressive_enabled / progressive_rates）

    預期輸入 plan 結構（精簡）：
    {
      "segment_type": "全天|二段|三段|任意",
      "holiday_type": "無假日|平日假日|完整假日",
      "segments": [{"name":"日間","start":"08:00","end":"22:00"}, ...],
      "rate_matrix": {
        "{segment_name}_{date_category}": {
          "unit_time": 60,
          "simple_rate": 30,
          "grace_time": 15,
          "progressive_enabled": false,
          "progressive_rates": [],
          "segment_cap_enabled": false,
          "segment_cap_amount": 0
        }
      },
      "global_caps": {"daily_cap_enabled": true, "daily_cap_amount": 200, "global_grace_time": 0}
    }
    """

    def __init__(self) -> None:
        pass

    def _segment_key(self, seg_name: str, date_category: str) -> str:
        return f"{seg_name}_{date_category}"

    def _resolve_daily_cap(
        self, global_caps: Dict[str, Any], date_category: str
    ) -> Tuple[bool, int]:
        """依 date_category 解析日上限；支援 MDP 的 daily_caps_by_category。"""
        by_cat = global_caps.get("daily_caps_by_category")
        if by_cat:
            cfg = by_cat.get(date_category)
            if cfg is None:
                for suffix in ("統一", "平日", "假日", "節慶日", "國定假日", "客製假日"):
                    fb = by_cat.get(suffix)
                    if fb is not None:
                        cfg = fb
                        break
            if cfg is not None:
                return (
                    bool(cfg.get("daily_cap_enabled", False)),
                    int(cfg.get("daily_cap_amount", 0) or 0),
                )
        return (
            bool(global_caps.get("daily_cap_enabled", False)),
            int(global_caps.get("daily_cap_amount", 0) or 0),
        )

    def _resolve_rate_config(
        self, rate_matrix: Dict[str, Any], seg_name: str, date_category: str
    ) -> Tuple[str, Dict[str, Any]]:
        key = self._segment_key(seg_name, date_category)
        if key in rate_matrix:
            return key, rate_matrix[key]
        for suffix in (
            date_category,
            "統一",
            "平日",
            "假日",
            "節慶日",
            "國定假日",
            "客製假日",
        ):
            fb_key = self._segment_key(seg_name, suffix)
            if fb_key in rate_matrix:
                return fb_key, rate_matrix[fb_key]
        return key, {}

    def _cap_priority(self, global_caps: Dict[str, Any]) -> str:
        priority = global_caps.get("cap_priority") or "segment"
        if priority not in ("daily", "segment", "lower", "higher"):
            return "segment"
        return priority

    def _build_billing_explanation(
        self,
        raw_fee: int,
        fee: int,
        *,
        progressive: bool,
        cycles_count: int,
        billed_minutes: int,
        unit: int,
        rate: int,
        seg_cap_enabled: bool,
        seg_cap_amount: int,
        daily_cap_enabled: bool,
        daily_cap_amount: int,
    ) -> str:
        """產生單段明細的計費說明（牌價、週期數、封頂原因）。"""
        parts: List[str] = []
        if progressive:
            parts.append("累進費率，非固定單價×時數")
        elif unit > 0 and rate >= 0 and (billed_minutes > 0 or cycles_count > 0):
            cycle_est = cycles_count if cycles_count > 0 else (
                math.ceil(billed_minutes / unit) if unit else 0
            )
            naive = cycle_est * rate
            if raw_fee > 0:
                parts.append(
                    f"牌價 {raw_fee} 元（{cycle_est} 個計費週期 × {rate} 元"
                    + (f"，與時數估算 {naive} 元一致" if naive == raw_fee else "")
                    + "）"
                )
            elif fee == 0:
                parts.append("寬限時間內免收費")

        if raw_fee > fee:
            cap_parts: List[str] = []
            if seg_cap_enabled and seg_cap_amount > 0:
                cap_parts.append(f"區段上限 {seg_cap_amount} 元")
            if daily_cap_enabled and daily_cap_amount > 0:
                cap_parts.append(f"日上限 {daily_cap_amount} 元")
            if cap_parts:
                parts.append(f"實收 {fee} 元（已達{'、'.join(cap_parts)}）")
            else:
                parts.append(f"實收 {fee} 元（已封頂）")
        elif fee == 0 and raw_fee > 0:
            parts.append("累計已達封頂，本段不另收費")
        elif not progressive and fee > 0 and raw_fee == fee and cycles_count > 1:
            parts.append(f"共 {cycles_count} 個計費週期，無封頂")

        return "；".join(parts)

    def _apply_segment_cap_fee(
        self,
        fee: int,
        cap_acc: Dict[str, int],
        seg_day_key: str,
        cap_amount: int,
    ) -> int:
        acc = cap_acc.get(seg_day_key, 0)
        if acc + fee > cap_amount:
            fee = max(0, cap_amount - acc)
        cap_acc[seg_day_key] = acc + fee
        return fee

    def _apply_daily_cap_fee(
        self,
        fee: int,
        daily_cap_acc: Dict[str, int],
        day_key: str,
        cap_amount: int,
    ) -> int:
        acc = daily_cap_acc.get(day_key, 0)
        if acc + fee > cap_amount:
            fee = max(0, cap_amount - acc)
        daily_cap_acc[day_key] = acc + fee
        return fee

    def _apply_caps_ordered(
        self,
        fee: int,
        cap_acc: Dict[str, int],
        daily_cap_acc: Dict[str, int],
        seg_day_key: str,
        day_key: str,
        seg_cap_amount: int,
        daily_cap_amount: int,
        order: str,
    ) -> int:
        if order == "daily":
            fee = self._apply_daily_cap_fee(fee, daily_cap_acc, day_key, daily_cap_amount)
            fee = self._apply_segment_cap_fee(fee, cap_acc, seg_day_key, seg_cap_amount)
        else:
            fee = self._apply_segment_cap_fee(fee, cap_acc, seg_day_key, seg_cap_amount)
            fee = self._apply_daily_cap_fee(fee, daily_cap_acc, day_key, daily_cap_amount)
        return fee

    def _simulate_caps_ordered(
        self,
        fee: int,
        cap_acc: Dict[str, int],
        daily_cap_acc: Dict[str, int],
        seg_day_key: str,
        day_key: str,
        seg_cap_amount: int,
        daily_cap_amount: int,
        order: str,
    ) -> int:
        seg_acc = dict(cap_acc)
        daily_acc = dict(daily_cap_acc)
        return self._apply_caps_ordered(
            fee,
            seg_acc,
            daily_acc,
            seg_day_key,
            day_key,
            seg_cap_amount,
            daily_cap_amount,
            order,
        )

    def _apply_dual_caps(
        self,
        fee: int,
        cap_acc: Dict[str, int],
        daily_cap_acc: Dict[str, int],
        seg_day_key: str,
        day_key: str,
        seg_cap_amount: int,
        daily_cap_amount: int,
        global_caps: Dict[str, Any],
    ) -> int:
        priority = self._cap_priority(global_caps)
        if priority == "lower":
            fee_sd = self._simulate_caps_ordered(
                fee,
                cap_acc,
                daily_cap_acc,
                seg_day_key,
                day_key,
                seg_cap_amount,
                daily_cap_amount,
                "segment",
            )
            fee_ds = self._simulate_caps_ordered(
                fee,
                cap_acc,
                daily_cap_acc,
                seg_day_key,
                day_key,
                seg_cap_amount,
                daily_cap_amount,
                "daily",
            )
            order = "segment" if fee_sd <= fee_ds else "daily"
        elif priority == "higher":
            fee_sd = self._simulate_caps_ordered(
                fee,
                cap_acc,
                daily_cap_acc,
                seg_day_key,
                day_key,
                seg_cap_amount,
                daily_cap_amount,
                "segment",
            )
            fee_ds = self._simulate_caps_ordered(
                fee,
                cap_acc,
                daily_cap_acc,
                seg_day_key,
                day_key,
                seg_cap_amount,
                daily_cap_amount,
                "daily",
            )
            order = "segment" if fee_sd >= fee_ds else "daily"
        else:
            order = priority
        return self._apply_caps_ordered(
            fee,
            cap_acc,
            daily_cap_acc,
            seg_day_key,
            day_key,
            seg_cap_amount,
            daily_cap_amount,
            order,
        )

    def _calc_progressive(self, minutes: int, rates: List[Dict[str, Any]], unit_time: int) -> int:
        """
        支援兩類資料格式：
        - { duration_minutes, rate }
        - { duration, rate, unit } （向後相容 user_defined_plans 中的結構）
        規則：每層以單位向上取整，扣除掉前層時間後繼續計算。
        """
        remaining = minutes
        total = 0
        for r in rates:
            duration_minutes = r.get("duration_minutes")
            if duration_minutes is None:
                # 兼容舊鍵名
                duration_minutes = r.get("duration") or unit_time
            rate = int((r.get("rate") if r.get("rate") is not None else r.get("unit_price") or 0))
            tier_unit = int((r.get("unit_time") if r.get("unit_time") is not None else r.get("unit") or unit_time))
            if remaining <= 0:
                break
            # 可用單位數（以 tier_unit 作為收費單位）
            tier_units_cap = max(1, int(duration_minutes // tier_unit)) if duration_minutes else math.ceil(remaining / tier_unit)
            units = min(math.ceil(remaining / tier_unit), tier_units_cap)
            total += units * rate
            remaining -= units * tier_unit
        return total

    def calculate(
        self,
        enter_time: datetime,
        exit_time: datetime,
        plan: Dict[str, Any],
        date_category_resolver: Optional[Any] = None,
    ) -> UnifiedEngineResult:
        try:
            segments: List[Dict[str, Any]] = plan.get("segments", [])
            rate_matrix: Dict[str, Any] = plan.get("rate_matrix", {})
            global_caps: Dict[str, Any] = plan.get("global_caps", {})

            current = enter_time
            global_grace = int(global_caps.get("global_grace_time", 0) or 0)
            global_grace_used = False if global_grace > 0 else True
            cycles: List[Dict[str, Any]] = []
            total_fee = 0
            original_fee = 0
            # 每日+時段累計 key
            cap_acc: Dict[str, int] = {}
            daily_cap_acc: Dict[str, int] = {}
            is_daily_capped = False

            while current < exit_time:
                seg = find_active_segment_at(current, segments)
                if not seg:
                    current += timedelta(minutes=1)
                    continue
                if date_category_resolver:
                    date_category = date_category_resolver(current)
                else:
                    date_category = "假日" if current.weekday() >= 5 else "平日"
                _, cfg = self._resolve_rate_config(rate_matrix, seg["name"], date_category)
                unit = int(cfg.get("unit_time", 60) or 60)
                simple_rate = int(cfg.get("simple_rate", 0) or 0)
                cycle_end = min(current + timedelta(minutes=unit), exit_time)
                cycle_minutes = int((cycle_end - current).total_seconds() / 60)
                if cycle_minutes <= 0:
                    break

                # 有全域免費，於第一個週期使用；否則使用時段免費
                effective_grace = 0
                if not global_grace_used and global_grace > 0:
                    effective_grace = global_grace
                    global_grace_used = True
                elif cfg.get("grace_time") is not None:
                    effective_grace = int(cfg.get("grace_time") or 0)

                billed_minutes = max(0, cycle_minutes - effective_grace)
                if billed_minutes <= 0:
                    fee = 0
                else:
                    if cfg.get("progressive_enabled") and cfg.get("progressive_rates"):
                        fee = self._calc_progressive(billed_minutes, cfg.get("progressive_rates", []), unit)
                    else:
                        fee = math.ceil(billed_minutes / unit) * simple_rate

                original_fee += fee

                seg_cap_enabled = bool(cfg.get("segment_cap_enabled")) and int(
                    cfg.get("segment_cap_amount") or 0
                ) > 0
                seg_cap_amount = int(cfg.get("segment_cap_amount") or 0)
                daily_cap_enabled, daily_cap_amount = self._resolve_daily_cap(
                    global_caps, date_category
                )
                seg_day_key = f"{current.date()}_{seg['name']}_{date_category}"
                day_key = str(current.date())
                pre_cap_fee = fee

                if seg_cap_enabled and daily_cap_enabled and daily_cap_amount > 0:
                    fee = self._apply_dual_caps(
                        fee,
                        cap_acc,
                        daily_cap_acc,
                        seg_day_key,
                        day_key,
                        seg_cap_amount,
                        daily_cap_amount,
                        global_caps,
                    )
                elif seg_cap_enabled:
                    fee = self._apply_segment_cap_fee(
                        fee, cap_acc, seg_day_key, seg_cap_amount
                    )
                elif daily_cap_enabled and daily_cap_amount > 0:
                    fee = self._apply_daily_cap_fee(
                        fee, daily_cap_acc, day_key, daily_cap_amount
                    )

                if daily_cap_enabled and daily_cap_amount > 0 and fee < pre_cap_fee:
                    is_daily_capped = True

                total_fee += fee
                cycles.append({
                    "segment": seg["name"],
                    "time_range": f"{current.strftime('%H:%M')}-{cycle_end.strftime('%H:%M')}",
                    "minutes": cycle_minutes,
                    "billed_minutes": billed_minutes,
                    "unit": unit,
                    "rate": simple_rate,
                    "raw_fee": pre_cap_fee,
                    "fee": fee,
                    "progressive": bool(cfg.get("progressive_enabled")),
                    "seg_cap_enabled": seg_cap_enabled,
                    "seg_cap_amount": seg_cap_amount if seg_cap_enabled else 0,
                    "daily_cap_enabled": daily_cap_enabled,
                    "daily_cap_amount": daily_cap_amount if daily_cap_enabled else 0,
                })

                current = cycle_end

            # 合併相鄰同 segment 的顯示
            session_details: List[Dict[str, Any]] = []
            if cycles:
                grp = None
                for c in cycles:
                    if grp is None:
                        grp = dict(
                            label=c["segment"],
                            time_range=c["time_range"],
                            duration=c["minutes"],
                            billed_minutes=c["billed_minutes"],
                            raw_fee=c["raw_fee"],
                            fee=c["fee"],
                            rate=c["rate"],
                            unit=c["unit"],
                            progressive=c["progressive"],
                            cycles_count=1,
                            seg_cap_enabled=c["seg_cap_enabled"],
                            seg_cap_amount=c["seg_cap_amount"],
                            daily_cap_enabled=c["daily_cap_enabled"],
                            daily_cap_amount=c["daily_cap_amount"],
                        )
                    else:
                        if grp["label"] == c["segment"] and grp["time_range"].split('-')[-1] == c["time_range"].split('-')[0]:
                            start = grp["time_range"].split('-')[0]
                            end = c["time_range"].split('-')[1]
                            grp["time_range"] = f"{start}-{end}"
                            grp["duration"] += c["minutes"]
                            grp["billed_minutes"] += c["billed_minutes"]
                            grp["raw_fee"] += c["raw_fee"]
                            grp["fee"] += c["fee"]
                            grp["cycles_count"] += 1
                        else:
                            session_details.append(grp)
                            grp = dict(
                                label=c["segment"],
                                time_range=c["time_range"],
                                duration=c["minutes"],
                                billed_minutes=c["billed_minutes"],
                                raw_fee=c["raw_fee"],
                                fee=c["fee"],
                                rate=c["rate"],
                                unit=c["unit"],
                                progressive=c["progressive"],
                                cycles_count=1,
                                seg_cap_enabled=c["seg_cap_enabled"],
                                seg_cap_amount=c["seg_cap_amount"],
                                daily_cap_enabled=c["daily_cap_enabled"],
                                daily_cap_amount=c["daily_cap_amount"],
                            )
                if grp:
                    session_details.append(grp)

            for s in session_details:
                s["billing_explanation"] = self._build_billing_explanation(
                    int(s.get("raw_fee", 0) or 0),
                    int(s.get("fee", 0) or 0),
                    progressive=bool(s.get("progressive")),
                    cycles_count=int(s.get("cycles_count", 1) or 1),
                    billed_minutes=int(s.get("billed_minutes", 0) or 0),
                    unit=int(s.get("unit", 60) or 60),
                    rate=int(s.get("rate", 0) or 0),
                    seg_cap_enabled=bool(s.get("seg_cap_enabled")),
                    seg_cap_amount=int(s.get("seg_cap_amount", 0) or 0),
                    daily_cap_enabled=bool(s.get("daily_cap_enabled")),
                    daily_cap_amount=int(s.get("daily_cap_amount", 0) or 0),
                )

            cap_note = (
                "依日期類別"
                if global_caps.get("daily_caps_by_category")
                else str(
                    int(global_caps.get("daily_cap_amount", 0) or 0)
                )
            )
            summary = (
                f"總費用: {total_fee} 元；每日上限: "
                f"{'是' if is_daily_capped else '否'} ({cap_note})"
            )

            return UnifiedEngineResult(
                success=True,
                total_amount=total_fee,
                original_amount=original_fee,
                session_details=session_details,
                calculation_summary=summary,
            )
        except Exception as e:
            return UnifiedEngineResult(
                success=False,
                total_amount=0,
                original_amount=0,
                session_details=[],
                calculation_summary=f"計算失敗: {e}",
            )




