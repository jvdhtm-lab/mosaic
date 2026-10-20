# Mosaic — Master Project Specification and Implementation Prompts

## How to use this prompt pack

1. Create an empty repository named `mosaic`.
2. Send **Prompt 0** to your coding LLM first.
3. Execute the phases in order, using one phase prompt at a time.
4. Require the agent to run tests and report results before proceeding.
5. Do not let the agent implement later phases prematurely.
6. Commit the repository after every accepted phase.

The coding agent must maintain the architecture, tests, and documentation as the project evolves.

---

# PROMPT 0 — Master Project Specification

You are the lead software architect and implementation engineer for Mosaic.

Your task is to build a production-oriented, modular Python system that learns to manage the memory residency of components belonging to a larger local AI model.

## 1. Project mission

Mosaic contains a small, trainable controller that learns which components of a larger model are useful for a given request and which components should be loaded, retained, prefetched, or evicted.

The larger model remains responsible for actual inference and answer generation.

Mosaic is NOT a knowledge-distillation project. Do not train the small controller to imitate the large model's generated answers as its primary objective.

Instead, train the controller to make routing and memory-management decisions based on execution traces, resource constraints, observed component usage, latency, and task outcomes.

## 2. Core architecture

Implement these independent subsystems:

- **Controller:** A trainable predictor that recommends components or clusters.
- **Component registry:** Stores component identifiers, hashes, sizes, dependencies, storage locations, and compatibility metadata.
- **Clustering engine:** Discovers components that frequently activate together and creates manageable clusters.
- **Memory manager:** Manages persistent storage, system RAM, and GPU VRAM.
- **Observer:** Collects runtime activations, loading times, memory measurements, cache events, and task outcomes.
- **Training pipeline:** Converts execution traces into datasets, trains the controller, evaluates checkpoints, and records experiments.
- **Runtime adapter:** Integrates Mosaic with a compatible inference engine.
- **Simulator:** Allows all core logic to be developed and tested without specialized hardware or a large model.

## 3. Fundamental technical constraint

Distinguish actual neural-network experts from arbitrary model weights.

A conventional dense transformer does not expose independent semantic components for Python, Django, SQL, or other topics. Its knowledge is distributed across the network.

Mosaic must not pretend it can safely remove arbitrary layers or tensor groups from a dense model and continue inference.

The first real integration should use a model architecture and inference runtime that expose the component-loading capabilities Mosaic needs, preferably a genuine mixture-of-experts (MoE) model.

If the chosen runtime cannot load and unload individual experts safely, document the limitation and select a supported alternative. Do not silently simulate functionality in the real-runtime adapter.

## 4. Initial technology choices

Use Python and a modular package architecture.

Preferred starting technologies:

- PyTorch for trainable predictors.
- Hugging Face Transformers for supported pretrained controller models.
- PEFT/LoRA when useful for controller fine-tuning.
- Pydantic for validated configuration and data contracts, where appropriate.
- pytest for automated testing.
- SQLite for the initial local registry and experiment metadata if a database is needed.
- JSONL for execution traces and training examples.
- A configuration file for paths, resource budgets, thresholds, and model settings.

Keep dependencies minimal. Verify package compatibility before selecting versions.

The system must run in simulation mode on a CPU-only machine. Real GPU inference must be optional.

## 5. Proposed repository structure

```text
mosaic/
├── pyproject.toml
├── README.md
├── configs/
├── docs/
│   ├── architecture.md
│   ├── decisions.md
│   └── experiments.md
├── src/
│   └── mosaic/
│       ├── core/
│       ├── registry/
│       ├── clustering/
│       ├── controller/
│       ├── memory/
│       ├── observer/
│       ├── training/
│       ├── runtime/
│       ├── evaluation/
│       └── cli/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── end_to_end/
├── scripts/
└── examples/
```

This is the initial proposal, not a mandate to create empty modules. Add modules only when they contain real functionality.

## 6. Component and cluster identity

Each component must have:

- A stable identifier.
- A cryptographic content hash.
- A component type.
- A source model and architecture identifier.
- A storage location.
- A size in bytes.
- Dependency metadata.
- Runtime compatibility metadata.

Clusters must contain references to components, not duplicated copies of their weights.

Use canonical serialization when hashing manifests. Distinguish a component's content hash from its logical ID.

