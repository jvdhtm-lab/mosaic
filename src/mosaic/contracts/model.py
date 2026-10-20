"""Model and runtime identity plus runtime capability declarations."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import PositiveInt, model_validator

from mosaic.contracts.common import Contract, Identifier, NonEmptyStr


class ModelIdentity(Contract):
    """Identity of the source model whose components Mosaic manages."""

    model_id: Identifier
    architecture: NonEmptyStr
    revision: NonEmptyStr | None = None
    quantization: NonEmptyStr | None = None


class RuntimeIdentity(Contract):
    """Identity of an inference runtime."""

    name: Identifier
    version: NonEmptyStr
    device: NonEmptyStr | None = None


class ActivationObservation(StrEnum):
    """Granularity at which a runtime can report component activation."""

    NONE = "none"
    AGGREGATE = "aggregate"
    PER_COMPONENT = "per_component"


class RuntimeCapabilities(Contract):
    """Operations and observations a runtime actually supports."""

    can_enumerate_components: bool
    can_load_components: bool
    can_evict_components: bool
    can_observe_activations: ActivationObservation
    supports_prefetch: bool
    supports_concurrent_requests: bool
    max_resident_components: PositiveInt | None = None
    notes: tuple[NonEmptyStr, ...] = ()

    @model_validator(mode="after")
    def _validate_capabilities(self) -> Self:
        if (
            self.can_observe_activations is ActivationObservation.PER_COMPONENT
            and not self.can_enumerate_components
        ):
            raise ValueError("per-component activation observation requires component enumeration")
        if self.supports_prefetch and not self.can_load_components:
            raise ValueError("prefetching requires component loading support")
        return self
