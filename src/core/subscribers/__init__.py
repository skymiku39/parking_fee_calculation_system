from .audit import register_audit_subscribers
from .runtime import register_runtime_subscribers


def register_default_subscribers(system, bus) -> None:
    register_runtime_subscribers(system, bus)
    register_audit_subscribers(bus)


__all__ = [
    "register_audit_subscribers",
    "register_default_subscribers",
    "register_runtime_subscribers",
]
