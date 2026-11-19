"""Helpers for resolving text and script direction."""

from __future__ import annotations

__all__ = ["is_vertical_script", "normalize_script_direction"]

_SUPPORTED_DIRECTIONS = {"ltr", "rtl", "ttb"}


def normalize_script_direction(value: str | None) -> str:
    """Normalize and validate a script direction value.

    Parameters
    ----------
    value : str or None
        Script direction from a lab configuration or metadata form. Missing
        values fall back to ``"ltr"``.

    Returns
    -------
    str
        One of ``"ltr"``, ``"rtl"`` or ``"ttb"``.

    Raises
    ------
    ValueError
        If the direction is unsupported.
    """
    if value is None or not str(value).strip():
        return "ltr"

    direction = str(value).strip().lower()
    if direction == "btt":
        raise ValueError(
            "script_direction 'btt' is not supported. Use 'ttb' for top-to-bottom text."
        )
    if direction not in _SUPPORTED_DIRECTIONS:
        raise ValueError(
            f"Unsupported script_direction {value!r}. "
            f"Supported values are: {sorted(_SUPPORTED_DIRECTIONS)}."
        )
    return direction


def is_vertical_script(value: str | None) -> bool:
    """Return whether a script direction describes vertical text."""
    return normalize_script_direction(value) == "ttb"
