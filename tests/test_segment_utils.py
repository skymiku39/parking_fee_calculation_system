from datetime import datetime, time

from src.domain.segment_utils import find_active_segment_at, is_time_in_segment


def test_is_time_in_segment_half_open_day_segment():
    seg = {"name": "日間", "start": "08:00", "end": "22:00"}
    assert is_time_in_segment(time(8, 0), seg) is True
    assert is_time_in_segment(time(21, 59), seg) is True
    assert is_time_in_segment(time(22, 0), seg) is False


def test_find_active_segment_cross_midnight():
    segments = [
        {"name": "夜間", "start": "22:00", "end": "08:00"},
        {"name": "日間", "start": "08:00", "end": "22:00"},
    ]
    assert find_active_segment_at(datetime(2025, 6, 20, 23, 0), segments)["name"] == "夜間"
    assert find_active_segment_at(datetime(2025, 6, 21, 7, 0), segments)["name"] == "夜間"
    assert find_active_segment_at(datetime(2025, 6, 21, 10, 0), segments)["name"] == "日間"
