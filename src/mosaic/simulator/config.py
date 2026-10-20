"""Deterministic simulator configuration."""

from __future__ import annotations

from typing import Self

from pydantic import NonNegativeInt, model_validator

from mosaic.contracts import (
    ComponentId,
    Contract,
    Identifier,
    MemoryBudget,
    NonEmptyStr,
    NonNegativeFloat,
    Score,
    TierBudget,
)
from mosaic.units import ByteSize


class SimulatorConfig(Contract):
    """Capacities, costs, identity, and failure injection for the simulator."""

    ram_capacity: ByteSize
    vram_capacity: ByteSize
    disk_capacity: ByteSize | None = None
    ram_safety_margin: ByteSize = 0
    vram_safety_margin: ByteSize = 0
    disk_to_ram_ms_per_gib: NonNegativeFloat = 50.0
    ram_to_vram_ms_per_gib: NonNegativeFloat = 20.0
    load_base_ms: NonNegativeFloat = 1.0
    inference_base_ms: NonNegativeFloat = 2.0
    inference_ms_per_component: NonNegativeFloat = 0.5
    latency_jitter_ratio: Score = 0.0
    seed: NonNegativeInt = 0
    runtime_name: Identifier = "simulator"
    runtime_version: NonEmptyStr = "0.1.0"
    precision: NonEmptyStr | None = None
    supported_features: tuple[NonEmptyStr, ...] = ()
    fail_components: tuple[ComponentId, ...] = ()
    verify_content_on_load: bool = False

    @model_validator(mode="after")
    def _validate_config(self) -> Self:
        if self.ram_safety_margin > self.ram_capacity:
            raise ValueError("ram_safety_margin must not exceed ram_capacity")
        if self.vram_safety_margin > self.vram_capacity:
            raise ValueError("vram_safety_margin must not exceed vram_capacity")
        if len(set(self.supported_features)) != len(self.supported_features):
            raise ValueError("supported_features must not contain duplicates")
        if len(set(self.fail_components)) != len(self.fail_components):
            raise ValueError("fail_components must not contain duplicates")
        return self

    def to_budget(self) -> MemoryBudget:
        """Return the simulator's RAM and VRAM budgets."""
        return MemoryBudget(
            ram=TierBudget(
                capacity_bytes=self.ram_capacity,
                safety_margin_bytes=self.ram_safety_margin,
            ),
            vram=TierBudget(
                capacity_bytes=self.vram_capacity,
                safety_margin_bytes=self.vram_safety_margin,
            ),
        )


DEFAULT_SIMULATOR_CONFIG = SimulatorConfig(
    ram_capacity=16 * 1024**3,
    vram_capacity=8 * 1024**3,
    disk_capacity=64 * 1024**3,
    ram_safety_margin=512 * 1024**2,
    vram_safety_margin=256 * 1024**2,
)
