"""Adapters for external systems. Tools call `integrations.get(name)`, never a client directly.

Each tool ships a mock adapter next to its code and registers it at import. In production
the real adapter is registered instead (same Protocol), selected by configuration.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Protocol


class Adapter(Protocol):
    name: str


_ADAPTERS: dict[str, Any] = {}


def register(adapter: Adapter) -> Adapter:
    _ADAPTERS[adapter.name] = adapter
    return adapter


def get(name: str) -> Any:
    try:
        return _ADAPTERS[name]
    except KeyError:
        raise LookupError(f"No adapter registered for {name!r}") from None


@contextmanager
def override(name: str, adapter: Any) -> Iterator[Any]:
    previous = _ADAPTERS.get(name)
    _ADAPTERS[name] = adapter
    try:
        yield adapter
    finally:
        if previous is None:
            _ADAPTERS.pop(name, None)
        else:
            _ADAPTERS[name] = previous
