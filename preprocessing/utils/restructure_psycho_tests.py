import argparse
import shutil
from pathlib import Path


def fix_psycho_tests_structure(config_folder: str, data_folder: str):
    config_files = Path(config_folder).glob("*.yaml")
    parent_folder = Path(data_folder).parent

    tests = Path(data_folder).glob("*", )
    all_tests = []

    for test_folder in tests:
        if not test_folder.stem.startswith("."):
            all_tests.append(test_folder.stem)

    participant_ids = {}

    for config_file in config_files:

        # check if there is a corresponding data file
        data_file = data_folder
        name = config_file.stem
        p_id = name.split("_")[0]

        if p_id not in participant_ids:
            participant_ids[p_id] = []

        session_folder = parent_folder / name
        session_folder.mkdir(parents=True, exist_ok=True)

        for test in all_tests:
            new_path = parent_folder / test

            old_path = Path(data_folder) / test / name
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
        else:
            print(f"Participant {p_id} has all tests.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Fix the structure of psychometric tests in a data collection folder.')
    parser.add_argument(
        'config_folder',
        type=str,
        help='Path to the folder containing the psychometric tests configuration files.',
    )
    parser.add_argument(
        'data_folder',
        type=str,
        help='Path to the folder containing the data collection.',
    )
    args = parser.parse_args()
    fix_psycho_tests_structure(args.config_folder, args.data_folder)
