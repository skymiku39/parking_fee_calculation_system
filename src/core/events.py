"""In-process Publish/Subscribe event bus for domain lifecycle events."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Type, TypeVar

TEvent = TypeVar("TEvent", bound="DomainEvent")
EventHandler = Callable[[Any], None]


@dataclass(frozen=True)
class DomainEvent:
    """Base type for all domain events."""

    pass


@dataclass(frozen=True)
class CalendarPersisted(DomainEvent):
    source: str = "manual"


@dataclass(frozen=True)
class SystemConfigUpdated(DomainEvent):
    changed_keys: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class MdpConfigSaved(DomainEvent):
    template_id: str | None = None
    action: str = "save"


@dataclass(frozen=True)
class UserPlanSaved(DomainEvent):
    plan_id: str = ""
    action: str = "update"


@dataclass(frozen=True)
class UserPlanDeleted(DomainEvent):
    plan_id: str = ""


@dataclass(frozen=True)
class ParkingFeeCalculated(DomainEvent):
    plan_id: str = ""
    engine: str = ""
    total_amount: int = 0


class EventBus:
    """Synchronous in-process pub/sub (sufficient for Flask single-process)."""

    def __init__(self) -> None:
        self._subscribers: Dict[Type[DomainEvent], List[EventHandler]] = {}

    def subscribe(self, event_type: Type[TEvent], handler: EventHandler) -> None:
        self._subscribers.setdefault(event_type, []).append(handler)

    def publish(self, event: DomainEvent) -> None:
        for handler in list(self._subscribers.get(type(event), [])):
            handler(event)

    def clear(self) -> None:
        self._subscribers.clear()
