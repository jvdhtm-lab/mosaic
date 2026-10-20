"""Byte-size parsing and formatting.

All memory quantities are represented internally as non-negative integers of
bytes. External configuration may use explicit units such as ``"512 MiB"``;
bare numbers are rejected so that a unit is never implicit.
"""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import BeforeValidator, Field

_BYTES_PER_UNIT: dict[str, int] = {
    "B": 1,
    "KB": 1000,
    "MB": 1000**2,
    "GB": 1000**3,
    "TB": 1000**4,
    "PB": 1000**5,
    "KIB": 1024,
    "MIB": 1024**2,
    "GIB": 1024**3,
    "TIB": 1024**4,
    "PIB": 1024**5,
}
_BYTE_SIZE_PATTERN = re.compile(r"^(?P<value>[0-9]+)\s*(?P<unit>[A-Za-z]+)$")
_SUPPORTED_UNITS = ", ".join(_BYTES_PER_UNIT)


def parse_byte_size(value: object) -> int:
    """Normalize an integer byte count or a unit-bearing string to bytes."""
    if isinstance(value, bool):
        raise ValueError("byte sizes must not be booleans")
    if isinstance(value, int):
        if value < 0:
            raise ValueError("byte sizes must be non-negative")
        return value
    if isinstance(value, str):
        match = _BYTE_SIZE_PATTERN.fullmatch(value.strip())
        if match is None:
            raise ValueError(
                f"invalid byte size {value!r}; use a value with an explicit unit such as '512 MiB'"
            )
        unit = match.group("unit").upper()
        if unit not in _BYTES_PER_UNIT:
            raise ValueError(
                f"unknown byte-size unit {match.group('unit')!r}; "
                f"expected one of: {_SUPPORTED_UNITS}"
            )
        return int(match.group("value")) * _BYTES_PER_UNIT[unit]
    raise ValueError(f"invalid byte size {value!r}; expected an integer or a string")


ByteSize = Annotated[int, BeforeValidator(parse_byte_size), Field(ge=0)]


def format_byte_size(size_bytes: int) -> str:
    """Format a byte count using an exact binary unit when one applies."""
    if size_bytes < 0:
        raise ValueError("byte sizes must be non-negative")
    for unit, factor in (
        ("PiB", _BYTES_PER_UNIT["PIB"]),
        ("TiB", _BYTES_PER_UNIT["TIB"]),
        ("GiB", _BYTES_PER_UNIT["GIB"]),
        ("MiB", _BYTES_PER_UNIT["MIB"]),
        ("KiB", _BYTES_PER_UNIT["KIB"]),
    ):
        if size_bytes >= factor and size_bytes % factor == 0:
            return f"{size_bytes // factor} {unit}"
    return f"{size_bytes} B"
