#!/usr/bin/env python3
"""Migrate config files to canonical terminology."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.domain.terminology import (
    TEMPLATE_ID_ALIASES,
    build_template_id,
    migrate_rate_matrix_key,
    normalize_holiday_type,
    normalize_segment_type,
)


def _migrate_dimension_configs(dim_cfg: dict) -> dict:
    out = copy.deepcopy(dim_cfg)
    ts_types = out.get("time_segments", {}).get("types", {})
    new_ts = {}
    for key, val in ts_types.items():
        nk = normalize_segment_type(key)
        new_ts[nk] = val
    if new_ts:
        out.setdefault("time_segments", {})["types"] = new_ts

    hol_types = out.get("holiday_types", {}).get("types", {})
    new_hol = {}
    for key, val in hol_types.items():
        nk = normalize_holiday_type(key)
        new_hol[nk] = val
    if new_hol:
        out.setdefault("holiday_types", {})["types"] = new_hol
    return out


def _migrate_mdp_template(tpl: dict) -> dict:
    t = copy.deepcopy(tpl)
    old_id = t.get("template_id", "")
    seg = normalize_segment_type(t.get("segment_type") or t.get("time_segment_type", "全天"))
    hol = normalize_holiday_type(t.get("holiday_type", "無假日"))
    new_id = build_template_id(seg, hol)

    t["template_id"] = new_id
    t["segment_type"] = seg
    t["holiday_type"] = hol
    t.pop("time_segment_type", None)
    return t, old_id, new_id


def migrate_multidimensional_config(data: dict) -> tuple[dict, dict]:
    result = copy.deepcopy(data)
    legacy_map: dict[str, str] = dict(TEMPLATE_ID_ALIASES)

    if "dimension_configs" in result:
        result["dimension_configs"] = _migrate_dimension_configs(result["dimension_configs"])

    migrated = []
    for tpl in result.get("rate_plan_templates", []):
        new_tpl, old_id, new_id = _migrate_mdp_template(tpl)
        if old_id and old_id != new_id:
            legacy_map[old_id] = new_id
        migrated.append(new_tpl)
    result["rate_plan_templates"] = migrated

    meta = result.setdefault("metadata", {})
    existing = meta.get("legacy_template_ids", {})
    existing.update(legacy_map)
    meta["legacy_template_ids"] = existing
    result["version"] = "3.1"
    return result, legacy_map


def migrate_user_defined_plans(data: dict) -> dict:
    result = copy.deepcopy(data)
    plans = result.get("plans", {})
    for plan_id, plan in plans.items():
        if "segment_type" in plan:
            plan["segment_type"] = normalize_segment_type(plan["segment_type"])
        if "holiday_type" in plan:
            plan["holiday_type"] = normalize_holiday_type(plan["holiday_type"])
        rm = plan.get("rate_matrix", {})
        if rm:
            new_rm = {}
            for key, val in rm.items():
                new_rm[migrate_rate_matrix_key(key)] = val
            plan["rate_matrix"] = new_rm
    return result


def migrate_system_templates(data: dict) -> dict:
    result = copy.deepcopy(data)
    mdp = result.get("templates", {}).get("multidimensional_basic", {})
    if "time_segment_types" in mdp:
        mdp["time_segment_types"] = [
            normalize_segment_type(v) for v in mdp["time_segment_types"]
        ]
    if "holiday_types" in mdp:
        mdp["holiday_types"] = [normalize_holiday_type(v) for v in mdp["holiday_types"]]
    return result


def main():
    parser = argparse.ArgumentParser(description="Migrate configs to canonical terminology")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without writing")
    args = parser.parse_args()

    config_dir = ROOT / "config"
    tasks = [
        ("multidimensional_rate_plans.json", migrate_multidimensional_config),
        ("user_defined_plans.json", migrate_user_defined_plans),
        ("system_templates.json", migrate_system_templates),
    ]

    for filename, migrator in tasks:
        path = config_dir / filename
        if not path.exists():
            print(f"{filename}: SKIP (missing)")
            continue
        raw = json.loads(path.read_text(encoding="utf-8"))
        if filename == "multidimensional_rate_plans.json":
            migrated, legacy = migrator(raw)
            print(f"{filename}: migrated {len(legacy)} legacy template_id mappings")
        else:
            migrated = migrator(raw)
            print(f"{filename}: OK")
        if args.dry_run:
            print(json.dumps(migrated, ensure_ascii=False, indent=2)[:500], "...")
        else:
            path.write_text(
                json.dumps(migrated, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"{filename}: written")


if __name__ == "__main__":
    main()
