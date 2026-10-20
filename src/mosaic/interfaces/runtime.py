"""Runtime adapter interface."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mosaic.contracts.common import ComponentId
from mosaic.contracts.model import RuntimeCapabilities, RuntimeIdentity


@runtime_checkable
class RuntimeAdapter(Protocol):
    """Controlled access to a runtime that owns actual model execution."""

    @property
    def identity(self) -> RuntimeIdentity:
        """Return the concrete runtime identity."""
        ...

    @property
    def capabilities(self) -> RuntimeCapabilities:
        """Return the capabilities the runtime actually provides."""
        ...

    def load_component(self, component_id: ComponentId) -> None:
        """Load a verified component through the runtime."""
        ...

    def evict_component(self, component_id: ComponentId) -> None:
        """Evict a component that is not in use."""
        ...

    def resident_components(self) -> tuple[ComponentId, ...]:
        """Return component identifiers currently resident in the runtime."""
        ...
