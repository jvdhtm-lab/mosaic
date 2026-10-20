"""Clustering engine interface."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, runtime_checkable

from mosaic.contracts.cluster import ClusterManifest
from mosaic.contracts.trace import ExecutionTrace


@runtime_checkable
class ClusteringEngine(Protocol):
    """Builds component clusters from observed execution traces."""

    def build_clusters(self, traces: Iterable[ExecutionTrace]) -> tuple[ClusterManifest, ...]:
        """Return deterministic cluster manifests for the supplied traces."""
        ...
