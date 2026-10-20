"""Exception hierarchy for Mosaic.

Pydantic validates structural manifests at construction time. Mosaic-specific
errors describe failures of domain operations: configuration loading,
integrity checks, unsupported runtime capabilities, resource limits, and
component lifecycle operations.
"""


class MosaicError(Exception):
    """Base class for all Mosaic domain errors."""


class ConfigurationError(MosaicError):
    """Raised when a configuration file is missing, malformed, or invalid."""


class InvalidManifestError(MosaicError):
    """Raised when a manifest is structurally invalid for a registry operation."""

    def __init__(self, message: str, *, manifest_id: str | None = None) -> None:
        super().__init__(message)
        self.manifest_id = manifest_id


class IntegrityError(MosaicError):
    """Raised when stored content does not match its declared identity."""

    def __init__(self, message: str, *, component_id: str | None = None) -> None:
        super().__init__(message)
        self.component_id = component_id


class UnsupportedRuntimeCapabilityError(MosaicError):
    """Raised when a runtime cannot perform a requested operation."""

    def __init__(self, message: str, *, capability: str | None = None) -> None:
        super().__init__(message)
        self.capability = capability


class ResourceBudgetError(MosaicError):
    """Raised when an action would exceed a RAM or VRAM budget."""

    def __init__(
        self,
        message: str,
        *,
        tier: str | None = None,
        requested_bytes: int | None = None,
        available_bytes: int | None = None,
    ) -> None:
        super().__init__(message)
        self.tier = tier
        self.requested_bytes = requested_bytes
        self.available_bytes = available_bytes


class ComponentOperationError(MosaicError):
    """Base class for failed component lifecycle operations."""

    def __init__(self, message: str, *, component_id: str | None = None) -> None:
        super().__init__(message)
        self.component_id = component_id


class ComponentNotFoundError(ComponentOperationError):
    """Raised when a requested component is not registered or stored."""


class DuplicateComponentError(ComponentOperationError):
    """Raised when a component is registered more than once under one identity."""


class DependencyError(ComponentOperationError):
    """Raised when component dependencies are missing, cyclic, or inconsistent."""


class ComponentInUseError(ComponentOperationError):
    """Raised when an operation targets a component that is currently in use."""


class InvalidStateTransitionError(ComponentOperationError):
    """Raised when a component lifecycle transition is not permitted."""


class RuntimeOperationError(MosaicError):
    """Raised when the inference runtime fails a component operation."""
