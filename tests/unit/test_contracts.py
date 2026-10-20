from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from mosaic.contracts import (
    ActivationObservation,
    CacheStatistics,
    CandidateType,
    CandidateUsage,
    ClusterManifest,
    ComponentMetadata,
    ComponentPlacement,
    ControllerCandidate,
    ControllerPrediction,
    ControllerRequest,
    ExecutionTrace,
    LatencyMeasurements,
    MemoryAction,
    MemoryActionType,
    MemoryBudget,
    MemoryMeasurements,
    MemoryPlan,
    MemoryPlanSource,
    MemoryState,
    ModelIdentity,
    RequestRecord,
    RuntimeCapabilities,
    RuntimeIdentity,
    ScoredCandidate,
    StorageTier,
    TaskOutcome,
    TierBudget,
    TierUsage,
    TraceEvent,
    TraceEventType,
)


def test_component_metadata_round_trip(component_metadata: ComponentMetadata) -> None:
    restored = ComponentMetadata.model_validate_json(component_metadata.model_dump_json())

    assert restored == component_metadata
    assert restored.component_id != restored.content_hash


def test_component_metadata_is_frozen(component_metadata: ComponentMetadata) -> None:
    with pytest.raises(ValidationError):
        component_metadata.size_bytes = 1


def test_component_rejects_unknown_fields(component_metadata: ComponentMetadata) -> None:
    data = component_metadata.model_dump()
    data["unexpected"] = True

    with pytest.raises(ValidationError, match="unexpected"):
        ComponentMetadata.model_validate(data)


def test_component_rejects_invalid_hash(component_metadata: ComponentMetadata) -> None:
    data = component_metadata.model_dump()
    data["content_hash"] = "A" * 64

    with pytest.raises(ValidationError, match="content_hash"):
        ComponentMetadata.model_validate(data)


def test_component_rejects_zero_size(component_metadata: ComponentMetadata) -> None:
    data = component_metadata.model_dump()
    data["size_bytes"] = 0

    with pytest.raises(ValidationError, match="size_bytes"):
        ComponentMetadata.model_validate(data)


def test_component_rejects_self_dependency(component_metadata: ComponentMetadata) -> None:
    data = component_metadata.model_dump()
    data["dependencies"] = [component_metadata.component_id]

    with pytest.raises(ValidationError, match="depend on itself"):
        ComponentMetadata.model_validate(data)


def test_component_rejects_duplicate_dependencies(component_metadata: ComponentMetadata) -> None:
    data = component_metadata.model_dump()
    data["dependencies"] = ["expert.1", "expert.1"]

    with pytest.raises(ValidationError, match="duplicates"):
        ComponentMetadata.model_validate(data)


def test_cluster_round_trip(cluster_manifest: ClusterManifest) -> None:
    restored = ClusterManifest.model_validate_json(cluster_manifest.model_dump_json())

    assert restored == cluster_manifest


def test_cluster_rejects_empty_members(cluster_manifest: ClusterManifest) -> None:
    data = cluster_manifest.model_dump()
    data["component_ids"] = []

    with pytest.raises(ValidationError, match="component_ids"):
        ClusterManifest.model_validate(data)


def test_cluster_rejects_duplicate_members(cluster_manifest: ClusterManifest) -> None:
    data = cluster_manifest.model_dump()
    data["component_ids"] = ["expert.0", "expert.0"]

    with pytest.raises(ValidationError, match="duplicates"):
        ClusterManifest.model_validate(data)


def test_runtime_capabilities_accept_supported_combinations() -> None:
    capabilities = RuntimeCapabilities(
        can_enumerate_components=True,
        can_load_components=True,
        can_evict_components=True,
        can_observe_activations=ActivationObservation.PER_COMPONENT,
        supports_prefetch=True,
        supports_concurrent_requests=False,
    )

    assert capabilities.can_observe_activations is ActivationObservation.PER_COMPONENT


