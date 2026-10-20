from __future__ import annotations

from mosaic.errors import (
    ComponentInUseError,
    ConfigurationError,
    IntegrityError,
    MosaicError,
    ResourceBudgetError,
    UnsupportedRuntimeCapabilityError,
)


def test_domain_errors_share_a_base_class() -> None:
    errors = [
        ConfigurationError("bad config"),
        IntegrityError("hash mismatch"),
        UnsupportedRuntimeCapabilityError("cannot load"),
        ResourceBudgetError("over budget"),
        ComponentInUseError("busy"),
    ]

    assert all(isinstance(error, MosaicError) for error in errors)


def test_errors_preserve_structured_context() -> None:
    integrity = IntegrityError("hash mismatch", component_id="expert.0")
    capability = UnsupportedRuntimeCapabilityError("unsupported", capability="prefetch")
    budget = ResourceBudgetError(
        "over budget",
        tier="vram",
        requested_bytes=2048,
        available_bytes=1024,
    )

    assert integrity.component_id == "expert.0"
    assert capability.capability == "prefetch"
    assert budget.tier == "vram"
    assert budget.requested_bytes == 2048
    assert budget.available_bytes == 1024
