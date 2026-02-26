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


def check_data_collection_exists(data_collection_name: str, data_root: Path) -> Path:
    """
    Checks if the data collection folder exists in the data directory.

    Parameters
    ----------
    data_collection_name : str
        The name of the data collection.
    data_root : Path
        The root directory for the data.

    Returns
    -------
    Path
        The path to the data collection folder.

    Raises
    ------
    FileNotFoundError
        If the data collection folder does not exist.
    """
    data_folder_path = data_root / data_collection_name

    if not data_folder_path.exists():
        raise FileNotFoundError(
            f"The data collection folder '{data_collection_name}' was not found in '{data_root}'.\n"
            f"Please check if 'data_collection_name' is correctly set in the config file "
            "and that the folder exists and is unzipped."
        )

    # Check if the folder is essentially empty or only contains log files
    contents = list(data_folder_path.glob("*"))
    # Filter out log files and hidden files
    meaningful_contents = [
        c
        for c in contents
        if c.name != "preprocessing_logs.txt" and not c.name.startswith(".")
    ]

    if not meaningful_contents:
        raise FileNotFoundError(
            f"The data collection folder '{data_collection_name}' exists but appears to be empty "
            "(or only contains log files).\n"
            "Please ensure the data collection is correctly unzipped and structured."
        )

    return data_folder_path
