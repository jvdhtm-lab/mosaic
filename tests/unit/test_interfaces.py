from __future__ import annotations

from collections.abc import Iterator
from contextlib import nullcontext
from typing import Any

from mosaic.contracts import (
    ActivationObservation,
    ClusterManifest,
    ComponentMetadata,
    ControllerPrediction,
    ControllerRequest,
    ExecutionTrace,
    MemoryPlan,
    MemoryState,
    RuntimeCapabilities,
    RuntimeIdentity,
    ScoredCandidate,
)
from mosaic.interfaces import (
    ClusteringEngine,
    ComponentRegistry,
    Controller,
    MemoryManager,
    Observer,
    RuntimeAdapter,
)


class FakeRegistry:
    def __init__(self) -> None:
        self.components: dict[str, ComponentMetadata] = {}
        self.clusters: dict[str, ClusterManifest] = {}

    def register_component(self, metadata: ComponentMetadata) -> None:
        self.components[metadata.component_id] = metadata

    def get_component(self, component_id: str) -> ComponentMetadata:
        return self.components[component_id]

    def has_component(self, component_id: str) -> bool:
        return component_id in self.components

    def list_components(self) -> tuple[ComponentMetadata, ...]:
        return tuple(self.components.values())

    def register_cluster(self, cluster: ClusterManifest) -> None:
        self.clusters[cluster.cluster_id] = cluster

    def get_cluster(self, cluster_id: str) -> ClusterManifest:
        return self.clusters[cluster_id]

    def list_clusters(self) -> tuple[ClusterManifest, ...]:
        return tuple(self.clusters.values())


class FakeClusteringEngine:
    def build_clusters(self, traces: Any) -> tuple[ClusterManifest, ...]:
        return ()


class FakeController:
    def predict(self, request: ControllerRequest) -> ControllerPrediction:
        candidates = tuple(
            ScoredCandidate(
                candidate_id=candidate.candidate_id,
                candidate_type=candidate.candidate_type,
                score=0.5,
            )
            for candidate in request.candidates
        )
        return ControllerPrediction(
            request_id=request.request.request_id,
            controller_version="fake",
            threshold=0.5,
            candidates=candidates,
        )


class FakeMemoryManager:
    def snapshot(self) -> MemoryState:
        return MemoryState()

    def apply(self, plan: MemoryPlan) -> MemoryState:
        return self.snapshot()

    def use(self, component_id: str) -> Any:
        return nullcontext()


class FakeObserver:
    def __init__(self) -> None:
        self.traces: list[ExecutionTrace] = []

    def record(self, trace: ExecutionTrace) -> None:
        self.traces.append(trace)

    def iter_traces(self) -> Iterator[ExecutionTrace]:
        return iter(self.traces)


class FakeRuntimeAdapter:
    def __init__(self) -> None:
        self.identity = RuntimeIdentity(name="simulator", version="0.1")
        self.capabilities = RuntimeCapabilities(
            can_enumerate_components=True,
            can_load_components=True,
            can_evict_components=True,
            can_observe_activations=ActivationObservation.PER_COMPONENT,
            supports_prefetch=False,
            supports_concurrent_requests=False,
        )
        self.loaded: list[str] = []

    def load_component(self, component_id: str) -> None:
        self.loaded.append(component_id)

    def evict_component(self, component_id: str) -> None:
        self.loaded.remove(component_id)

    def resident_components(self) -> tuple[str, ...]:
        return tuple(self.loaded)


def test_fake_registry_satisfies_protocol() -> None:
    assert isinstance(FakeRegistry(), ComponentRegistry)


def test_fake_clustering_engine_satisfies_protocol() -> None:
    assert isinstance(FakeClusteringEngine(), ClusteringEngine)


def test_fake_controller_satisfies_protocol() -> None:
    assert isinstance(FakeController(), Controller)


def test_fake_memory_manager_satisfies_protocol() -> None:
    assert isinstance(FakeMemoryManager(), MemoryManager)


def test_fake_observer_satisfies_protocol() -> None:
    assert isinstance(FakeObserver(), Observer)


def test_fake_runtime_adapter_satisfies_protocol() -> None:
    assert isinstance(FakeRuntimeAdapter(), RuntimeAdapter)