Validate integrity and compatibility before loading a component.

## 7. Controller training

The initial controller should predict which components or clusters are likely to be useful for a request.

Inputs may include:

- Request features.
- Candidate cluster descriptions and metadata.
- Current resident components.
- Available RAM and VRAM.
- Component sizes and loading costs.
- Historical routing statistics.

Begin with a simple trainable predictor or a small pretrained language model with a trainable classification head.

Use supervised training from execution traces. Later, evaluate LoRA fine-tuning and more advanced policies.

Do not assume that a 0.5B–1.5B model is automatically optimal. Benchmark controller accuracy, inference latency, and memory overhead before choosing a size.

## 8. Memory-management policy

The controller recommends actions. A deterministic memory manager validates and executes them.

The manager must enforce:

- RAM and VRAM budgets.
- Component dependencies.
- In-use component protection.
- Valid loading and eviction state transitions.
- Safe handling of failures and concurrent requests.
- Integrity and runtime compatibility checks.

Account for runtime allocations, KV caches, temporary buffers, and safety margins where measurable.

Start with an LRU baseline. Compare it with frequency-aware caching and controller-assisted policies.

## 9. Clustering policy

Collect observed component activation traces.

Calculate co-activation statistics and use them to build clusters.

Implement a configurable merge threshold. The initial rule is to consider merging clusters that share more than two components.

This is a heuristic, not a universal rule. Evaluate cluster size, loading costs, activation frequency, and memory constraints before merging.

Record the reason for each merge. Prevent unbounded cluster growth.

## 10. Evaluation requirements

Evaluate Mosaic against a baseline that does not use its learned controller.

Measure:

- Routing precision, recall, and F1.
- Component-load count.
- Cache hit rate.
- Loading latency.
- End-to-end inference latency.
- Peak RAM and VRAM.
- Evictions and reloads.
- Resource-budget violations.
- Task quality.

Do not claim a performance improvement unless the benchmark demonstrates it.

Separate simulation results from real-runtime results.

## 11. Engineering rules

- Implement only the currently authorized phase.
- Inspect the existing repository before changing it.
- Keep public interfaces stable unless a documented change is necessary.
- Write tests alongside implementation.
- Do not replace existing functionality without justification.
- Do not create speculative abstractions.
- Do not leave silent placeholder implementations.
- Use type hints, structured logging, and explicit errors.
- Document important architectural decisions.
- Keep all configuration external to the implementation.
- Make training runs reproducible where practical.
- Never fabricate test results or benchmark numbers.

At the end of every phase, report the changed files, implemented behavior, commands executed, actual test results, known limitations, and remaining work.

---

# PROMPT 1 — Architecture and Repository Foundation

Implement Phase 1 only.

First inspect the repository and determine whether any existing files or code must be preserved.

## Objectives

1. Establish the Python package and development environment.
2. Define core data contracts.
3. Define interfaces between the subsystems.
4. Establish configuration, logging, errors, and testing conventions.
5. Document the architecture and important design decisions.

## Requirements

Create the project metadata, package structure, configuration validation, and minimal documentation.

Define typed contracts for:

- Component metadata.
- Cluster manifests.
- Model and runtime identity.
- Memory state.
- Memory action proposals.
- Execution traces.
- Runtime capabilities.
- Controller predictions.

Use immutable data structures where appropriate.

Define abstract or protocol-based interfaces for:

- Component registry.
- Clustering engine.
- Controller.
- Memory manager.
- Observer.
- Runtime adapter.

Avoid creating large frameworks or implementing future functionality prematurely.

Use explicit units in all resource-related fields. Memory sizes must be represented consistently in bytes internally.

Define errors for invalid manifests, integrity failures, unsupported runtime capabilities, resource-budget violations, and failed component operations.

## Tests

Test configuration validation, serialization, invalid data rejection, unit consistency, and interface contracts.

## Acceptance criteria

- The package installs in development mode.
- Imports work without loading a large model.
- Tests run on CPU-only hardware.
- No GPU is required.
- Architecture and interfaces are documented.
- No major subsystem contains placeholder business logic.

Stop after this phase and report results.

---

# PROMPT 2 — Registry, Component Hashing, and Simulator

Implement Phase 2 only.

Use the existing architecture and interfaces. Do not redesign the project without explaining why.

## Objectives

Build a working component registry and a deterministic simulation runtime.

