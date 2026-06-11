import json
import sys
from datetime import date, datetime
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.core.calendar_resolver import HolidayCalendar
from src.core.system import SmartParkingSystem
from src.domain.terminology import DateCategory
from src.domain.multidimensional_calculator import MultidimensionalParkingCalculator


@pytest.fixture
def calendar_file(tmp_path: Path) -> Path:
    path = tmp_path / "system_calendar.json"
    path.write_text(
        json.dumps(
            {
                "weekend_as_holiday": True,
                "custom_workdays": ["2025-02-08"],
                "custom_holidays": ["2025-02-02"],
                "national_holidays": [
                    {"date": "2025-01-01", "name": "元旦"},
                    {"date": "2025-10-10", "name": "國慶日"},
                ],
                "festival_holidays": [
                    {"date": "2025-12-25", "name": "聖誕節"},
                    {"date": "2025-02-14", "name": "情人節"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def test_holiday_calendar_classifies_festival_and_national(calendar_file: Path):
    cal = HolidayCalendar(calendar_file)

    assert cal.classify_user_defined_date(date(2025, 12, 25), "完整假日") == "節慶日"
    assert cal.classify_user_defined_date(date(2025, 1, 1), "完整假日") == "節慶日"
    assert cal.classify_user_defined_date(date(2025, 2, 14), "平日假日") == "假日"
    assert cal.classify_user_defined_date(date(2025, 2, 8), "平日假日") == "平日"
    assert cal.classify_mdp_date(date(2025, 12, 25), []) == "custom_holiday"
    assert cal.classify_mdp_date(date(2025, 1, 1), []) == "national_holiday"
    assert cal.classify_date(date(2025, 12, 25), "完整假日") == "節慶日"


def test_smart_parking_system_uses_calendar_for_user_defined(tmp_path: Path, calendar_file: Path):
    system = SmartParkingSystem(base_path=tmp_path)
    category = system.determine_date_category(
        datetime(2025, 12, 25, 10, 0),
        "完整假日",
    )
    assert category == "節慶日"


def test_multidimensional_calculator_reads_calendar(
    tmp_path: Path,
    calendar_file: Path,
):
    repo_root = Path(__file__).resolve().parents[1]
    import shutil

    shutil.copy2(
        repo_root / "config" / "multidimensional_rate_plans.json",
        tmp_path / "multidimensional_rate_plans.json",
    )

    cal = HolidayCalendar(calendar_file)
    calculator = MultidimensionalParkingCalculator(
        str(tmp_path / "multidimensional_rate_plans.json"),
        holiday_calendar=cal,
    )

    assert calculator.get_date_category(date(2025, 10, 10), "完整假日") == DateCategory.FESTIVAL
    assert calculator.get_date_category(date(2025, 12, 25), "完整假日") == DateCategory.FESTIVAL
    # MDP dimension_configs 的 custom_holidays 應在行事曆未登錄時仍生效
    assert calculator.get_date_category(date(2024, 12, 25), "完整假日") == DateCategory.FESTIVAL
    assert (
        calculator._mdp_billing_category(date(2025, 10, 10), "完整假日")
        == "國定假日"
    )
    assert (
        calculator._mdp_billing_category(date(2024, 12, 25), "完整假日")
        == DateCategory.FESTIVAL.value
    )

    result = calculator.calculate_parking_fee(
        datetime(2025, 10, 10, 8, 0),
        datetime(2025, 10, 10, 20, 0),
        "多時段_完整假日",
    )
    assert result.total_amount == 451


def test_classify_date_honors_extra_custom_holidays(calendar_file: Path):
    cal = HolidayCalendar(calendar_file)
    assert (
        cal.classify_date(
            date(2024, 12, 25),
            "完整假日",
            extra_custom_holidays=["2024-12-25"],
        )
        == DateCategory.FESTIVAL.value
    )
