"""Fee calculation strategies (Open/Closed Principle)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.system import SmartParkingSystem


class MultidimensionalFeeStrategy:
    def __init__(self, system: SmartParkingSystem) -> None:
        self._system = system

    def supports(self, plan_id: str) -> bool:
        return self._system.is_multidimensional_plan(plan_id)

    def calculate(
        self,
        enter_time: datetime,
        exit_time: datetime,
        plan_id: str,
        manual_adjustment: int = 0,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self._system.calculate_with_multidimensional(
            enter_time, exit_time, plan_id, manual_adjustment, context
        )


class UserDefinedFeeStrategy:
    def __init__(self, system: SmartParkingSystem) -> None:
        self._system = system

    def supports(self, plan_id: str) -> bool:
        return self._system.is_user_defined_plan(plan_id)

    def calculate(
        self,
        enter_time: datetime,
        exit_time: datetime,
        plan_id: str,
        manual_adjustment: int = 0,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self._system.calculate_with_user_defined_plan(
            enter_time, exit_time, plan_id, manual_adjustment, context
        )


def build_fee_strategies(system: SmartParkingSystem) -> List[Any]:
    return [
        MultidimensionalFeeStrategy(system),
        UserDefinedFeeStrategy(system),
    ]