## Registry

Implement:

- Component registration.
- Canonical metadata serialization.
- SHA-256 content verification.
- Cluster manifest registration.
- Dependency validation.
- Storage metadata.
- Versioned manifest persistence.
- Detection of missing or corrupted components.

Separate content identity from logical identity.

Never trust a declared file size or hash without verifying it when verification is required.

Do not load model weights merely to register their metadata.

## Simulator

Implement a simulated runtime that represents components with configurable sizes, loading costs, dependencies, and compatibility requirements.

The simulator must track:

- Components stored on disk.
- Components staged in RAM.
- Components resident in VRAM.
- Loading and transfer costs.
- Component usage during simulated inference.
- Cache hits and misses.
- Evictions.
- Resource consumption.

Make simulation deterministic when provided with the same seed and input sequence.

Clearly mark simulated operations and measurements as simulated.

## Tests

Cover hash determinism, corrupted files, duplicate registration, dependency cycles, missing dependencies, incompatible components, and simulated loading failures.

## Acceptance criteria

- Components can be registered and verified.
- Clusters can reference registered components.
- The simulator can load, use, and evict components.
- Resource state is inspectable.
- No real neural-network weights are required.
- All tests pass.

Stop after this phase.

---

# PROMPT 3 — Execution Traces and Automatic Clustering

Implement Phase 3 only.

Build the observation and offline clustering pipeline using the existing contracts.

## Execution traces

Implement a versioned JSONL trace format.

Each trace should support:

- Request identifier and privacy-safe features.
- Model and runtime identity.
- Predicted components.
- Actual activated components when observable.
- Component load and eviction events.
- RAM and VRAM measurements.
- Latency measurements.
- Cache statistics.
- Task outcome or quality score, when available.

Do not confuse predicted components with actual activations.

Support incomplete traces without silently treating missing measurements as zero.

## Clustering engine

Implement:

1. Trace ingestion and validation.
2. Component activation frequency calculations.
3. Pairwise co-activation statistics.
4. Candidate cluster generation.
5. Cluster merge decisions.
6. Manifest generation.
7. A report explaining cluster membership and merge decisions.

Start with a transparent co-activation-based algorithm.

Use the configurable initial rule that clusters sharing more than two components are candidates for merging.

Before committing a merge, evaluate:

- Resulting cluster size.
- Estimated loading cost.
- Activation frequency.
- Memory-budget implications.
- Whether the merge is likely to reduce repeated loading.

Add limits to prevent excessive cluster growth.

Make the algorithm deterministic for identical inputs and configuration.

## Tests

Use synthetic activation traces with known expected patterns.

Test malformed traces, missing measurements, repeated observations, threshold boundaries, oversized clusters, and deterministic manifests.

## Acceptance criteria

- Traces can be collected, validated, and replayed.
- Clusters are generated from observed usage.
- Merge decisions are explainable.
- The system never requires manually assigning semantic expert labels.
- All outputs are reproducible and testable.

Stop after this phase.

---

# PROMPT 4 — Trainable Mosaic Controller

Implement Phase 4 only.

The objective is to train Mosaic to predict useful components or clusters, not to reproduce the large model's answers.

## Training dataset

Build a dataset generator that converts validated execution traces into supervised examples.

Each example should contain:

- Request features.
- Candidate cluster IDs and metadata.
- Available memory information when relevant.
- Labels for components observed or independently evaluated as useful.
- Provenance and trace identifiers.

Distinguish observed activations from verified usefulness.

Do not automatically assume that every activated expert was necessary or that every inactive expert was unnecessary.

## Initial model

Implement a baseline heuristic and a trainable multi-label predictor.

Use a compact trainable model first. A simple classification model is acceptable if it is a useful baseline.

If using a pretrained language model, make it optional and configurable. Keep the training pipeline independent of a particular pretrained model.

Do not download large models automatically during tests.

## Training pipeline

Implement:

- Dataset splitting.
- Reproducible training.
- Validation.
- Checkpoint saving and loading.
- Configurable thresholds for multi-label predictions.
- Metrics and training logs.
- A command-line training entry point.

Prevent data leakage by splitting on task groups or source traces when appropriate, rather than randomly duplicating closely related examples across training and validation sets.

## Evaluation

Compare the learned predictor against the baseline heuristic.

