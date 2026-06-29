"""Subscribe runtime state refresh handlers to domain events (Pub/Sub)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.core.events import (
    CalendarPersisted,
    EventBus,
    MdpConfigSaved,
    SystemConfigUpdated,
)

if TYPE_CHECKING:
    from src.core.system import SmartParkingSystem

logger = logging.getLogger(__name__)


def register_runtime_subscribers(system: SmartParkingSystem, bus: EventBus) -> None:
    """Wire calendar / MDP reload reactions to configuration change events."""

    def on_calendar_persisted(_event: CalendarPersisted) -> None:
        system.refresh_runtime_state(calendar=True, mdp=True)

    def on_mdp_saved(_event: MdpConfigSaved) -> None:
        system.refresh_runtime_state(mdp=True)

    def on_system_config_updated(event: SystemConfigUpdated) -> None:
        if "system_mode" in event.changed_keys:
            system.refresh_runtime_state(mdp=True)

    bus.subscribe(CalendarPersisted, on_calendar_persisted)
    bus.subscribe(MdpConfigSaved, on_mdp_saved)
    bus.subscribe(SystemConfigUpdated, on_system_config_updated)
