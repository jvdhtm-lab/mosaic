from __future__ import annotations

from pathlib import Path

import pytest

from mosaic.contracts import StorageTier
from mosaic.errors import (
    ComponentInUseError,
    ComponentNotFoundError,
    DependencyError,
    IncompatibleComponentError,
    IntegrityError,
    InvalidStateTransitionError,
    ResourceBudgetError,
    RuntimeOperationError,
)
from mosaic.registry import SQLiteRegistry
from mosaic.simulator import LoadSource, Simulator, SimulatorConfig
from mosaic.storage import SimulatedContentStore


def make_config(**overrides) -> SimulatorConfig:
    values = {
        "ram_capacity": 100_000,
        "vram_capacity": 100_000,
        "disk_capacity": 1_000_000,
        "load_base_ms": 1.0,
        "inference_base_ms": 2.0,
        "inference_ms_per_component": 0.5,
        "disk_to_ram_ms_per_gib": 0.0,
        "ram_to_vram_ms_per_gib": 0.0,
        "seed": 0,
    }
    values.update(overrides)
    return SimulatorConfig(**values)


def test_load_moves_component_from_disk_to_vram(make_component) -> None:
    simulator = Simulator(make_config())
    component = make_component("expert.0", size_bytes=4)
    simulator.register_component(component)

    result = simulator.load_component("expert.0")
    snapshot = simulator.snapshot()

    assert result.simulated is True
    assert result.cache_hit is False
    assert result.source_tier is LoadSource.DISK
    assert result.target_tier is StorageTier.VRAM
    assert result.bytes_transferred == 8
    assert result.latency_ms == 1.0
    assert snapshot.simulated is True
    assert snapshot.ram_hits == 0
    assert snapshot.cache_misses == 1
    assert snapshot.bytes_read_from_disk == 4
    assert snapshot.bytes_written_to_ram == 4
    assert snapshot.bytes_written_to_vram == 4
    assert {placement.tier for placement in snapshot.memory.placements} == {
        StorageTier.RAM,
        StorageTier.VRAM,
    }


def test_second_load_is_a_cache_hit(make_component) -> None:
    simulator = Simulator(make_config())
    simulator.register_component(make_component("expert.0", size_bytes=4))
    simulator.load_component("expert.0")

    result = simulator.load_component("expert.0")
    snapshot = simulator.snapshot()

    assert result.cache_hit is True
    assert result.bytes_transferred == 0
    assert snapshot.cache_hits == 1
    assert snapshot.cache_misses == 1
    assert simulator.cache_hit_rate() == pytest.approx(0.5)


def test_load_loads_dependencies_first(make_component) -> None:
    simulator = Simulator(make_config())
    simulator.register_component(make_component("dependency", size_bytes=4))
    simulator.register_component(
        make_component("expert.0", size_bytes=4, dependencies=("dependency",))
    )

    result = simulator.load_component("expert.0")

    assert result.dependencies_loaded == ("dependency",)
    assert simulator.resident_components() == ("dependency", "expert.0")


def test_prefetch_stages_in_ram_and_then_counts_as_hit(make_component) -> None:
    simulator = Simulator(make_config())
    simulator.register_component(make_component("expert.0", size_bytes=4))

    prefetch = simulator.prefetch_component("expert.0")
    load = simulator.load_component("expert.0")
    snapshot = simulator.snapshot()

    assert prefetch.target_tier is StorageTier.RAM
    assert prefetch.bytes_transferred == 4
    assert load.source_tier is LoadSource.RAM
    assert load.bytes_transferred == 4
    assert snapshot.prefetch_attempts == 1
    assert snapshot.prefetch_hits == 1
    assert snapshot.ram_hits == 1


def test_simulator_enforces_ram_and_vram_capacities(make_component) -> None:
    simulator = Simulator(make_config(ram_capacity=20, vram_capacity=10))
    simulator.register_component(make_component("a", size_bytes=6))
    simulator.register_component(make_component("b", size_bytes=6))
    simulator.load_component("a")

    with pytest.raises(ResourceBudgetError, match="vram"):
        simulator.load_component("b")

    assert simulator.staged_components() == ("a", "b")
    assert simulator.resident_components() == ("a",)


