from __future__ import annotations

import pytest

from mosaic.errors import DependencyError
from mosaic.registry.dependencies import dependency_order


def test_dependency_order_places_dependencies_first(make_component) -> None:
    a = make_component("a")
    b = make_component("b", dependencies=("a",))
    c = make_component("c", dependencies=("b",))

    assert dependency_order((c, b, a)) == ("a", "b", "c")
    assert dependency_order((c, b, a), roots=("c",)) == ("a", "b", "c")


def test_dependency_order_deduplicates_shared_dependencies(make_component) -> None:
    base = make_component("base")
    left = make_component("left", dependencies=("base",))
    right = make_component("right", dependencies=("base",))

    order = dependency_order((left, right, base))

    assert order.count("base") == 1
    assert order.index("base") < order.index("left")
    assert order.index("base") < order.index("right")


def test_dependency_order_subset_excludes_unrelated_components(make_component) -> None:
    wanted = make_component("wanted", dependencies=("dep",))
    dep = make_component("dep")
    unrelated = make_component("unrelated")

    assert dependency_order((wanted, dep, unrelated), roots=("wanted",)) == ("dep", "wanted")


def test_dependency_order_rejects_missing_dependency(make_component) -> None:
    component = make_component("component", dependencies=("missing",))

    with pytest.raises(DependencyError, match="missing"):
        dependency_order((component,))


def test_dependency_order_rejects_unknown_root(make_component) -> None:
    with pytest.raises(DependencyError, match="unknown root"):
        dependency_order((make_component("a"),), roots=("missing",))


def test_dependency_order_rejects_cycle(make_component) -> None:
    a = make_component("a", dependencies=("b",))
    b = make_component("b", dependencies=("a",))

    with pytest.raises(DependencyError, match="cycle"):
        dependency_order((a, b))


def test_dependency_order_is_deterministic(make_component) -> None:
    a = make_component("a")
    b = make_component("b", dependencies=("a",))
    c = make_component("c", dependencies=("a",))

    assert dependency_order((c, a, b)) == dependency_order((b, c, a))
