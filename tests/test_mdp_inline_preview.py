"""MDP inline preview must not mutate loaded template registry."""

from datetime import datetime
from pathlib import Path
from shutil import copy2

import pytest

from src.core.system import SmartParkingSystem


@pytest.fixture
def system(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    for filename in (
        "multidimensional_rate_plans.json",
        "system_config.json",
        "system_calendar.json",
    ):
        src = repo_root / "config" / filename
        if src.exists():
            copy2(src, tmp_path / filename)
    return SmartParkingSystem(base_path=tmp_path)


def test_inline_preview_does_not_mutate_templates(system):
    calc = system.multidimensional_calculator
    assert calc is not None
    keys_before = set(calc.rate_plan_templates.keys())

    template = {
        "template_id": "_preview_probe",
        "label": "probe",
        "description": "probe",
        "segment_type": "全天",
        "holiday_type": "無假日",
        "unified_plan": {
            "label": "probe",
            "time_slots": [
                {
                    "time_slot_id": "all",
                    "label": "全天",
                    "start": "00:00",
                    "end": "24:00",
                    "unit_minutes": 60,
                    "grace_minutes": 0,
                    "grace_enabled": False,
                    "cap_enabled": False,
                    "cap_amount": 0,
                    "progressive_enabled": False,
                    "default_unit_price": 30,
                    "progressive_rates": [],
                }
            ],
            "global_caps": {"global_grace_time": 0},
        },
    }

    result = calc.calculate_with_inline_template(
        datetime(2025, 6, 20, 10, 0),
        datetime(2025, 6, 20, 12, 0),
        template,
    )

    assert result.total_amount >= 0
    assert set(calc.rate_plan_templates.keys()) == keys_before
    assert "_preview_probe" not in calc.rate_plan_templates