def test_simulator_enforces_disk_capacity(make_component) -> None:
    simulator = Simulator(make_config(disk_capacity=10))
    simulator.register_component(make_component("a", size_bytes=6))

    with pytest.raises(ResourceBudgetError, match="disk"):
        simulator.register_component(make_component("b", size_bytes=6))


def test_in_use_components_cannot_be_evicted(make_component) -> None:
    simulator = Simulator(make_config())
    simulator.register_component(make_component("expert.0", size_bytes=4))

    with simulator.use("expert.0"):
        assert simulator.snapshot().in_use_component_ids == ("expert.0",)
        with pytest.raises(ComponentInUseError):
            simulator.evict_component("expert.0")

    simulator.evict_component("expert.0")
    assert simulator.resident_components() == ()
    assert simulator.snapshot().evictions == 1


def test_least_recently_used_tracks_access_order(make_component) -> None:
    simulator = Simulator(make_config())
    simulator.register_component(make_component("a", size_bytes=3))
    simulator.register_component(make_component("b", size_bytes=3))
    simulator.load_component("a")
    simulator.load_component("b")
    simulator.load_component("a")

    assert simulator.least_recently_used(StorageTier.VRAM) == "b"
    assert simulator.least_recently_used(StorageTier.RAM) == "b"


def test_failed_component_load_is_injected(make_component) -> None:
    simulator = Simulator(make_config(fail_components=("bad",)))
    simulator.register_component(make_component("bad", size_bytes=4))

    with pytest.raises(RuntimeOperationError, match="simulated load failure"):
        simulator.load_component("bad")


def test_missing_component_is_reported_by_simulator() -> None:
    simulator = Simulator(make_config())

    with pytest.raises(ComponentNotFoundError, match="not known"):
        simulator.load_component("missing")


def test_simulator_rejects_incompatible_components(make_component) -> None:
    simulator = Simulator(make_config(precision="fp16", supported_features=("prefetch",)))

    with pytest.raises(IncompatibleComponentError, match="runtime"):
        simulator.register_component(make_component("a", runtime_name="other"))
    with pytest.raises(IncompatibleComponentError, match="version"):
        simulator.register_component(make_component("b", runtime_version="9.9.9"))
    with pytest.raises(IncompatibleComponentError, match="features"):
        simulator.register_component(make_component("c", required_features=("speculative",)))
    with pytest.raises(IncompatibleComponentError, match="precision"):
        simulator.register_component(make_component("d", precision="fp32"))


def test_simulator_accepts_matching_compatibility(make_component) -> None:
    simulator = Simulator(
        make_config(
            runtime_version="0.1.0",
            precision="fp16",
            supported_features=("prefetch",),
        )
    )
    simulator.register_component(
        make_component(
            "a",
            runtime_version="0.1.0",
            precision="fp16",
            required_features=("prefetch",),
        )
    )

    assert simulator.load_component("a").cache_hit is False


def test_execute_loads_and_activates_components(make_component) -> None:
    simulator = Simulator(make_config())
    simulator.register_component(make_component("a", size_bytes=4))
    simulator.register_component(make_component("b", size_bytes=4))

    execution = simulator.execute("req-1", ("a", "b", "a"))
    snapshot = simulator.snapshot()

    assert execution.request_id == "req-1"
    assert execution.activated_components == ("a", "b")
    assert execution.simulated is True
    assert execution.total_latency_ms == pytest.approx(
        sum(result.latency_ms for result in execution.load_results) + execution.inference_latency_ms
    )
    assert {item.component_id: item.count for item in snapshot.activations} == {"a": 1, "b": 1}
    assert snapshot.in_use_component_ids == ()


def test_execute_without_components_has_base_inference_latency() -> None:
    simulator = Simulator(make_config())

    execution = simulator.execute("req-1", ())

    assert execution.activated_components == ()
    assert execution.total_latency_ms == 2.0


