"""Utilities for working with paths, session identifiers, and further data locations."""

import os
import yaml
from pathlib import Path
from preprocessing.config import settings


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

    if not is_valid_pid(pid):
        raise ValueError(
            f"PID must be exactly three digits (possibly zero-padded), got '{pid}' from '{folder}'."
        )

    return pid


def is_valid_pid(pid: str) -> bool:
    """
    Checks if a participant identifier (PID) is valid.

    A valid PID is exactly three digits (0-9), possibly zero-padded.

    Parameters
    ----------
    pid : str
        The identifier to check.

    Returns
    -------
    bool
        True if the identifier is exactly three digits, False otherwise.
    """
    return isinstance(pid, str) and len(pid) == 3 and pid.isdigit()


def is_valid_sid(sid: str) -> bool:
    """
    Checks if a session identifier (SID) is valid.

    A valid SID follows the format: {PID}_{LANG}_{COUNTRY}_{LAB}_{SESSION}
    Example: 002_ZH_CH_1_PT2

    Parameters
    ----------
    sid : str
        The identifier to check.

    Returns
    -------
    bool
        True if the identifier follows the SID format, False otherwise.
    """
    if not isinstance(sid, str):
        return False

    parts = sid.split("_")
    if len(parts) != 5:
        return False

    pid, lang, country, lab, session = parts

    # Validate PID (3 digits)
    if not is_valid_pid(pid):
        return False

    # Validate Language (2 uppercase letters)
    if len(lang) != 2 or not lang.isalpha() or not lang.isupper():
        return False

    # Validate Country (2 uppercase letters)
    if len(country) != 2 or not country.isalpha() or not country.isupper():
        return False

    # Lab and Session should be non-empty
    if not lab or not session:
        return False

    return True


def validate_psychometric_data(
    config_folder: Path,
    data_folder: Path,
    is_restructured: bool = False,
) -> dict[str, list[str]]:
    """
    Validates psychometric data against participant configuration YAMLs.

    This function checks if the expected data folders exist based on the configuration flags
    in the participant YAML files. It logs warnings for missing or unexpected data.

    Parameters
    ----------
    config_folder : Path
        The folder containing configuration files (.yaml) for the psychometric tests.
    data_folder : Path
        The folder containing test data. If is_restructured is True, this should be
        the folder with per-participant subdirectories.
    is_restructured : bool
        Whether the data is already restructured into per-participant folders.

    Returns
    -------
    dict[str, list[str]]
        A dictionary mapping participant IDs to a list of identified issues.
    """
    from .logging import get_logger

    logger = get_logger(__name__)

    issues = {}

    # Find config files
    config_files = list(config_folder.glob("*.yaml"))
    if not config_files:
        logger.warning(f"No configuration files ('*.yaml') found in {config_folder}.")
        return issues

    for config_file in config_files:
        name = config_file.stem
        participant_issues = []

        if not is_valid_sid(name):
            msg = f"Configuration file name is not SID-compliant: {config_file.name}."
            logger.warning(f"{msg} Attempting to process anyway.")
            participant_issues.append(msg)

        with open(config_file, "r") as f:
            try:
                config_data = yaml.safe_load(f)
            except yaml.YAMLError as exc:
                msg = f"Error reading configuration file {config_file}: {exc}"
                logger.error(msg)
                participant_issues.append(msg)
                issues[name] = participant_issues
                continue

        # Normalize name for the output folder if needed (S1/S2 -> PT1/PT2)
        target_name = name
        if target_name.endswith("S1"):
            target_name = target_name.replace("S1", "PT1")
        elif target_name.endswith("S2"):
            target_name = target_name.replace("S2", "PT2")

        for yaml_flag, folder_name in settings.PSYCHOMETRIC_TEST_MAPPING.items():
            expected = config_data.get(yaml_flag, False)

            if is_restructured:
                test_path = data_folder / target_name / folder_name
            else:
                test_path = data_folder / folder_name / name

            if expected is True:
                if not test_path.exists():
                    msg = (
                        f"!!! MISSING DATA !!!: Participant {name} is marked for {folder_name} "
                        f"in participant configuration ({config_file.name}), "
                        f"but the data folder does not exist at: {test_path}. "
                        "Please check the experimenter session documentation for any noteworthy points. "
                        "Note that if psychometric tests were restarted, the participant YAML configuration "
                        "might have been overwritten."
                    )
                    logger.warning(msg)
                    participant_issues.append(msg)
            else:
                if test_path.exists():
                    msg = (
                        f"Participant {name} has data for {folder_name}, "
                        f"but it is marked as False (or missing) in participant config ({config_file.name})."
                    )
                    if not is_restructured:
                        msg += " Copying anyway."
                    logger.warning(msg)
                    participant_issues.append(msg)

        if participant_issues:
            issues[name] = participant_issues

    return issues


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
