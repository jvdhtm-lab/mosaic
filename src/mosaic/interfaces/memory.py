"""Memory manager interface."""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Protocol, runtime_checkable

from mosaic.contracts.common import ComponentId
from mosaic.contracts.memory import MemoryPlan, MemoryState


@runtime_checkable
class MemoryManager(Protocol):
    """Validates and executes memory plans while enforcing resource invariants."""

    def snapshot(self) -> MemoryState:
        """Return the current residency state."""
        ...

    def apply(self, plan: MemoryPlan) -> MemoryState:
        """Validate and execute a plan, returning the resulting state."""
        ...

    def use(self, component_id: ComponentId) -> AbstractContextManager[None]:
        """Mark a component in use for the duration of a runtime operation."""
        ...
