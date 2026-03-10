import argparse
import re
import shutil
import tarfile
from pathlib import Path

import pandas as pd
from preprocessing import constants

from ..utils.data_path_utils import check_data_collection_exists
from ..utils.logging import get_logger
from ..scripts.restructure_psycho_tests import fix_psycho_tests_structure


def prepare_language_folder(data_collection_name):
    _, lang, country, city, lab_no, year = data_collection_name.split("_")
    logger = get_logger(__name__)

    # Check if the data collection folder exists
    data_folder_path = check_data_collection_exists(
        data_collection_name, constants.THIS_REPO / "data"
    )

    # check if there exists an eye-tracking-sessions folder
    eye_tracking_sessions_path = data_folder_path / "eye-tracking-sessions"
    if not eye_tracking_sessions_path.exists():
        # check if it is still in a tar
        zipped_path = data_folder_path / "eye-tracking-sessions.tar"
        if zipped_path.exists():
            # unzip

            with tarfile.open(zipped_path, "r") as tar:
                tar.extractall(path=data_folder_path)
            logger.info(f"Extracted 'eye-tracking-sessions' from '{zipped_path}'")
        else:
            raise FileNotFoundError(
                f"The 'eye-tracking-sessions' folder does not exist in '{data_folder_path}'. "
                "Please ensure the data collection is correctly structured."
            )

    # check if there is a core_sessions folder and if yes, check if there are any folder inside and then move them up and delete the core_sessions folder
    core_session_paths = [
        eye_tracking_sessions_path / "core_sessions",
        eye_tracking_sessions_path / "core_dataset",
    ]
    for core_session_path in core_session_paths:
        if core_session_path.exists():
            core_folders = list(core_session_path.glob("*"))
            if len(core_folders) > 0:
                for folder in core_folders:
                    shutil.move(str(folder), str(eye_tracking_sessions_path))
                shutil.rmtree(core_session_path)
                logger.info(
                    "Moved folders from 'core_sessions' to 'eye-tracking-sessions' "
                    "and removed 'core_sessions' folder."
                )

    psychometric_tests_path = data_folder_path / "psychometric-tests-sessions"
    if not psychometric_tests_path.exists():
        # if there is no psychometric-tests folder, check if it is still in a tar
        tar_path = data_folder_path / "psychometric-tests.tar"
        if tar_path.exists():
            with tarfile.open(tar_path, "r") as tar:
                tar.extractall(path=data_folder_path)
            logger.info(f"Extracted 'psychometric-tests' from '{tar_path}'")
        else:
            raise FileNotFoundError(
                f"The 'psychometric-tests-sessions' folder does not exist in '{data_folder_path}'. "
                "Please ensure the data collection is correctly structured."
            )

    # che if ps tests need to be prepared because they use the old structure
    config_path = (
        psychometric_tests_path / f"participant_configs_{lang}_{country}_{lab_no}"
    )
    data_path = psychometric_tests_path / f"psychometric_test_{lang}_{country}_{lab_no}"
    if config_path.exists() and data_path.exists():
        logger.info(
            f"Preparing psychometric tests structure for {data_collection_name}..."
        )
        fix_psycho_tests_structure(config_path, data_path)

    # check if the participant folders are zipped and if yes, unzip them
    for participant_folder in eye_tracking_sessions_path.glob("*"):
        if participant_folder.suffix == ".zip":
            shutil.unpack_archive(
                participant_folder, extract_dir=eye_tracking_sessions_path
            )
            logger.info(f"Extracted participant data from '{participant_folder}'")
            # remove the zip file after extraction
            participant_folder.unlink()

    pilot_folder = eye_tracking_sessions_path / "pilot_sessions"
    if pilot_folder.exists():
        for pilot_participant_folder in pilot_folder.glob("*"):
            if pilot_participant_folder.suffix == ".zip":
                shutil.unpack_archive(
                    pilot_participant_folder, extract_dir=pilot_folder
                )
                logger.info(
                    f"Extracted pilot participant data from '{pilot_participant_folder}'"
                )
                # remove the zip file after extraction
                pilot_participant_folder.unlink()

    stimulus_folder_path = data_folder_path / f"stimuli_{data_collection_name}"

    if not stimulus_folder_path.exists():
        logger.warning(
            f"The stimulus folder stimuli_{data_collection_name} does not exist. Check and if necessary, ask team to upload."
        )
    else:
        config_path = stimulus_folder_path / "config"
        if not config_path.exists():
            raise FileNotFoundError(
                f"The stimulus config folder not found in '{stimulus_folder_path}'. "
                "Please check and restructure or possibly unzip the stimulus folder."
            )

    # if aoi files are not yet split into questions and texts, do it here:
    aoi_path = (
        data_folder_path
        / stimulus_folder_path
        / f"aoi_stimuli_{lang}_{country}_{lab_no}"
    )

    # get all aoi files, if there are only 12 files, they are not yet split
    aoi_files = list(aoi_path.glob("*.csv"))
    if len(aoi_files) == 12:
        logger.info("Splitting AOI files into text and question AOIs...")
        for aoi_file in aoi_files:
            aoi_df = pd.read_csv(aoi_file)
            # split the aoi_df into two parts, one for the stimulus and one for the questions
            aoi_df_texts = aoi_df[~aoi_df["page"].str.contains("question", na=False)]
            aoi_df_texts.drop(
                columns=["question_image_version"], inplace=True, errors="ignore"
            )
            aoi_df_questions = aoi_df[aoi_df["page"].str.contains("question", na=False)]

            aoi_df_texts.to_csv(aoi_file, sep=",", index=False, encoding="UTF-8")

            question_path = aoi_path / (aoi_file.stem + "_questions" + aoi_file.suffix)
            aoi_df_questions.to_csv(
                question_path, sep=",", index=False, encoding="UTF-8"
            )

    elif len(aoi_files) == 24:
        pass
    else:
        raise ValueError(
            f"Unexpected number of AOI files ({len(aoi_files)}) found in '{aoi_path}'. "
            "Expected 12 (not split) or 24 (already split into texts and questions)."
        )


def extract_stimulus_version_number_from_asc(asc_file_path: Path) -> int:
    pattern = r"MSG\s+\d+\s+stimulus_order_version:\s+(?P<version_num>\d\d?\d?)\n"

    with open(asc_file_path) as asc_file:
        for line in asc_file:
            if match := re.match(pattern, line):
                return int(match.group("version_num"))

        return -1


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run multipleye preprocessing on an experiment file"
    )

    parser.add_argument(
        "data_collection_name",
        type=str,
        help='Name of the folder containing the data collection. E.g. "MultiplEYE_ET_EE_Tartu_1_2022". '
        'The folder should be located in the "data" directory of this repository.',
    )

    return parser.parse_args()


def main():
    args = parse_args()
    logger = get_logger(__name__)

    logger.info(f"Preparing language folder for {args.data_collection_name}...")

    prepare_language_folder(args.data_collection_name)
