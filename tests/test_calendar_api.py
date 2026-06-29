"""日曆 API 測試：讀寫、週末產生與官方同步（含錯誤分支與離線 mock）。"""

import json
from unittest.mock import patch


def test_get_calendar_returns_default_when_absent(isolated_client):
    _, client, tmp_path = isolated_client
    (tmp_path / "system_calendar.json").unlink(missing_ok=True)

    resp = client.get("/api/calendar")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["success"] is True
    assert payload["calendar"]["weekend_as_holiday"] is True


def test_save_and_reload_calendar(isolated_client):
    _, client, tmp_path = isolated_client
    save_resp = client.post(
        "/api/calendar",
        json={
            "description": "roundtrip",
            "weekend_as_holiday": False,
            "custom_holidays": ["2026-09-28"],
            "custom_workdays": [],
            "festival_holidays": [],
            "national_holidays": [],
            "weekend_holidays": [],
            "lunar_festivals": [],
            "special_events": [],
        },
    )
    assert save_resp.status_code == 200

    get_resp = client.get("/api/calendar")
    payload = get_resp.get_json()
    assert payload["calendar"]["description"] == "roundtrip"
    assert payload["calendar"]["weekend_as_holiday"] is False

    on_disk = json.loads((tmp_path / "system_calendar.json").read_text(encoding="utf-8"))
    assert on_disk["custom_holidays"] == ["2026-09-28"]


def test_generate_weekends_is_idempotent(isolated_client):
    _, client, _ = isolated_client

    first = client.post("/api/calendar/generate_weekends", json={"year": 2030})
    assert first.status_code == 200
    first_payload = first.get_json()
    assert first_payload["success"] is True
    assert first_payload["generated_year"] == 2030
    assert first_payload["added"] > 0

    second = client.post("/api/calendar/generate_weekends", json={"year": 2030})
    assert second.get_json()["added"] == 0


def test_sync_official_v2_taiwan_cdn_source(isolated_client):
    _, client, _ = isolated_client
    mock_calendar = {
        "national_holidays": [{"date": "2027-01-01", "name": "開國紀念日"}],
        "festival_holidays": [{"date": "2027-02-06", "name": "春節"}],
        "custom_workdays": ["2027-02-15"],
    }
    with patch("src.web.calendar._fetch_taiwan_cdn_holidays", return_value=mock_calendar):
        resp = client.post(
            "/api/calendar/sync_official_v2",
            json={"year": 2027, "source": "taiwan_cdn"},
        )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["success"] is True
    assert payload["added_national"] == 1
    assert payload["added_festival"] == 1
    assert payload["added_workdays"] == 1


def test_sync_official_v2_cdn_failure_returns_502(isolated_client):
    _, client, _ = isolated_client
    with patch("src.web.calendar._fetch_taiwan_cdn_holidays", return_value=None):
        resp = client.post(
            "/api/calendar/sync_official_v2",
            json={"year": 2027, "source": "taiwan_cdn"},
        )
    assert resp.status_code == 502
    assert resp.get_json()["code"] == "SYNC_FETCH_ERROR"


def test_legacy_sync_official_merges_gov_holidays(isolated_client):
    _, client, tmp_path = isolated_client
    gov_items = [
        {"date": "2028-01-01", "name": "開國紀念日"},
        {"date": "2028-02-28", "name": "和平紀念日"},
    ]
    with patch("src.web.calendar._fetch_gov_tw_official_holidays", return_value=gov_items):
        resp = client.post(
            "/api/calendar/_legacy/sync_official",
            json={"year": 2028},
        )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["success"] is True
    assert payload["source_used"] == "gov_tw"
    assert payload["added_holidays"] == 2

    saved = json.loads((tmp_path / "system_calendar.json").read_text(encoding="utf-8"))
    assert "2028-01-01" in saved["custom_holidays"]
    assert any(h["date"] == "2028-02-28" for h in saved["national_holidays"])


