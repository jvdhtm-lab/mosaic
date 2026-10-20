"""Component content storage verification and simulated payload creation."""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

from mosaic.contracts import ComponentMetadata, StorageKind, StorageLocation
from mosaic.errors import IntegrityError, UnsupportedRuntimeCapabilityError
from mosaic.serialization import (
    canonical_json,
    directory_size,
    hash_directory,
    hash_file,
    sha256_hex,
)

SIMULATED_FORMAT = "mosaic-simulated-v1"


def _is_windows_path(uri: str) -> bool:
    return (len(uri) >= 2 and uri[1] == ":") or uri.startswith("\\\\")


def storage_path(location: StorageLocation) -> Path:
    """Resolve a file-based storage location to a local path."""
    if location.kind is StorageKind.OBJECT:
        raise UnsupportedRuntimeCapabilityError(
            "object storage is not configured",
            capability="object_storage",
        )
    uri = location.uri
    if _is_windows_path(uri):
        return Path(uri)
    parsed = urlparse(uri)
    if parsed.scheme == "file":
        path_text = url2pathname(parsed.path)
        if parsed.netloc:
            path_text = f"//{parsed.netloc}{path_text}"
        if (
            os.name == "nt"
            and len(path_text) >= 3
            and path_text[0] in "/\\"
            and path_text[2] == ":"
        ):
            path_text = path_text[1:]
        return Path(path_text)
    if parsed.scheme:
        raise UnsupportedRuntimeCapabilityError(
            f"unsupported storage scheme {parsed.scheme!r}",
            capability="storage",
        )
    return Path(uri)


def _verify_simulated(metadata: ComponentMetadata, path: Path) -> None:
    if not path.is_file():
        raise IntegrityError(
            f"simulated content for {metadata.component_id!r} is missing",
            component_id=metadata.component_id,
        )
    data = path.read_bytes()
    actual_hash = sha256_hex(data)
    if actual_hash != metadata.content_hash:
        raise IntegrityError(
            f"content hash mismatch for {metadata.component_id!r}",
            component_id=metadata.component_id,
        )
    try:
        payload = json.loads(data)
    except json.JSONDecodeError as exc:
        raise IntegrityError(
            f"simulated content for {metadata.component_id!r} is malformed",
            component_id=metadata.component_id,
        ) from exc
    if not isinstance(payload, dict) or set(payload) != {"format", "seed", "size_bytes"}:
        raise IntegrityError(
            f"simulated content for {metadata.component_id!r} has an invalid descriptor",
            component_id=metadata.component_id,
        )
    if payload["format"] != SIMULATED_FORMAT:
        raise IntegrityError(
            f"simulated content for {metadata.component_id!r} has an unsupported format",
            component_id=metadata.component_id,
        )
    if not isinstance(payload["seed"], int) or isinstance(payload["seed"], bool):
        raise IntegrityError(
            f"simulated content for {metadata.component_id!r} has an invalid seed",
            component_id=metadata.component_id,
        )
    if payload["size_bytes"] != metadata.size_bytes:
        raise IntegrityError(
            f"simulated size mismatch for {metadata.component_id!r}",
            component_id=metadata.component_id,
        )


def verify_storage(metadata: ComponentMetadata) -> None:
    """Verify that stored content matches the declared identity and size."""
    kind = metadata.storage.kind
    path = storage_path(metadata.storage)
    if kind is StorageKind.SIMULATED:
        _verify_simulated(metadata, path)
        return
    if kind is StorageKind.FILE:
        if not path.is_file():
            raise IntegrityError(
                f"content file for {metadata.component_id!r} is missing",
                component_id=metadata.component_id,
            )
        actual_size = path.stat().st_size
        if actual_size != metadata.size_bytes:
            raise IntegrityError(
                f"size mismatch for {metadata.component_id!r}: "
                f"declared {metadata.size_bytes}, found {actual_size}",
                component_id=metadata.component_id,
            )
        actual_hash = hash_file(path)
    elif kind is StorageKind.DIRECTORY:
        if not path.is_dir():
            raise IntegrityError(
                f"content directory for {metadata.component_id!r} is missing",
                component_id=metadata.component_id,
            )
        actual_size = directory_size(path)
        if actual_size != metadata.size_bytes:
            raise IntegrityError(
                f"size mismatch for {metadata.component_id!r}: "
                f"declared {metadata.size_bytes}, found {actual_size}",
                component_id=metadata.component_id,
            )
        actual_hash = hash_directory(path)
    else:
        raise UnsupportedRuntimeCapabilityError(
            f"storage kind {kind.value!r} is not supported",
            capability="storage",
        )
    if actual_hash != metadata.content_hash:
        raise IntegrityError(
            f"content hash mismatch for {metadata.component_id!r}",
            component_id=metadata.component_id,
        )


class SimulatedContentStore:
    """Content-addressed storage for small synthetic component descriptors."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def create(self, *, size_bytes: int, seed: int) -> tuple[StorageLocation, str]:
        """Create a deterministic simulated payload with a logical byte size."""
        if size_bytes <= 0:
            raise ValueError("size_bytes must be greater than zero")
        payload = {
            "format": SIMULATED_FORMAT,
            "seed": seed,
            "size_bytes": size_bytes,
        }
        data = canonical_json(payload).encode("utf-8")
        digest = sha256_hex(data)
        path = self.root / f"{digest}.json"
        if not path.exists():
            temporary = path.with_name(f"{path.name}.tmp")
            temporary.write_bytes(data)
            os.replace(temporary, path)
        return StorageLocation(kind=StorageKind.SIMULATED, uri=str(path)), digest
