"""Utilities for working with paths, session identifiers, and further data locations."""

import os
from pathlib import Path


def pid_from_session(folder: Path | str) -> str:
    """
    Extracts a participant identifier (PID) from a session folder or identifier.

    This function takes a folder represented as a `Path` object or a string and
    extracts the first three characters of its stem
    (the folder's name without its suffix).
    The function returns this substring, which can be used as a participant identifier.

    The PID must be exactly three digits (0-9), possibly zero-padded (e.g., "001", "042", "123").

    Parameters
    ----------
    folder : Path | str
        The path to the folder whose stem is used to extract the participant identifier.
        If given as a string, it must be a simple session identifier without path separators.

    Returns
    -------
    str
        The participant identifier.
        A string of exactly three digits extracted from the folder's stem.

    Raises
    ------
    ValueError
        If the extracted PID is not exactly three digits,
        or if a string contains path separators.
    TypeError
        If the provided folder is neither a Path nor a string.
    """
    if isinstance(folder, Path):
        folder = folder.stem
    elif not isinstance(folder, str):
        raise TypeError("folder must be of type Path or str.")
    else:
        # Validate that string does not contain any OS-specific path separators
        separators = [os.sep]
        if os.altsep is not None:
            separators.append(os.altsep)

        if any(sep in folder for sep in separators):
            raise ValueError(
                f"String input must be a simple session identifier without path separators, got '{folder}'."
            )

    pid = folder[:3]

    if len(pid) != 3 or not pid.isdigit():
        raise ValueError(
            f"PID must be exactly three digits (possibly zero-padded), got '{pid}' from '{folder}'."
        )

    return pid
