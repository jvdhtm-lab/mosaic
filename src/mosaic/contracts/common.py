"""Shared contract primitives: identifiers, hashes, scores, and base models."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

type Identifier = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=200,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$",
    ),
]
type ComponentId = Identifier
type ClusterId = Identifier
type RequestId = Identifier
type TraceId = Identifier
type CandidateId = Identifier

type NonEmptyStr = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]
type Sha256Hex = Annotated[
    str,
    StringConstraints(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"),
]
type Score = Annotated[float, Field(ge=0.0, le=1.0, allow_inf_nan=False)]
type NonNegativeFloat = Annotated[float, Field(ge=0.0, allow_inf_nan=False)]


class Contract(BaseModel):
    """Base class for immutable, strictly validated Mosaic contracts."""

    model_config = ConfigDict(frozen=True, extra="forbid")
