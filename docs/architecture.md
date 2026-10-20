# Mosaic Architecture

## 1. Purpose

Mosaic learns routing and memory-residency decisions for a componentized local
model. A trainable controller predicts which components or clusters are useful
for a request. A deterministic memory manager validates those recommendations
against resource budgets, dependencies, runtime compatibility, and in-use
protection before changing residency.

The large model performs inference. Mosaic never replaces the model's answer
generation with a learned imitation objective.

## 2. Non-goals

- Mosaic does not treat arbitrary tensors or layers of a dense transformer as
  independently removable components.
- Mosaic does not silently simulate capabilities that a real runtime lacks.
- Mosaic does not assume that every activated component was necessary or that
  every inactive component was unnecessary.
- Mosaic does not claim benchmark improvements before measuring them.

## 3. Subsystems

| Subsystem | Responsibility | Interface |
| --- | --- | --- |
| Component registry | Authoritative component and cluster metadata, integrity, dependencies | `ComponentRegistry` |
| Clustering engine | Offline co-activation clustering and merge explanations | `ClusteringEngine` |
| Controller | Ranks candidate components or clusters for a request | `Controller` |
| Memory manager | Validates and executes memory plans, enforces budgets and lifecycle rules | `MemoryManager` |
| Observer | Records and replays validated execution traces | `Observer` |
| Runtime adapter | Controlled component operations through a real inference runtime | `RuntimeAdapter` |
| Simulator | Deterministic implementation of the runtime and memory environment | Phase 2 implementation |

Interfaces live in `mosaic.interfaces` and are expressed as
`typing.Protocol` classes. Implementations are not required to inherit from a
framework base class.

The controller only recommends. It returns a `ControllerPrediction` and cannot
mutate `MemoryState`. The memory manager validates every proposal and owns the
resulting state transitions.

## 4. Data contracts

All contracts derive from `mosaic.contracts.Contract`, a frozen Pydantic model
with `extra="forbid"`.

| Area | Contracts |
| --- | --- |
| Identity | `ModelIdentity`, `RuntimeIdentity`, `RuntimeCapabilities` |
| Components | `ComponentMetadata`, `ComponentType`, `StorageLocation`, `RuntimeCompatibility` |
| Clusters | `ClusterManifest` |
| Memory | `TierBudget`, `MemoryBudget`, `TierUsage`, `ComponentPlacement`, `MemoryState` |
| Actions | `MemoryAction`, `MemoryPlan`, `MemoryActionType`, `MemoryPlanSource` |
| Traces | `RequestRecord`, `ExecutionTrace`, `TraceEvent`, `MemoryMeasurements`, `LatencyMeasurements`, `CacheStatistics`, `TaskOutcome` |
| Controller | `ControllerCandidate`, `CandidateUsage`, `ControllerRequest`, `ScoredCandidate`, `ControllerPrediction` |

### Identity

Each component has a stable logical `component_id` and a separate SHA-256
`content_hash`. Clusters reference component identifiers and never duplicate
component weights or metadata. Canonical manifest hashing and content
verification are implemented in `mosaic.serialization` and `mosaic.storage`.

### Units

Resource fields inside contracts use an explicit `_bytes` suffix and hold
non-negative integers of bytes. External configuration accepts unit-bearing
strings through the `ByteSize` type. Durations use `_ms` and are floating-point
milliseconds. Validation rejects negative values, non-finite floats, and
ambiguous bare numeric strings.

### Missing measurements

Every optional measurement in a trace defaults to `None`. This preserves the
difference between:

- activation observation unavailable (`activated_components is None`);
- observation available and no component activated (`activated_components == ()`).

### Memory state

`MemoryState` is a snapshot of RAM and VRAM usage plus component placements.
Placement sizes must sum exactly to the reported `resident_bytes` for each tier.
A component may appear once in RAM and once in VRAM, but not twice in the same
tier. Runtime allocations such as KV caches are represented by
`runtime_overhead_bytes` rather than being attributed to a component.