def test_runtime_capabilities_reject_observation_without_enumeration() -> None:
    with pytest.raises(ValidationError, match="component enumeration"):
        RuntimeCapabilities(
            can_enumerate_components=False,
            can_load_components=True,
            can_evict_components=True,
            can_observe_activations=ActivationObservation.PER_COMPONENT,
            supports_prefetch=False,
            supports_concurrent_requests=False,
        )


def test_runtime_capabilities_reject_prefetch_without_loading() -> None:
    with pytest.raises(ValidationError, match="prefetching"):
        RuntimeCapabilities(
            can_enumerate_components=False,
            can_load_components=False,
            can_evict_components=False,
            can_observe_activations=ActivationObservation.NONE,
            supports_prefetch=True,
            supports_concurrent_requests=False,
        )


def test_tier_budget_computes_effective_capacity() -> None:
    budget = TierBudget(capacity_bytes=1024, safety_margin_bytes=24)

    assert budget.effective_capacity_bytes == 1000


def test_tier_budget_rejects_margin_above_capacity() -> None:
    with pytest.raises(ValidationError, match="safety_margin_bytes"):
        TierBudget(capacity_bytes=1024, safety_margin_bytes=1025)


def test_memory_budget_selects_tiers(memory_budget: MemoryBudget) -> None:
    assert memory_budget.effective_capacity_bytes(StorageTier.RAM) == 8 * 1024**3 - 512 * 1024**2
    assert memory_budget.effective_capacity_bytes(StorageTier.VRAM) == 0


def test_memory_state_round_trip() -> None:
    state = MemoryState(
        ram=TierUsage(resident_bytes=4096, runtime_overhead_bytes=512),
        placements=(
            ComponentPlacement(
                component_id="expert.0",
                tier=StorageTier.RAM,
                size_bytes=4096,
            ),
        ),
    )

    restored = MemoryState.model_validate_json(state.model_dump_json())

    assert restored == state
    assert state.ram.used_bytes == 4608


def test_memory_state_rejects_placement_total_mismatch() -> None:
    with pytest.raises(ValidationError, match="resident_bytes"):
        MemoryState(
            ram=TierUsage(resident_bytes=1),
            placements=(
                ComponentPlacement(
                    component_id="expert.0",
                    tier=StorageTier.RAM,
                    size_bytes=4096,
                ),
            ),
        )


def test_memory_state_rejects_duplicate_placement() -> None:
    placement = ComponentPlacement(
        component_id="expert.0",
        tier=StorageTier.RAM,
        size_bytes=4096,
    )

    with pytest.raises(ValidationError, match="duplicate placement"):
        MemoryState(
            ram=TierUsage(resident_bytes=8192),
            placements=(placement, placement),
        )


def test_memory_state_allows_component_in_both_tiers() -> None:
    state = MemoryState(
        ram=TierUsage(resident_bytes=4096),
        vram=TierUsage(resident_bytes=4096),
        placements=(
            ComponentPlacement(
                component_id="expert.0",
                tier=StorageTier.RAM,
                size_bytes=4096,
            ),
            ComponentPlacement(
                component_id="expert.0",
                tier=StorageTier.VRAM,
                size_bytes=4096,
            ),
        ),
    )

    assert len(state.placements) == 2


def test_memory_action_requires_target_for_mutations() -> None:
    with pytest.raises(ValidationError, match="target tier"):
        MemoryAction(
            action=MemoryActionType.LOAD,
            component_id="expert.0",
            reason="required by request",
        )


def test_memory_action_rejects_target_for_retain() -> None:
    with pytest.raises(ValidationError, match="retain"):
        MemoryAction(
            action=MemoryActionType.RETAIN,
            component_id="expert.0",
            target_tier=StorageTier.VRAM,
            reason="keep resident",
        )


def test_memory_action_accepts_valid_mutations() -> None:
    load = MemoryAction(
        action=MemoryActionType.LOAD,
        component_id="expert.0",
        target_tier=StorageTier.VRAM,
        reason="required by request",
    )
    retain = MemoryAction(
        action=MemoryActionType.RETAIN,
        component_id="expert.0",
        reason="frequently used",
    )

    assert load.target_tier is StorageTier.VRAM
    assert retain.target_tier is None


