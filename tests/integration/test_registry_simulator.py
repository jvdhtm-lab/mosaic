from __future__ import annotations

from pathlib import Path

from mosaic.contracts import ClusterManifest, ModelIdentity
from mosaic.registry import SQLiteRegistry
from mosaic.simulator import Simulator, SimulatorConfig
from mosaic.storage import SimulatedContentStore


def test_registry_and_simulator_share_component_identity(
    tmp_path: Path, make_component, model_identity: ModelIdentity
) -> None:
    store = SimulatedContentStore(tmp_path / "content")
    dependency_location, dependency_hash = store.create(size_bytes=4096, seed=1)
    expert_location, expert_hash = store.create(size_bytes=8192, seed=2)
    dependency = make_component(
        "mixtral/layer.0/router",
        storage=dependency_location,
        content_hash=dependency_hash,
        size_bytes=4096,
    )
    expert = make_component(
        "mixtral/layer.0/expert.0",
        storage=expert_location,
        content_hash=expert_hash,
        size_bytes=8192,
        dependencies=("mixtral/layer.0/router",),
    )
    cluster = ClusterManifest(
        cluster_id="layer-0",
        source_model=model_identity,
        component_ids=(dependency.component_id, expert.component_id),
    )

    with SQLiteRegistry(tmp_path / "registry.sqlite3") as registry:
        registry.register_component(dependency)
        registry.register_component(expert)
        registry.register_cluster(cluster)

        simulator = Simulator(
            SimulatorConfig(
                ram_capacity=32 * 1024**3,
                vram_capacity=16 * 1024**3,
                disk_capacity=128 * 1024**3,
                supported_features=("prefetch",),
                verify_content_on_load=True,
            ),
            registry=registry,
        )
        simulator.prefetch_component("mixtral/layer.0/router")
        execution = simulator.execute("req-1", ("mixtral/layer.0/expert.0",))
        snapshot = simulator.snapshot()

        assert execution.activated_components == ("mixtral/layer.0/expert.0",)
        assert execution.load_results[0].dependencies_loaded == ("mixtral/layer.0/router",)
        assert snapshot.disk_component_ids == (
            "mixtral/layer.0/expert.0",
            "mixtral/layer.0/router",
        )
        assert snapshot.prefetch_hits == 1
        assert snapshot.memory.vram.resident_bytes == 4096 + 8192
        assert registry.get_cluster("layer-0") == cluster
