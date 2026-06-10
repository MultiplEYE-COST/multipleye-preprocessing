"""Conversion utilities."""


def convert_to_time_str(duration_ms: float | int) -> str:
    """Convert a duration in milliseconds to a string in the format HH:MM:SS.

    Parameters
    ----------
    duration_ms : float | int
        Duration in milliseconds.

    Returns
    -------
    str
        Time string in the format HH:MM:SS.

    Raises
    ------
    ValueError
        If duration_ms is >= 86,400,000 (24 hours or more), negative, or not a number.
    """
    if not isinstance(duration_ms, (int, float)):
        raise ValueError(f"Duration must be a number: {duration_ms}")
    if duration_ms < 0:
        raise ValueError(f"Duration cannot be negative: {duration_ms}")
    if duration_ms >= 86400000:
        raise ValueError(
            f"Duration overflow: {duration_ms}ms exceeds 24 hours (86400000ms)"
        )

    seconds = int(duration_ms / 1000) % 60
    minutes = int(duration_ms / (1000 * 60)) % 60
    hours = int(duration_ms / (1000 * 60 * 60)) % 24

    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
