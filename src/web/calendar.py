import json
import ssl
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request, send_from_directory

from src.core.context import parking_system
from src.web.utils import error_response
from src.core.utils import NAGER_BASE_URL


calendar_bp = Blueprint("calendar_bp", __name__)


def _fetch_gov_tw_official_holidays(year: int) -> Optional[List[Dict[str, Any]]]:
    api_url = (
        parking_system.system_config.get("official_calendar_api")
        if isinstance(parking_system.system_config, dict)
        else None
    )
    if not api_url:
        return None

    def _fetch(ctx: ssl.SSLContext) -> Optional[List[Dict[str, Any]]]:
        with urllib.request.urlopen(f"{api_url}?year={year}", context=ctx, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        items: List[Dict[str, Any]] = []
        for row in (data if isinstance(data, list) else data.get("result", [])):
            d = row.get("date") or row.get("Date") or row.get("date_str")
            nm = row.get("name") or row.get("Name") or row.get("holiday_name")
            if d:
                items.append({"date": d, "name": nm or "假日"})
        return items

    try:
        return _fetch(ssl.create_default_context())
    except Exception:
        try:
            insecure = ssl.create_default_context()
            insecure.check_hostname = False
            insecure.verify_mode = ssl.CERT_NONE
            return _fetch(insecure)
        except Exception:
            return None


@calendar_bp.route("/api/calendar", methods=["GET", "POST"])
def api_calendar():
    calendar_file = Path("config/system_calendar.json")
    if request.method == "GET":
        if calendar_file.exists():
            try:
                return jsonify({
                    "success": True,
                    "calendar": json.loads(calendar_file.read_text(encoding="utf-8")),
                })
            except Exception as e:
                return error_response("CAL_READ_ERROR", str(e), 500)
        return jsonify(
            {
                "success": True,
                "calendar": {
                    "description": "",
                    "weekend_as_holiday": True,
                    "custom_holidays": [],
                    "custom_workdays": [],
                    "festival_holidays": [],
                    "national_holidays": [],
                    "weekend_holidays": [],
                    "lunar_festivals": [],
                    "special_events": [],
                },
            }
        )
    else:
        try:
            data = request.get_json() or {}
            calendar_file.parent.mkdir(parents=True, exist_ok=True)
            calendar_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            return jsonify({"success": True, "message": "calendar saved"})
        except Exception as e:
            return error_response("CAL_WRITE_ERROR", str(e), 500)


@calendar_bp.route("/api/calendar/sync_official_v2", methods=["POST"])
def api_calendar_sync_official_v2():
    try:
        payload = request.get_json() or {}
        year = int(payload.get("year") or datetime.now().year)
        mode = (payload.get("source") or "both").lower()

        holidays: List[Dict[str, Any]] = []
        used_sources: List[str] = []

        def add_items(items: Optional[List[Dict[str, Any]]], tag: str):
            if not items:
                return
            for it in items:
                d = it.get("date")
                nm = it.get("name") or tag
                if d:
                    holidays.append({"date": d, "name": nm, "source": tag})

        if mode in ("gov_tw", "both"):
            gov = _fetch_gov_tw_official_holidays(year)
            if gov:
                used_sources.append("gov_tw")
                add_items(gov, "gov_tw")

        if mode in ("nager", "both") and (mode != "nager" or not holidays):
            try:
                ctx = ssl.create_default_context()
                with urllib.request.urlopen(
                    NAGER_BASE_URL.format(year=year),
                    context=ctx,
                    timeout=20,
                ) as resp:
                    raw = resp.read().decode("utf-8")
                data = json.loads(raw)
                items = [{"date": it.get("date"), "name": (it.get("localName") or it.get("name"))} for it in data]
                used_sources.append("nager")
                add_items(items, "nager")
            except Exception:
                try:
                    insecure = ssl.create_default_context()
                    insecure.check_hostname = False
                    insecure.verify_mode = ssl.CERT_NONE
                    with urllib.request.urlopen(
                        NAGER_BASE_URL.format(year=year),
                        context=insecure,
                        timeout=20,
                    ) as resp:
                        raw = resp.read().decode("utf-8")
                    data = json.loads(raw)
                    items = [{"date": it.get("date"), "name": (it.get("localName") or it.get("name"))} for it in data]
                    used_sources.append("nager")
                    add_items(items, "nager")
                except Exception as e:
                    if mode == "nager":
                        return error_response("SYNC_FETCH_ERROR", f"抓取 Nager 失敗: {e}", 500)

        calendar_file = Path("config/system_calendar.json")
        cal: Dict[str, Any] = {}
        if calendar_file.exists():
            try:
                cal = json.loads(calendar_file.read_text(encoding="utf-8"))
            except Exception:
                cal = {}

        cal.setdefault("description", f"官方假日 {year}")
        cal.setdefault("weekend_as_holiday", True)
        cal.setdefault("custom_holidays", [])
        cal.setdefault("custom_workdays", [])
        cal.setdefault("festival_holidays", [])
        cal.setdefault("lunar_festivals", [])
        cal.setdefault("national_holidays", [])
        cal.setdefault("weekend_holidays", [])
        cal.setdefault("special_events", [])

        existing_dates = set(d if isinstance(d, str) else d.get("date") for d in cal.get("national_holidays", []))
        for h in holidays:
            d = h.get("date")
            if not d:
                continue
            if d not in existing_dates:
                cal["national_holidays"].append({"date": d, "name": h.get("name"), "source": h.get("source")})
                existing_dates.add(d)

        calendar_file.parent.mkdir(parents=True, exist_ok=True)
        calendar_file.write_text(json.dumps(cal, ensure_ascii=False, indent=2), encoding="utf-8")

        return jsonify({
            "success": True,
            "synced_year": year,
            "sources": used_sources,
            "added": len(holidays),
        })
    except Exception as e:
        return error_response("SYNC_INTERNAL_ERROR", str(e), 500)


@calendar_bp.route("/api/calendar/sync_official", methods=["POST"])
def api_calendar_sync_official():
    try:
        payload = request.get_json() or {}
        year = int(payload.get("year") or datetime.now().year)

        official_items = _fetch_gov_tw_official_holidays(year)
        source_used = "gov_tw" if official_items is not None else "nager"
        holidays: List[Dict[str, Any]] = []

        if official_items is not None:
            holidays = official_items
        else:
            def _fetch_nager(ctx: ssl.SSLContext):
                with urllib.request.urlopen(
                    NAGER_BASE_URL.format(year=year),
                    context=ctx,
                    timeout=20,
                ) as resp:
                    raw = resp.read().decode("utf-8")
                data = json.loads(raw)
                for it in data:
                    d = it.get("date")
                    nm = it.get("localName") or it.get("name")
                    if d:
                        holidays.append({"date": d, "name": nm or "假日"})

            try:
                _fetch_nager(ssl.create_default_context())
            except Exception:
                try:
                    insecure = ssl.create_default_context()
                    insecure.check_hostname = False
                    insecure.verify_mode = ssl.CERT_NONE
                    _fetch_nager(insecure)
                except Exception as e:
                    return error_response("SYNC_FETCH_ERROR", f"抓取假日失敗: {e}", 500)

        custom_holidays: List[str] = []
        festival_holidays: List[Any] = []
        national_holidays: List[Any] = []
        for h in holidays:
            d = h.get("date")
            if d:
                custom_holidays.append(d)
                entry = {"date": d, "name": h.get("name")}
                festival_holidays.append(entry)
                national_holidays.append(entry)

        calendar_file = Path("config/system_calendar.json")
        if calendar_file.exists():
            try:
                cal = json.loads(calendar_file.read_text(encoding="utf-8"))
            except Exception:
                cal = {}
        else:
            cal = {}

        cal.setdefault("description", f"{('政府資料' if source_used=='gov_tw' else 'Nager.Date')} TW {year} 公眾假期")
        cal.setdefault("weekend_as_holiday", True)
        cal.setdefault("custom_holidays", [])
        cal.setdefault("custom_workdays", [])
        cal.setdefault("festival_holidays", [])
        cal.setdefault("lunar_festivals", [])
        cal.setdefault("national_holidays", [])
        cal.setdefault("weekend_holidays", [])
        cal.setdefault("special_events", [])

        existing_h = set(cal.get("custom_holidays", []))
        for d in custom_holidays:
            if d not in existing_h:
                cal["custom_holidays"].append(d)

        existing_f = {
            (f["date"] if isinstance(f, dict) and "date" in f else f)
            for f in cal.get("festival_holidays", [])
        }
        for f in festival_holidays:
            key = f.get("date")
            if key and key not in existing_f:
                cal["festival_holidays"].append(f)

        existing_n = {
            (f["date"] if isinstance(f, dict) and "date" in f else f)
            for f in cal.get("national_holidays", [])
        }
        for f in national_holidays:
            key = f.get("date")
            if key and key not in existing_n:
                cal["national_holidays"].append(f)

        calendar_file.parent.mkdir(parents=True, exist_ok=True)
        calendar_file.write_text(
            json.dumps(cal, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        return jsonify(
            {
                "success": True,
                "synced_year": year,
                "source_used": source_used,
                "added_holidays": len(custom_holidays),
            }
        )
    except Exception as e:
        return error_response("SYNC_INTERNAL_ERROR", str(e), 500)


@calendar_bp.route("/api/calendar/generate_weekends", methods=["POST"])
def api_calendar_generate_weekends():
    try:
        payload = request.get_json() or {}
        year = int(payload.get("year") or datetime.now().year)

        first_day = datetime(year, 1, 1)
        last_day = datetime(year, 12, 31)
        d = first_day
        weekends: List[str] = []
        while d <= last_day:
            if d.weekday() >= 5:
                weekends.append(d.strftime("%Y-%m-%d"))
            d += timedelta(days=1)

        calendar_file = Path("config/system_calendar.json")
        if calendar_file.exists():
            try:
                cal = json.loads(calendar_file.read_text(encoding="utf-8"))
            except Exception:
                cal = {}
        else:
            cal = {}

        cal.setdefault("description", cal.get("description", ""))
        cal.setdefault("weekend_as_holiday", True)
        cal.setdefault("custom_holidays", [])
        cal.setdefault("custom_workdays", [])
        cal.setdefault("festival_holidays", [])
        cal.setdefault("national_holidays", [])
        cal.setdefault("weekend_holidays", [])
        cal.setdefault("lunar_festivals", [])
        cal.setdefault("special_events", [])

        existing_w = set(cal.get("weekend_holidays", []))
        added = 0
        for dt in weekends:
            if dt not in existing_w:
                cal["weekend_holidays"].append(dt)
                added += 1

        calendar_file.parent.mkdir(parents=True, exist_ok=True)
        calendar_file.write_text(json.dumps(cal, ensure_ascii=False, indent=2), encoding="utf-8")

        return jsonify({"success": True, "generated_year": year, "added": added})
    except Exception as e:
        return error_response("WEEKEND_GEN_ERROR", str(e), 500)


