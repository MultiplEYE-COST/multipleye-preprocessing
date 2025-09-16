import argparse
import shutil
import zipfile
from pathlib import Path
import tarfile

from preprocessing.utils.restructure_psycho_tests import fix_psycho_tests_structure


def prepare_language_folder(data_collection_name):

    _, lang, country, city, lab_no, year = data_collection_name.split("_")


    # Check if the data collection folder exists
    this_repo = Path().resolve()
    data_folder_path = this_repo / "data" / data_collection_name
    if not data_folder_path.exists():
        raise FileNotFoundError(f"The data collection folder '{data_folder_path}' does not exist. "
                                "Please check the name or path provided and make sure it is unzipped.")

    # check if there exists an eye-tracking-sessions folder
    eye_tracking_sessions_path = data_folder_path / "eye-tracking-sessions"
    if not eye_tracking_sessions_path.exists():
        # check if it is still in a tar
        zipped_path = data_folder_path / "eye-tracking-sessions.tar"
        if zipped_path.exists():
            # unzip

            with tarfile.open(zipped_path, "r") as tar:
                tar.extractall(path=data_folder_path)
            print(f"Extracted 'eye-tracking-sessions' from '{zipped_path}'")
        else:
            raise FileNotFoundError(f"The 'eye-tracking-sessions' folder does not exist in '{data_folder_path}'. "
                                "Please ensure the data collection is correctly structured.")

    psychometric_tests_path = data_folder_path / "psychometric-tests-sessions"
    if not psychometric_tests_path.exists():
        # if there is no psychometric-tests folder, check if it is still in a tar
        tar_path = data_folder_path / "psychometric-tests.tar"
        if tar_path.exists():
            with tarfile.open(tar_path, "r") as tar:
                tar.extractall(path=data_folder_path)
            print(f"Extracted 'psychometric-tests' from '{tar_path}'")
        else:
            raise FileNotFoundError(f"The 'psychometric-tests-sessions' folder does not exist in '{data_folder_path}'. "
                                    "Please ensure the data collection is correctly structured.")

    # che if ps tests need to be prepared because they use the old structure
    config_path = psychometric_tests_path / f"participant_configs_{lang}_{country}_{lab_no}"
    data_path = psychometric_tests_path / f"psychometric_test_{lang}_{country}_{lab_no}"
    if config_path.exists() and data_path.exists():
        print(f"Preparing psychometric tests structure for {data_collection_name}...")
        fix_psycho_tests_structure(config_path, data_path)

    # check if the participant folders are zipped and if yes, unzip them
    for participant_folder in eye_tracking_sessions_path.glob("*"):
        if participant_folder.suffix == ".zip":
            shutil.unpack_archive(participant_folder, extract_dir=eye_tracking_sessions_path)
            print(f"Extracted participant data from '{participant_folder}'")
            # remove the zip file after extraction
            participant_folder.unlink()
        else:
            print(f"No zipped data found for {participant_folder.name}. Proceeding with existing data.")

    stimulus_folder_path = data_folder_path / f"stimuli_{data_collection_name}"

    if not stimulus_folder_path.exists():
        print(f'The stimulus folder stimuli_{data_collection_name} does not exist. Check and if necessary, ask team to upload.')
    else:
        config_path = stimulus_folder_path / "config"
        if not config_path.exists():
            raise FileNotFoundError(f"The stimulus config folder not found in '{stimulus_folder_path}'. "
                                    "Please check and restructure or possibly unzip the stimulus folder.")


def parse_args():
    parser = argparse.ArgumentParser(description='Run multipleye preprocessing on an experiment file')

    parser.add_argument(
        'data_collection_name',
        type=str,
        help='Name of the folder containing the data collection. E.g. "MultiplEYE_ET_EE_Tartu_1_2022". '
             'The folder should be located in the "data" directory of this repository.',
    )

    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()

    prepare_language_folder(**vars(args))
