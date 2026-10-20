"""Component and cluster registry interface."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mosaic.contracts.cluster import ClusterManifest
from mosaic.contracts.common import ClusterId, ComponentId
from mosaic.contracts.component import ComponentMetadata


@runtime_checkable
class ComponentRegistry(Protocol):
    """Authoritative store for component metadata and cluster manifests."""

    def register_component(self, metadata: ComponentMetadata) -> None:
        """Register a component, rejecting duplicate logical identities."""
        ...

    def get_component(self, component_id: ComponentId) -> ComponentMetadata:
        """Return component metadata or raise ``ComponentNotFoundError``."""
        ...

    def has_component(self, component_id: ComponentId) -> bool:
        """Report whether a logical component identity is registered."""
        ...

    def list_components(self) -> tuple[ComponentMetadata, ...]:
        """Return all registered component metadata."""
        ...

    def verify_component(self, component_id: ComponentId) -> None:
        """Verify stored content for a component or raise ``ContentVerificationError``."""
        ...

    def register_cluster(self, cluster: ClusterManifest) -> None:
        """Register a cluster that references known components."""
        ...

    def get_cluster(self, cluster_id: ClusterId) -> ClusterManifest:
        """Return a cluster manifest or raise ``ComponentNotFoundError``."""
        ...

    def list_clusters(self) -> tuple[ClusterManifest, ...]:
        """Return all registered cluster manifests."""
        ...
