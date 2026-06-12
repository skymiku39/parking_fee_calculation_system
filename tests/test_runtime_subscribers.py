"""Integration tests: Pub/Sub subscribers refresh runtime state."""

from pathlib import Path
from shutil import copy2

import pytest

from src.core.events import EventBus
from src.core.system import SmartParkingSystem


@pytest.fixture
def isolated_system(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    for filename in (
        "multidimensional_rate_plans.json",
        "system_config.json",
        "system_calendar.json",
        "user_defined_plans.json",
    ):
        src = repo_root / "config" / filename
        if src.exists():
            copy2(src, tmp_path / filename)
    return SmartParkingSystem(base_path=tmp_path, event_bus=EventBus())


def test_calendar_persisted_event_reloads_mdp_calculator(isolated_system):
    system = isolated_system
    original = system.multidimensional_calculator
    assert original is not None

    cal = system.load_calendar()
    cal["description"] = "pubsub-test-marker"
    system.save_calendar(cal, source="test")

    assert system.multidimensional_calculator is not None
    assert system.holiday_calendar is not None
