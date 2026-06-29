"""Repository 持久化測試：讀寫、檔案缺失與毀損 JSON 的容錯行為。"""

import json

import pytest

from src.core.repositories import (
    CalendarRepository,
    MdpConfigRepository,
    SystemConfigRepository,
    UserPlansRepository,
)
from src.core.validation import ConfigValidationError


def test_calendar_repository_returns_default_when_missing(tmp_path):
    repo = CalendarRepository(tmp_path)
    data = repo.load()
    assert data["weekend_as_holiday"] is True
    assert data["custom_holidays"] == []


def test_calendar_repository_roundtrip(tmp_path):
    repo = CalendarRepository(tmp_path)
    repo.save({"description": "demo", "custom_holidays": ["2026-01-01"]})
    reloaded = repo.load()
    assert reloaded["description"] == "demo"
    assert reloaded["custom_holidays"] == ["2026-01-01"]


def test_calendar_repository_corrupt_json_falls_back_to_default(tmp_path):
    repo = CalendarRepository(tmp_path)
    repo.path.write_text("{ not valid json", encoding="utf-8")
    data = repo.load()
    assert data == CalendarRepository.DEFAULT_CALENDAR


def test_mdp_repository_returns_empty_when_missing(tmp_path):
    repo = MdpConfigRepository(tmp_path)
    assert repo.load() == {}


def test_mdp_repository_corrupt_json_returns_empty(tmp_path):
    repo = MdpConfigRepository(tmp_path)
    repo.path.write_text("<broken>", encoding="utf-8")
    assert repo.load() == {}


def test_mdp_repository_roundtrip(tmp_path):
    repo = MdpConfigRepository(tmp_path)
    repo.save({"rate_plan_templates": []})
    assert repo.load() == {"rate_plan_templates": []}


def test_user_plans_repository_returns_skeleton_when_missing(tmp_path):
    repo = UserPlansRepository(tmp_path)
    data = repo.load()
    assert data == {"plans": {}, "metadata": {}}


def test_user_plans_repository_rejects_invalid_schema(tmp_path):
    repo = UserPlansRepository(tmp_path)
    with pytest.raises(ConfigValidationError):
        repo.save({"plans": {"bad": {"name": "x"}}})


def test_user_plans_repository_roundtrip(tmp_path):
    repo = UserPlansRepository(tmp_path)
    config = {
        "plans": {
            "demo": {
                "name": "demo",
                "segment_type": "全天",
                "holiday_type": "無假日",
                "segments": [{"name": "全天", "start": "00:00", "end": "24:00"}],
            }
        },
        "metadata": {},
    }
    repo.save(config)
    assert repo.load()["plans"]["demo"]["name"] == "demo"


def test_system_config_repository_returns_empty_raw_when_missing(tmp_path):
    repo = SystemConfigRepository(tmp_path)
    assert repo.load_raw() == {}


def test_system_config_repository_normalizes_persisted(tmp_path):
    repo = SystemConfigRepository(tmp_path)
    repo.save({"currency_symbol": "USD", "ui_settings": {"max_user_plans_display": 7}})
    persisted = repo.load_persisted()
    assert persisted["currency_symbol"] == "USD"
    assert persisted["ui_settings"]["max_user_plans_display"] == 7


def test_system_config_repository_corrupt_json_returns_empty(tmp_path):
    repo = SystemConfigRepository(tmp_path)
    repo.path.write_text("{bad", encoding="utf-8")
    assert repo.load_raw() == {}
    on_disk = repo.path.read_text(encoding="utf-8")
    assert on_disk == "{bad"  # load 不應改寫毀損檔案


def test_system_config_repository_save_persists_json(tmp_path):
    repo = SystemConfigRepository(tmp_path)
    repo.save({"system_mode": "multidimensional"})
    raw = json.loads(repo.path.read_text(encoding="utf-8"))
    assert raw["system_mode"] == "multidimensional"
