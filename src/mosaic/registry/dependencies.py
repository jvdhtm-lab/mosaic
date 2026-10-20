"""Dependency graph validation for component manifests."""

from __future__ import annotations

from collections.abc import Iterable

from mosaic.contracts import ComponentId, ComponentMetadata
from mosaic.errors import DependencyError


def dependency_order(
    components: Iterable[ComponentMetadata],
    *,
    roots: Iterable[ComponentId] | None = None,
) -> tuple[ComponentId, ...]:
    """Return component IDs in dependency-first order.

    When ``roots`` is provided, only the dependency closure of those roots is
    returned. Missing dependencies, duplicate IDs, unknown roots, and cycles
    raise ``DependencyError``. The order is deterministic for identical inputs.
    """
    by_id: dict[ComponentId, ComponentMetadata] = {}
    for metadata in components:
        if metadata.component_id in by_id:
            raise DependencyError(
                f"duplicate component {metadata.component_id!r}",
                component_id=metadata.component_id,
            )
        by_id[metadata.component_id] = metadata

    selected = set(by_id)
    if roots is not None:
        selected = set()
        stack = list(roots)
        for root in stack:
            if root not in by_id:
                raise DependencyError(
                    f"unknown root component {root!r}",
                    component_id=root,
                )
        while stack:
            node = stack.pop()
            if node in selected:
                continue
            selected.add(node)
            stack.extend(by_id[node].dependencies)

    for component_id in selected:
        for dependency in by_id[component_id].dependencies:
            if dependency not in by_id:
                raise DependencyError(
                    f"component {component_id!r} depends on missing component {dependency!r}",
                    component_id=component_id,
                )

    state: dict[ComponentId, int] = {}
    order: list[ComponentId] = []

    def visit(node: ComponentId) -> None:
        current = state.get(node, 0)
        if current == 1:
            raise DependencyError(
                f"dependency cycle detected at component {node!r}",
                component_id=node,
            )
        if current == 2:
            return
        state[node] = 1
        for dependency in by_id[node].dependencies:
            visit(dependency)
        state[node] = 2
        order.append(node)

    for node in sorted(selected):
        visit(node)
    return tuple(order)
