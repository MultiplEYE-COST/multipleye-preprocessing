import logging
from unittest.mock import patch

import preprocessing.utils.logging as logging_utils


def test_setup_logging_version_levels():
    """Test that pipeline info is logged as INFO first, then DEBUG."""
    # Reset the initialisation flag for testing
    with (  # capture what's being logged to a custom handler or mock logger
        patch("preprocessing.utils.logging._logging_initialized", False),
        patch("preprocessing.utils.logging.logger.log") as mock_log,
    ):
        logging_utils.setup_logging()

        # Check if any call was INFO and contained "Pipeline version"
        info_calls = [
            call for call in mock_log.call_args_list if call[0][0] == logging.INFO
        ]
        assert any("Pipeline version" in call[0][1] for call in info_calls)

        mock_log.reset_mock()

        # Second call should be DEBUG
        logging_utils.setup_logging()

        debug_calls = [
            call for call in mock_log.call_args_list if call[0][0] == logging.DEBUG
        ]
        assert any("Pipeline version" in call[0][1] for call in debug_calls)
        assert not any(call[0][0] == logging.INFO for call in mock_log.call_args_list)


def test_setup_logging_respects_levels():
    """Test that setup_logging correctly sets the console level."""
    # Reset state
    with patch("preprocessing.utils.logging._logging_initialized", True):
        # Set to WARNING, should not show INFO/DEBUG
        logging_utils.setup_logging(console_level=logging.WARNING)

        # Check handler level
        found_console = False
        for handler in logging.getLogger().handlers:
            if isinstance(handler, logging.StreamHandler):
                assert handler.level == logging.WARNING
                found_console = True
        assert found_console
