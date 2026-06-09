"""
停車費系統 canonical 術語定義與 deprecated alias 正規化。

自訂方案 schema 為業務概念基準；MDP / Legacy 透過 normalize 函式對齊。
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional, Tuple


class HolidayType(str, Enum):
    NO_HOLIDAY = "無假日"
    WEEKDAY_WEEKEND = "平日假日"
    FULL_HOLIDAY = "完整假日"


class SegmentType(str, Enum):
    ALL_DAY = "全天"
    TWO_SEGMENT = "二段"
    THREE_SEGMENT = "三段"
    MULTI_SEGMENT = "多時段"
    ARBITRARY = "任意段"


class DateCategory(str, Enum):
    UNIFIED = "統一"
    WEEKDAY = "平日"
    HOLIDAY = "假日"
    FESTIVAL = "節慶日"


class MdpPlanTier(str, Enum):
    """MDP 內部選擇 weekday/weekend/national/custom 方案用。"""

    UNIFIED = "unified"
    WEEKDAY = "weekday"
    WEEKEND = "weekend"
    NATIONAL_HOLIDAY = "national_holiday"
    CUSTOM_HOLIDAY = "custom_holiday"


# --- Deprecated → canonical 映射 ---

HOLIDAY_TYPE_ALIASES: Dict[str, str] = {
    "無假日費率": HolidayType.NO_HOLIDAY.value,
    "六日費率": HolidayType.WEEKDAY_WEEKEND.value,
    "國定假費率": HolidayType.FULL_HOLIDAY.value,
}

SEGMENT_TYPE_ALIASES: Dict[str, str] = {
    "兩段": SegmentType.TWO_SEGMENT.value,
    "四段": SegmentType.MULTI_SEGMENT.value,
    "自訂": SegmentType.MULTI_SEGMENT.value,
}

DATE_CATEGORY_ALIASES: Dict[str, str] = {
    "週末": DateCategory.HOLIDAY.value,
    "國定假日": DateCategory.FESTIVAL.value,
    "客製假日": DateCategory.FESTIVAL.value,
}

TEMPLATE_ID_ALIASES: Dict[str, str] = {
    "全天_無假日費率": "全天_無假日",
    "兩段_六日費率": "二段_平日假日",
    "四段_國定假費率": "多時段_完整假日",
}

LEGACY_TEMPLATE_IDS: Dict[str, str] = {v: k for k, v in TEMPLATE_ID_ALIASES.items()}

CANONICAL_HOLIDAY_TYPES: Tuple[str, ...] = tuple(h.value for h in HolidayType)
CANONICAL_SEGMENT_TYPES: Tuple[str, ...] = tuple(s.value for s in SegmentType)
CANONICAL_DATE_CATEGORIES: Tuple[str, ...] = tuple(d.value for d in DateCategory)

DEPRECATED_HOLIDAY_TYPES = frozenset(HOLIDAY_TYPE_ALIASES.keys())
DEPRECATED_SEGMENT_TYPES = frozenset(SEGMENT_TYPE_ALIASES.keys())
DEPRECATED_DATE_CATEGORIES = frozenset(DATE_CATEGORY_ALIASES.keys())


def normalize_holiday_type(value: Optional[str]) -> str:
    if not value:
        return HolidayType.NO_HOLIDAY.value
    if value in CANONICAL_HOLIDAY_TYPES:
        return value
    if value in HOLIDAY_TYPE_ALIASES:
        return HOLIDAY_TYPE_ALIASES[value]
    return value


def normalize_segment_type(value: Optional[str]) -> str:
    if not value:
        return SegmentType.ALL_DAY.value
    if value in CANONICAL_SEGMENT_TYPES:
        return value
    if value in SEGMENT_TYPE_ALIASES:
        return SEGMENT_TYPE_ALIASES[value]
    return value


def normalize_date_category(value: Optional[str]) -> str:
    if not value:
        return DateCategory.WEEKDAY.value
    if value in CANONICAL_DATE_CATEGORIES:
        return value
    if value in DATE_CATEGORY_ALIASES:
        return DATE_CATEGORY_ALIASES[value]
    return value


def normalize_template_id(template_id: Optional[str]) -> str:
    if not template_id:
        return template_id or ""
    if template_id in TEMPLATE_ID_ALIASES:
        return TEMPLATE_ID_ALIASES[template_id]
    return template_id


def resolve_template_id(template_id: Optional[str], legacy_map: Optional[Dict[str, str]] = None) -> str:
    """Accept canonical or legacy template_id."""
    if not template_id:
        return ""
    canonical = normalize_template_id(template_id)
    combined = {**TEMPLATE_ID_ALIASES, **(legacy_map or {})}
    if template_id in combined:
        return combined[template_id]
    reverse = {v: k for k, v in combined.items()}
    if template_id in reverse:
        return template_id
    return canonical


def build_template_id(segment_type: str, holiday_type: str) -> str:
    seg = normalize_segment_type(segment_type)
    hol = normalize_holiday_type(holiday_type)
    return f"{seg}_{hol}"


def date_categories_for_holiday_type(holiday_type: str) -> List[str]:
    hol = normalize_holiday_type(holiday_type)
    if hol == HolidayType.NO_HOLIDAY.value:
        return [DateCategory.UNIFIED.value]
    if hol == HolidayType.FULL_HOLIDAY.value:
        return [
            DateCategory.WEEKDAY.value,
            DateCategory.HOLIDAY.value,
            DateCategory.FESTIVAL.value,
        ]
    return [DateCategory.WEEKDAY.value, DateCategory.HOLIDAY.value]


def mdp_plan_tier_to_date_category(tier: MdpPlanTier, holiday_type: str) -> str:
    """Map internal MDP plan tier to canonical date category for display."""
    hol = normalize_holiday_type(holiday_type)
    if tier == MdpPlanTier.UNIFIED or hol == HolidayType.NO_HOLIDAY.value:
        return DateCategory.UNIFIED.value
    if tier == MdpPlanTier.WEEKDAY:
        return DateCategory.WEEKDAY.value
    if tier in (MdpPlanTier.NATIONAL_HOLIDAY, MdpPlanTier.CUSTOM_HOLIDAY):
        if hol == HolidayType.FULL_HOLIDAY.value:
            return DateCategory.FESTIVAL.value if tier == MdpPlanTier.NATIONAL_HOLIDAY else DateCategory.HOLIDAY.value
        return DateCategory.HOLIDAY.value
    if tier == MdpPlanTier.WEEKEND:
        return DateCategory.HOLIDAY.value
    return DateCategory.WEEKDAY.value


def migrate_rate_matrix_key(key: str) -> str:
    """Rename deprecated date suffix in rate_matrix keys."""
    if "_" not in key:
        return key
    prefix, suffix = key.rsplit("_", 1)
    new_suffix = normalize_date_category(suffix)
    return f"{prefix}_{new_suffix}"


def collect_deprecated_warnings(obj: dict, path: str = "") -> List[str]:
    """Scan config dict for deprecated terminology values."""
    warnings: List[str] = []

    def _walk(node, p: str):
        if isinstance(node, dict):
            for k, v in node.items():
                cp = f"{p}.{k}" if p else k
                if k == "legacy_template_ids":
                    continue
                if k == "holiday_type" and isinstance(v, str) and v in DEPRECATED_HOLIDAY_TYPES:
                    warnings.append(f"{cp}: deprecated holiday_type '{v}' → use '{HOLIDAY_TYPE_ALIASES[v]}'")
                elif k in ("segment_type", "time_segment_type") and isinstance(v, str) and v in DEPRECATED_SEGMENT_TYPES:
                    warnings.append(f"{cp}: deprecated segment '{v}' → use '{SEGMENT_TYPE_ALIASES[v]}'")
                elif k == "template_id" and isinstance(v, str) and v in TEMPLATE_ID_ALIASES:
                    warnings.append(f"{cp}: deprecated template_id '{v}' → use '{TEMPLATE_ID_ALIASES[v]}'")
                _walk(v, cp)
        elif isinstance(node, list):
            for i, item in enumerate(node):
                _walk(item, f"{p}[{i}]")

    _walk(obj, path)
    return warnings
