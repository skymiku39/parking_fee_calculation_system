"""Tests for in-process Publish/Subscribe event bus."""

from src.core.events import CalendarPersisted, EventBus, MdpConfigSaved


def test_event_bus_delivers_to_subscribers():
    bus = EventBus()
    received: list[str] = []

    bus.subscribe(CalendarPersisted, lambda e: received.append(e.source))
    bus.publish(CalendarPersisted(source="manual"))

    assert received == ["manual"]


def test_event_bus_type_isolation():
    bus = EventBus()
    calendar_hits: list[str] = []
    mdp_hits: list[str] = []

    bus.subscribe(CalendarPersisted, lambda e: calendar_hits.append(e.source))
    bus.subscribe(MdpConfigSaved, lambda e: mdp_hits.append(e.action))

    bus.publish(MdpConfigSaved(template_id="tpl", action="save"))

    assert calendar_hits == []
    assert mdp_hits == ["save"]
