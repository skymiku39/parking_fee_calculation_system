"""Resolve runtime data and bundle paths for dev and PyInstaller builds."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

DATA_ENV_VAR = "PARKING_DATA_DIR"
DEFAULT_DATA_SUBDIR = "data"
DEV_CONFIG_SUBDIR = "config"

DATA_FILES = (
    "system_config.json",
    "system_calendar.json",
    "multidimensional_rate_plans.json",
    "user_defined_plans.json",
)


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def executable_dir() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return project_root()


def bundle_dir() -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", executable_dir()))
    return project_root()


def default_seed_dir() -> Path:
    if is_frozen():
        seed = bundle_dir() / "defaults"
        if seed.is_dir():
            return seed
    return project_root() / DEV_CONFIG_SUBDIR


def resolve_data_dir() -> Path:
    override = os.getenv(DATA_ENV_VAR)
    if override:
        return Path(override).expanduser().resolve()
    if is_frozen():
        return executable_dir() / DEFAULT_DATA_SUBDIR
    return project_root() / DEV_CONFIG_SUBDIR


def ensure_data_dir(seed_if_missing: bool = True) -> Path:
    data_dir = resolve_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)

    if not seed_if_missing:
        return data_dir

    seed_dir = default_seed_dir()
    for name in DATA_FILES:
        target = data_dir / name
        if target.exists():
            continue
        source = seed_dir / name
        if source.is_file():
            shutil.copy2(source, target)
    return data_dir
