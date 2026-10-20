# Architectural Decisions

## ADR-001: Python 3.12 and uv

**Status:** Accepted

**Context:** Mosaic is a new project, and Python 3.9 is end-of-life. Later phases
need a maintained runtime for PyTorch and optional pretrained controllers. uv is
already available and provides reproducible environment creation.

**Decision:** Target Python 3.12 or newer and use `uv` for environment and
dependency installation. The package metadata declares `requires-python >=3.12`.

**Consequences:** Python 3.9 compatibility is not maintained. Engineers need a
Python 3.12 interpreter; uv can provide one where permitted.

## ADR-002: Frozen Pydantic v2 contracts

**Status:** Accepted

**Context:** Subsystems exchange manifests, traces, plans, and predictions.
Untyped dictionaries or mutable dataclasses would permit unknown fields,
inconsistent units, and accidental state changes.

**Decision:** Model data contracts as frozen Pydantic v2 models with
`extra="forbid"`. Structural validation raises Pydantic `ValidationError`;
domain operations use the explicit exception hierarchy in `mosaic.errors`.

**Consequences:** Contracts serialize cleanly to JSON and reject malformed input
at construction. Frozen models prevent attribute reassignment, though nested
mapping payloads such as request features are only shallowly immutable.

## ADR-003: Bytes internally, explicit units at boundaries

**Status:** Accepted

**Context:** Memory budgets and component sizes are easy to misstate when MiB,
MB, and raw numbers are mixed.

**Decision:** Store bytes as non-negative integers in contracts and use `_bytes`
field suffixes. Accept integer byte counts or unit-bearing strings at the
configuration boundary through `mosaic.units.ByteSize`. Bare numeric strings are
rejected. Use `_ms` for millisecond durations.

**Consequences:** Internal arithmetic is exact and unit-checked. TOML integer
values remain valid byte counts, while strings must name a unit.

## ADR-004: Protocol-based subsystem interfaces

**Status:** Accepted

**Context:** The simulator, registry, controller, and real runtime adapter must
be replaceable without a shared inheritance hierarchy. Phase 1 must define
boundaries without implementing later phases.

**Decision:** Express subsystem interfaces as `typing.Protocol` classes in
`mosaic.interfaces`, marked `runtime_checkable` for structural conformance tests.

**Consequences:** Implementations remain decoupled from Mosaic base classes.
Interface changes require a documented decision because later phases rely on
them.

## ADR-005: TOML configuration and standard-library logging

**Status:** Accepted

**Context:** Configuration must stay external to implementation, and Phase 1
needs structured logs without adding a logging framework.

**Decision:** Use TOML parsed with `tomllib`, validated by Pydantic, and configure
Python standard-library logging with text and JSON formatters. Relative paths
resolve against the configuration file directory.

**Consequences:** There is no dependency on `pydantic-settings` or a third-party
logging package. JSON logs support structured `extra` fields.

## ADR-006: No runtime or simulator implementation in Phase 1

**Status:** Accepted

**Context:** The phase plan forbids implementing later phases prematurely. The
architecture and contracts must nevertheless be concrete.

**Decision:** Phase 1 delivers only metadata contracts, protocols, configuration,
errors, logging, CLI configuration validation, and tests. It does not implement
component registration, hashing, simulation, clustering, controller training, or
memory management.

**Consequences:** The package is importable and testable on CPU-only hardware
without model weights. Later phases add implementations behind the existing
interfaces.

## ADR-007: Logical identity separate from content identity

**Status:** Accepted

**Context:** A component may move between storage locations, and its logical role
must not be confused with the bytes currently stored for it.

**Decision:** `ComponentMetadata` carries both a stable `component_id` and a
lowercase SHA-256 `content_hash`. Clusters reference component identifiers only.
Phase 2 verifies declared hashes against stored content before registration or
loading.

**Consequences:** Renaming or relocating a component does not change logical
routing identity, while content changes are detectable. Verification is not yet
implemented in Phase 1.

## ADR-008: No nested Git repository initialized

**Status:** Proposed

**Context:** `mosaic` currently sits inside the existing `python_apps` repository
worktree. The project prompt assumes an empty repository named `mosaic`.

**Decision:** Do not create a nested `.git` directory during Phase 1. Keep source
changes in the existing worktree until the repository layout is confirmed.

**Consequences:** Mosaic currently shares its parent repository's history. A
standalone repository or workspace member can be established later without
rewriting the package layout.
