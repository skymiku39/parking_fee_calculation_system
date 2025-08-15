from __future__ import annotations

from typing import Dict, List, Optional
from pydantic import BaseModel, Field, validator


class Segment(BaseModel):
    name: str
    start: str  # HH:MM or 24:00
    end: str    # HH:MM or 24:00

    @validator("start", "end")
    def _validate_hhmm(cls, v: str) -> str:
        if v == "24:00":
            return v
        parts = v.split(":")
        if len(parts) != 2:
            raise ValueError("時間格式需為 HH:MM 或 24:00")
        hh, mm = parts
        if not (hh.isdigit() and mm.isdigit()):
            raise ValueError("時間格式需為 HH:MM 或 24:00")
        h, m = int(hh), int(mm)
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError("時間數值不合法")
        return v


class ProgressiveRate(BaseModel):
    # 接受多種鍵：duration_minutes 或 duration；unit_time 或 unit
    duration_minutes: Optional[int] = Field(default=None)
    duration: Optional[int] = Field(default=None)
    rate: int = Field(default=0, ge=0)
    unit_time: Optional[int] = Field(default=None)
    unit: Optional[int] = Field(default=None)

    @property
    def resolved_duration_minutes(self) -> int:
        return int(self.duration_minutes if self.duration_minutes is not None else self.duration or 0)

    @property
    def resolved_unit_time(self) -> int:
        return int(self.unit_time if self.unit_time is not None else self.unit or 60)


class RateConfig(BaseModel):
    unit_time: int = Field(default=60, ge=1)
    progressive_enabled: bool = Field(default=False)
    progressive_rates: List[ProgressiveRate] = Field(default_factory=list)
    simple_rate: Optional[int] = Field(default=None, ge=0)
    segment_cap_enabled: bool = Field(default=False)
    segment_cap_amount: Optional[int] = Field(default=None, ge=0)
    grace_time: Optional[int] = Field(default=None, ge=0)

    @validator("progressive_rates", always=True)
    def _validate_progressive_vs_simple(cls, v, values):
        if values.get("progressive_enabled"):
            # 若啟用累進，允許 simple_rate 為 None
            if not v:
                raise ValueError("累進費率已啟用但未提供任何階段")
        else:
            # 未啟用累進時，需提供 simple_rate
            simple = values.get("simple_rate")
            if simple is None:
                raise ValueError("未啟用累進時需要 simple_rate")
        return v


class GlobalCaps(BaseModel):
    daily_cap_enabled: bool = Field(default=False)
    daily_cap_amount: Optional[int] = Field(default=None, ge=0)
    segment_caps_enabled: Optional[bool] = Field(default=None)
    cap_priority: Optional[str] = Field(default=None)
    global_grace_time: int = Field(default=0, ge=0)


class PlanV2(BaseModel):
    name: str
    segment_type: str  # "全天" | "二段" | "三段" | "任意段" | "多時段"
    holiday_type: str  # "無假日" | "平日假日" | "完整假日"
    segments: List[Segment]
    rate_matrix: Dict[str, RateConfig] = Field(default_factory=dict)
    global_caps: GlobalCaps = Field(default_factory=GlobalCaps)
    version: str = Field(default="2.0")

    @validator("segment_type")
    def _validate_segment_type(cls, v: str) -> str:
        allowed = {"全天", "二段", "三段", "任意段", "多時段"}
        if v not in allowed:
            raise ValueError(f"segment_type 僅支援 {sorted(allowed)}")
        return v

    @validator("holiday_type")
    def _validate_holiday_type(cls, v: str) -> str:
        allowed = {"無假日", "平日假日", "完整假日"}
        if v not in allowed:
            raise ValueError(f"holiday_type 僅支援 {sorted(allowed)}")
        return v


