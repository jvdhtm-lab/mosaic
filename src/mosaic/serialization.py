"""Canonical serialization and content hashing."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from mosaic.errors import IntegrityError

_CHUNK_SIZE = 1024 * 1024


def _regular_files(path: Path) -> list[Path]:
    if path.is_symlink():
        raise IntegrityError(f"symlink is not allowed in stored content: {path}")
    files: list[Path] = []
    for candidate in path.rglob("*"):
        if candidate.is_symlink():
            raise IntegrityError(f"symlink is not allowed in stored content: {candidate}")
        if candidate.is_file():
            files.append(candidate)
    return files


def canonical_json(value: BaseModel | Mapping[str, Any]) -> str:
    """Serialize a contract or mapping to deterministic JSON."""
    data: Mapping[str, Any] = (
        value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    )
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def sha256_hex(data: bytes) -> str:
    """Return the lowercase hexadecimal SHA-256 digest of ``data``."""
    return hashlib.sha256(data).hexdigest()


def hash_file(path: Path) -> str:
    """Hash a file's bytes without loading the whole file into memory."""
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK_SIZE), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def hash_directory(path: Path) -> str:
    """Hash a directory deterministically, including relative paths and sizes."""
    if not path.is_dir():
        raise NotADirectoryError(path)
    hasher = hashlib.sha256()
    files = sorted(
        _regular_files(path),
        key=lambda candidate: candidate.relative_to(path).as_posix(),
    )
    for file_path in files:
        relative = file_path.relative_to(path).as_posix().encode("utf-8")
        hasher.update(len(relative).to_bytes(8, "big"))
        hasher.update(relative)
        hasher.update(file_path.stat().st_size.to_bytes(8, "big"))
        with file_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(_CHUNK_SIZE), b""):
                hasher.update(chunk)
    return hasher.hexdigest()


def directory_size(path: Path) -> int:
    """Return the total size of regular files under a directory."""
    return sum(candidate.stat().st_size for candidate in _regular_files(path))


def manifest_hash(manifest: BaseModel) -> str:
    """Hash the canonical serialization of a manifest."""
    return sha256_hex(canonical_json(manifest).encode("utf-8"))
