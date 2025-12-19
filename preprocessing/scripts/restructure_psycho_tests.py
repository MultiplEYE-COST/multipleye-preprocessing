"""Utility script to restructure psychometric tests data folders."""
import argparse
import shutil
from pathlib import Path

from preprocessing.config import PSYM_PARTICIPANT_CONFIGS, PSYM_CORE_DATA, PSYCHOMETRIC_TESTS_DIR


def fix_psycho_tests_structure(
        config_folder: Path = PSYM_PARTICIPANT_CONFIGS,
        data_folder: Path = PSYM_CORE_DATA,
        out_folder: Path = PSYCHOMETRIC_TESTS_DIR,
):
    """
    Restructures psychometric tests data into per-participant folders.

    This function processes configuration files in the `config_folder` and data directories within
    `data_folder`.
    It identifies tests, organises each participant's test data based on the configuration,
    and relocates data to a per-participant directory format in the `out_folder`.

    Parameters
    ----------
    config_folder : Path
        The folder containing configuration files (.yaml) for the psychometric tests.
        (default: config.PSYM_PARTICIPANT_CONFIGS)
    data_folder : Path
        The folder containing raw test data for participants.
        The data is assumed to be structured with subfolders for each test type.
        (default: config.PSYM_CORE_DATA)
    out_folder : Path
        Session folder where the restructured data / user folders will be saved.
        If not provided, defaults to the folder specified in the config.
        (default: config.PSYCHOMETRIC_TESTS_DIR)

    Notes
    -----
    1. The function identifies participants and their corresponding session data based on the file
       naming convention in the `config_folder`.
    2. Configurations ending with specific session markers ('S1', 'S2')
       are transformed into specific folder names ('PT1', 'PT2') to create session directories.
    3. Any missing tests for a participant are logged to the console.

    Raises
    ------
    TypeError:
        If `config_folder`, `data_folder`, or `out_folder` are not of type `Path`.
    FileNotFoundError:
        If `config_folder` or `data_folder` do not exist.
    """

    # Check that the folders are of type Path
    if not isinstance(config_folder, Path):
        raise TypeError("config_folder must be of type Path.")
    if not isinstance(data_folder, Path):
        raise TypeError("data_folder must be of type Path.")
    if not isinstance(out_folder, Path):
        raise TypeError("out_folder must be of type Path.")

    # Check that the folders exist
    if not config_folder.exists():
        raise FileNotFoundError(f"config_folder does not exist: {config_folder}")
    if not data_folder.exists():
        raise FileNotFoundError(f"data_folder does not exist: {data_folder}")

    # Create out folder if it does not exist
    if not out_folder.exists():
        out_folder.mkdir(parents=True)

    # Find config files
    config_files = config_folder.glob("*.yaml")
    # Check there is at least one config file
    if not config_files:
        raise ValueError(f"No configuration files ('*.yaml') found in {config_folder}.")

    # Find test folders
    tests = data_folder.glob("*")
    # filter hidden directories and possibly the config folder from the test folders
    all_tests = [folder.stem for folder in tests if not folder.stem.startswith(".") and config_folder != folder]

    participant_ids = {}

    # Loop over participants
    for config_file in config_files:

        # Check if there is a corresponding data file
        name = config_file.stem
        p_id = name.split("_")[0]  # Participant id

        if name.endswith('S1'):
            name = name.replace('S1', 'PT1')
        elif name.endswith('S2'):
            name = name.replace('S2', 'PT2')

        if p_id not in participant_ids:
            participant_ids[p_id] = []

        session_folder = out_folder / name
        session_folder.mkdir(parents=True, exist_ok=True)

        for test in all_tests:

            old_path = data_folder / test / name
            # find participant folder in old path and move to new session folder in a subfolder
            if old_path.exists():
                participant_ids[p_id].append(test)
                new_participant_path = session_folder / test
                new_participant_path.mkdir(parents=True, exist_ok=True)
                shutil.copytree(old_path, new_participant_path, dirs_exist_ok=True)


        # copy the config file to the new session folder
        new_config_path = session_folder / config_file.name
        shutil.copy(config_file, new_config_path)

    # make sure all participant ids have all tests
    for p_id, tests in participant_ids.items():
        if len(tests) != len(all_tests):
            # get the missing tests
            missing_tests = [test for test in all_tests if test not in tests]
            print(f"Participant {p_id} is missing some tests: {missing_tests}")
        # else:
        #     print(f"Participant {p_id} has all tests.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Fix the structure of psychometric tests in a data collection folder.')
    parser.add_argument(
        '--config_folder',
        type=str,
        help='Path to the folder containing the psychometric tests configuration files.',
        default=PSYM_PARTICIPANT_CONFIGS
    )
    parser.add_argument(
        '--data_folder',
        type=str,
        help='Path to the folder containing the data collection.',
        default=PSYM_CORE_DATA
    )
    parser.add_argument(
        '--out_folder',
        type=str,
        help='Path to the session folder where the restructured data / user folders will be saved.',
        default=PSYCHOMETRIC_TESTS_DIR
    )
    args = parser.parse_args()
    fix_psycho_tests_structure(
        Path(args.config_folder), Path(args.data_folder), Path(args.out_folder)
    )
