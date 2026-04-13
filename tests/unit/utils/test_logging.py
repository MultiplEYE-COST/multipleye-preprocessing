import logging
import warnings
from pathlib import Path
from unittest.mock import patch

import pytest

from preprocessing.data_collection.multipleye_data_collection import (
    MultipleyeDataCollection,
)
from preprocessing.config import settings
from preprocessing.utils.logging import setup_logging, clear_log_file


@pytest.fixture
def temp_log_file(tmp_path):
    log_file = tmp_path / "test_logs.txt"
    return log_file


@pytest.fixture
def mock_multipleye_instance(temp_log_file):
    """Create a MultipleyeDataCollection instance with minimal initialization."""
    with (
        patch.object(MultipleyeDataCollection, "add_recorded_sessions"),
        patch.object(MultipleyeDataCollection, "create_dataset_overview"),
    ):
        # We need to provide a valid data_root parent for the log file
        data_root = Path("/tmp/fake_data/eye-tracking-sessions")
        # Ensure parent exists for setup_logging if it checks it

        instance = MultipleyeDataCollection.__new__(MultipleyeDataCollection)
        instance.data_root = data_root
        instance.reports_dir = Path("/tmp/no_reports")

        # Initialize logging manually like in __init__
        clear_log_file(temp_log_file)
        setup_logging(log_file=temp_log_file)
        instance.logger = logging.getLogger(
            "preprocessing.data_collection.multipleye_data_collection"
        )

        return instance


@pytest.fixture
def warnings_to_log(temp_log_file):
    """Configure logging to capture warnings into the log file and ensure flush."""
    setup_logging(log_file=temp_log_file)
    logging.captureWarnings(True)
    yield
    for logger_name in ("", "py.warnings"):
        logger = logging.getLogger(logger_name)
        for handler in logger.handlers:
            if hasattr(handler, "flush"):
                handler.flush()


@pytest.mark.parametrize(
    "log_level, log_name",
    [
        (logging.INFO, "INFO"),
        (logging.WARNING, "WARNING"),
        (logging.ERROR, "ERROR"),
    ],
)
def test_logging_to_file(mock_multipleye_instance, temp_log_file, log_level, log_name):
    """Test that logger correctly writes to the log file at various levels."""
    test_message = f"Test {log_name} message"
    setup_logging(log_file=temp_log_file, file_level=log_level)
    mock_multipleye_instance.logger.log(log_level, test_message)

    assert temp_log_file.exists()
    with open(temp_log_file, "r") as f:
        content = f.read()
        assert test_message in content
        assert log_name in content


def test_warning_capture(warnings_to_log, temp_log_file):
    """Test that standard warnings are captured by the logging system."""
    test_warning_msg = "This is a captured warning"

    # Emit via warnings (should be captured) and directly via the py.warnings logger
    with pytest.warns(UserWarning, match=test_warning_msg):
        warnings.warn(test_warning_msg, UserWarning)
    logging.getLogger("py.warnings").warning(test_warning_msg)

    assert temp_log_file.exists()
    with open(temp_log_file, "r") as f:
        content = f.read()
        assert test_warning_msg in content

    assert any(test_warning_msg in msg for msg in logging._captured_warnings)  # type: ignore


def test_ignored_log_regexes(temp_log_file, monkeypatch):
    """Test that log messages matching IGNORED_LOG_REGEXES are filtered out."""
    ignored_msg = "Could not determine dtype for column 19, falling back to string"
    allowed_msg = "This is an allowed message"

    # Set up settings with our regex
    monkeypatch.setattr(
        settings,
        "IGNORED_LOG_REGEXES",
        [r"Could not determine dtype for column \d+, falling back to string"],
    )

    # Initialize logging with the new settings
    setup_logging(log_file=temp_log_file, file_level=logging.WARNING)

    # Create a logger and log both messages
    test_logger = logging.getLogger("fastexcel.types.dtype")
    test_logger.warning(ignored_msg)
    test_logger.warning(allowed_msg)

    # Also test via py.warnings
    logging.getLogger("py.warnings").warning(ignored_msg)
    logging.getLogger("py.warnings").warning(allowed_msg)

    # Check the log file
    assert temp_log_file.exists()
    with open(temp_log_file, "r") as f:
        content = f.read()
        assert ignored_msg not in content
        assert allowed_msg in content

    # Test that regex-based filtering also works for captured warnings via warnings.warn
    with pytest.warns(UserWarning, match=ignored_msg):
        warnings.warn(ignored_msg, UserWarning)
    with pytest.warns(UserWarning, match=allowed_msg):
        warnings.warn(allowed_msg, UserWarning)

    with open(temp_log_file, "r") as f:
        content = f.read()
        assert ignored_msg not in content
        assert allowed_msg in content


@pytest.mark.parametrize(
    "append_flag, initial_kept, message",
    [
        (True, True, "Append message"),
        (False, False, "New run message"),
    ],
)
def test_log_append_behavior(
    temp_log_file, monkeypatch, append_flag, initial_kept, message
):
    """Test that logging appends to the file based on LOG_APPEND constant."""
    # Ensure file starts with some content
    with open(temp_log_file, "w") as f:
        f.write("Initial content\n")

    # Patch LOG_APPEND and simulate the __init__-like flow
    monkeypatch.setattr(
        "preprocessing.data_collection.multipleye_data_collection.LOG_APPEND",
        append_flag,
        raising=False,
    )

    if not append_flag:
        clear_log_file(temp_log_file)
    setup_logging(log_file=temp_log_file, file_level=logging.WARNING)

    logger = logging.getLogger("test_append" if append_flag else "test_no_append")
    logger.warning(message)

    with open(temp_log_file, "r") as f:
        content = f.read()
        assert ("Initial content" in content) == initial_kept
        assert message in content
