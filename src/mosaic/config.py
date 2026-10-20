"""Validated, external configuration for Mosaic."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, ValidationError, field_validator, model_validator

from mosaic.contracts.common import Contract
from mosaic.contracts.memory import MemoryBudget, TierBudget
from mosaic.errors import ConfigurationError
from mosaic.logging import LogFormat
from mosaic.units import ByteSize


class LoggingConfig(Contract):
    """Logging settings."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    format: LogFormat = LogFormat.TEXT


class PathsConfig(Contract):
    """Filesystem locations used by Mosaic."""

    data_dir: Path
    traces_dir: Path
    artifacts_dir: Path

    @field_validator("data_dir", "traces_dir", "artifacts_dir", mode="before")
    @classmethod
    def _reject_empty_paths(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            raise ValueError("paths must not be empty")
        return value

    def resolved(self, base_dir: Path) -> PathsConfig:
        """Return a copy with relative paths resolved against ``base_dir``."""

        def resolve(path: Path) -> Path:
            return path.resolve() if path.is_absolute() else (base_dir / path).resolve()

        return self.model_copy(
            update={
                "data_dir": resolve(self.data_dir),
                "traces_dir": resolve(self.traces_dir),
                "artifacts_dir": resolve(self.artifacts_dir),
            }
        )


class MemoryConfig(Contract):
    """Configured memory capacities and safety margin."""

    ram_capacity: ByteSize
    vram_capacity: ByteSize = 0
    safety_margin: ByteSize = 0

    @model_validator(mode="after")
    def _validate_budgets(self) -> Self:
        if self.ram_capacity <= 0:
            raise ValueError("ram_capacity must be greater than zero")
        if self.safety_margin > self.ram_capacity:
            raise ValueError("safety_margin must not exceed ram_capacity")
        if self.vram_capacity > 0 and self.safety_margin > self.vram_capacity:
            raise ValueError("safety_margin must not exceed vram_capacity")
        return self

    def to_budget(self) -> MemoryBudget:
        """Convert the configuration to an immutable memory budget contract."""
        vram_margin = self.safety_margin if self.vram_capacity > 0 else 0
        return MemoryBudget(
            ram=TierBudget(
                capacity_bytes=self.ram_capacity,
                safety_margin_bytes=self.safety_margin,
            ),
            vram=TierBudget(
                capacity_bytes=self.vram_capacity,
                safety_margin_bytes=vram_margin,
            ),
        )


class MosaicConfig(Contract):
    """Top-level Mosaic configuration."""

    schema_version: Literal[1] = 1
    paths: PathsConfig
    memory: MemoryConfig
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    @classmethod
    def load(cls, path: str | Path) -> MosaicConfig:
        """Load a TOML configuration file and resolve its paths."""
        config_path = Path(path).expanduser().resolve()
        try:
            text = config_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ConfigurationError(f"cannot read configuration {config_path}: {exc}") from exc
        try:
            raw = tomllib.loads(text)
        except tomllib.TOMLDecodeError as exc:
            raise ConfigurationError(f"invalid TOML in {config_path}: {exc}") from exc
        try:
            config = cls.model_validate(raw)
        except ValidationError as exc:
            raise ConfigurationError(f"invalid configuration {config_path}: {exc}") from exc
        return config.model_copy(update={"paths": config.paths.resolved(config_path.parent)})
