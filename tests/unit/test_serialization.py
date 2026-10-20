from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from mosaic.errors import IntegrityError
from mosaic.serialization import (
    canonical_json,
    directory_size,
    hash_directory,
    hash_file,
    manifest_hash,
    sha256_hex,
)


def test_canonical_json_sorts_keys_and_is_stable() -> None:
    payload = {"b": 2, "a": {"d": 4, "c": 3}}

    encoded = canonical_json(payload)

    assert encoded == '{"a":{"c":3,"d":4},"b":2}'
    assert canonical_json(payload) == encoded


def test_sha256_hex_matches_known_digest() -> None:
    assert sha256_hex(b"abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_hash_file_matches_sha256(tmp_path: Path) -> None:
    path = tmp_path / "content.bin"
    path.write_bytes(b"mosaic")

    assert hash_file(path) == hashlib.sha256(b"mosaic").hexdigest()


def test_hash_directory_is_order_independent(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    for root in (first, second):
        root.mkdir()
        (root / "a.bin").write_bytes(b"a")
        (root / "b.bin").write_bytes(b"b")
    (first / "nested").mkdir()
    (first / "nested" / "c.bin").write_bytes(b"c")
    (second / "nested").mkdir()
    (second / "nested" / "c.bin").write_bytes(b"c")

    assert hash_directory(first) == hash_directory(second)
    assert directory_size(first) == directory_size(second) == 3


def test_hash_directory_changes_with_content(tmp_path: Path) -> None:
    root = tmp_path / "content"
    root.mkdir()
    (root / "a.bin").write_bytes(b"a")
    before = hash_directory(root)

    (root / "a.bin").write_bytes(b"b")

    assert hash_directory(root) != before


def test_hash_directory_rejects_symlink(tmp_path: Path) -> None:
    root = tmp_path / "content"
    root.mkdir()
    target = tmp_path / "target.bin"
    target.write_bytes(b"target")
    try:
        (root / "link.bin").symlink_to(target)
    except OSError:
        pytest.skip("symlink creation is not available")

    with pytest.raises(IntegrityError, match="symlink"):
        hash_directory(root)


def test_manifest_hash_changes_with_manifest(component_metadata) -> None:
    assert manifest_hash(component_metadata) == manifest_hash(component_metadata)
    changed = component_metadata.model_copy(
        update={"size_bytes": component_metadata.size_bytes + 1}
    )
    assert manifest_hash(changed) != manifest_hash(component_metadata)
