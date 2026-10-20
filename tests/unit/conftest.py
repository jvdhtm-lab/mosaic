from __future__ import annotations

import pytest

from mosaic.contracts import (
    ClusterManifest,
    ComponentMetadata,
    ComponentType,
    MemoryBudget,
    ModelIdentity,
    RuntimeCompatibility,
    StorageKind,
    StorageLocation,
    TierBudget,
)

CONTENT_HASH = "a" * 64


@pytest.fixture
def component_metadata(model_identity: ModelIdentity) -> ComponentMetadata:
    return ComponentMetadata(
        component_id="mixtral/layer.0/expert.0",
        content_hash=CONTENT_HASH,
        component_type=ComponentType.MOE_EXPERT,
        source_model=model_identity,
        storage=StorageLocation(kind=StorageKind.SIMULATED, uri="simulated://expert-0"),
        size_bytes=4096,
        compatibility=RuntimeCompatibility(runtime_name="simulator"),
    )


@pytest.fixture
def cluster_manifest(model_identity: ModelIdentity) -> ClusterManifest:
    return ClusterManifest(
        cluster_id="cluster-0",
        source_model=model_identity,
        component_ids=("mixtral/layer.0/expert.0", "mixtral/layer.0/expert.1"),
    )


@pytest.fixture
def memory_budget() -> MemoryBudget:
    return MemoryBudget(
        ram=TierBudget(capacity_bytes=8 * 1024**3, safety_margin_bytes=512 * 1024**2),
        vram=TierBudget(capacity_bytes=0),
    )
