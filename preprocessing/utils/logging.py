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
    log_file: Path | str | None = None, level: int = logging.INFO
) -> None:
    """Set up logging to console and optionally to a file.

    Parameters
    ----------
    log_file : Path | str, optional
        Path to the log file.
    level : int, optional
        Logging level (default logging.INFO).
    """
    handlers: list[logging.Handler] = [logging.StreamHandler()]

    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        # Use 'w' mode to overwrite/clear existing log file on start if desired,
        # but standard logging usually appends. Given open(..., 'w').close() was used before,
        # we might want to clear it once at the start of the collection.
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        level=level,
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
