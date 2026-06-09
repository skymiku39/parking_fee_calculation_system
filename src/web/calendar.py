import json
import ssl
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from src.core.context import parking_system
from src.core.taiwan_calendar_fetcher import fetch_taiwan_official_calendar
from src.web.utils import error_response
from src.core.utils import NAGER_BASE_URL


calendar_bp = Blueprint("calendar_bp", __name__)


def _calendar_file() -> Path:
    base_path = getattr(parking_system, "base_path", Path("."))
    return Path(base_path) / "system_calendar.json"


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


def _date_key(entry: Any) -> Optional[str]:
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        value = entry.get("date")
        return str(value).strip() if value else None
    return None


def _merge_named_entries(
    cal: Dict[str, Any],
    field: str,
    items: List[Dict[str, Any]],
    source_tag: str,
) -> int:
    cal.setdefault(field, [])
    existing = {_date_key(item) for item in cal[field]}
    added = 0
    for item in items:
        date_str = item.get("date")
        if not date_str or date_str in existing:
            continue
        cal[field].append(
            {"date": date_str, "name": item.get("name"), "source": source_tag}
        )
        existing.add(date_str)
        added += 1
    return added


def _merge_workdays(cal: Dict[str, Any], dates: List[str]) -> int:
    cal.setdefault("custom_workdays", [])
    existing = set(cal["custom_workdays"])
    added = 0
    for date_str in dates:
        if date_str and date_str not in existing:
            cal["custom_workdays"].append(date_str)
            existing.add(date_str)
            added += 1
    return added


def _load_calendar_defaults(cal: Dict[str, Any], year: int) -> None:
    cal.setdefault("description", f"官方假日 {year}")
    cal.setdefault("weekend_as_holiday", True)
    cal.setdefault("custom_holidays", [])
    cal.setdefault("custom_workdays", [])
    cal.setdefault("festival_holidays", [])
    cal.setdefault("lunar_festivals", [])
    cal.setdefault("national_holidays", [])
    cal.setdefault("weekend_holidays", [])
    cal.setdefault("special_events", [])


def _fetch_taiwan_cdn_holidays(year: int) -> Optional[Dict[str, List[Any]]]:
    return fetch_taiwan_official_calendar(year)


@calendar_bp.route("/api/calendar", methods=["GET", "POST"])
def api_calendar():
    calendar_file = _calendar_file()
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
            try:
                parking_system.reload_holiday_calendar()
                parking_system.init_multidimensional_calculator()
            except Exception:
                pass
            return jsonify({"success": True, "message": "calendar saved"})
        except Exception as e:
            return error_response("CAL_WRITE_ERROR", str(e), 500)


@calendar_bp.route("/api/calendar/sync_official_v2", methods=["POST"])
def api_calendar_sync_official_v2():
    try:
        payload = request.get_json() or {}
        year = int(payload.get("year") or datetime.now().year)
        mode = (payload.get("source") or "gov_tw").lower()

        used_sources: List[str] = []
        national_items: List[Dict[str, Any]] = []
        festival_items: List[Dict[str, Any]] = []
        workday_items: List[str] = []

        def absorb_taiwan_calendar(source_tag: str) -> bool:
            parsed = _fetch_taiwan_cdn_holidays(year)
            if not parsed:
                return False
            used_sources.append(source_tag)
            national_items.extend(parsed.get("national_holidays", []))
            festival_items.extend(parsed.get("festival_holidays", []))
            workday_items.extend(parsed.get("custom_workdays", []))
            return True

        if mode in ("gov_tw", "both"):
            gov = _fetch_gov_tw_official_holidays(year)
            if gov:
                used_sources.append("gov_tw")
                national_items.extend(gov)
                festival_items.extend(gov)
            elif absorb_taiwan_calendar("taiwan_cdn"):
                pass
            elif mode == "gov_tw":
                return error_response(
                    "SYNC_FETCH_ERROR",
                    "無法取得台灣官方行事曆，請確認網路連線或稍後再試",
                    502,
                )

        if mode in ("taiwan_cdn", "cdn"):
            if not absorb_taiwan_calendar("taiwan_cdn"):
                return error_response(
                    "SYNC_FETCH_ERROR",
                    "無法從 TaiwanCalendar CDN 取得官方行事曆",
                    502,
                )

        if mode in ("nager", "both") and mode != "both":
            try:
                ctx = ssl.create_default_context()
                with urllib.request.urlopen(
                    NAGER_BASE_URL.format(year=year),
                    context=ctx,
                    timeout=20,
                ) as resp:
                    raw = resp.read().decode("utf-8")
                if raw.strip():
                    data = json.loads(raw)
                    items = [
                        {
                            "date": it.get("date"),
                            "name": (it.get("localName") or it.get("name")),
                        }
                        for it in data
                    ]
                    if items:
                        used_sources.append("nager")
                        national_items.extend(items)
            except Exception as e:
                return error_response("SYNC_FETCH_ERROR", f"抓取 Nager 失敗: {e}", 500)

        if mode == "both" and "taiwan_cdn" not in used_sources and "gov_tw" not in used_sources:
            absorb_taiwan_calendar("taiwan_cdn")

        calendar_file = _calendar_file()
        cal: Dict[str, Any] = {}
        if calendar_file.exists():
            try:
                cal = json.loads(calendar_file.read_text(encoding="utf-8"))
            except Exception:
                cal = {}

        _load_calendar_defaults(cal, year)

        source_tag = used_sources[0] if used_sources else mode
        added_national = _merge_named_entries(
            cal, "national_holidays", national_items, source_tag
        )
        added_festival = _merge_named_entries(
            cal, "festival_holidays", festival_items, source_tag
        )
        added_workdays = _merge_workdays(cal, workday_items)
        added_total = added_national + added_festival + added_workdays

        calendar_file.parent.mkdir(parents=True, exist_ok=True)
        calendar_file.write_text(json.dumps(cal, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            parking_system.reload_holiday_calendar()
            parking_system.init_multidimensional_calculator()
        except Exception:
            pass

        response: Dict[str, Any] = {
            "success": True,
            "synced_year": year,
            "sources": used_sources,
            "added": added_total,
            "added_national": added_national,
            "added_festival": added_festival,
            "added_workdays": added_workdays,
        }
        if added_total == 0:
            response["warning"] = (
                "本次未新增任何假日資料，可能該年度資料已存在，或外部來源暫時無法提供"
            )
        return jsonify(response)
    except Exception as e:
        return error_response("SYNC_INTERNAL_ERROR", str(e), 500)


@calendar_bp.route("/api/calendar/_legacy/sync_official", methods=["POST"])
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

        calendar_file = _calendar_file()
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
        try:
            parking_system.reload_holiday_calendar()
            parking_system.init_multidimensional_calculator()
        except Exception:
            pass

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

        calendar_file = _calendar_file()
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
        try:
            parking_system.reload_holiday_calendar()
            parking_system.init_multidimensional_calculator()
        except Exception:
            pass

        return jsonify({"success": True, "generated_year": year, "added": added})
    except Exception as e:
        return error_response("WEEKEND_GEN_ERROR", str(e), 500)
