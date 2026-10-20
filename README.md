# Mosaic

Mosaic is a learned controller for the memory residency of components in a
componentized local model. It predicts which components or clusters are likely
to be useful for a request, while a deterministic memory manager validates and
executes loading, retention, prefetching, and eviction decisions.

The large model remains the executor. Mosaic is not a knowledge-distillation
project and does not train a small model to reproduce the large model's answers.

## Status

Phase 1 is implemented: package foundation, typed contracts, subsystem
protocols, configuration, logging, error taxonomy, documentation, and tests.
The registry, simulator, clustering engine, trainable controller, memory
manager, and real runtime adapter are not implemented yet.

## Scope and constraints

- Components must be genuine loadable units, such as mixture-of-experts (MoE)
  experts. Mosaic does not pretend that arbitrary tensor groups can be removed
  from a dense transformer without breaking inference.
- Simulation is the first execution environment. Real hardware measurements and
  simulated measurements must remain clearly separated.
- Phase 1 has no model downloads, no GPU requirement, and no runtime inference.
- Memory quantities are represented internally as non-negative integers of
  bytes. External configuration accepts explicit units such as `"512 MiB"`.
- Contracts are immutable, reject unknown fields, and distinguish logical
  component identity from the SHA-256 content hash.
- Missing trace measurements are represented as `None`; they are never silently
  converted to zero. An observed empty activation set is an empty tuple.

## Requirements

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Setup

```powershell
uv venv --python 3.12
uv pip install --python .venv\Scripts\python.exe -e ".[dev]"
```

On Unix-like systems:

```bash
uv venv --python 3.12
uv pip install --python .venv/bin/python -e ".[dev]"
```

If Windows Application Control blocks uv-managed Python binaries with
`os error 4551`, create the environment from a signed python.org installation
instead:

```powershell
uv venv .venv --python "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
uv pip install --python .venv\Scripts\python.exe -e ".[dev]"
```

Validate the shipped configuration:

```powershell
.venv\Scripts\python.exe -m mosaic config validate --config configs\default.toml
```

The same command is available through the installed `mosaic` entry point. If
`--config` is omitted, Mosaic uses `$MOSAIC_CONFIG` or `configs/default.toml`
relative to the current directory.

## Configuration

The default configuration is in [`configs/default.toml`](configs/default.toml).
Relative paths are resolved against the configuration file's directory.

```toml
schema_version = 1

[paths]
data_dir = "../data"
traces_dir = "../data/traces"
artifacts_dir = "../artifacts"

[memory]
ram_capacity = "16 GiB"
vram_capacity = "0 B"
safety_margin = "512 MiB"

[logging]
level = "INFO"
format = "text"
```

Byte-size values accept binary units (`KiB`, `MiB`, `GiB`, `TiB`, `PiB`) and
decimal units (`KB`, `MB`, `GB`, `TB`, `PB`). Bare numeric strings are rejected;
integer TOML values are interpreted as bytes.

## Repository layout

```text
mosaic/
├── configs/              # External TOML configuration
├── docs/                 # Architecture and decision records
├── src/mosaic/
│   ├── cli/              # Command-line entry point
│   ├── contracts/        # Immutable data contracts
│   ├── interfaces/       # Runtime-checkable subsystem protocols
│   ├── config.py         # Configuration loading and validation
│   ├── errors.py         # Domain exception taxonomy
│   ├── logging.py        # Text and JSON structured logging
│   ├── units.py          # Explicit byte-size parsing
│   └── __main__.py       # python -m mosaic
└── tests/
    ├── integration/
    └── unit/
```

## Development checks

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\ruff.exe check .
.venv\Scripts\ruff.exe format --check .
.venv\Scripts\mypy.exe src
```

## Design notes

- [`docs/architecture.md`](docs/architecture.md) describes subsystem boundaries,
  data contracts, invariants, and the phase plan.
- [`docs/decisions.md`](docs/decisions.md) records architectural decisions.

Mosaic claims no performance improvement until the evaluation suite demonstrates
one against an equivalent baseline. Simulated latency is never presented as
evidence of real hardware speed.
