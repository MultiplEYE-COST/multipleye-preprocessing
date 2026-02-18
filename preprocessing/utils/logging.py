from __future__ import annotations

import logging
from pathlib import Path


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
