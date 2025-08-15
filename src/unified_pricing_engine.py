from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, time
from typing import Any, Dict, List, Optional, Tuple


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

    def _parse_hhmm(self, hhmm: str) -> time:
        if hhmm == "24:00":
            return time(23, 59, 59)
        h, m = map(int, hhmm.split(":"))
        return time(h, m)

    def _is_in_segment(self, t: time, seg: Dict[str, Any]) -> bool:
        s = self._parse_hhmm(seg["start"])
        e = self._parse_hhmm(seg["end"])
        if s <= e:
            return s <= t <= e
        return t >= s or t <= e

    def _find_active_segment(self, dt: datetime, segments: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        for seg in segments:
            if self._is_in_segment(dt.time(), seg):
                return seg
        return None

    def _segment_key(self, seg_name: str, date_category: str) -> str:
        return f"{seg_name}_{date_category}"

    def _calc_progressive(self, minutes: int, rates: List[Dict[str, Any]], unit_time: int) -> int:
        remaining = minutes
        total = 0
        for r in rates:
            duration = int((r.get("duration_minutes") or unit_time) // unit_time)
            rate = int(r.get("rate") or 0)
            if remaining <= 0:
                break
            units = min(math.ceil(remaining / unit_time), duration)
            total += units * rate
            remaining -= units * unit_time
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

            # 日期類別：預設由 enter_time 判斷；可注入 resolver 供外部客製（含國定/週末等）
            if date_category_resolver:
                date_category = date_category_resolver(enter_time)
            else:
                # 簡化：週末/平日
                date_category = "假日" if enter_time.weekday() >= 5 else "平日"

            current = enter_time
            global_grace = int(global_caps.get("global_grace_time", 0) or 0)
            global_grace_used = False if global_grace > 0 else True
            cycles: List[Dict[str, Any]] = []
            total_fee = 0
            # 每日+時段累計 key
            cap_acc: Dict[str, int] = {}

            while current < exit_time:
                seg = self._find_active_segment(current, segments)
                if not seg:
                    current += timedelta(minutes=1)
                    continue
                key = self._segment_key(seg["name"], date_category)
                cfg = rate_matrix.get(key) or {}
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

                # 區段上限（每日累計）
                if cfg.get("segment_cap_enabled") and int(cfg.get("segment_cap_amount") or 0) > 0:
                    day_key = f"{current.date()}_{seg['name']}_{date_category}"
                    acc = cap_acc.get(day_key, 0)
                    cap_amount = int(cfg.get("segment_cap_amount") or 0)
                    if acc + fee > cap_amount:
                        fee = max(0, cap_amount - acc)
                    cap_acc[day_key] = acc + fee

                total_fee += fee
                cycles.append({
                    "segment": seg["name"],
                    "time_range": f"{current.strftime('%H:%M')}-{cycle_end.strftime('%H:%M')}",
                    "minutes": cycle_minutes,
                    "billed_minutes": billed_minutes,
                    "unit": unit,
                    "rate": simple_rate,
                    "fee": fee,
                    "progressive": bool(cfg.get("progressive_enabled")),
                })

                current = cycle_end

            # 全域每日上限
            daily_cap_enabled = bool(global_caps.get("daily_cap_enabled", False))
            daily_cap_amount = int(global_caps.get("daily_cap_amount", 0) or 0)
            is_daily_capped = False
            if daily_cap_enabled and daily_cap_amount > 0 and total_fee > daily_cap_amount:
                total_fee = daily_cap_amount
                is_daily_capped = True

            # 合併相鄰同 segment 的顯示
            session_details: List[Dict[str, Any]] = []
            if cycles:
                grp = None
                for c in cycles:
                    if grp is None:
                        grp = dict(label=c["segment"], time_range=c["time_range"], duration=c["minutes"], fee=c["fee"])
                    else:
                        if grp["label"] == c["segment"] and grp["time_range"].split('-')[-1] == c["time_range"].split('-')[0]:
                            # 連續
                            start = grp["time_range"].split('-')[0]
                            end = c["time_range"].split('-')[1]
                            grp["time_range"] = f"{start}-{end}"
                            grp["duration"] += c["minutes"]
                            grp["fee"] += c["fee"]
                        else:
                            session_details.append(grp)
                            grp = dict(label=c["segment"], time_range=c["time_range"], duration=c["minutes"], fee=c["fee"])
                if grp:
                    session_details.append(grp)

            summary = f"總費用: {total_fee} 元；每日上限: {'是' if is_daily_capped else '否'} ({daily_cap_amount}元)"

            return UnifiedEngineResult(
                success=True,
                total_amount=total_fee,
                original_amount=sum(c["fee"] for c in cycles),
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



