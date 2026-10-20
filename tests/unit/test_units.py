from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from mosaic.units import ByteSize, format_byte_size, parse_byte_size

_BYTE_SIZE_ADAPTER = TypeAdapter(ByteSize)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, 0),
        (1024, 1024),
        ("1 B", 1),
        ("1 KB", 1000),
        ("1 KiB", 1024),
        ("8 GiB", 8 * 1024**3),
        ("2 GB", 2 * 1000**3),
        ("  512 MiB  ", 512 * 1024**2),
        ("8gib", 8 * 1024**3),
    ],
)
def test_parse_byte_size(value: object, expected: int) -> None:
    assert parse_byte_size(value) == expected
    assert _BYTE_SIZE_ADAPTER.validate_python(value) == expected


@pytest.mark.parametrize("value", [-1, "-1 B", "1024", "8 XB", "8", 1.5, True])
def test_parse_byte_size_rejects_invalid_values(value: object) -> None:
    with pytest.raises(ValueError):
        parse_byte_size(value)
    with pytest.raises(ValidationError):
        _BYTE_SIZE_ADAPTER.validate_python(value)


@pytest.mark.parametrize(
    ("size_bytes", "expected"),
    [
        (0, "0 B"),
        (1024, "1 KiB"),
        (512 * 1024**2, "512 MiB"),
        (8 * 1024**3, "8 GiB"),
        (1500, "1500 B"),
    ],
)
def test_format_byte_size(size_bytes: int, expected: str) -> None:
    assert format_byte_size(size_bytes) == expected


def test_format_byte_size_round_trips_exact_units() -> None:
    assert format_byte_size(parse_byte_size("2 TiB")) == "2 TiB"


def test_format_byte_size_rejects_negative() -> None:
    with pytest.raises(ValueError):
        format_byte_size(-1)
