from __future__ import annotations

from pathlib import Path

import pytest

from mosaic.contracts import StorageKind, StorageLocation
from mosaic.errors import IntegrityError, UnsupportedRuntimeCapabilityError
from mosaic.serialization import directory_size, hash_directory, hash_file
from mosaic.storage import SIMULATED_FORMAT, SimulatedContentStore, storage_path, verify_storage


def test_storage_path_accepts_absolute_paths(tmp_path: Path) -> None:
    location = StorageLocation(kind=StorageKind.FILE, uri=str(tmp_path / "content.bin"))

    assert storage_path(location) == tmp_path / "content.bin"


def test_storage_path_accepts_file_uri(tmp_path: Path) -> None:
    path = tmp_path / "content.bin"
    location = StorageLocation(kind=StorageKind.FILE, uri=path.as_uri())

    assert storage_path(location) == path


def test_storage_path_rejects_object_storage() -> None:
    location = StorageLocation(kind=StorageKind.OBJECT, uri="s3://bucket/object")

    with pytest.raises(UnsupportedRuntimeCapabilityError, match="object storage"):
        storage_path(location)


def test_storage_path_rejects_unknown_scheme() -> None:
    location = StorageLocation(kind=StorageKind.FILE, uri="https://example.com/content")

    with pytest.raises(UnsupportedRuntimeCapabilityError, match="scheme"):
        storage_path(location)


def test_simulated_content_store_is_deterministic(tmp_path: Path) -> None:
    store = SimulatedContentStore(tmp_path / "store")

    first_location, first_hash = store.create(size_bytes=4096, seed=1)
    second_location, second_hash = store.create(size_bytes=4096, seed=1)

    assert first_location == second_location
    assert first_hash == second_hash


def test_simulated_content_store_rejects_zero_size(tmp_path: Path) -> None:
    store = SimulatedContentStore(tmp_path / "store")

    with pytest.raises(ValueError, match="greater than zero"):
        store.create(size_bytes=0, seed=1)


def test_verify_simulated_content(tmp_path: Path, make_component) -> None:
    store = SimulatedContentStore(tmp_path / "store")
    location, content_hash = store.create(size_bytes=4096, seed=7)
    metadata = make_component(
        "expert", storage=location, content_hash=content_hash, size_bytes=4096
    )

    verify_storage(metadata)


def test_verify_simulated_content_detects_tampering(tmp_path: Path, make_component) -> None:
    store = SimulatedContentStore(tmp_path / "store")
    location, content_hash = store.create(size_bytes=4096, seed=7)
    metadata = make_component(
        "expert", storage=location, content_hash=content_hash, size_bytes=4096
    )
    Path(location.uri).write_text("{}", encoding="utf-8")

    with pytest.raises(IntegrityError, match="hash mismatch"):
        verify_storage(metadata)


def test_verify_simulated_content_detects_size_mismatch(tmp_path: Path, make_component) -> None:
    store = SimulatedContentStore(tmp_path / "store")
    location, content_hash = store.create(size_bytes=4096, seed=7)
    metadata = make_component(
        "expert", storage=location, content_hash=content_hash, size_bytes=4097
    )

    with pytest.raises(IntegrityError, match="size mismatch"):
        verify_storage(metadata)


def test_verify_simulated_content_rejects_bad_descriptor(tmp_path: Path, make_component) -> None:
    path = tmp_path / "bad.json"
    path.write_text('{"format":"wrong","seed":1,"size_bytes":4}', encoding="utf-8")
    metadata = make_component(
        "expert",
        storage=StorageLocation(kind=StorageKind.SIMULATED, uri=str(path)),
        content_hash=hash_file(path),
        size_bytes=4,
    )

    with pytest.raises(IntegrityError, match="format"):
        verify_storage(metadata)


def test_verify_file_content(tmp_path: Path, make_component) -> None:
    path = tmp_path / "content.bin"
    path.write_bytes(b"mosaic")
    metadata = make_component(
        "expert",
        storage=StorageLocation(kind=StorageKind.FILE, uri=str(path)),
        content_hash=hash_file(path),
        size_bytes=path.stat().st_size,
    )

    verify_storage(metadata)


def test_verify_file_detects_missing_and_invalid_content(tmp_path: Path, make_component) -> None:
    path = tmp_path / "content.bin"
    path.write_bytes(b"mosaic")
    missing = make_component(
        "missing",
        storage=StorageLocation(kind=StorageKind.FILE, uri=str(tmp_path / "missing.bin")),
        content_hash=hash_file(path),
    )
    wrong_size = make_component(
        "wrong-size",
        storage=StorageLocation(kind=StorageKind.FILE, uri=str(path)),
        content_hash=hash_file(path),
        size_bytes=99,
    )

    with pytest.raises(IntegrityError, match="missing"):
        verify_storage(missing)
    with pytest.raises(IntegrityError, match="size mismatch"):
        verify_storage(wrong_size)


def test_verify_directory_content(tmp_path: Path, make_component) -> None:
    root = tmp_path / "content"
    root.mkdir()
    (root / "weights.bin").write_bytes(b"weights")
    metadata = make_component(
        "cluster",
        storage=StorageLocation(kind=StorageKind.DIRECTORY, uri=str(root)),
        content_hash=hash_directory(root),
        size_bytes=directory_size(root),
    )

    verify_storage(metadata)


def test_verify_directory_detects_missing_content(tmp_path: Path, make_component) -> None:
    metadata = make_component(
        "cluster",
        storage=StorageLocation(kind=StorageKind.DIRECTORY, uri=str(tmp_path / "missing")),
        content_hash="a" * 64,
    )

    with pytest.raises(IntegrityError, match="missing"):
        verify_storage(metadata)


def test_verify_simulated_descriptor_has_expected_format(tmp_path: Path) -> None:
    store = SimulatedContentStore(tmp_path / "store")
    location, _ = store.create(size_bytes=4, seed=1)

    assert SIMULATED_FORMAT in Path(location.uri).read_text(encoding="utf-8")
