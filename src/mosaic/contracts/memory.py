"""Memory budgets, residency state, and action proposals."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import Field, NonNegativeInt, PositiveInt, model_validator

from mosaic.contracts.common import ComponentId, Contract, NonEmptyStr, RequestId


class StorageTier(StrEnum):
    """Resource tier in which a component can be resident."""

    RAM = "ram"
    VRAM = "vram"


class MemoryActionType(StrEnum):
    """Actions a memory manager can be asked to perform."""

    LOAD = "load"
    PREFETCH = "prefetch"
    RETAIN = "retain"
    EVICT = "evict"


class MemoryPlanSource(StrEnum):
    """Origin of a memory plan."""

    CONTROLLER = "controller"
    HEURISTIC = "heuristic"
    FALLBACK = "fallback"


class TierBudget(Contract):
    """Capacity and safety margin for one memory tier."""

    capacity_bytes: NonNegativeInt
    safety_margin_bytes: NonNegativeInt = 0

    @model_validator(mode="after")
    def _validate_margin(self) -> Self:
        if self.safety_margin_bytes > self.capacity_bytes:
            raise ValueError("safety_margin_bytes must not exceed capacity_bytes")
        return self

    @property
    def effective_capacity_bytes(self) -> int:
        """Capacity available to components after subtracting the margin."""
        return self.capacity_bytes - self.safety_margin_bytes


class MemoryBudget(Contract):
    """RAM and VRAM budgets enforced by the memory manager."""

    ram: TierBudget
    vram: TierBudget

    def tier(self, tier: StorageTier) -> TierBudget:
        """Return the budget for a storage tier."""
        return self.ram if tier is StorageTier.RAM else self.vram

    def effective_capacity_bytes(self, tier: StorageTier) -> int:
        """Return usable capacity for a storage tier."""
        return self.tier(tier).effective_capacity_bytes


class TierUsage(Contract):
    """Observed usage of one memory tier."""

    resident_bytes: NonNegativeInt = 0
    runtime_overhead_bytes: NonNegativeInt = 0

    @property
    def used_bytes(self) -> int:
        """Total bytes consumed by components and runtime allocations."""
        return self.resident_bytes + self.runtime_overhead_bytes


class ComponentPlacement(Contract):
    """A component's size and tier in a memory snapshot."""

    component_id: ComponentId
    tier: StorageTier
    size_bytes: PositiveInt


class MemoryState(Contract):
    """Inspectable residency snapshot for both memory tiers."""

    ram: TierUsage = Field(default_factory=TierUsage)
    vram: TierUsage = Field(default_factory=TierUsage)
    placements: tuple[ComponentPlacement, ...] = ()

    @model_validator(mode="after")
    def _validate_placements(self) -> Self:
        seen: set[tuple[str, StorageTier]] = set()
        totals: dict[StorageTier, int] = {StorageTier.RAM: 0, StorageTier.VRAM: 0}
        for placement in self.placements:
            key = (placement.component_id, placement.tier)
            if key in seen:
                raise ValueError(
                    f"duplicate placement for {placement.component_id!r} in {placement.tier.value}"
                )
            seen.add(key)
            totals[placement.tier] += placement.size_bytes
        for tier, tier_usage in ((StorageTier.RAM, self.ram), (StorageTier.VRAM, self.vram)):
            if totals[tier] != tier_usage.resident_bytes:
                raise ValueError(f"{tier.value} resident_bytes does not match placement sizes")
        return self


class MemoryAction(Contract):
    """One proposed memory operation.

    A plan never mutates state directly; the memory manager validates and
    executes it against current budgets and lifecycle state.
    """

    action: MemoryActionType
    component_id: ComponentId
    target_tier: StorageTier | None = None
    reason: NonEmptyStr
    request_id: RequestId | None = None

    @model_validator(mode="after")
    def _validate_target_tier(self) -> Self:
        if self.action is MemoryActionType.RETAIN:
            if self.target_tier is not None:
                raise ValueError("retain actions must not specify a target tier")
            return self
        if self.target_tier is None:
            raise ValueError(f"{self.action.value} actions require a target tier")
        return self


class MemoryPlan(Contract):
    """An ordered set of actions proposed for one request."""

    request_id: RequestId
    source: MemoryPlanSource
    actions: tuple[MemoryAction, ...] = ()
    controller_version: NonEmptyStr | None = None

    @model_validator(mode="after")
    def _validate_plan(self) -> Self:
        if self.source is MemoryPlanSource.CONTROLLER and self.controller_version is None:
            raise ValueError("controller plans must declare controller_version")
        seen: set[tuple[MemoryActionType, str, StorageTier | None]] = set()
        for action in self.actions:
            if action.request_id is not None and action.request_id != self.request_id:
                raise ValueError("action request_id does not match the plan request_id")
            key = (action.action, action.component_id, action.target_tier)
            if key in seen:
                raise ValueError("duplicate action in memory plan")
            seen.add(key)
        return self
