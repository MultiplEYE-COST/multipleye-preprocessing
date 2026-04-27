"""Utilities for working with paths, session identifiers, and further data locations."""

import yaml
from pathlib import Path
from ..models.sid import Sid
from preprocessing.config import settings


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
        config_sid_str = config_file.stem
        participant_issues = []

        try:
            config_sid = Sid(config_sid_str)
        except (ValueError, TypeError):
            msg = f"Configuration file name is not SID-compliant: {config_file.name}."
            logger.warning(f"{msg} Attempting to process anyway.")
            participant_issues.append(msg)
            config_sid = None

        with open(config_file, "r") as f:
            try:
                config_data = yaml.safe_load(f)
            except yaml.YAMLError as exc:
                msg = f"Error reading configuration file {config_file}: {exc}"
                logger.error(msg)
                participant_issues.append(msg)
                issues[config_sid_str] = participant_issues
                continue

        # Find matching data folder
        matched_folder_name = config_sid_str
        if config_sid and is_restructured:
            # Try to find a folder that soft-matches the config SID
            actual_folders = [p.name for p in data_folder.iterdir() if p.is_dir()]
            for folder_name in actual_folders:
                try:
                    folder_sid = Sid(folder_name)
                    if config_sid.equals_soft(folder_sid):
                        matched_folder_name = folder_name
                        break
                except (ValueError, TypeError):
                    continue

        for yaml_flag, folder_name in settings.PSYCHOMETRIC_TEST_MAPPING.items():
            expected = config_data.get(yaml_flag, False)

            if is_restructured:
                test_path = data_folder / matched_folder_name / folder_name
            else:
                test_path = data_folder / folder_name / config_sid_str

            if expected is True:
                if not test_path.exists():
                    msg = (
                        f"!!! MISSING DATA !!!: Participant {config_sid_str} is marked for {folder_name} "
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
                        f"Participant {config_sid_str} has data for {folder_name}, "
                        f"but it is marked as False (or missing) in participant config ({config_file.name})."
                    )
                    if not is_restructured:
                        msg += " Copying anyway."
                    logger.warning(msg)
                    participant_issues.append(msg)

        if participant_issues:
            issues[config_sid_str] = participant_issues

    return issues


def check_data_collection_exists(data_collection_name: str, data_root: Path) -> Path:
    """
    Checks if the data collection folder exists and contains meaningful data.

    Parameters
    ----------
    data_collection_name : str
        The name of the data collection subdirectory.
    data_root : Path
        The root directory where the data collection should be located.

    Returns
    -------
    Path
        The absolute path to the data collection folder.

    Raises
    ------
    FileNotFoundError
        If the folder does not exist or if it contains no meaningful files
        (excluding logs and hidden files).
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
