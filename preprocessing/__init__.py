"""Pipeline for MultiplEYE data preprocessing"""

from .config import settings
from .utils.logging import clear_log_file, setup_logging

# Initialise logging for the entire package upon import
try:
    # We use a default log file path if possible, but we don't trigger settings.load()
    # via property access if it would cause issues.
    # DATASET_DIR access might trigger _ensure_loaded()
    # Since load() is now silent, it's safer, but we still want to be careful.

    # Check if config was already found or if we should skip triggering load
    if not hasattr(settings, "_config_found") or not settings._config_found:
        log_file = None
    else:
        log_file = settings.DATASET_DIR / "preprocessing_logs.txt"
        if not settings.DATASET_DIR.exists():
            log_file = None
        elif not settings.APPEND_LOGS:
            clear_log_file(log_file)
except (ValueError, AttributeError):
    log_file = None

setup_logging(
    log_file=log_file,
    console_level=settings.CONSOLE_LOG_LEVEL,
    file_level=settings.FILE_LOG_LEVEL,
)

from .api import *  # noqa: F403, E402 # Brings all functions from API into the top-level preprocessing namespace

# Functionality made available with absolute imports
from .api import __all__ as _api_all  # noqa: E402
from .data_collection import __all__ as _data_collection_all  # noqa: E402
from .utils import __all__ as _utils_all  # noqa: E402

__all__ = list(set(_api_all + _data_collection_all + _utils_all)) + ["settings"]
