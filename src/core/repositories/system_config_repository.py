from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

from src.core.utils import validate_and_normalize_system_config

logger = logging.getLogger(__name__)


class SystemConfigRepository:
    """Single Responsibility: system_config.json persistence."""

    def __init__(self, base_path: Path) -> None:
        self._path = base_path / "system_config.json"

    @property
    def path(self) -> Path:
        return self._path

    def load_raw(self) -> Dict[str, Any]:
        if not self._path.exists():
            return {}
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.exception("載入系統配置失敗: %s", e)
            return {}

    def load_persisted(self) -> Dict[str, Any]:
        return validate_and_normalize_system_config(
            self.load_raw(),
            include_env_overrides=False,
        )

    def load_runtime(self, persisted: Dict[str, Any]) -> Dict[str, Any]:
        return validate_and_normalize_system_config(persisted)

    def save(self, persisted_config: Dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(persisted_config, f, ensure_ascii=False, indent=2)
