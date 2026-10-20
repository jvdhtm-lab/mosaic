"""Mosaic command-line interface."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from mosaic import __version__
from mosaic.config import MosaicConfig
from mosaic.errors import ConfigurationError
from mosaic.units import format_byte_size


def _default_config_path() -> Path:
    override = os.environ.get("MOSAIC_CONFIG")
    return Path(override) if override else Path("configs/default.toml")


def build_parser() -> argparse.ArgumentParser:
    """Build the Mosaic argument parser."""
    parser = argparse.ArgumentParser(prog="mosaic", description="Mosaic component controller")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    config_parser = commands.add_parser("config", help="inspect and validate configuration")
    config_commands = config_parser.add_subparsers(dest="config_command", required=True)
    validate_parser = config_commands.add_parser("validate", help="validate a TOML configuration")
    validate_parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="path to a TOML configuration (default: configs/default.toml or $MOSAIC_CONFIG)",
    )
    return parser


def _validate_config(config_path: Path | None) -> int:
    path = config_path or _default_config_path()
    try:
        config = MosaicConfig.load(path)
    except ConfigurationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Configuration valid: {Path(path).expanduser().resolve()}")
    print(f"RAM capacity: {format_byte_size(config.memory.ram_capacity)}")
    print(f"VRAM capacity: {format_byte_size(config.memory.vram_capacity)}")
    print(f"Safety margin: {format_byte_size(config.memory.safety_margin)}")
    print(f"Data directory: {config.paths.data_dir}")
    print(f"Traces directory: {config.paths.traces_dir}")
    print(f"Artifacts directory: {config.paths.artifacts_dir}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Mosaic command-line interface."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "config" and args.config_command == "validate":
        return _validate_config(args.config)
    parser.print_usage(sys.stderr)
    return 2
