"""Cluster manifests that reference registered components."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from mosaic.contracts.common import ClusterId, ComponentId, Contract
from mosaic.contracts.model import ModelIdentity


class ClusterManifest(Contract):
    """A named group of components that are managed together.

    Clusters store component identifiers only; component weights and metadata
    remain authoritative in the component registry.
    """

    schema_version: Literal[1] = 1
    cluster_id: ClusterId
    source_model: ModelIdentity
    component_ids: Annotated[tuple[ComponentId, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def _validate_members(self) -> Self:
        if len(set(self.component_ids)) != len(self.component_ids):
            raise ValueError("cluster component_ids must not contain duplicates")
        return self
