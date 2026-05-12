from typing import Dict, Any, List

from jsonschema import validate
from jsonschema.exceptions import ValidationError


class ConfigValidationError(Exception):
    def __init__(self, message: str, errors: List[str] = None):
        super().__init__(message)
        self.errors = errors or []


def _assert(condition: bool, message: str):
    if not condition:
        raise ConfigValidationError(message)


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
                    "segment_type": {
                        "type": "string",
                        "enum": ["全天", "二段", "三段", "任意段", "多時段"],
                    },
                    "holiday_type": {
                        "type": "string",
                        "enum": ["無假日", "平日假日", "完整假日"],
                    },
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
        "segment_type": {
            "type": "string",
            "enum": ["全天", "二段", "三段", "任意段", "多時段"],
        },
        "holiday_type": {
            "type": "string",
            "enum": ["無假日", "平日假日", "完整假日"],
        },
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
        "unit_pivot": {
            "type": "string",
            "enum": ["start", "end"],
            "default": "start",
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
                    "simple_rate": {"type": "integer", "minimum": 0},
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
                "segment_caps_enabled": {"type": ["boolean", "null"]},
                "cap_priority": {
                    "type": ["string", "null"],
                    "enum": ["daily", "segment", "lower", "higher", None],
                },
                "global_grace_time": {"type": "integer", "minimum": 0},
            },
            "additionalProperties": True,
        },
    },
    "additionalProperties": True,
}


def validate_user_defined_plans_json(config_obj: Dict[str, Any]) -> None:
    try:
        validate(instance=config_obj, schema=USER_DEFINED_SCHEMA)
    except ValidationError as e:
        raise ConfigValidationError("用戶自訂方案配置不符合Schema", [e.message])


def validate_multidimensional_config_json(config_obj: Dict[str, Any]) -> None:
    try:
        validate(instance=config_obj, schema=MULTIDIMENSIONAL_SCHEMA)
    except ValidationError as e:
        raise ConfigValidationError("多維度方案配置不符合Schema", [e.message])


def validate_plan_v2_json(plan_obj: Dict[str, Any]) -> None:
    try:
        validate(instance=plan_obj, schema=PLAN_V2_SCHEMA)
    except ValidationError as e:
        raise ConfigValidationError("PlanV2 請求不符合Schema", [e.message])