def test_memory_plan_requires_controller_version() -> None:
    with pytest.raises(ValidationError, match="controller_version"):
        MemoryPlan(
            request_id="req-1",
            source=MemoryPlanSource.CONTROLLER,
        )


def test_memory_plan_accepts_empty_fallback_plan() -> None:
    plan = MemoryPlan(request_id="req-1", source=MemoryPlanSource.FALLBACK)

    assert plan.actions == ()


def test_memory_plan_rejects_action_request_mismatch() -> None:
    with pytest.raises(ValidationError, match="request_id"):
        MemoryPlan(
            request_id="req-1",
            source=MemoryPlanSource.CONTROLLER,
            controller_version="0.1",
            actions=(
                MemoryAction(
                    action=MemoryActionType.LOAD,
                    component_id="expert.0",
                    target_tier=StorageTier.VRAM,
                    reason="required",
                    request_id="req-2",
                ),
            ),
        )


def test_memory_plan_rejects_duplicate_actions() -> None:
    action = MemoryAction(
        action=MemoryActionType.LOAD,
        component_id="expert.0",
        target_tier=StorageTier.VRAM,
        reason="required",
    )

    with pytest.raises(ValidationError, match="duplicate action"):
        MemoryPlan(
            request_id="req-1",
            source=MemoryPlanSource.HEURISTIC,
            actions=(action, action),
        )


def make_request() -> RequestRecord:
    return RequestRecord(
        request_id="req-1",
        feature_schema="v1",
        features={"language": "python", "tokens": 12},
    )


def make_runtime() -> RuntimeIdentity:
    return RuntimeIdentity(name="simulator", version="0.1", device="cpu")


def make_trace(
    model_identity: ModelIdentity,
    *,
    activated_components: tuple[str, ...] | None = (),
) -> ExecutionTrace:
    return ExecutionTrace(
        trace_id="trace-1",
        request=make_request(),
        source_model=model_identity,
        runtime=make_runtime(),
        predicted_components=("expert.0",),
        activated_components=activated_components,
        events=(
            TraceEvent(
                sequence=0,
                event_type=TraceEventType.ACTIVATED,
                component_id="expert.0",
                tier=StorageTier.VRAM,
            ),
        ),
        memory=MemoryMeasurements(peak_ram_bytes=1024),
        latency=LatencyMeasurements(end_to_end_ms=12.5),
        cache=CacheStatistics(hits=2, misses=1),
        outcome=TaskOutcome(success=True, quality_score=1.0),
    )


def test_trace_distinguishes_missing_and_empty_activations(
    model_identity: ModelIdentity,
) -> None:
    observed_none = make_trace(model_identity, activated_components=())
    unobserved = make_trace(model_identity, activated_components=None)

    assert observed_none.activated_components == ()
    assert unobserved.activated_components is None
    restored = ExecutionTrace.model_validate_json(observed_none.model_dump_json())
    assert restored.activated_components == ()


def test_trace_predicted_and_activated_are_separate(model_identity: ModelIdentity) -> None:
    trace = make_trace(model_identity, activated_components=("expert.1",))

    assert trace.predicted_components == ("expert.0",)
    assert trace.activated_components == ("expert.1",)


def test_trace_round_trip(model_identity: ModelIdentity) -> None:
    trace = make_trace(model_identity)

    restored = ExecutionTrace.model_validate_json(trace.model_dump_json())

    assert restored == trace


def test_trace_rejects_duplicate_predictions(model_identity: ModelIdentity) -> None:
    data = make_trace(model_identity).model_dump()
    data["predicted_components"] = ["expert.0", "expert.0"]

    with pytest.raises(ValidationError, match="duplicates"):
        ExecutionTrace.model_validate(data)


