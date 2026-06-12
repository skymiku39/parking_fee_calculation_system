from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from src.core.validation import validate_multidimensional_config_json


class MdpConfigRepository:
    """Single Responsibility: multidimensional_rate_plans.json persistence."""

    def __init__(self, base_path: Path) -> None:
        self._path = base_path / "multidimensional_rate_plans.json"

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> Dict[str, Any]:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def save(self, data: Dict[str, Any], *, validate: bool = True) -> None:
        if validate:
            try:
                validate_multidimensional_config_json(data)
            except Exception:
                pass
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
