"""Pipeline for MultiplEYE data preprocessing"""

from .constants import CONSOLE_LOG_LEVEL, DATASET_DIR, FILE_LOG_LEVEL, LOG_APPEND
from .utils.logging import clear_log_file, setup_logging

# Initialise logging for the entire package upon import
log_file = DATASET_DIR / "preprocessing_logs.txt"

if not LOG_APPEND:
    clear_log_file(log_file)

setup_logging(
    log_file=log_file,
    console_level=CONSOLE_LOG_LEVEL,
    file_level=FILE_LOG_LEVEL,
)

from .api import *  # noqa: F403, E402 # Brings all functions from API into the top-level preprocessing namespace

# Functionality made available with absolute imports
from .api import __all__ as _api_all  # noqa: E402
from .data_collection import __all__ as _data_collection_all  # noqa: E402
from .utils import __all__ as _utils_all  # noqa: E402

__all__ = list(set(_api_all + _data_collection_all + _utils_all))
