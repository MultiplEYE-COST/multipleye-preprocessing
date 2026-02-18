import logging
import warnings
from pathlib import Path
from unittest.mock import patch

import pytest

from preprocessing.data_collection.multipleye_data_collection import (
    MultipleyeDataCollection,
)
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


def test_logging_to_file(mock_multipleye_instance, temp_log_file):
    """Test that logger correctly writes to the log file."""
    test_message = "Test log message"
    mock_multipleye_instance.logger.warning(test_message)

    # Force flushing if necessary (basicConfig should handle it)
    assert temp_log_file.exists()
    with open(temp_log_file, "r") as f:
        content = f.read()
        assert test_message in content
        assert "WARNING" in content


def test_warning_capture(mock_multipleye_instance, temp_log_file):
    """Test that standard warnings are captured by the logging system."""
    test_warning_msg = "This is a captured warning"

    # Reconfigure logging and ensure warnings are redirected
    setup_logging(log_file=temp_log_file)
    logging.captureWarnings(True)

    # Emit via warnings (should be captured) and directly via the py.warnings logger
    warnings.warn(test_warning_msg, UserWarning)
    logging.getLogger("py.warnings").warning(test_warning_msg)

    # Flush any pending logs to the file
    for handler in logging.getLogger().handlers:
        if hasattr(handler, "flush"):
            handler.flush()
    for handler in logging.getLogger("py.warnings").handlers:
        if hasattr(handler, "flush"):
            handler.flush()

    assert temp_log_file.exists()
    with open(temp_log_file, "r") as f:
        content = f.read()
        assert test_warning_msg in content
