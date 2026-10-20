"""Controller inputs, candidate descriptions, and predictions."""

from __future__ import annotations

from enum import StrEnum
from itertools import pairwise
from typing import Self

from pydantic import Field, NonNegativeInt, PositiveInt, model_validator

from mosaic.contracts.common import (
    CandidateId,
    ClusterId,
    Contract,
    NonEmptyStr,
    NonNegativeFloat,
    RequestId,
    Score,
)
from mosaic.contracts.memory import MemoryBudget, MemoryState
from mosaic.contracts.trace import RequestRecord


class CandidateType(StrEnum):
    """Whether a controller candidate is a component or a cluster."""

    COMPONENT = "component"
    CLUSTER = "cluster"


class ControllerCandidate(Contract):
    """Description of one component or cluster offered to the controller."""

    candidate_id: CandidateId
    candidate_type: CandidateType
    size_bytes: PositiveInt
    estimated_load_ms: NonNegativeFloat | None = None
    activation_frequency: Score | None = None


class CandidateUsage(Contract):
    """Historical routing statistics for one candidate."""

    candidate_id: CandidateId
    requests: NonNegativeInt = 0
    activations: NonNegativeInt = 0
    loads: NonNegativeInt = 0
    evictions: NonNegativeInt = 0


class ControllerRequest(Contract):
    """All information a controller may use to produce a prediction."""

    request: RequestRecord
    candidates: tuple[ControllerCandidate, ...] = ()
    resident_cluster_ids: tuple[ClusterId, ...] = ()
    memory: MemoryState = Field(default_factory=MemoryState)
    budget: MemoryBudget
    usage: tuple[CandidateUsage, ...] = ()

    @model_validator(mode="after")
    def _validate_candidates(self) -> Self:
        candidate_ids = [candidate.candidate_id for candidate in self.candidates]
        if len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError("candidates must not contain duplicate candidate_id values")
        if len(set(self.resident_cluster_ids)) != len(self.resident_cluster_ids):
            raise ValueError("resident_cluster_ids must not contain duplicates")
        return self


class ScoredCandidate(Contract):
    """A controller score for one candidate."""

    candidate_id: CandidateId
    candidate_type: CandidateType
    score: Score


class ControllerPrediction(Contract):
    """Ranked controller output, ordered from highest to lowest score."""

    request_id: RequestId
    controller_version: NonEmptyStr
    threshold: Score
    candidates: tuple[ScoredCandidate, ...] = ()

    @model_validator(mode="after")
    def _validate_ranking(self) -> Self:
        candidate_ids = [candidate.candidate_id for candidate in self.candidates]
        if len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError("prediction candidates must not contain duplicates")
        scores = [candidate.score for candidate in self.candidates]
        if any(current < following for current, following in pairwise(scores)):
            raise ValueError("prediction candidates must be ordered by descending score")
        return self

    @property
    def selected(self) -> tuple[ScoredCandidate, ...]:
        """Candidates at or above the configured threshold."""
        return tuple(
            candidate for candidate in self.candidates if candidate.score >= self.threshold
        )
