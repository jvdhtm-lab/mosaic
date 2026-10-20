from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from mosaic.contracts import ClusterManifest, ComponentMetadata, ModelIdentity
from mosaic.errors import (
    ClusterNotFoundError,
    ComponentNotFoundError,
    DependencyError,
    DuplicateClusterError,
    DuplicateComponentError,
    IncompatibleComponentError,
    IntegrityError,
    InvalidManifestError,
)
from mosaic.registry import SQLiteRegistry
from mosaic.storage import SimulatedContentStore


@pytest.fixture
def store(tmp_path: Path) -> SimulatedContentStore:
    return SimulatedContentStore(tmp_path / "content")


def publish(
    make_component,
    store: SimulatedContentStore,
    component_id: str,
    *,
    size_bytes: int = 4096,
    seed: int = 1,
    dependencies: tuple[str, ...] = (),
) -> ComponentMetadata:
    location, content_hash = store.create(size_bytes=size_bytes, seed=seed)
    return make_component(
        component_id,
        storage=location,
        content_hash=content_hash,
        size_bytes=size_bytes,
        dependencies=dependencies,
    )


def test_registry_round_trip_and_persistence(tmp_path: Path, make_component, store) -> None:
    database = tmp_path / "registry.sqlite3"
    metadata = publish(make_component, store, "expert.0")

    with SQLiteRegistry(database) as registry:
        registry.register_component(metadata)
        assert registry.has_component("expert.0")
        assert registry.get_component("expert.0") == metadata
        assert registry.list_components() == (metadata,)

    with SQLiteRegistry(database) as registry:
        assert registry.get_component("expert.0") == metadata


def test_registry_rejects_duplicate_component(tmp_path: Path, make_component, store) -> None:
    metadata = publish(make_component, store, "expert.0")

    with SQLiteRegistry(tmp_path / "registry.sqlite3") as registry:
        registry.register_component(metadata)
        with pytest.raises(DuplicateComponentError, match="already registered"):
            registry.register_component(metadata)


def test_registry_verifies_storage_on_registration(tmp_path: Path, make_component, store) -> None:
    location, content_hash = store.create(size_bytes=4096, seed=1)
    metadata = make_component(
        "expert.0", storage=location, content_hash=content_hash, size_bytes=4096
    )
    Path(location.uri).write_text("tampered", encoding="utf-8")

    with SQLiteRegistry(tmp_path / "registry.sqlite3") as registry:
        with pytest.raises(IntegrityError):
            registry.register_component(metadata)
        assert not registry.has_component("expert.0")


def test_registry_missing_component(tmp_path: Path) -> None:
    with SQLiteRegistry(tmp_path / "registry.sqlite3") as registry:
        with pytest.raises(ComponentNotFoundError, match="not registered"):
            registry.get_component("missing")
        with pytest.raises(ComponentNotFoundError, match="not registered"):
            registry.verify_component("missing")


def test_registry_update_records_history(tmp_path: Path, make_component, store) -> None:
    original = publish(make_component, store, "expert.0", size_bytes=4096, seed=1)
    updated = publish(make_component, store, "expert.0", size_bytes=8192, seed=2)

    with SQLiteRegistry(tmp_path / "registry.sqlite3") as registry:
        registry.register_component(original)
        revision = registry.update_component(updated)

        assert revision == 2
        assert registry.get_component("expert.0") == updated
        history = registry.component_history("expert.0")
        assert len(history) == 2
        assert history[0].revision == 1
        assert history[1].revision == 2
        assert history[1].content_hash == updated.content_hash
        assert history[1].schema_version == 1
        assert history[1].recorded_at.tzinfo is not None


def test_registry_update_requires_registration(tmp_path: Path, make_component, store) -> None:
    metadata = publish(make_component, store, "expert.0")

    with (
        SQLiteRegistry(tmp_path / "registry.sqlite3") as registry,
        pytest.raises(ComponentNotFoundError, match="not registered"),
    ):
        registry.update_component(metadata)


def test_registry_verify_component_detects_tampering(tmp_path: Path, make_component, store) -> None:
    metadata = publish(make_component, store, "expert.0")

    with SQLiteRegistry(tmp_path / "registry.sqlite3") as registry:
        registry.register_component(metadata)
        Path(metadata.storage.uri).write_text("tampered", encoding="utf-8")

        with pytest.raises(IntegrityError, match="hash mismatch"):
            registry.verify_component("expert.0")


def test_registry_verify_all_reports_failures(tmp_path: Path, make_component, store) -> None:
    healthy = publish(make_component, store, "healthy", seed=1)
    broken = publish(make_component, store, "broken", seed=2)

    with SQLiteRegistry(tmp_path / "registry.sqlite3") as registry:
        registry.register_component(healthy)
        registry.register_component(broken)
        Path(broken.storage.uri).write_text("tampered", encoding="utf-8")

        failures = registry.verify_all()

        assert [failure[0] for failure in failures] == ["broken"]


