"""Application version (dev: pyproject.toml; frozen: bundled VERSION file)."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from src.core.paths import bundle_dir, is_frozen, project_root


@lru_cache(maxsize=1)
def get_version() -> str:
    if is_frozen():
        version_file = bundle_dir() / "VERSION"
        if version_file.is_file():
            return version_file.read_text(encoding="utf-8").strip()

    pyproject = project_root() / "pyproject.toml"
    if pyproject.is_file():
        text = pyproject.read_text(encoding="utf-8")
        match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
        if match:
            return match.group(1)
    return "0.0.0"


__version__ = get_version()
