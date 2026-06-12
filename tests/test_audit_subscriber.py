import logging

from src.core.events import EventBus, ParkingFeeCalculated
from src.core.subscribers.audit import register_audit_subscribers


def test_audit_subscriber_logs_fee_calculation(caplog):
    bus = EventBus()
    register_audit_subscribers(bus)

    with caplog.at_level(logging.INFO):
        bus.publish(
            ParkingFeeCalculated(
                plan_id="全天_無假日",
                engine="multidimensional",
                total_amount=120,
            )
        )

    assert any("ParkingFeeCalculated" in r.message for r in caplog.records)
