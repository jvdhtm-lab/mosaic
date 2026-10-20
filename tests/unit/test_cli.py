from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from mosaic.cli.main import main

VALID_CONFIG = """
schema_version = 1

[paths]
data_dir = "data"
traces_dir = "data/traces"
artifacts_dir = "artifacts"

[memory]
ram_capacity = "16 GiB"
vram_capacity = "0 B"
safety_margin = "512 MiB"
"""


def write_config(tmp_path: Path, body: str = VALID_CONFIG) -> Path:
    path = tmp_path / "mosaic.toml"
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


def test_validate_command_succeeds(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = write_config(tmp_path)

    assert main(["config", "validate", "--config", str(path)]) == 0

    output = capsys.readouterr().out
    assert "Configuration valid:" in output
    assert "RAM capacity: 16 GiB" in output
    assert "VRAM capacity: 0 B" in output
    assert f"Data directory: {(tmp_path / 'data').resolve()}" in output


def test_validate_command_reports_invalid_config(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
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

    assert main(["config", "validate", "--config", str(path)]) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "error:" in captured.err
    assert "safety_margin" in captured.err


def test_validate_command_reads_environment_override(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = write_config(tmp_path)
    monkeypatch.setenv("MOSAIC_CONFIG", str(path))

    assert main(["config", "validate"]) == 0

    assert "Configuration valid:" in capsys.readouterr().out


def test_validate_command_reports_missing_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["config", "validate", "--config", str(tmp_path / "missing.toml")]) == 1

    assert "cannot read configuration" in capsys.readouterr().err


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])

    assert exit_info.value.code == 0
    assert "mosaic 0.1.0" in capsys.readouterr().out
