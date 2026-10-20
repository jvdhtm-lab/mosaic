"""SQLite-backed component and cluster registry."""

from __future__ import annotations

import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Self

from pydantic import PositiveInt, ValidationError

from mosaic.contracts import (
    ClusterId,
    ClusterManifest,
    ComponentId,
    ComponentMetadata,
    Sha256Hex,
)
from mosaic.contracts.common import Contract
from mosaic.errors import (
    ClusterNotFoundError,
    ComponentNotFoundError,
    DependencyError,
    DuplicateClusterError,
    DuplicateComponentError,
    IncompatibleComponentError,
    IntegrityError,
    InvalidManifestError,
    UnsupportedRuntimeCapabilityError,
)
from mosaic.registry.dependencies import dependency_order
from mosaic.serialization import canonical_json, sha256_hex
from mosaic.serialization import manifest_hash as compute_manifest_hash
from mosaic.storage import verify_storage

_SCHEMA = """
CREATE TABLE IF NOT EXISTS components (
    component_id TEXT PRIMARY KEY,
    manifest_json TEXT NOT NULL,
    manifest_hash TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    manifest_version INTEGER NOT NULL,
    recorded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS component_revisions (
    revision INTEGER PRIMARY KEY AUTOINCREMENT,
    component_id TEXT NOT NULL,
    manifest_json TEXT NOT NULL,
    manifest_hash TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    manifest_version INTEGER NOT NULL,
    recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_component_revisions_component
    ON component_revisions(component_id, revision);
CREATE TABLE IF NOT EXISTS clusters (
    cluster_id TEXT PRIMARY KEY,
    manifest_json TEXT NOT NULL,
    manifest_hash TEXT NOT NULL,
    manifest_version INTEGER NOT NULL,
    recorded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cluster_revisions (
    revision INTEGER PRIMARY KEY AUTOINCREMENT,
    cluster_id TEXT NOT NULL,
    manifest_json TEXT NOT NULL,
    manifest_hash TEXT NOT NULL,
    manifest_version INTEGER NOT NULL,
    recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cluster_revisions_cluster
    ON cluster_revisions(cluster_id, revision);
"""


class ManifestRevision(Contract):
    """One persisted revision of a component or cluster manifest."""

    revision: PositiveInt
    manifest_hash: Sha256Hex
    content_hash: Sha256Hex | None = None
    schema_version: PositiveInt
    recorded_at: datetime


def _now() -> datetime:
    return datetime.now(UTC)


