"""Versioned execution-trace contracts.

Missing measurements are represented as ``None``. A missing activation
observation (``None``) is distinct from an observation that found no active
components (an empty tuple).
"""

from __future__ import annotations

import math
from enum import StrEnum
from itertools import pairwise
from typing import Annotated, Literal, Self

from pydantic import (
    Field,
    NonNegativeInt,
    StringConstraints,
    model_validator,
)

from mosaic.contracts.common import (
    ComponentId,
    Contract,
    NonEmptyStr,
    NonNegativeFloat,
    RequestId,
    Score,
    TraceId,
)
from mosaic.contracts.memory import StorageTier
from mosaic.contracts.model import ModelIdentity, RuntimeIdentity

type FeatureName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
type FeatureValue = bool | int | float | str


class RequestRecord(Contract):
    """Privacy-safe request identity and features."""

    request_id: RequestId
    feature_schema: NonEmptyStr
    features: dict[FeatureName, FeatureValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_features(self) -> Self:
        for name, value in self.features.items():
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError(f"feature {name!r} must be a finite number")
        return self


class TraceEventType(StrEnum):
    """Runtime events recorded in an execution trace."""

    LOAD_STARTED = "load_started"
    LOAD_COMPLETED = "load_completed"
    LOAD_FAILED = "load_failed"
    PREFETCH_STARTED = "prefetch_started"
    PREFETCH_COMPLETED = "prefetch_completed"
    PREFETCH_FAILED = "prefetch_failed"
    EVICTED = "evicted"
    ACTIVATED = "activated"


class TraceEvent(Contract):
    """One ordered component event within a trace."""

    sequence: NonNegativeInt
    event_type: TraceEventType
    component_id: ComponentId
    tier: StorageTier | None = None
    latency_ms: NonNegativeFloat | None = None
    detail: NonEmptyStr | None = None


class MemoryMeasurements(Contract):
    """Observed memory measurements; unavailable values remain ``None``."""

    ram_bytes: NonNegativeInt | None = None
    vram_bytes: NonNegativeInt | None = None
    peak_ram_bytes: NonNegativeInt | None = None
    peak_vram_bytes: NonNegativeInt | None = None


class LatencyMeasurements(Contract):
    """Observed latency measurements in milliseconds."""

    queue_ms: NonNegativeFloat | None = None
    load_ms: NonNegativeFloat | None = None
    inference_ms: NonNegativeFloat | None = None
    end_to_end_ms: NonNegativeFloat | None = None


class CacheStatistics(Contract):
    """Observed cache counters; unavailable counters remain ``None``."""

    hits: NonNegativeInt | None = None
    misses: NonNegativeInt | None = None
    evictions: NonNegativeInt | None = None
    prefetch_attempts: NonNegativeInt | None = None
    prefetch_hits: NonNegativeInt | None = None

    @property
    def hit_rate(self) -> float | None:
        """Hit rate when both hit and miss counts are available."""
        if self.hits is None or self.misses is None:
            return None
        total = self.hits + self.misses
        if total == 0:
            return None
        return self.hits / total


class TaskOutcome(Contract):
    """Observed task outcome, separate from system-efficiency metrics."""

    success: bool
    quality_score: Score | None = None
    error: NonEmptyStr | None = None


class ExecutionTrace(Contract):
    """One request's observed execution, suitable for JSONL persistence."""

    trace_version: Literal[1] = 1
    trace_id: TraceId
    request: RequestRecord
    source_model: ModelIdentity
    runtime: RuntimeIdentity
    predicted_components: tuple[ComponentId, ...] | None = None
    activated_components: tuple[ComponentId, ...] | None = None
    events: tuple[TraceEvent, ...] = ()
    memory: MemoryMeasurements | None = None
    latency: LatencyMeasurements | None = None
    cache: CacheStatistics | None = None
    outcome: TaskOutcome | None = None

    @model_validator(mode="after")
    def _validate_trace(self) -> Self:
        for label, components in (
            ("predicted_components", self.predicted_components),
            ("activated_components", self.activated_components),
        ):
            if components is not None and len(set(components)) != len(components):
                raise ValueError(f"{label} must not contain duplicates")
        sequences = [event.sequence for event in self.events]
        if any(current >= following for current, following in pairwise(sequences)):
            raise ValueError("event sequences must be strictly increasing")
        return self
