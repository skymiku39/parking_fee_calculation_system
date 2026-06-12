from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from src.core.validation import validate_user_defined_plans_json


class UserPlansRepository:
    """Single Responsibility: user_defined_plans.json persistence."""

    def __init__(self, base_path: Path) -> None:
        self._path = base_path / "user_defined_plans.json"

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> Dict[str, Any]:
        if not self._path.exists():
            return {"plans": {}, "metadata": {}}
        with open(self._path, "r", encoding="utf-8") as f:
            config_obj = json.load(f)
        validate_user_defined_plans_json(config_obj)
        return config_obj

    def save(self, config_obj: Dict[str, Any]) -> None:
        validate_user_defined_plans_json(config_obj)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(config_obj, f, ensure_ascii=False, indent=2)