def test_activate_requires_resident_component(make_component) -> None:
    simulator = Simulator(make_config())
    simulator.register_component(make_component("a", size_bytes=4))

    with pytest.raises(InvalidStateTransitionError, match="not resident"):
        simulator.activate("a")

    simulator.load_component("a")
    simulator.activate("a")
    assert simulator.snapshot().activations[0].count == 1


def test_evict_from_ram_keeps_vram_copy(make_component) -> None:
    simulator = Simulator(make_config())
    simulator.register_component(make_component("a", size_bytes=4))
    simulator.load_component("a")

    simulator.evict_from_ram("a")

    assert simulator.staged_components() == ()
    assert simulator.resident_components() == ("a",)


def test_available_bytes_and_evict_errors(make_component) -> None:
    simulator = Simulator(make_config(ram_capacity=10, vram_capacity=10))
    simulator.register_component(make_component("a", size_bytes=4))

    assert simulator.available_bytes(StorageTier.RAM) == 10
    simulator.load_component("a")
    assert simulator.available_bytes(StorageTier.RAM) == 6
    assert simulator.available_bytes(StorageTier.VRAM) == 6

    with pytest.raises(InvalidStateTransitionError, match="not staged"):
        simulator.evict_from_ram("missing")
    with pytest.raises(InvalidStateTransitionError, match="not resident"):
        simulator.evict_component("missing")


def test_simulator_detects_dependency_cycles_between_registered_components(make_component) -> None:
    simulator = Simulator(make_config())
    simulator.register_component(make_component("a", size_bytes=4, dependencies=("b",)))
    simulator.register_component(make_component("b", size_bytes=4, dependencies=("a",)))

    with pytest.raises(DependencyError, match="cycle"):
        simulator.load_component("a")


def test_simulator_auto_registers_from_registry(tmp_path: Path, make_component) -> None:
    store = SimulatedContentStore(tmp_path / "content")
    location, content_hash = store.create(size_bytes=4, seed=1)
    component = make_component(
        "expert.0",
        storage=location,
        content_hash=content_hash,
        size_bytes=4,
    )
    with SQLiteRegistry(tmp_path / "registry.sqlite3") as registry:
        registry.register_component(component)
        simulator = Simulator(make_config(verify_content_on_load=True), registry=registry)

        result = simulator.load_component("expert.0")

        assert result.cache_hit is False
        assert simulator.snapshot().disk_component_ids == ("expert.0",)


def test_simulator_verifies_content_when_loading_from_registry(
    tmp_path: Path, make_component
) -> None:
    store = SimulatedContentStore(tmp_path / "content")
    location, content_hash = store.create(size_bytes=4, seed=1)
    component = make_component(
        "expert.0",
        storage=location,
        content_hash=content_hash,
        size_bytes=4,
    )
    with SQLiteRegistry(tmp_path / "registry.sqlite3") as registry:
        registry.register_component(component)
        Path(location.uri).write_text("tampered", encoding="utf-8")
        simulator = Simulator(make_config(verify_content_on_load=True), registry=registry)

        with pytest.raises(IntegrityError):
            simulator.load_component("expert.0")


def test_simulator_identity_capabilities_and_jitter_are_deterministic(make_component) -> None:
    config = make_config(
        runtime_name="simulator", runtime_version="0.2.0", latency_jitter_ratio=0.5
    )
    first = Simulator(config)
    second = Simulator(config)
    first.register_component(make_component("a", size_bytes=4))
    second.register_component(make_component("b", size_bytes=4))

    assert first.identity.name == "simulator"
    assert first.identity.device == "simulated"
    assert first.capabilities.notes == ("simulated measurements",)
    assert first.load_component("a").latency_ms == second.load_component("b").latency_ms


def test_simulator_snapshot_has_no_hidden_state_aliasing(make_component) -> None:
    simulator = Simulator(make_config())
    simulator.register_component(make_component("a", size_bytes=4))
    simulator.load_component("a")

    first = simulator.snapshot()
    second = simulator.snapshot()

    assert first == second
    assert first is not second
