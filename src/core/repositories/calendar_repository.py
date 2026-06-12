from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


class CalendarRepository:
    """Single Responsibility: system_calendar.json persistence."""

    DEFAULT_CALENDAR: Dict[str, Any] = {
        "description": "",
        "weekend_as_holiday": True,
        "custom_holidays": [],
        "custom_workdays": [],
        "festival_holidays": [],
        "national_holidays": [],
        "weekend_holidays": [],
        "lunar_festivals": [],
        "special_events": [],
    }

    def __init__(self, base_path: Path) -> None:
        self._path = base_path / "system_calendar.json"

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> Dict[str, Any]:
        if not self._path.exists():
            return dict(self.DEFAULT_CALENDAR)
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return dict(self.DEFAULT_CALENDAR)

    def save(self, data: Dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
