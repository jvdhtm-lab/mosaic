from __future__ import annotations

from collections.abc import Callable, Iterable

import pytest

from mosaic.contracts import (
    ComponentMetadata,
    ComponentType,
    ModelIdentity,
    RuntimeCompatibility,
    StorageKind,
    StorageLocation,
)
from mosaic.contracts.common import ComponentId

CONTENT_HASH = "a" * 64


@pytest.fixture
def model_identity() -> ModelIdentity:
    return ModelIdentity(
        model_id="mistralai/Mixtral-8x7B-v0.1",
        architecture="mixtral",
        revision="main",
    )


@pytest.fixture
def make_component() -> Callable[..., ComponentMetadata]:
    def factory(
        component_id: ComponentId,
        *,
        size_bytes: int = 4096,
        dependencies: Iterable[ComponentId] = (),
        storage: StorageLocation | None = None,
        content_hash: str = CONTENT_HASH,
        runtime_name: str = "simulator",
        runtime_version: str | None = None,
        precision: str | None = None,
        required_features: Iterable[str] = (),
    ) -> ComponentMetadata:
        return ComponentMetadata(
            component_id=component_id,
            content_hash=content_hash,
            component_type=ComponentType.MOE_EXPERT,
            source_model=ModelIdentity(
                model_id="mistralai/Mixtral-8x7B-v0.1",
                architecture="mixtral",
                revision="main",
            ),
            storage=storage
            or StorageLocation(kind=StorageKind.SIMULATED, uri=f"simulated://{component_id}"),
            size_bytes=size_bytes,
            dependencies=tuple(dependencies),
            compatibility=RuntimeCompatibility(
                runtime_name=runtime_name,
                runtime_version=runtime_version,
                precision=precision,
                required_features=tuple(required_features),
            ),
        )

    return factory