def test_sync_official_v2_no_new_data_sets_warning(isolated_client):
    _, client, _ = isolated_client
    empty = {"national_holidays": [], "festival_holidays": [], "custom_workdays": []}
    with patch("src.web.calendar._fetch_gov_tw_official_holidays", return_value=None), patch(
        "src.web.calendar._fetch_taiwan_cdn_holidays", return_value=empty
    ):
        resp = client.post(
            "/api/calendar/sync_official_v2",
            json={"year": 2027, "source": "taiwan_cdn"},
        )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["added"] == 0
    assert "warning" in payload


def test_sync_official_v2_gov_tw_source(isolated_client):
    _, client, tmp_path = isolated_client
    gov_items = [{"date": "2029-01-01", "name": "開國紀念日"}]
    with patch("src.web.calendar._fetch_gov_tw_official_holidays", return_value=gov_items):
        resp = client.post(
            "/api/calendar/sync_official_v2",
            json={"year": 2029, "source": "gov_tw"},
        )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["success"] is True
    assert "gov_tw" in payload["sources"]
    assert payload["added_national"] >= 1

    saved = json.loads((tmp_path / "system_calendar.json").read_text(encoding="utf-8"))
    assert any(h["date"] == "2029-01-01" for h in saved["national_holidays"])


def test_sync_official_v2_gov_tw_fetch_failure_returns_502(isolated_client):
    _, client, _ = isolated_client
    with patch("src.web.calendar._fetch_gov_tw_official_holidays", return_value=None), patch(
        "src.web.calendar._fetch_taiwan_cdn_holidays", return_value=None
    ):
        resp = client.post(
            "/api/calendar/sync_official_v2",
            json={"year": 2029, "source": "gov_tw"},
        )
    assert resp.status_code == 502
    assert resp.get_json()["code"] == "SYNC_FETCH_ERROR"


def test_get_calendar_corrupt_json_returns_500(isolated_client):
    _, client, tmp_path = isolated_client
    (tmp_path / "system_calendar.json").write_text("{broken", encoding="utf-8")
    resp = client.get("/api/calendar")
    assert resp.status_code == 500
    assert resp.get_json()["code"] == "CAL_READ_ERROR"


def test_sync_official_v2_nager_source(isolated_client):
    _, client, _ = isolated_client
    nager_payload = json.dumps(
        [{"date": "2031-01-01", "localName": "New Year's Day"}]
    ).encode("utf-8")

    class FakeResp:
        def read(self):
            return nager_payload

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    with patch("src.web.calendar.urllib.request.urlopen", return_value=FakeResp()):
        resp = client.post(
            "/api/calendar/sync_official_v2",
            json={"year": 2031, "source": "nager"},
        )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["success"] is True
    assert "nager" in payload["sources"]


def test_generate_weekends_with_corrupt_calendar_file(isolated_client):
    _, client, tmp_path = isolated_client
    (tmp_path / "system_calendar.json").write_text("{bad json", encoding="utf-8")
    resp = client.post("/api/calendar/generate_weekends", json={"year": 2032})
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True
    assert resp.get_json()["added"] > 0


def test_legacy_sync_official_falls_back_to_nager(isolated_client):
    _, client, tmp_path = isolated_client
    nager_payload = json.dumps(
        [{"date": "2033-05-01", "localName": "勞動節"}]
    ).encode("utf-8")

    class FakeResp:
        def read(self):
            return nager_payload

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    with patch("src.web.calendar._fetch_gov_tw_official_holidays", return_value=None), patch(
        "src.web.calendar.urllib.request.urlopen", return_value=FakeResp()
    ):
        resp = client.post(
            "/api/calendar/_legacy/sync_official",
            json={"year": 2033},
        )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["success"] is True
    assert payload["source_used"] == "nager"
    assert "2033-05-01" in json.loads(
        (tmp_path / "system_calendar.json").read_text(encoding="utf-8")
    )["custom_holidays"]
