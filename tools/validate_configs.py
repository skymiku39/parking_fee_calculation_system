import json
import sys
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent.parent
    # 確保可匯入專案內模組
    if str(root) not in sys.path:
        sys.path.append(str(root))

    from src.core.validation import (
        validate_user_defined_plans_json,
        validate_multidimensional_config_json,
    )
    errors = []

    user_plans = root / "config" / "user_defined_plans.json"
    multi_cfg = root / "config" / "multidimensional_rate_plans.json"

    if user_plans.exists():
        try:
            obj = json.loads(user_plans.read_text(encoding="utf-8"))
            validate_user_defined_plans_json(obj)
            print("user_defined_plans.json: OK")
        except Exception as e:
            errors.append(f"user_defined_plans.json: {e}")
    else:
        print("user_defined_plans.json: MISSING (skip)")

    if multi_cfg.exists():
        try:
            obj = json.loads(multi_cfg.read_text(encoding="utf-8"))
            validate_multidimensional_config_json(obj)
            print("multidimensional_rate_plans.json: OK")
        except Exception as e:
            errors.append(f"multidimensional_rate_plans.json: {e}")
    else:
        print("multidimensional_rate_plans.json: MISSING (skip)")

    if errors:
        print("\nValidation errors:")
        for e in errors:
            print(" -", e)
        raise SystemExit(1)


if __name__ == "__main__":
    main()


