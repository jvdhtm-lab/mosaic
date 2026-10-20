"""Execution observer interface."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol, runtime_checkable

from mosaic.contracts.trace import ExecutionTrace


@runtime_checkable
class Observer(Protocol):
    """Collects and replays validated execution traces."""

    def record(self, trace: ExecutionTrace) -> None:
        """Persist one trace."""
        ...

    def iter_traces(self) -> Iterator[ExecutionTrace]:
        """Iterate over recorded traces."""
        ...
