import json
import sys
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.append(str(root))

    from src.core.utils import validate_and_normalize_system_config
    from src.core.validation import (
        validate_multidimensional_config_json,
        validate_system_calendar_json,
        validate_user_defined_plans_json,
    )
    from src.domain.terminology import collect_deprecated_warnings

    errors = []
    warnings = []

    def _check(filename: str, validator, *, collect_warnings: bool = False) -> None:
        path = root / "config" / filename
        if not path.exists():
            print(f"{filename}: MISSING (skip)")
            return
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
            validator(obj)
            if collect_warnings:
                warnings.extend(collect_deprecated_warnings(obj, filename))
            print(f"{filename}: OK")
        except Exception as e:
            errors.append(f"{filename}: {e}")

    _check("user_defined_plans.json", validate_user_defined_plans_json, collect_warnings=True)
    _check(
        "multidimensional_rate_plans.json",
        validate_multidimensional_config_json,
        collect_warnings=True,
    )
    _check("system_calendar.json", validate_system_calendar_json)
    _check(
        "system_config.json",
        lambda obj: validate_and_normalize_system_config(obj, include_env_overrides=False),
    )

    if warnings:
        print("\nDeprecated terminology warnings:")
        for w in warnings:
            print(" -", w)

    if errors:
        print("\nValidation errors:")
        for e in errors:
            print(" -", e)
        raise SystemExit(1)

    if warnings:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
