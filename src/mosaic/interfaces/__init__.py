"""Subsystem interfaces expressed as runtime-checkable protocols."""

from mosaic.interfaces.clustering import ClusteringEngine
from mosaic.interfaces.controller import Controller
from mosaic.interfaces.memory import MemoryManager
from mosaic.interfaces.observer import Observer
from mosaic.interfaces.registry import ComponentRegistry
from mosaic.interfaces.runtime import RuntimeAdapter

__all__ = [
    "ClusteringEngine",
    "ComponentRegistry",
    "Controller",
    "MemoryManager",
    "Observer",
    "RuntimeAdapter",
]
