from __future__ import annotations

import logging
import subprocess
from importlib import metadata
from pathlib import Path

import pymovements as pm


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
    console_level: int = logging.WARNING,
    file_level: int = logging.INFO,
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
    handlers: list[logging.Handler] = []

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    handlers.append(console_handler)

    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        # File handler
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(file_level)
        handlers.append(file_handler)

    logging.basicConfig(
        level=min(console_level, file_level) if log_file else console_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
        force=True,
    )

    # Capture warnings
    logging.captureWarnings(True)

    logger = logging.getLogger(__name__)
    logger.info("MultiplEYE preprocessing package loaded.")

    # Log versions
    pipeline_version, last_update = get_pipeline_info()
    logger.info(f"Pipeline version: {pipeline_version}")
    logger.info(f"Last updated (git): {last_update}")
    logger.info(f"pymovements version: {pm.__version__}")

    # Optional: specialised filter/formatter for specific warnings if needed
    # For now, captureWarnings(True) will redirect all warnings to a logger named 'py.warnings'


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
