"""Trainable controller interface."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mosaic.contracts.controller import ControllerPrediction, ControllerRequest


@runtime_checkable
class Controller(Protocol):
    """Predicts useful components or clusters without mutating memory state."""

    def predict(self, request: ControllerRequest) -> ControllerPrediction:
        """Return a ranked prediction for one request."""
        ...