def test_trace_rejects_out_of_order_events(model_identity: ModelIdentity) -> None:
    data = make_trace(model_identity).model_dump()
    data["events"] = [
        TraceEvent(
            sequence=1,
            event_type=TraceEventType.ACTIVATED,
            component_id="expert.0",
        ),
        TraceEvent(
            sequence=1,
            event_type=TraceEventType.EVICTED,
            component_id="expert.0",
        ),
    ]

    with pytest.raises(ValidationError, match="strictly increasing"):
        ExecutionTrace.model_validate(data)


def test_trace_rejects_non_finite_feature(model_identity: ModelIdentity) -> None:
    data = make_trace(model_identity).model_dump()
    data["request"]["features"]["temperature"] = math.inf

    with pytest.raises(ValidationError, match="finite"):
        ExecutionTrace.model_validate(data)


def test_cache_hit_rate_requires_both_counters() -> None:
    assert CacheStatistics(hits=2, misses=1).hit_rate == pytest.approx(2 / 3)
    assert CacheStatistics(hits=2).hit_rate is None
    assert CacheStatistics(hits=0, misses=0).hit_rate is None


def make_candidates() -> tuple[ControllerCandidate, ...]:
    return (
        ControllerCandidate(
            candidate_id="expert.0",
            candidate_type=CandidateType.COMPONENT,
            size_bytes=4096,
            estimated_load_ms=1.5,
            activation_frequency=0.8,
        ),
        ControllerCandidate(
            candidate_id="cluster-0",
            candidate_type=CandidateType.CLUSTER,
            size_bytes=8192,
        ),
    )


def test_controller_request_round_trip(memory_budget: MemoryBudget) -> None:
    request = ControllerRequest(
        request=make_request(),
        candidates=make_candidates(),
        resident_cluster_ids=("cluster-0",),
        budget=memory_budget,
        usage=(
            CandidateUsage(
                candidate_id="expert.0",
                requests=10,
                activations=8,
                loads=3,
                evictions=1,
            ),
        ),
    )

    restored = ControllerRequest.model_validate_json(request.model_dump_json())

    assert restored == request


def test_controller_request_rejects_duplicate_candidates(
    memory_budget: MemoryBudget,
) -> None:
    candidate = make_candidates()[0]

    with pytest.raises(ValidationError, match="duplicate"):
        ControllerRequest(
            request=make_request(),
            candidates=(candidate, candidate),
            budget=memory_budget,
        )


def test_controller_prediction_orders_and_selects() -> None:
    prediction = ControllerPrediction(
        request_id="req-1",
        controller_version="0.1",
        threshold=0.5,
        candidates=(
            ScoredCandidate(
                candidate_id="expert.0",
                candidate_type=CandidateType.COMPONENT,
                score=0.9,
            ),
            ScoredCandidate(
                candidate_id="cluster-0",
                candidate_type=CandidateType.CLUSTER,
                score=0.4,
            ),
        ),
    )

    assert [candidate.candidate_id for candidate in prediction.selected] == ["expert.0"]


def test_controller_prediction_rejects_ascending_scores() -> None:
    with pytest.raises(ValidationError, match="descending"):
        ControllerPrediction(
            request_id="req-1",
            controller_version="0.1",
            threshold=0.5,
            candidates=(
                ScoredCandidate(
                    candidate_id="expert.0",
                    candidate_type=CandidateType.COMPONENT,
                    score=0.4,
                ),
                ScoredCandidate(
                    candidate_id="cluster-0",
                    candidate_type=CandidateType.CLUSTER,
                    score=0.9,
                ),
            ),
        )


def test_controller_prediction_rejects_out_of_range_score() -> None:
    with pytest.raises(ValidationError, match="score"):
        ScoredCandidate(
            candidate_id="expert.0",
            candidate_type=CandidateType.COMPONENT,
            score=1.1,
        )


def test_controller_prediction_rejects_duplicate_candidates() -> None:
    candidate = ScoredCandidate(
        candidate_id="expert.0",
        candidate_type=CandidateType.COMPONENT,
        score=0.9,
    )

    with pytest.raises(ValidationError, match="duplicates"):
        ControllerPrediction(
            request_id="req-1",
            controller_version="0.1",
            threshold=0.5,
            candidates=(candidate, candidate),
        )
