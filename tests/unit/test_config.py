from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from mosaic.config import MosaicConfig
from mosaic.errors import ConfigurationError
from mosaic.logging import LogFormat

VALID_CONFIG = """
schema_version = 1

[paths]
data_dir = "../data"
traces_dir = "../data/traces"
artifacts_dir = "../artifacts"

[memory]
ram_capacity = "8 GiB"
vram_capacity = "4 GiB"
safety_margin = "512 MiB"

[logging]
level = "DEBUG"
format = "json"
"""


def write_config(tmp_path: Path, body: str) -> Path:
    config_dir = tmp_path / "configs"
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / "mosaic.toml"
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


def test_loads_valid_config_and_resolves_paths(tmp_path: Path) -> None:
    path = write_config(tmp_path, VALID_CONFIG)

    config = MosaicConfig.load(path)

    assert config.paths.data_dir == (tmp_path / "data").resolve()
    assert config.paths.traces_dir == (tmp_path / "data" / "traces").resolve()
    assert config.paths.artifacts_dir == (tmp_path / "artifacts").resolve()
    assert config.memory.ram_capacity == 8 * 1024**3
    assert config.memory.vram_capacity == 4 * 1024**3
    assert config.memory.safety_margin == 512 * 1024**2
    assert config.logging.level == "DEBUG"
    assert config.logging.format is LogFormat.JSON


def test_converts_config_to_memory_budget(tmp_path: Path) -> None:
    config = MosaicConfig.load(write_config(tmp_path, VALID_CONFIG))

    budget = config.memory.to_budget()

    assert budget.ram.capacity_bytes == 8 * 1024**3
    assert budget.ram.effective_capacity_bytes == 8 * 1024**3 - 512 * 1024**2
    assert budget.vram.capacity_bytes == 4 * 1024**3
    assert budget.vram.effective_capacity_bytes == 4 * 1024**3 - 512 * 1024**2


def test_defaults_are_applied(tmp_path: Path) -> None:
    path = write_config(
        tmp_path,
        """
        [paths]
        data_dir = "data"
        traces_dir = "data/traces"
        artifacts_dir = "artifacts"

        [memory]
        ram_capacity = "1 GiB"
        """,
    )

    config = MosaicConfig.load(path)

    assert config.memory.vram_capacity == 0
    assert config.memory.safety_margin == 0
    assert config.logging.level == "INFO"
    assert config.logging.format is LogFormat.TEXT
    assert config.memory.to_budget().vram.safety_margin_bytes == 0


def test_vram_margin_is_ignored_when_vram_is_disabled(tmp_path: Path) -> None:
    path = write_config(
        tmp_path,
        """
        [paths]
        data_dir = "data"
        traces_dir = "data/traces"
        artifacts_dir = "artifacts"

        [memory]
        ram_capacity = "1 GiB"
        safety_margin = "256 MiB"
        """,
    )

    budget = MosaicConfig.load(path).memory.to_budget()

    assert budget.ram.safety_margin_bytes == 256 * 1024**2
    assert budget.vram.safety_margin_bytes == 0


def test_rejects_margin_larger_than_ram(tmp_path: Path) -> None:
    path = write_config(
        tmp_path,
        """
        [paths]
        data_dir = "data"
        traces_dir = "data/traces"
        artifacts_dir = "artifacts"

        [memory]
        ram_capacity = "1 GiB"
        safety_margin = "2 GiB"
        """,
    )

    with pytest.raises(ConfigurationError, match="safety_margin"):
        MosaicConfig.load(path)


def test_rejects_margin_larger_than_vram(tmp_path: Path) -> None:
    path = write_config(
        tmp_path,
        """
        [paths]
        data_dir = "data"
        traces_dir = "data/traces"
        artifacts_dir = "artifacts"

        [memory]
        ram_capacity = "8 GiB"
        vram_capacity = "1 GiB"
        safety_margin = "2 GiB"
        """,
    )

    with pytest.raises(ConfigurationError, match="vram_capacity"):
        MosaicConfig.load(path)


def test_rejects_zero_ram_capacity(tmp_path: Path) -> None:
    path = write_config(
        tmp_path,
        """
        [paths]
        data_dir = "data"
        traces_dir = "data/traces"
        artifacts_dir = "artifacts"

        [memory]
        ram_capacity = "0 B"
        """,
    )

    with pytest.raises(ConfigurationError, match="ram_capacity"):
        MosaicConfig.load(path)


@pytest.mark.parametrize(
    "body",
    [
        """
        [paths]
        data_dir = "data"
        traces_dir = "data/traces"
        artifacts_dir = "artifacts"

        [memory]
        ram_capacity = "8 XB"
        """,
        """
        [paths]
        data_dir = "data"
        traces_dir = "data/traces"
        artifacts_dir = "artifacts"

        [memory]
        ram_capacity = "8"
        """,
        """
        [paths]
        data_dir = "data"
        traces_dir = "data/traces"
        artifacts_dir = "artifacts"

        [memory]
        ram_capacity = -1
        """,
        """
        [paths]
        data_dir = ""
        traces_dir = "data/traces"
        artifacts_dir = "artifacts"

        [memory]
        ram_capacity = "1 GiB"
        """,
        """
        [paths]
        data_dir = "data"
        traces_dir = "data/traces"
        artifacts_dir = "artifacts"

        [memory]
        ram_capacity = "1 GiB"

        [logging]
        level = "VERBOSE"
        """,
    ],
)
def test_rejects_invalid_values(tmp_path: Path, body: str) -> None:
    path = write_config(tmp_path, body)

    with pytest.raises(ConfigurationError):
        MosaicConfig.load(path)


def test_rejects_unknown_keys(tmp_path: Path) -> None:
    path = write_config(
        tmp_path,
        """
        [paths]
        data_dir = "data"
        traces_dir = "data/traces"
        artifacts_dir = "artifacts"

        [memory]
        ram_capacity = "1 GiB"
        unexpected = true
        """,
    )

    with pytest.raises(ConfigurationError, match="unexpected"):
        MosaicConfig.load(path)


def test_rejects_malformed_toml(tmp_path: Path) -> None:
    path = write_config(tmp_path, "[paths\n")

    with pytest.raises(ConfigurationError, match="invalid TOML"):
        MosaicConfig.load(path)


def test_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="cannot read"):
        MosaicConfig.load(tmp_path / "missing.toml")