`TierBudget.effective_capacity_bytes` is capacity minus the safety margin.
The Phase 2 simulator enforces these limits; the Phase 5 memory manager will own
plan validation and orchestration.

### Registry

`SQLiteRegistry` is the authoritative store for component and cluster manifests.
It persists canonical JSON, a manifest hash, the content hash, the manifest schema
version, and a timestamp. Both the current row and an append-only revision table
are written for every registration and update.

Registration verifies stored content before writing, rejects duplicate logical
identities, and validates dependencies with `dependency_order`. Clusters may only
reference registered components from the same source model. Manifests are
re-validated and hash-checked when read, so direct database tampering is detected.

`mosaic.storage.verify_storage` supports file, directory, and simulated content.
File and directory verification checks size and SHA-256. Directory hashing is
deterministic over relative paths and rejects symlinks. Simulated content is a
small canonical JSON descriptor carrying a logical byte size; it is explicitly
not a model weight file.

### Simulator

`Simulator` implements deterministic RAM/VRAM/disk residency without performing
inference. Components begin on simulated disk. Loading reads bytes into RAM and
then VRAM, loads dependencies first, and enforces effective capacities. Prefetch
stages bytes in RAM without making a component resident. Execution activates
resident components and records per-component activation counts.

In-use components cannot be evicted. The simulator never chooses an eviction
victim automatically; `least_recently_used` is an inspection helper for policies
that will be evaluated in later phases. All result models carry
`simulated = True`, and latency jitter is driven by an explicit seed.

## 5. Configuration

Configuration is TOML, loaded by `mosaic.config.MosaicConfig.load`. Validation
rejects unknown keys, missing sections, invalid units, and margins larger than
capacity. Relative paths are resolved against the configuration file directory.

Logging uses the Python standard library. The JSON formatter emits one object
per line with core fields plus structured `extra` values such as `event` and
`trace_id`.

## 6. Errors

Structural contract violations raise Pydantic `ValidationError`. Domain
operations raise subclasses of `mosaic.errors.MosaicError`:

- `ConfigurationError` for unreadable or invalid configuration;
- `InvalidManifestError` for registry-level manifest failures;
- `IntegrityError` for hash or content mismatches;
- `UnsupportedRuntimeCapabilityError` for operations the runtime cannot perform;
- `ResourceBudgetError` for RAM/VRAM violations;
- `ComponentOperationError` and its subclasses for lifecycle failures;
- `RuntimeOperationError` for runtime execution failures.

## 7. Runtime truth

The Phase 1 package does not contact a model runtime. Phase 2 adds a deterministic
simulator whose measurements are explicitly simulated. Phase 7 may add a real
MoE runtime adapter only after verifying that the runtime can enumerate
components, observe actual activations, load and evict experts safely, and
handle in-flight inference. If those capabilities are unavailable, the phase
must stop and report the limitation rather than fabricate support.

## 8. Testing strategy

- Unit tests cover contract validation, serialization, hashing, storage
  verification, dependency ordering, registry persistence and revisions,
  simulator lifecycle rules, unit parsing, configuration, logging, and protocol
  conformance.
- Integration tests import the installed package, load the shipped configuration,
  exercise `python -m mosaic`, and connect the SQLite registry to the simulator.
- No test downloads model weights or requires a GPU.
- Simulator and real-runtime results remain separately labeled.
- Tests use temporary directories and SQLite databases; no persistent test data
  is written into the repository.

## 9. Phase plan

1. Architecture, contracts, configuration, logging, interfaces, tests. **Done.**
2. Registry, content hashing, deterministic simulator. **Done.**
3. Execution traces and automatic co-activation clustering.
4. Trainable controller and reproducible training pipeline.
5. Memory manager and validated controller integration.
6. End-to-end evaluation against LRU, frequency-aware, heuristic, and
   load-everything baselines.
7. Verified real MoE runtime integration and real measurements.
8. Outcome-driven controller learning and safe policy promotion.
