from __future__ import annotations

import json
import logging
import sys

import pytest

from mosaic.logging import JsonFormatter, LogFormat, configure_logging


def test_json_formatter_includes_structured_fields() -> None:
    record = logging.LogRecord(
        name="mosaic.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="loaded %s",
        args=("expert.0",),
        exc_info=None,
    )
    record.event = "component_loaded"
    record.trace_id = "trace-1"

    payload = json.loads(JsonFormatter().format(record))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "mosaic.test"
    assert payload["message"] == "loaded expert.0"
    assert payload["event"] == "component_loaded"
    assert payload["trace_id"] == "trace-1"
    assert "timestamp" in payload
    assert "args" not in payload
    assert "msg" not in payload


def test_json_formatter_serializes_exceptions() -> None:
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="mosaic.test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=20,
        msg="failed",
        args=(),
        exc_info=exc_info,
    )

    payload = json.loads(JsonFormatter().format(record))

    assert "RuntimeError: boom" in payload["exception"]


def test_configure_logging_emits_json(capsys: pytest.CaptureFixture[str]) -> None:
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    try:
        configure_logging("DEBUG", LogFormat.JSON)
        logging.getLogger("mosaic.test").info("hello", extra={"event": "started"})
    finally:
        root.handlers = original_handlers
        root.setLevel(original_level)

    payload = json.loads(capsys.readouterr().err)
    assert payload["message"] == "hello"
    assert payload["event"] == "started"


def test_configure_logging_rejects_unknown_level() -> None:
    with pytest.raises(ValueError, match="unsupported log level"):
        configure_logging("VERBOSE")
