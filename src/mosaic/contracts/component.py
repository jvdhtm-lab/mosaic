"""Component identity, storage, dependencies, and compatibility metadata."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, PositiveInt, model_validator

from mosaic.contracts.common import ComponentId, Contract, NonEmptyStr, Sha256Hex
from mosaic.contracts.model import ModelIdentity


class ComponentType(StrEnum):
    """Kind of component exposed by a componentized model."""

    MOE_EXPERT = "moe_expert"
    SHARED_EXPERT = "shared_expert"
    ROUTER = "router"
    EMBEDDING = "embedding"
    OTHER = "other"


class StorageKind(StrEnum):
    """Storage backend that holds component content."""

    FILE = "file"
    DIRECTORY = "directory"
    OBJECT = "object"
    SIMULATED = "simulated"


class StorageLocation(Contract):
    """Location of component content in persistent storage."""

    kind: StorageKind
    uri: NonEmptyStr


class RuntimeCompatibility(Contract):
    """Runtime compatibility declarations for a component."""

    runtime_name: NonEmptyStr
    runtime_version: NonEmptyStr | None = None
    precision: NonEmptyStr | None = None
    required_features: tuple[NonEmptyStr, ...] = ()

    @model_validator(mode="after")
    def _validate_features(self) -> Self:
        if len(set(self.required_features)) != len(self.required_features):
            raise ValueError("required_features must not contain duplicates")
        return self


class ComponentMetadata(Contract):
    """Logical identity and metadata for one component.

    The logical ``component_id`` is distinct from the ``content_hash``, which
    commits to the component's content. Registration and verification are
    responsible for checking the declared hash against stored bytes.
    """

    schema_version: Literal[1] = 1
    component_id: ComponentId
    content_hash: Sha256Hex
    component_type: ComponentType
    source_model: ModelIdentity
    storage: StorageLocation
    size_bytes: PositiveInt
    dependencies: Annotated[tuple[ComponentId, ...], Field(default=())]
    compatibility: RuntimeCompatibility

    @model_validator(mode="after")
    def _validate_dependencies(self) -> Self:
        if self.component_id in self.dependencies:
            raise ValueError("a component must not depend on itself")
        if len(set(self.dependencies)) != len(self.dependencies):
            raise ValueError("dependencies must not contain duplicates")
        return self
