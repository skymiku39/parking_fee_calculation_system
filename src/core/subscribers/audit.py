"""Audit subscriber: logs successful fee calculations (Pub/Sub)."""

from __future__ import annotations

import logging

from src.core.events import EventBus, ParkingFeeCalculated

logger = logging.getLogger(__name__)


def register_audit_subscribers(bus: EventBus) -> None:
    def on_parking_fee_calculated(event: ParkingFeeCalculated) -> None:
        logger.info(
            "ParkingFeeCalculated plan_id=%s engine=%s total_amount=%s",
            event.plan_id,
            event.engine,
            event.total_amount,
        )

    bus.subscribe(ParkingFeeCalculated, on_parking_fee_calculated)