def test_registry_rejects_unregistered_dependency(tmp_path: Path, make_component, store) -> None:
    dependent = publish(make_component, store, "dependent", dependencies=("missing",))

    with SQLiteRegistry(tmp_path / "registry.sqlite3") as registry:
        with pytest.raises(DependencyError, match="missing"):
            registry.register_component(dependent)
        assert not registry.has_component("dependent")


def test_registry_accepts_registered_dependency(tmp_path: Path, make_component, store) -> None:
    dependency = publish(make_component, store, "dependency", seed=1)
    dependent = publish(
        make_component,
        store,
        "dependent",
        seed=2,
        dependencies=("dependency",),
    )

    with SQLiteRegistry(tmp_path / "registry.sqlite3") as registry:
        registry.register_component(dependency)
        registry.register_component(dependent)

        assert registry.list_components() == (dependency, dependent)


def test_registry_rejects_dependency_cycle_on_update(tmp_path: Path, make_component, store) -> None:
    first = publish(make_component, store, "first", seed=1)
    second = publish(make_component, store, "second", seed=2, dependencies=("first",))
    cyclic = publish(make_component, store, "first", seed=1, dependencies=("second",))

    with SQLiteRegistry(tmp_path / "registry.sqlite3") as registry:
        registry.register_component(first)
        registry.register_component(second)

        with pytest.raises(DependencyError, match="cycle"):
            registry.update_component(cyclic)
        assert registry.get_component("first") == first


def test_registry_cluster_round_trip(tmp_path: Path, make_component, store, model_identity) -> None:
    first = publish(make_component, store, "expert.0", seed=1)
    second = publish(make_component, store, "expert.1", seed=2)
    cluster = ClusterManifest(
        cluster_id="cluster-0",
        source_model=model_identity,
        component_ids=(first.component_id, second.component_id),
    )

    with SQLiteRegistry(tmp_path / "registry.sqlite3") as registry:
        registry.register_component(first)
        registry.register_component(second)
        registry.register_cluster(cluster)

        assert registry.get_cluster("cluster-0") == cluster
        assert registry.list_clusters() == (cluster,)
        history = registry.cluster_history("cluster-0")
        assert len(history) == 1
        assert history[0].content_hash is None


def test_registry_cluster_requires_registered_members(
    tmp_path: Path, make_component, store, model_identity
) -> None:
    cluster = ClusterManifest(
        cluster_id="cluster-0",
        source_model=model_identity,
        component_ids=("missing",),
    )

    with (
        SQLiteRegistry(tmp_path / "registry.sqlite3") as registry,
        pytest.raises(InvalidManifestError, match="unregistered"),
    ):
        registry.register_cluster(cluster)


def test_registry_cluster_rejects_mismatched_source_model(
    tmp_path: Path, make_component, store
) -> None:
    component = publish(make_component, store, "expert.0")
    other_model = ModelIdentity(model_id="other/model", architecture="other", revision="main")
    cluster = ClusterManifest(
        cluster_id="cluster-0",
        source_model=other_model,
        component_ids=(component.component_id,),
    )

    with SQLiteRegistry(tmp_path / "registry.sqlite3") as registry:
        registry.register_component(component)
        with pytest.raises(IncompatibleComponentError, match="does not belong"):
            registry.register_cluster(cluster)


def test_registry_rejects_duplicate_cluster(
    tmp_path: Path, make_component, store, model_identity
) -> None:
    component = publish(make_component, store, "expert.0")
    cluster = ClusterManifest(
        cluster_id="cluster-0",
        source_model=model_identity,
        component_ids=(component.component_id,),
    )

    with SQLiteRegistry(tmp_path / "registry.sqlite3") as registry:
        registry.register_component(component)
        registry.register_cluster(cluster)
        with pytest.raises(DuplicateClusterError, match="already registered"):
            registry.register_cluster(cluster)


def test_registry_missing_cluster(tmp_path: Path) -> None:
    with (
        SQLiteRegistry(tmp_path / "registry.sqlite3") as registry,
        pytest.raises(ClusterNotFoundError, match="not registered"),
    ):
        registry.get_cluster("missing")


def test_registry_detects_manifest_tampering(tmp_path: Path, make_component, store) -> None:
    database = tmp_path / "registry.sqlite3"
    metadata = publish(make_component, store, "expert.0")

    with SQLiteRegistry(database) as registry:
        registry.register_component(metadata)

    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE components SET manifest_json = ? WHERE component_id = ?",
            ('{"schema_version":1}', metadata.component_id),
        )

    with SQLiteRegistry(database) as registry, pytest.raises(InvalidManifestError):
        registry.get_component("expert.0")
