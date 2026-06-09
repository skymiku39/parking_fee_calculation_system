import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.core.taiwan_calendar_fetcher import (
    fetch_taiwan_official_calendar,
    is_festival_description,
    normalize_taiwan_date,
    parse_taiwan_calendar_rows,
)


def test_normalize_taiwan_date():
    assert normalize_taiwan_date("20250101") == "2025-01-01"
    assert normalize_taiwan_date("2025-01-01") == "2025-01-01"
    assert normalize_taiwan_date("") is None


def test_parse_taiwan_calendar_rows_splits_holiday_types():
    rows = [
        {"date": "20250101", "isHoliday": True, "description": "開國紀念日"},
        {"date": "20250129", "isHoliday": True, "description": "春節"},
        {"date": "20250208", "isHoliday": False, "description": "補行上班"},
        {"date": "20250104", "isHoliday": True, "description": ""},
    ]
    parsed = parse_taiwan_calendar_rows(rows)

    assert len(parsed["national_holidays"]) == 2
    assert parsed["national_holidays"][0]["date"] == "2025-01-01"
    assert len(parsed["festival_holidays"]) == 1
    assert parsed["festival_holidays"][0]["name"] == "春節"
    assert parsed["custom_workdays"] == ["2025-02-08"]


def test_is_festival_description():
    assert is_festival_description("春節")
    assert not is_festival_description("開國紀念日")


@patch("src.core.taiwan_calendar_fetcher.urllib.request.urlopen")
def test_fetch_taiwan_official_calendar(mock_urlopen):
    payload = json.dumps(
        [
            {"date": "20251010", "isHoliday": True, "description": "國慶日"},
            {"date": "20250208", "isHoliday": False, "description": "補行上班"},
        ]
    ).encode("utf-8")

    class _Resp:
        def read(self):
            return payload

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    mock_urlopen.return_value = _Resp()
    parsed = fetch_taiwan_official_calendar(2025)

    assert parsed is not None
    assert parsed["national_holidays"][0]["date"] == "2025-10-10"
    assert parsed["custom_workdays"] == ["2025-02-08"]