Report precision, recall, F1, and prediction latency.

Include a test proving that a saved checkpoint can be reloaded and used to make predictions.

## Constraints

Do not implement reinforcement learning in this phase.

Do not train Mosaic to generate code.

Do not require a GPU to run the small synthetic training example.

## Acceptance criteria

- Synthetic data can train a working controller.
- The trained model predicts candidate clusters.
- Evaluation metrics are calculated from held-out examples.
- Training is reproducible.
- The model can be saved and reloaded.
- No claimed accuracy is fabricated.

Stop after this phase.

---

# PROMPT 5 — Memory Manager and Controller Integration

Implement Phase 5 only.

Connect the trained controller to the registry, simulator, and memory manager.

## Memory manager

Implement validated actions for:

- Load.
- Prefetch.
- Retain.
- Evict.

Enforce RAM and VRAM budgets, dependencies, compatibility, and in-use component protection.

Implement LRU as the baseline eviction policy. Add frequency-aware caching only if it can be tested independently.

## Controller integration

Give Mosaic the information needed to make routing decisions:

- Request features.
- Candidate clusters.
- Current resident clusters.
- Available RAM and VRAM.
- Cluster sizes.
- Estimated loading costs.
- Relevant usage statistics.

The controller should recommend components or actions. It must not directly modify memory state.

Validate every recommendation before executing it.

If the controller fails, returns invalid identifiers, or exceeds the budget, use a documented fallback policy.

## Prefetching

Implement prefetching only when it can be performed without breaking memory budgets or delaying required operations unnecessarily.

Track whether prefetched components were actually used.

## Concurrency and failures

Handle duplicate load requests, in-use components, failed loads, interrupted operations, and state consistency.

A component must not be evicted while a runtime operation is still using it.

Use explicit lifecycle states and tests for legal transitions.

## Tests

Test memory-budget enforcement, fallback behavior, concurrent requests, in-use protection, dependency loading, eviction, and controller integration.

## Acceptance criteria

- Mosaic can predict clusters and execute validated memory plans in simulation.
- Invalid predictions cannot violate resource limits.
- Memory state remains consistent after failures.
- Controller-assisted decisions can be compared with LRU and heuristic baselines.

Stop after this phase.

---

# PROMPT 6 — End-to-End Evaluation and Optimization

Implement Phase 6 only.

Build an experiment runner that evaluates Mosaic against meaningful baselines.

## Required baselines

1. LRU caching without learned routing.
2. Frequency-aware caching.
3. Heuristic component selection.
4. Learned Mosaic routing with the same resource budgets.

Where applicable, compare against a policy that loads all components required by the workload before execution.

## Workloads

Create synthetic workloads representing:

- Repeated requests with similar component requirements.
- Rapidly changing component requirements.
- Requests with overlapping clusters.
- Memory-constrained workloads.
- Workloads with inaccurate controller predictions.
- Workloads containing expensive component loads.

Keep workload definitions reproducible.

## Metrics

Report:

- Total component loads.
- Reloads caused by eviction.
- Cache hit rate.
- Prefetch usefulness.
- Average and percentile loading latency.
- End-to-end simulated latency.
- Peak RAM and VRAM usage.
- Budget violations.
- Routing precision, recall, and F1 where labels are available.

Report task quality separately from system efficiency.

Do not use simulated latency as evidence of real hardware speed.

## Acceptance criteria

- One command runs the evaluation suite.
- Results are saved in a machine-readable format.
- Baselines use equivalent workload sequences and resource budgets.
- Results include configuration and seed information.
- The report distinguishes simulated and real measurements.
- No performance improvement is claimed unless demonstrated.

Stop after this phase.

---

# PROMPT 7 — Real MoE Runtime Research and Integration

Implement Phase 7 only after the previous phases pass.

This phase connects Mosaic to an actual inference runtime capable of exposing the model components Mosaic needs to manage.

## Step 1: Verify runtime capabilities

Before coding, research and verify the current capabilities of candidate runtimes and models.

Determine whether the selected combination supports:

- Discovering actual expert modules.
- Mapping expert IDs to model weights.
- Observing actual expert activations.
- Loading or offloading experts at runtime.
- Safely handling in-flight inference.
- Respecting component dependencies and execution requirements.
- Measuring RAM, VRAM, and transfer costs.