class SQLiteRegistry:
    """Versioned component registry persisted in SQLite."""

    def __init__(self, path: str | Path) -> None:
        self._lock = threading.RLock()
        raw_path = str(path)
        if raw_path == ":memory:":
            database = raw_path
        else:
            resolved = Path(raw_path).expanduser().resolve()
            resolved.parent.mkdir(parents=True, exist_ok=True)
            database = str(resolved)
        self._connection = sqlite3.connect(database, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        if database != ":memory:":
            self._connection.execute("PRAGMA journal_mode = WAL")
        self._initialize()

    def _initialize(self) -> None:
        with self._lock, self._connection:
            row = self._connection.execute("PRAGMA user_version").fetchone()
            version = int(row[0]) if row is not None else 0
            if version == 0:
                self._connection.executescript(_SCHEMA)
                self._connection.execute("PRAGMA user_version = 1")
            elif version != 1:
                raise InvalidManifestError(f"unsupported registry schema version {version}")

    def close(self) -> None:
        """Close the underlying database connection."""
        with self._lock:
            self._connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def register_component(self, metadata: ComponentMetadata) -> None:
        """Verify and register a component manifest."""
        verify_storage(metadata)
        with self._lock:
            if self._component_row(metadata.component_id) is not None:
                raise DuplicateComponentError(
                    f"component {metadata.component_id!r} is already registered",
                    component_id=metadata.component_id,
                )
            self._validate_dependencies(metadata)
            with self._connection:
                self._insert_component(metadata)

    def update_component(self, metadata: ComponentMetadata) -> int:
        """Replace a registered component and record a new manifest revision."""
        verify_storage(metadata)
        with self._lock:
            if self._component_row(metadata.component_id) is None:
                raise ComponentNotFoundError(
                    f"component {metadata.component_id!r} is not registered",
                    component_id=metadata.component_id,
                )
            self._validate_dependencies(metadata)
            with self._connection:
                self._update_component(metadata)
                return self._insert_component_revision(metadata)

    def get_component(self, component_id: ComponentId) -> ComponentMetadata:
        """Return a component manifest or raise ``ComponentNotFoundError``."""
        with self._lock:
            row = self._component_row(component_id)
        if row is None:
            raise ComponentNotFoundError(
                f"component {component_id!r} is not registered",
                component_id=component_id,
            )
        return self._component_from_row(row)

    def has_component(self, component_id: ComponentId) -> bool:
        """Report whether a component is registered."""
        with self._lock:
            return self._component_row(component_id) is not None

    def list_components(self) -> tuple[ComponentMetadata, ...]:
        """Return all components ordered by logical identifier."""
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM components ORDER BY component_id"
            ).fetchall()
        return tuple(self._component_from_row(row) for row in rows)

    def verify_component(self, component_id: ComponentId) -> None:
        """Verify stored content for one component."""
        verify_storage(self.get_component(component_id))

    def verify_all(self) -> tuple[tuple[ComponentId, str], ...]:
        """Verify every component and return failures without raising."""
        failures: list[tuple[ComponentId, str]] = []
        for metadata in self.list_components():
            try:
                verify_storage(metadata)
            except (IntegrityError, UnsupportedRuntimeCapabilityError) as exc:
                failures.append((metadata.component_id, str(exc)))
        return tuple(failures)

    def register_cluster(self, cluster: ClusterManifest) -> None:
        """Register a cluster that references registered components."""
        with self._lock:
            if self._cluster_row(cluster.cluster_id) is not None:
                raise DuplicateClusterError(
                    f"cluster {cluster.cluster_id!r} is already registered",
                    cluster_id=cluster.cluster_id,
                )
            self._validate_cluster(cluster)
            with self._connection:
                self._insert_cluster(cluster)

    def update_cluster(self, cluster: ClusterManifest) -> int:
        """Replace a registered cluster and record a new manifest revision."""
        with self._lock:
            if self._cluster_row(cluster.cluster_id) is None:
                raise ClusterNotFoundError(
                    f"cluster {cluster.cluster_id!r} is not registered",
                    cluster_id=cluster.cluster_id,
                )
            self._validate_cluster(cluster)
            with self._connection:
                self._update_cluster(cluster)
                return self._insert_cluster_revision(cluster)

    def get_cluster(self, cluster_id: ClusterId) -> ClusterManifest:
        """Return a cluster manifest or raise ``ClusterNotFoundError``."""
        with self._lock:
            row = self._cluster_row(cluster_id)
        if row is None:
            raise ClusterNotFoundError(
                f"cluster {cluster_id!r} is not registered",
                cluster_id=cluster_id,
            )
        return self._cluster_from_row(row)

    def list_clusters(self) -> tuple[ClusterManifest, ...]:
        """Return all clusters ordered by logical identifier."""
        with self._lock:
            rows = self._connection.execute("SELECT * FROM clusters ORDER BY cluster_id").fetchall()
        return tuple(self._cluster_from_row(row) for row in rows)

    def component_history(self, component_id: ComponentId) -> tuple[ManifestRevision, ...]:
        """Return persisted revisions for a component, oldest first."""
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM component_revisions WHERE component_id = ? ORDER BY revision",
                (component_id,),
            ).fetchall()
        return tuple(
            ManifestRevision(
                revision=row["revision"],
                manifest_hash=row["manifest_hash"],
                content_hash=row["content_hash"],
                schema_version=row["manifest_version"],
                recorded_at=datetime.fromisoformat(row["recorded_at"]),
            )
            for row in rows
        )

    def cluster_history(self, cluster_id: ClusterId) -> tuple[ManifestRevision, ...]:
        """Return persisted revisions for a cluster, oldest first."""
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM cluster_revisions WHERE cluster_id = ? ORDER BY revision",
                (cluster_id,),
            ).fetchall()
        return tuple(
            ManifestRevision(
                revision=row["revision"],
                manifest_hash=row["manifest_hash"],
                content_hash=None,
                schema_version=row["manifest_version"],
                recorded_at=datetime.fromisoformat(row["recorded_at"]),
            )
            for row in rows
        )

    def _component_row(self, component_id: ComponentId) -> sqlite3.Row | None:
        row: sqlite3.Row | None = self._connection.execute(
            "SELECT * FROM components WHERE component_id = ?",
            (component_id,),
        ).fetchone()
        return row

    def _cluster_row(self, cluster_id: ClusterId) -> sqlite3.Row | None:
        row: sqlite3.Row | None = self._connection.execute(
            "SELECT * FROM clusters WHERE cluster_id = ?",
            (cluster_id,),
        ).fetchone()
        return row

    def _component_from_row(self, row: sqlite3.Row) -> ComponentMetadata:
        try:
            metadata = ComponentMetadata.model_validate_json(row["manifest_json"])
        except ValidationError as exc:
            raise InvalidManifestError(
                f"stored component manifest {row['component_id']!r} is invalid",
                manifest_id=row["component_id"],
            ) from exc
        if compute_manifest_hash(metadata) != row["manifest_hash"]:
            raise InvalidManifestError(
                f"stored component manifest {metadata.component_id!r} failed its hash check",
                manifest_id=metadata.component_id,
            )
        if metadata.content_hash != row["content_hash"]:
            raise InvalidManifestError(
                f"stored component {metadata.component_id!r} has inconsistent content hashes",
                manifest_id=metadata.component_id,
            )
        return metadata

    def _cluster_from_row(self, row: sqlite3.Row) -> ClusterManifest:
        try:
            cluster = ClusterManifest.model_validate_json(row["manifest_json"])
        except ValidationError as exc:
            raise InvalidManifestError(
                f"stored cluster manifest {row['cluster_id']!r} is invalid",
                manifest_id=row["cluster_id"],
            ) from exc
        if compute_manifest_hash(cluster) != row["manifest_hash"]:
            raise InvalidManifestError(
                f"stored cluster manifest {cluster.cluster_id!r} failed its hash check",
                manifest_id=cluster.cluster_id,
            )
        return cluster

    def _validate_dependencies(self, metadata: ComponentMetadata) -> None:
        components = {item.component_id: item for item in self.list_components()}
        components[metadata.component_id] = metadata
        try:
            dependency_order(components.values())
        except DependencyError as exc:
            raise DependencyError(str(exc), component_id=metadata.component_id) from exc

    def _validate_cluster(self, cluster: ClusterManifest) -> None:
        for component_id in cluster.component_ids:
            try:
                component = self.get_component(component_id)
            except ComponentNotFoundError as exc:
                raise InvalidManifestError(
                    f"cluster {cluster.cluster_id!r} references unregistered "
                    f"component {component_id!r}",
                    manifest_id=cluster.cluster_id,
                ) from exc
            if component.source_model != cluster.source_model:
                raise IncompatibleComponentError(
                    f"component {component_id!r} does not belong to cluster model "
                    f"{cluster.source_model.model_id!r}",
                    component_id=component_id,
                )

    def _manifest_values(
        self, manifest: ComponentMetadata | ClusterManifest
    ) -> tuple[str, str, int, str]:
        manifest_json = canonical_json(manifest)
        return (
            manifest_json,
            sha256_hex(manifest_json.encode("utf-8")),
            manifest.schema_version,
            _now().isoformat(),
        )

    def _insert_component(self, metadata: ComponentMetadata) -> None:
        manifest_json, digest, version, recorded_at = self._manifest_values(metadata)
        self._connection.execute(
            "INSERT INTO components "
            "(component_id, manifest_json, manifest_hash, content_hash, "
            "manifest_version, recorded_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                metadata.component_id,
                manifest_json,
                digest,
                metadata.content_hash,
                version,
                recorded_at,
            ),
        )
        self._insert_component_revision(metadata)

    def _update_component(self, metadata: ComponentMetadata) -> None:
        manifest_json, digest, version, recorded_at = self._manifest_values(metadata)
        self._connection.execute(
            "UPDATE components SET manifest_json = ?, manifest_hash = ?, "
            "content_hash = ?, manifest_version = ?, recorded_at = ? "
            "WHERE component_id = ?",
            (
                manifest_json,
                digest,
                metadata.content_hash,
                version,
                recorded_at,
                metadata.component_id,
            ),
        )

    def _insert_component_revision(self, metadata: ComponentMetadata) -> int:
        manifest_json, digest, version, recorded_at = self._manifest_values(metadata)
        cursor = self._connection.execute(
            "INSERT INTO component_revisions "
            "(component_id, manifest_json, manifest_hash, content_hash, "
            "manifest_version, recorded_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                metadata.component_id,
                manifest_json,
                digest,
                metadata.content_hash,
                version,
                recorded_at,
            ),
        )
        if cursor.lastrowid is None:
            raise InvalidManifestError("failed to record component revision")
        return int(cursor.lastrowid)

    def _insert_cluster(self, cluster: ClusterManifest) -> None:
        manifest_json, digest, version, recorded_at = self._manifest_values(cluster)
        self._connection.execute(
            "INSERT INTO clusters "
            "(cluster_id, manifest_json, manifest_hash, manifest_version, recorded_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (cluster.cluster_id, manifest_json, digest, version, recorded_at),
        )
        self._insert_cluster_revision(cluster)

    def _update_cluster(self, cluster: ClusterManifest) -> None:
        manifest_json, digest, version, recorded_at = self._manifest_values(cluster)
        self._connection.execute(
            "UPDATE clusters SET manifest_json = ?, manifest_hash = ?, "
            "manifest_version = ?, recorded_at = ? WHERE cluster_id = ?",
            (manifest_json, digest, version, recorded_at, cluster.cluster_id),
        )

    def _insert_cluster_revision(self, cluster: ClusterManifest) -> int:
        manifest_json, digest, version, recorded_at = self._manifest_values(cluster)
        cursor = self._connection.execute(
            "INSERT INTO cluster_revisions "
            "(cluster_id, manifest_json, manifest_hash, manifest_version, recorded_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (cluster.cluster_id, manifest_json, digest, version, recorded_at),
        )
        if cursor.lastrowid is None:
            raise InvalidManifestError("failed to record cluster revision")
        return int(cursor.lastrowid)
