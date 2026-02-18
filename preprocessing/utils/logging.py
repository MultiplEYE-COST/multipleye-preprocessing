from __future__ import annotations

import logging
import subprocess
from importlib import metadata
from pathlib import Path

import pymovements as pm

from ..constants import CONSOLE_LOG_LEVEL, FILE_LOG_LEVEL, WARNINGS_CAPTURE_LEVEL

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
    console_level: int | None = None,
    file_level: int | None = None,
) -> None:
    """Set up logging to console and optionally to a file.

    Parameters
    ----------
    log_file : Path | str, optional
        Path to the log file.
    console_level : int, optional
        Logging level for console output (default logging.WARNING).
    file_level : int, optional
        Logging level for file output (default logging.INFO).
    """
    # Resolve defaults from constants if not provided
    resolved_console_level = (
        CONSOLE_LOG_LEVEL if console_level is None else console_level
    )
    resolved_file_level = FILE_LOG_LEVEL if file_level is None else file_level

    handlers: list[logging.Handler] = []

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(resolved_console_level)
    handlers.append(console_handler)

    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        # File handler
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(resolved_file_level)
        handlers.append(file_handler)

    logging.basicConfig(
        level=min(resolved_console_level, resolved_file_level)
        if log_file
        else resolved_console_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
        force=True,
    )

    # Capture warnings
    logging.captureWarnings(True)

    # Note: We use the package-level logger defined at module level
    logger.info("MultiplEYE preprocessing package loaded.")

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
    capture_handler.setLevel(WARNINGS_CAPTURE_LEVEL)
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
