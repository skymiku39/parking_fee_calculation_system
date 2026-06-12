"""Abstract ports (interfaces) for Dependency Inversion."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol


class ConfigRepository(Protocol):
    """Persistence port for JSON configuration files."""

    def load(self) -> Dict[str, Any]: ...

    def save(self, data: Dict[str, Any]) -> None: ...

    @property
    def path(self) -> Path: ...


class DateCategoryResolver(Protocol):
    """Resolves billing date categories for user-defined plans."""

    def determine_date_category(self, check_time: datetime, holiday_type: str) -> str: ...

    def find_active_segment_at_time(
        self, check_time: datetime, segments: List[dict]
    ) -> Optional[dict]: ...

    def determine_segment_date_category(
        self, current_time: datetime, segment: dict, holiday_type: str
    ) -> str: ...


class FeeCalculationStrategy(Protocol):
    """Open/Closed: new billing engines register without changing the orchestrator."""

    def supports(self, plan_id: str) -> bool: ...

    def calculate(
        self,
        enter_time: datetime,
        exit_time: datetime,
        plan_id: str,
        manual_adjustment: int = 0,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]: ...
