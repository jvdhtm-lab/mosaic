from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import mosaic
from mosaic.config import MosaicConfig

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_package_imports_without_loading_a_ml_framework() -> None:
    assert mosaic.__version__ == "0.1.0"
    assert "torch" not in sys.modules
    assert "transformers" not in sys.modules


def test_shipped_default_config_is_valid() -> None:
    config = MosaicConfig.load(REPO_ROOT / "configs" / "default.toml")

    assert config.memory.ram_capacity == 16 * 1024**3
    assert config.memory.vram_capacity == 0
    assert config.paths.data_dir == (REPO_ROOT / "data").resolve()


def test_module_entry_point_validates_configuration() -> None:
    config_path = REPO_ROOT / "configs" / "default.toml"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mosaic",
            "config",
            "validate",
            "--config",
            str(config_path),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Configuration valid:" in result.stdout
    assert result.stderr == ""
