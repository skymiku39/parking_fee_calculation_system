from typing import Dict, Any, List

from jsonschema import validate
from jsonschema.exceptions import ValidationError

from src.domain.terminology import (
    CANONICAL_HOLIDAY_TYPES,
    CANONICAL_SEGMENT_TYPES,
)


class ConfigValidationError(Exception):
    def __init__(self, message: str, errors: List[str] = None):
        super().__init__(message)
        self.errors = errors or []


def _assert(condition: bool, message: str):
    if not condition:
        raise ConfigValidationError(message)


SEGMENT_TYPE_SCHEMA = {
    "type": "string",
    "enum": list(CANONICAL_SEGMENT_TYPES),
}

HOLIDAY_TYPE_SCHEMA = {
    "type": "string",
    "enum": list(CANONICAL_HOLIDAY_TYPES),
}


USER_DEFINED_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "plans": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "required": [
                    "name",
                    "segment_type",
                    "holiday_type",
                    "segments",
                ],
                "properties": {
                    "name": {"type": "string", "minLength": 1},
                    "segment_type": SEGMENT_TYPE_SCHEMA,
                    "holiday_type": HOLIDAY_TYPE_SCHEMA,
                    "segments": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "required": ["name", "start", "end"],
                            "properties": {
                                "name": {"type": "string", "minLength": 1},
                                "start": {"type": "string", "pattern": "^\\d{2}:\\d{2}$"},
                                "end": {
                                    "type": "string",
                                    "pattern": "^(\\d{2}:\\d{2}|24:00)$",
                                },
                            },
                        },
                    },
                    "rate_matrix": {"type": "object"},
                    "global_caps": {"type": "object"},
                    "global_grace_time": {"type": "number"},
                },
                "additionalProperties": True,
            },
        },
        "metadata": {"type": "object"},
    },
    "required": ["plans"],
}


MULTIDIMENSIONAL_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "rate_plan_templates": {"type": "array"},
    },
    "required": ["rate_plan_templates"],
}


PLAN_V2_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["name", "segment_type", "holiday_type", "segments"],
    "properties": {
        "name": {"type": "string"},
        "segment_type": SEGMENT_TYPE_SCHEMA,
        "holiday_type": HOLIDAY_TYPE_SCHEMA,
        "segments": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "start", "end"],
                "properties": {
                    "name": {"type": "string"},
                    "start": {"type": "string"},
                    "end": {"type": "string"},
                },
            },
            "minItems": 1,
        },
        "rate_matrix": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "properties": {
                    "unit_time": {"type": "integer", "minimum": 1},
                    "progressive_enabled": {"type": "boolean"},
                    "progressive_rates": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "duration_minutes": {"type": "integer", "minimum": 1},
                                "duration": {"type": "integer", "minimum": 1},
                                "rate": {"type": "integer", "minimum": 0},
                                "unit_time": {"type": "integer", "minimum": 1},
                                "unit": {"type": "integer", "minimum": 1},
                            },
                        },
                    },
                    "simple_rate": {"type": ["integer", "null"], "minimum": 0},
                    "grace_time": {"type": "integer", "minimum": 0},
                    "segment_cap_enabled": {"type": "boolean"},
                    "segment_cap_amount": {"type": "integer", "minimum": 0},
                },
            },
        },
        "global_caps": {
            "type": "object",
            "properties": {
                "daily_cap_enabled": {"type": "boolean"},
                "daily_cap_amount": {"type": ["integer", "null"], "minimum": 0},
                "cap_priority": {
                    "type": "string",
                    "enum": ["daily", "segment", "lower", "higher"],
                    "default": "segment",
                },
                "global_grace_time": {"type": "integer", "minimum": 0},
            },
            "additionalProperties": True,
        },
    },
    "additionalProperties": True,
}


def _reject_removed_plan_fields(plan_obj: Dict[str, Any], path: str = "plan") -> None:
    if "unit_pivot" in plan_obj:
        raise ConfigValidationError(
            f"{path}: unit_pivot 已移除，收費週期固定以進場時間對齊 unit_time"
        )
    global_caps = plan_obj.get("global_caps") or {}
    if "segment_caps_enabled" in global_caps:
        raise ConfigValidationError(
            f"{path}.global_caps: segment_caps_enabled 已移除，請使用 rate_matrix 各格的 segment_cap_enabled"
        )


def validate_user_defined_plans_json(config_obj: Dict[str, Any]) -> None:
    try:
        validate(instance=config_obj, schema=USER_DEFINED_SCHEMA)
    except ValidationError as e:
        raise ConfigValidationError("用戶自訂方案配置不符合Schema", [e.message])
    for plan_id, plan in (config_obj.get("plans") or {}).items():
        _reject_removed_plan_fields(plan, f"plans.{plan_id}")
        try:
            validate(instance=plan, schema=PLAN_V2_SCHEMA)
        except ValidationError as e:
            raise ConfigValidationError(
                f"plans.{plan_id} 不符合 PlanV2 Schema", [e.message]
            )


def validate_multidimensional_config_json(config_obj: Dict[str, Any]) -> None:
    try:
        validate(instance=config_obj, schema=MULTIDIMENSIONAL_SCHEMA)
    except ValidationError as e:
        raise ConfigValidationError("多維度方案配置不符合Schema", [e.message])


def validate_plan_v2_json(plan_obj: Dict[str, Any]) -> None:
    _reject_removed_plan_fields(plan_obj)
    try:
        validate(instance=plan_obj, schema=PLAN_V2_SCHEMA)
    except ValidationError as e:
        raise ConfigValidationError("PlanV2 請求不符合Schema", [e.message])
