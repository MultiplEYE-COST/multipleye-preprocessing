from __future__ import annotations

from ..config import settings
import logging
import re
import subprocess
from importlib import metadata
from pathlib import Path

import pymovements as pm

logger = logging.getLogger("preprocessing")


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a logger.

    If ``name`` is provided, returns a named logger so that records include the
    fully-qualified module path (e.g. "preprocessing.data_collection.stimulus").
    Otherwise, returns the package base logger "preprocessing".
    """
    return logging.getLogger(name if name else "preprocessing")


def get_pipeline_info() -> tuple[str, str]:
    """Get the pipeline version and last update date.

    Returns
    -------
    tuple[str, str]
        Pipeline version and last update date.
    """
    version = "unknown"
    try:
        version = metadata.version("MultiplEYE-preprocessing")
    except metadata.PackageNotFoundError:
        # Fallback to pyproject.toml if not installed
        pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
        if pyproject_path.exists():
            with open(pyproject_path, encoding="utf-8") as f:
                for line in f:
                    if line.startswith("version ="):
                        version = line.split("=")[1].strip().strip('"')
                        break

    last_update = "unknown"
    try:
        # Try to get git tag/commit and date
        repo_path = Path(__file__).parent.parent.parent
        git_info = subprocess.check_output(
            ["git", "-C", str(repo_path), "describe", "--tags", "--always"],
            stderr=subprocess.STDOUT,
            text=True,
        ).strip()
        git_date = subprocess.check_output(
            ["git", "-C", str(repo_path), "log", "-1", "--format=%ci"],
            stderr=subprocess.STDOUT,
            text=True,
        ).strip()
        last_update = f"{git_info} ({git_date})"
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    return version, last_update


def setup_logging(
    log_file: Path | str | None = None,
    console_level: int | str | None = None,
    file_level: int | str | None = None,
) -> None:
    """Set up logging to console and optionally to a file.

    Parameters
    ----------
    log_file : Path | str, optional
        Path to the log file.
    console_level : int | str, optional
        Logging level for console output (default logging.WARNING).
    file_level : int | str, optional
        Logging level for file output (default logging.INFO).
    """
    # Resolve defaults from constants if not provided
    resolved_console_level = (
        settings.CONSOLE_LOG_LEVEL if console_level is None else console_level
    )
    resolved_file_level = settings.FILE_LOG_LEVEL if file_level is None else file_level

    # Ensure both levels are integers for comparison
    if isinstance(resolved_console_level, str):
        resolved_console_level = logging.getLevelName(resolved_console_level.upper())
    if isinstance(resolved_file_level, str):
        resolved_file_level = logging.getLevelName(resolved_file_level.upper())

    # --- Formatter definitions ---
    base_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # ANSI colors (only for console)
    RESET = "\033[0m"
    COLORS = {
        logging.DEBUG: "\033[36m",  # Cyan
        logging.INFO: "\033[37m",  # Light gray
        logging.WARNING: "\033[33m",  # Yellow
        logging.ERROR: "\033[31m",  # Red
        logging.CRITICAL: "\033[1;41m",  # Bold on red background
    }

    class ShortPathFormatter(logging.Formatter):
        """Formatter that shortens absolute paths in the message to project-relative ones."""

        def format(self, record: logging.LogRecord) -> str:
            if record.name == "py.warnings":
                # Shorten full paths to project-relative paths or filename
                msg = record.getMessage()
                project_root = str(Path(__file__).parent.parent.parent)
                if project_root in msg:
                    msg = msg.replace(project_root, "").lstrip("/")

                # Remove trailing warnings.warn(...) and newline
                if "\n  warnings.warn(" in msg:
                    msg = msg.split("\n  warnings.warn(")[0]

                record.msg = msg
            return super().format(record)

    class ColorFormatter(ShortPathFormatter):
        def format(self, record: logging.LogRecord) -> str:
            color = COLORS.get(record.levelno, "")
            # Emphasise captured warnings specifically
            if record.name == "py.warnings":
                # Magenta for warnings redirected from warnings module
                color = "\033[35m"
                record.levelname = f"PYWARN:{record.levelname}"
            msg = super().format(record)
            # Only colorise if stream is a TTY (most notebooks and terminals support ANSI)
            return f"{color}{msg}{RESET}" if color else msg

    handlers: list[logging.Handler] = []

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(resolved_console_level)
    console_handler.setFormatter(ColorFormatter(base_format))
    handlers.append(console_handler)

    # File handler (plain formatter with short paths)
    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(resolved_file_level)
        file_handler.setFormatter(ShortPathFormatter(base_format))
        handlers.append(file_handler)

    logging.basicConfig(
        level=min(resolved_console_level, resolved_file_level)
        if log_file
        else resolved_console_level,
        handlers=handlers,
        force=True,
    )

    # Capture warnings
    logging.captureWarnings(True)

    # Note: We use the package-level logger defined at module level
    logger.info("MultiplEYE preprocessing package loaded.")

    # Add regex filter to root logger and py.warnings logger
    class RegexFilter(logging.Filter):
        def __init__(self, patterns: list[str]):
            super().__init__()
            self.patterns = [re.compile(p) for p in patterns]

        def filter(self, record: logging.LogRecord) -> bool:
            msg = record.getMessage()
            for pattern in self.patterns:
                if pattern.search(msg):
                    return False
            return True

    if hasattr(settings, "IGNORED_LOG_REGEXES") and settings.IGNORED_LOG_REGEXES:
        regex_filter = RegexFilter(settings.IGNORED_LOG_REGEXES)
        logging.getLogger().addFilter(regex_filter)
        for handler in logging.getLogger().handlers:
            handler.addFilter(regex_filter)
        # Also ensure the filter is on the py.warnings logger
        # which might have its own handlers or be attached to root
        warn_logger = logging.getLogger("py.warnings")
        warn_logger.addFilter(regex_filter)
        for handler in warn_logger.handlers:
            handler.addFilter(regex_filter)

    # Log versions
    pipeline_version, last_update = get_pipeline_info()
    logger.info(f"Pipeline version: {pipeline_version}")
    logger.info(f"Last updated (git): {last_update}")
    logger.info(f"pymovements version: {pm.__version__}")

    # Initialise a list to store warnings for the summary report
    if not hasattr(logging, "_captured_warnings"):
        logging._captured_warnings = []  # type: ignore

    class WarningCaptureHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            if record.name == "py.warnings":
                logging._captured_warnings.append(record.getMessage())  # type: ignore

    capture_handler = WarningCaptureHandler()
    capture_handler.setLevel(settings.WARNINGS_CAPTURE_LEVEL)
    logging.getLogger("py.warnings").addHandler(capture_handler)


def clear_log_file(log_file: Path | str) -> None:
    """Clear the contents of the log file.

    Parameters
    ----------
    log_file : Path | str
        Path to the log file to clear.
    """
    log_file = Path(log_file)
    if log_file.exists():
        open(log_file, "w", encoding="utf-8").close()
