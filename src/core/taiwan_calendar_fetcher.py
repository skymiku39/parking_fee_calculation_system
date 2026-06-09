from __future__ import annotations

import json
import ssl
import urllib.request
from typing import Any, Dict, List, Optional

from src.core.utils import TAIWAN_CALENDAR_CDN_URL

WORKDAY_KEYWORDS = ("補行上班", "調整上班")
FESTIVAL_KEYWORDS = (
    "春節",
    "除夕",
    "小年夜",
    "端午",
    "中秋",
    "清明",
    "兒童節",
    "民族掃墓",
    "元宵",
    "中元",
    "重陽",
    "七夕",
)


def normalize_taiwan_date(raw: Any) -> Optional[str]:
    value = str(raw or "").strip()
    if len(value) == 8 and value.isdigit():
        return f"{value[:4]}-{value[4:6]}-{value[6:8]}"
    if len(value) == 10 and value[4] == "-" and value[7] == "-":
        return value
    return None


def is_festival_description(description: str) -> bool:
    text = (description or "").strip()
    if not text:
        return False
    return any(keyword in text for keyword in FESTIVAL_KEYWORDS)


def parse_taiwan_calendar_rows(rows: List[Dict[str, Any]]) -> Dict[str, List[Any]]:
    national_holidays: List[Dict[str, str]] = []
    festival_holidays: List[Dict[str, str]] = []
    custom_workdays: List[str] = []

    for row in rows:
        date_str = normalize_taiwan_date(row.get("date"))
        if not date_str:
            continue

        description = (
            row.get("description")
            or row.get("caption")
            or row.get("name")
            or ""
        ).strip()
        is_holiday = bool(row.get("isHoliday"))

        if is_holiday and description:
            entry = {"date": date_str, "name": description}
            national_holidays.append(entry)
            if is_festival_description(description):
                festival_holidays.append(dict(entry))
            continue

        if not is_holiday and any(keyword in description for keyword in WORKDAY_KEYWORDS):
            custom_workdays.append(date_str)

    return {
        "national_holidays": national_holidays,
        "festival_holidays": festival_holidays,
        "custom_workdays": custom_workdays,
    }


def fetch_taiwan_official_calendar(year: int) -> Optional[Dict[str, List[Any]]]:
    url = TAIWAN_CALENDAR_CDN_URL.format(year=year)

    def _fetch(ctx: ssl.SSLContext) -> List[Dict[str, Any]]:
        with urllib.request.urlopen(url, context=ctx, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        if not isinstance(data, list):
            raise ValueError("Taiwan calendar payload must be a list")
        return data

    try:
        rows = _fetch(ssl.create_default_context())
    except Exception:
        try:
            insecure = ssl.create_default_context()
            insecure.check_hostname = False
            insecure.verify_mode = ssl.CERT_NONE
            rows = _fetch(insecure)
        except Exception:
            return None

    return parse_taiwan_calendar_rows(rows)