Do not assume that an ordinary Transformers model loader can dynamically load arbitrary experts.

Document the chosen model, license, runtime, supported operations, limitations, and hardware requirements.

If no supported runtime offers the required capabilities, stop and present the available alternatives instead of pretending integration is complete.

## Step 2: Implement the runtime adapter

Implement a real adapter behind the existing runtime interface.

It must distinguish:

- Requested expert availability.
- Actual expert activation.
- Weight transfer.
- Runtime execution.
- Memory usage.
- Errors and unsupported operations.

Use the runtime's supported APIs. Do not patch internal execution paths without a documented design and tests.

## Step 3: Integrate observation

Collect real activation traces and memory measurements where supported.

Verify that trace records correspond to actual runtime events.

## Step 4: Integrate controlled loading

Connect Mosaic's validated memory plans to the runtime.

The runtime must remain responsible for correct model execution. Mosaic must not remove required experts or interfere with an in-flight operation.

Start with conservative loading and eviction behavior. Enable predictive prefetching only after correctness is established.

## Step 5: Real evaluation

Compare Mosaic with the runtime's normal behavior and any supported built-in expert-caching policy.

Measure real loading latency, inference latency, memory usage, and task quality.

## Acceptance criteria

- The adapter uses a verified real runtime.
- Actual runtime capabilities are documented.
- Unsupported behavior is reported honestly.
- The large model can execute requests correctly.
- Loading and eviction do not break inference.
- Real benchmarks are reproducible and separate from simulation results.

Stop after this phase.

---

# PROMPT 8 — Controller Learning from Outcomes

Implement Phase 8 only after real runtime integration works.

Improve Mosaic using measured execution outcomes rather than assuming its first routing prediction is correct.

## Objective

Develop a feedback loop that improves component selection and memory decisions while preserving task quality.

## Data collection

Record:

- Predicted components.
- Actual activations.
- Components loaded and evicted.
- Loading and inference costs.
- Memory usage.
- Task quality and success indicators.
- Whether prefetching was useful.
- Whether an eviction caused a later reload.

Track missing or uncertain outcomes explicitly.

## Training experiments

Begin by retraining the supervised controller on newly collected traces.

Then evaluate whether a contextual bandit can improve decisions involving cache retention, prefetching, and eviction.

Use reinforcement learning only if the simpler approaches demonstrate a meaningful limitation.

Do not reward speed alone. A fast result that damages task quality is not a successful optimization.

## Reward design

Experiment with a documented objective combining:

- Task quality.
- End-to-end latency.
- Memory cost.
- Component-loading overhead.
- Unnecessary evictions and reloads.
- Resource-budget violations.

Normalize metrics and justify weights using measurable trade-offs.

## Safe experimentation

- Keep the previous model checkpoint available.
- Evaluate new policies before promoting them.
- Use held-out workloads.
- Compare against fixed baselines.
- Prevent uncontrolled exploration during normal inference.
- Record model and policy versions for every experiment.

## Acceptance criteria

- New traces can be incorporated into training.
- Model versions can be compared reproducibly.
- A new controller is promoted only after passing evaluation.
- Any improvement is supported by measurements.
- Failed experiments can be rolled back.

Stop after this phase.

---

# Standard Completion Prompt

Use this after every implementation phase:

Review the work completed in the current phase against its prompt and the master project specification.

1. Inspect the actual repository changes.
2. Run the relevant automated tests.
3. Run formatting, linting, and type checks if configured.
4. Identify unimplemented requirements, broken interfaces, hidden assumptions, and unnecessary abstractions.
5. Fix issues introduced by this phase.
6. Verify that previously implemented behavior still works.
7. Update documentation and the architecture decision log.
8. Do not begin the next phase.

Return a concise engineering report containing:

- Implemented features.
- Files changed.
- Commands executed.
- Actual test results.
- Known limitations.
- Requirements not yet met.
- Any architectural decisions that require approval.
- The exact command to begin the next phase.

Never claim that a command or test passed unless you actually executed it and observed the result.

---

# Final Project Principle

Mosaic's intelligence lies in learning which model components to prepare and how to manage their residency efficiently.

The large model remains the executor. Mosaic becomes the learned controller that makes execution more efficient.

The system should first demonstrate that its decisions are measurable and useful in simulation, then prove that those decisions improve a real model runtime without sacrificing correctness or task quality.
