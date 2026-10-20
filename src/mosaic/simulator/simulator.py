"""Deterministic in-process simulator for component residency."""

from __future__ import annotations

import random
import threading
from collections.abc import Iterator
from contextlib import contextmanager

from mosaic.contracts import (
    ActivationObservation,
    ComponentId,
    ComponentMetadata,
    MemoryBudget,
    MemoryState,
    RequestId,
    RuntimeCapabilities,
    RuntimeIdentity,
    StorageTier,
)
from mosaic.errors import (
    ComponentInUseError,
    ComponentNotFoundError,
    DependencyError,
    DuplicateComponentError,
    IncompatibleComponentError,
    InvalidStateTransitionError,
    ResourceBudgetError,
    RuntimeOperationError,
)
from mosaic.interfaces import ComponentRegistry
from mosaic.simulator.config import SimulatorConfig
from mosaic.simulator.models import (
    ComponentActivation,
    LoadSource,
    SimulatedExecution,
    SimulatedLoadResult,
    SimulatorSnapshot,
    build_memory_state,
)

_GIB = 1024**3


class Simulator:
    """Simulated runtime and memory tiers with deterministic measurements."""

    def __init__(
        self,
        config: SimulatorConfig,
        *,
        registry: ComponentRegistry | None = None,
    ) -> None:
        self._config = config
        self._registry = registry
        self._budget = config.to_budget()
        self._components: dict[ComponentId, ComponentMetadata] = {}
        self._disk: set[ComponentId] = set()
        self._ram: set[ComponentId] = set()
        self._vram: set[ComponentId] = set()
        self._in_use: dict[ComponentId, int] = {}
        self._prefetched: set[ComponentId] = set()
        self._activations: dict[ComponentId, int] = {}
        self._last_used: dict[ComponentId, int] = {}
        self._clock = 0
        self._cache_hits = 0
        self._cache_misses = 0
        self._ram_hits = 0
        self._evictions = 0
        self._prefetch_attempts = 0
        self._prefetch_hits = 0
        self._bytes_read_from_disk = 0
        self._bytes_written_to_ram = 0
        self._bytes_written_to_vram = 0
        self._rng = random.Random(config.seed)
        self._lock = threading.RLock()

    @property
    def simulated(self) -> bool:
        """All measurements from this runtime are simulated."""
        return True

    @property
    def config(self) -> SimulatorConfig:
        """Return the simulator configuration."""
        return self._config

    @property
    def identity(self) -> RuntimeIdentity:
        """Return the simulated runtime identity."""
        return RuntimeIdentity(
            name=self._config.runtime_name,
            version=self._config.runtime_version,
            device="simulated",
        )

    @property
    def capabilities(self) -> RuntimeCapabilities:
        """Return simulated capability declarations."""
        return RuntimeCapabilities(
            can_enumerate_components=True,
            can_load_components=True,
            can_evict_components=True,
            can_observe_activations=ActivationObservation.PER_COMPONENT,
            supports_prefetch=True,
            supports_concurrent_requests=False,
            notes=("simulated measurements",),
        )

    @property
    def budget(self) -> MemoryBudget:
        """Return the simulated memory budget."""
        return self._budget

    def register_component(self, metadata: ComponentMetadata) -> None:
        """Register a component with the simulator and place it on disk."""
        with self._lock:
            if metadata.component_id in self._components:
                raise DuplicateComponentError(
                    f"component {metadata.component_id!r} is already registered",
                    component_id=metadata.component_id,
                )
            self._check_compatibility(metadata)
            new_disk_usage = sum(self._size(item) for item in self._disk) + metadata.size_bytes
            if (
                self._config.disk_capacity is not None
                and new_disk_usage > self._config.disk_capacity
            ):
                raise ResourceBudgetError(
                    f"simulated disk capacity exceeded by {metadata.component_id!r}",
                    tier="disk",
                    requested_bytes=metadata.size_bytes,
                    available_bytes=max(
                        0, self._config.disk_capacity - (new_disk_usage - metadata.size_bytes)
                    ),
                )
            self._components[metadata.component_id] = metadata
            self._disk.add(metadata.component_id)

    def load_component(self, component_id: ComponentId) -> SimulatedLoadResult:
        """Load a component into simulated VRAM, loading dependencies first."""
        with self._lock:
            return self._load_locked(component_id, stack=())

    def prefetch_component(self, component_id: ComponentId) -> SimulatedLoadResult:
        """Prefetch a component into simulated RAM without making it resident."""
        with self._lock:
            metadata = self._metadata_for(component_id)
            if component_id in self._vram:
                self._cache_hits += 1
                self._touch(component_id)
                return SimulatedLoadResult(
                    component_id=component_id,
                    cache_hit=True,
                    target_tier=StorageTier.VRAM,
                )
            self._prefetch_attempts += 1
            latency = self._config.load_base_ms
            transferred = 0
            source = LoadSource.RAM
            if component_id in self._ram:
                self._ram_hits += 1
            else:
                source = LoadSource.DISK
                self._ensure_capacity(StorageTier.RAM, metadata.size_bytes)
                self._ram.add(component_id)
                self._bytes_read_from_disk += metadata.size_bytes
                self._bytes_written_to_ram += metadata.size_bytes
                transferred = metadata.size_bytes
                latency += self._config.disk_to_ram_ms_per_gib * metadata.size_bytes / _GIB
            self._prefetched.add(component_id)
            self._touch(component_id)
            return SimulatedLoadResult(
                component_id=component_id,
                cache_hit=source is LoadSource.RAM,
                source_tier=source,
                target_tier=StorageTier.RAM,
                bytes_transferred=transferred,
                latency_ms=self._jitter(latency),
            )

    @contextmanager
    def use(self, component_id: ComponentId) -> Iterator[None]:
        """Mark a loaded component in use for the duration of the context."""
        with self._lock:
            self._load_locked(component_id, stack=())
            self._in_use[component_id] = self._in_use.get(component_id, 0) + 1
        try:
            yield
        finally:
            with self._lock:
                remaining = self._in_use.get(component_id, 0) - 1
                if remaining <= 0:
                    self._in_use.pop(component_id, None)
                else:
                    self._in_use[component_id] = remaining

    def execute(
        self,
        request_id: RequestId,
        component_ids: tuple[ComponentId, ...],
    ) -> SimulatedExecution:
        """Load and activate components for one simulated request."""
        unique_components = tuple(dict.fromkeys(component_ids))
        with self._lock:
            load_results: list[SimulatedLoadResult] = []
            for component_id in unique_components:
                load_results.append(self._load_locked(component_id, stack=()))
            for component_id in unique_components:
                self._in_use[component_id] = self._in_use.get(component_id, 0) + 1
            try:
                for component_id in unique_components:
                    self._activate_locked(component_id)
                inference_latency = self._jitter(
                    self._config.inference_base_ms
                    + self._config.inference_ms_per_component * len(unique_components)
                )
            finally:
                for component_id in unique_components:
                    remaining = self._in_use.get(component_id, 0) - 1
                    if remaining <= 0:
                        self._in_use.pop(component_id, None)
                    else:
                        self._in_use[component_id] = remaining
            total_latency = sum(result.latency_ms for result in load_results) + inference_latency
            return SimulatedExecution(
                request_id=request_id,
                activated_components=unique_components,
                load_results=tuple(load_results),
                inference_latency_ms=inference_latency,
                total_latency_ms=total_latency,
            )

    def activate(self, component_id: ComponentId) -> None:
        """Record an activation of a resident component."""
        with self._lock:
            self._activate_locked(component_id)

    def evict_component(self, component_id: ComponentId) -> None:
        """Evict a component from simulated VRAM."""
        with self._lock:
            if component_id not in self._vram:
                raise InvalidStateTransitionError(
                    f"component {component_id!r} is not resident in VRAM",
                    component_id=component_id,
                )
            if self._in_use.get(component_id, 0) > 0:
                raise ComponentInUseError(
                    f"component {component_id!r} is in use",
                    component_id=component_id,
                )
            self._vram.remove(component_id)
            self._last_used.pop(component_id, None)
            self._evictions += 1

    def evict_from_ram(self, component_id: ComponentId) -> None:
        """Drop a staged component from simulated RAM."""
        with self._lock:
            if component_id not in self._ram:
                raise InvalidStateTransitionError(
                    f"component {component_id!r} is not staged in RAM",
                    component_id=component_id,
                )
            if self._in_use.get(component_id, 0) > 0:
                raise ComponentInUseError(
                    f"component {component_id!r} is in use",
                    component_id=component_id,
                )
            self._ram.remove(component_id)
            self._prefetched.discard(component_id)
            self._last_used.pop(component_id, None)
            self._evictions += 1

    def resident_components(self) -> tuple[ComponentId, ...]:
        """Return components currently resident in simulated VRAM."""
        with self._lock:
            return tuple(sorted(self._vram))

    def staged_components(self) -> tuple[ComponentId, ...]:
        """Return components currently staged in simulated RAM."""
        with self._lock:
            return tuple(sorted(self._ram))

    def snapshot(self) -> SimulatorSnapshot:
        """Return a deterministic snapshot of simulator state and counters."""
        with self._lock:
            sizes = {
                component_id: item.size_bytes for component_id, item in self._components.items()
            }
            memory = build_memory_state(
                ram_ids=tuple(sorted(self._ram)),
                vram_ids=tuple(sorted(self._vram)),
                sizes=sizes,
            )
            activations = tuple(
                ComponentActivation(
                    component_id=component_id, count=self._activations[component_id]
                )
                for component_id in sorted(self._activations)
            )
            return SimulatorSnapshot(
                memory=memory,
                disk_component_ids=tuple(sorted(self._disk)),
                in_use_component_ids=tuple(sorted(self._in_use)),
                activations=activations,
                cache_hits=self._cache_hits,
                cache_misses=self._cache_misses,
                ram_hits=self._ram_hits,
                evictions=self._evictions,
                prefetch_attempts=self._prefetch_attempts,
                prefetch_hits=self._prefetch_hits,
                bytes_read_from_disk=self._bytes_read_from_disk,
                bytes_written_to_ram=self._bytes_written_to_ram,
                bytes_written_to_vram=self._bytes_written_to_vram,
            )

    def memory_state(self) -> MemoryState:
        """Return only the current memory-state snapshot."""
        return self.snapshot().memory

    def cache_hit_rate(self) -> float | None:
        """Return the simulated cache hit rate, if any lookups occurred."""
        with self._lock:
            total = self._cache_hits + self._cache_misses
            return None if total == 0 else self._cache_hits / total

    def used_bytes(self, tier: StorageTier) -> int:
        """Return component bytes resident in a tier."""
        with self._lock:
            ids = self._ram if tier is StorageTier.RAM else self._vram
            return sum(self._size(component_id) for component_id in ids)

    def available_bytes(self, tier: StorageTier) -> int:
        """Return bytes available in a tier after the safety margin."""
        with self._lock:
            return self._budget.effective_capacity_bytes(tier) - self.used_bytes(tier)

    def least_recently_used(self, tier: StorageTier) -> ComponentId | None:
        """Return the least recently used resident component in a tier."""
        with self._lock:
            ids = self._ram if tier is StorageTier.RAM else self._vram
            if not ids:
                return None
            return min(ids, key=lambda component_id: self._last_used.get(component_id, -1))

    def _metadata_for(self, component_id: ComponentId) -> ComponentMetadata:
        metadata = self._components.get(component_id)
        if metadata is not None:
            return metadata
        if self._registry is not None and self._registry.has_component(component_id):
            metadata = self._registry.get_component(component_id)
            if self._config.verify_content_on_load:
                self._registry.verify_component(component_id)
            self.register_component(metadata)
            return metadata
        raise ComponentNotFoundError(
            f"component {component_id!r} is not known to the simulator",
            component_id=component_id,
        )

    def _load_locked(
        self,
        component_id: ComponentId,
        stack: tuple[ComponentId, ...],
    ) -> SimulatedLoadResult:
        metadata = self._metadata_for(component_id)
        if component_id in self._vram:
            self._cache_hits += 1
            self._touch(component_id)
            return SimulatedLoadResult(
                component_id=component_id,
                cache_hit=True,
                target_tier=StorageTier.VRAM,
            )
        if component_id in self._config.fail_components:
            raise RuntimeOperationError(f"simulated load failure for component {component_id!r}")
        if component_id in stack:
            raise DependencyError(
                f"dependency cycle detected at component {component_id!r}",
                component_id=component_id,
            )
        dependencies_loaded: list[ComponentId] = []
        for dependency in metadata.dependencies:
            if dependency in stack or dependency == component_id:
                raise DependencyError(
                    f"dependency cycle detected at component {component_id!r}",
                    component_id=component_id,
                )
            if dependency not in self._vram:
                result = self._load_locked(dependency, stack=(*stack, component_id))
                dependencies_loaded.append(dependency)
                dependencies_loaded.extend(result.dependencies_loaded)

        self._cache_misses += 1
        latency = self._config.load_base_ms
        transferred = 0
        source = LoadSource.RAM
        if component_id not in self._ram:
            source = LoadSource.DISK
            self._ensure_capacity(StorageTier.RAM, metadata.size_bytes)
            self._ram.add(component_id)
            self._bytes_read_from_disk += metadata.size_bytes
            self._bytes_written_to_ram += metadata.size_bytes
            transferred += metadata.size_bytes
            latency += self._config.disk_to_ram_ms_per_gib * metadata.size_bytes / _GIB
        else:
            self._ram_hits += 1
            if component_id in self._prefetched:
                self._prefetch_hits += 1
                self._prefetched.discard(component_id)
        self._ensure_capacity(StorageTier.VRAM, metadata.size_bytes)
        self._vram.add(component_id)
        self._bytes_written_to_vram += metadata.size_bytes
        transferred += metadata.size_bytes
        latency += self._config.ram_to_vram_ms_per_gib * metadata.size_bytes / _GIB
        self._touch(component_id)
        return SimulatedLoadResult(
            component_id=component_id,
            cache_hit=False,
            source_tier=source,
            target_tier=StorageTier.VRAM,
            bytes_transferred=transferred,
            latency_ms=self._jitter(latency),
            dependencies_loaded=tuple(dict.fromkeys(dependencies_loaded)),
        )

    def _activate_locked(self, component_id: ComponentId) -> None:
        if component_id not in self._vram:
            raise InvalidStateTransitionError(
                f"component {component_id!r} is not resident in VRAM",
                component_id=component_id,
            )
        self._activations[component_id] = self._activations.get(component_id, 0) + 1
        self._touch(component_id)

    def _check_compatibility(self, metadata: ComponentMetadata) -> None:
        compatibility = metadata.compatibility
        if compatibility.runtime_name != self._config.runtime_name:
            raise IncompatibleComponentError(
                f"component {metadata.component_id!r} targets runtime "
                f"{compatibility.runtime_name!r}, not {self._config.runtime_name!r}",
                component_id=metadata.component_id,
            )
        if (
            compatibility.runtime_version is not None
            and compatibility.runtime_version != self._config.runtime_version
        ):
            raise IncompatibleComponentError(
                f"component {metadata.component_id!r} targets runtime version "
                f"{compatibility.runtime_version!r}, not {self._config.runtime_version!r}",
                component_id=metadata.component_id,
            )
        if (
            compatibility.precision is not None
            and self._config.precision is not None
            and compatibility.precision != self._config.precision
        ):
            raise IncompatibleComponentError(
                f"component {metadata.component_id!r} requires precision "
                f"{compatibility.precision!r}",
                component_id=metadata.component_id,
            )
        missing = set(compatibility.required_features) - set(self._config.supported_features)
        if missing:
            raise IncompatibleComponentError(
                f"component {metadata.component_id!r} requires unsupported features "
                f"{sorted(missing)!r}",
                component_id=metadata.component_id,
            )

    def _ensure_capacity(self, tier: StorageTier, additional_bytes: int) -> None:
        available = self.available_bytes(tier)
        if additional_bytes > available:
            raise ResourceBudgetError(
                f"simulated {tier.value} capacity exceeded",
                tier=tier.value,
                requested_bytes=additional_bytes,
                available_bytes=max(0, available),
            )

    def _size(self, component_id: ComponentId) -> int:
        return self._components[component_id].size_bytes

    def _touch(self, component_id: ComponentId) -> None:
        self._clock += 1
        self._last_used[component_id] = self._clock

    def _jitter(self, latency_ms: float) -> float:
        ratio = self._config.latency_jitter_ratio
        if ratio == 0:
            return latency_ms
        return latency_ms * (1 + self._rng.uniform(-ratio, ratio))
