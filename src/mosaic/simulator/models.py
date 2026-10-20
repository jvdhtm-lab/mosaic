"""Simulation results and inspectable state."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import NonNegativeInt

from mosaic.contracts import (
    ComponentId,
    ComponentPlacement,
    Contract,
    MemoryState,
    NonNegativeFloat,
    RequestId,
    StorageTier,
    TierUsage,
)


class LoadSource(StrEnum):
    """Tier from which simulated component bytes were read."""

    DISK = "disk"
    RAM = "ram"


class SimulatedLoadResult(Contract):
    """Result of a simulated component load or prefetch."""

    simulated: Literal[True] = True
    component_id: ComponentId
    cache_hit: bool
    source_tier: LoadSource | None = None
    target_tier: StorageTier
    bytes_transferred: NonNegativeInt = 0
    latency_ms: NonNegativeFloat = 0.0
    dependencies_loaded: tuple[ComponentId, ...] = ()


class SimulatedExecution(Contract):
    """Result of simulated inference over a set of components."""

    simulated: Literal[True] = True
    request_id: RequestId
    activated_components: tuple[ComponentId, ...]
    load_results: tuple[SimulatedLoadResult, ...]
    inference_latency_ms: NonNegativeFloat
    total_latency_ms: NonNegativeFloat


class ComponentActivation(Contract):
    """Activation count for one component."""

    component_id: ComponentId
    count: NonNegativeInt


class SimulatorSnapshot(Contract):
    """Deterministic, explicitly simulated snapshot of runtime state."""

    simulated: Literal[True] = True
    memory: MemoryState
    disk_component_ids: tuple[ComponentId, ...]
    in_use_component_ids: tuple[ComponentId, ...]
    activations: tuple[ComponentActivation, ...] = ()
    cache_hits: NonNegativeInt = 0
    cache_misses: NonNegativeInt = 0
    ram_hits: NonNegativeInt = 0
    evictions: NonNegativeInt = 0
    prefetch_attempts: NonNegativeInt = 0
    prefetch_hits: NonNegativeInt = 0
    bytes_read_from_disk: NonNegativeInt = 0
    bytes_written_to_ram: NonNegativeInt = 0
    bytes_written_to_vram: NonNegativeInt = 0

    @property
    def cache_hit_rate(self) -> float | None:
        """Cache hit rate when at least one lookup has occurred."""
        total = self.cache_hits + self.cache_misses
        if total == 0:
            return None
        return self.cache_hits / total


def build_memory_state(
    *,
    ram_ids: tuple[ComponentId, ...],
    vram_ids: tuple[ComponentId, ...],
    sizes: dict[ComponentId, int],
) -> MemoryState:
    """Build a consistent memory snapshot from simulated resident sets."""
    placements: list[ComponentPlacement] = []
    for component_id in ram_ids:
        placements.append(
            ComponentPlacement(
                component_id=component_id,
                tier=StorageTier.RAM,
                size_bytes=sizes[component_id],
            )
        )
    for component_id in vram_ids:
        placements.append(
            ComponentPlacement(
                component_id=component_id,
                tier=StorageTier.VRAM,
                size_bytes=sizes[component_id],
            )
        )
    return MemoryState(
        ram=TierUsage(resident_bytes=sum(sizes[item] for item in ram_ids)),
        vram=TierUsage(resident_bytes=sum(sizes[item] for item in vram_ids)),
        placements=tuple(placements),
    )
