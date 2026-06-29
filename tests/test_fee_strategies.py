"""計費策略路由測試（Open/Closed：依 plan_id 選擇引擎）。"""

from datetime import datetime

from src.application.fee_strategies import (
    MultidimensionalFeeStrategy,
    UserDefinedFeeStrategy,
    build_fee_strategies,
)


def test_build_fee_strategies_order(isolated_system):
    strategies = build_fee_strategies(isolated_system)
    assert isinstance(strategies[0], MultidimensionalFeeStrategy)
    assert isinstance(strategies[1], UserDefinedFeeStrategy)


def test_multidimensional_strategy_supports_template(isolated_system):
    strategy = MultidimensionalFeeStrategy(isolated_system)
    assert strategy.supports("全天_無假日") is True
    assert strategy.supports("跨日測試方案") is False


def test_user_defined_strategy_supports_user_plan(isolated_system):
    strategy = UserDefinedFeeStrategy(isolated_system)
    assert strategy.supports("跨日測試方案") is True
    assert strategy.supports("全天_無假日") is False


def test_calculate_routes_to_multidimensional_engine(isolated_system):
    result = isolated_system.calculate_parking_fee(
        datetime(2025, 6, 20, 10, 0),
        datetime(2025, 6, 20, 12, 0),
        "全天_無假日",
    )
    assert result["success"] is True
    assert result["calculation_engine"] == "multidimensional"


def test_calculate_routes_to_user_defined_engine(isolated_system):
    result = isolated_system.calculate_parking_fee(
        datetime(2025, 6, 20, 10, 0),
        datetime(2025, 6, 20, 12, 0),
        "跨日測試方案",
    )
    assert result["success"] is True
    assert result["calculation_engine"] == "user_defined_billing_cycle"


def test_calculate_unknown_plan_returns_failure(isolated_system):
    result = isolated_system.calculate_parking_fee(
        datetime(2025, 6, 20, 10, 0),
        datetime(2025, 6, 20, 12, 0),
        "不存在的方案",
    )
    assert result["success"] is False
    assert result["calculation_engine"] == "none"


def test_calculate_without_plan_id_returns_failure(isolated_system):
    result = isolated_system.calculate_parking_fee(
        datetime(2025, 6, 20, 10, 0),
        datetime(2025, 6, 20, 12, 0),
        None,
    )
    assert result["success"] is False
