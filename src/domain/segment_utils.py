"""Shared time-segment boundary logic (single source of truth for UPE and billing resolvers)."""

from __future__ import annotations

from datetime import datetime, time
from typing import Any, Dict, List, Optional


def parse_hhmm(hhmm: str) -> time:
    if hhmm == "24:00":
        return time(23, 59, 59)
    h, m = map(int, hhmm.split(":"))
    return time(h, m)


def is_time_in_segment(t: time, seg: Dict[str, Any]) -> bool:
    """Half-open interval [start, end); adjacent boundaries belong to the next segment."""
    start_str = seg["start"]
    end_str = seg["end"]
    if end_str == "24:00":
        if start_str == "00:00":
            return True
        s = parse_hhmm(start_str)
        return t >= s
    s = parse_hhmm(start_str)
    e = parse_hhmm(end_str)
    if s <= e:
        return s <= t < e
    return t >= s or t < e


def find_active_segment_at(
    dt: datetime, segments: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    for seg in segments:
        if is_time_in_segment(dt.time(), seg):
            return seg
    return None
