import os
from argparse import ArgumentParser

import yaml
from tqdm import tqdm

from ..utils.logging import get_logger
import preprocessing
from preprocessing import constants


def run_multipleye_preprocessing(config_path: str):
    this_repo = constants.THIS_REPO
    logger = get_logger(__name__)
    config = yaml.load(open(this_repo / config_path), Loader=yaml.SafeLoader)

    data_collection_name = config["data_collection_name"]
    logger.info(
        f"Running MultiplEYE preprocessing for data collection: {data_collection_name}"
    )

    preprocessing.utils.prepare_language_folder(data_collection_name)

    data_folder_path = this_repo / "data" / data_collection_name

    if not os.path.exists(data_folder_path):
        raise FileNotFoundError(
            f"Data folder {data_folder_path} does not exist. Please make sure to download the data and place it in the correct folder. "
            f"And check if you have filled in the correct data collection name in the config file {config_path}."
        )

    multipleye = (
        preprocessing.data_collection.MultipleyeDataCollection.create_from_data_folder(
            data_folder_path,
            include_pilots=config["include_pilots"],
            excluded_sessions=config["exclude_sessions"],
            included_sessions=config["include_sessions"],
        )
    )

    multipleye.convert_edf_to_asc()
    multipleye.prepare_session_level_information()

    sessions = [s for s in multipleye]

    for sess in (pbar := tqdm(sessions)):
        idf = sess.session_identifier
        # this is a bit of a hack to make the session names consistent for the file names as the multipleye
        # session names contain infos when it was restarted
        session_save_name = idf.split("_")[:5]
        session_save_name = "_".join(session_save_name)

        pbar.set_description(f"Preprocessing session {idf}:")

        asc = sess.asc_path
        output_folder = constants.OUTPUT_DIR / idf
        output_folder.mkdir(parents=True, exist_ok=True)

        # create or load raw data
        raw_data_folder = output_folder / constants.RAW_DATA_FOLDER
        if raw_data_folder.exists():
            pbar.set_description(f"Loading samples {idf}:")
            gaze = preprocessing.load_trial_level_raw_data(
                raw_data_folder,
                trial_columns=constants.TRIAL_COLS,
                metadata_path=output_folder,
            )

        else:
            pbar.set_description(f"Extracting samples {idf}:")
            gaze = preprocessing.load_gaze_data(
                asc_file=asc,
                lab_config=sess.lab_config,
                session_idf=idf,
                trial_cols=constants.TRIAL_COLS,
            )
            preprocessing.save_raw_data(constants.OUTPUT_DIR, session_save_name, gaze)
            preprocessing.save_session_metadata(constants.OUTPUT_DIR, idf, gaze)

        sess.pm_gaze_metadata = gaze._metadata
        sess.calibrations = gaze.calibrations
        sess.validations = gaze.validations

        # preprocess gaze data
        pbar.set_description(f"Preprocessing samples {idf}:")
        preprocessing.preprocess_gaze(
            gaze,
        )

        # create or load fixation data
        fixation_data_folder = output_folder / constants.FIXATIONS_FOLDER
        saccade_data_folder = output_folder / constants.SACCADES_FOLDER
        if fixation_data_folder.exists():
            pbar.set_description(f"Loading events {idf}:")
            gaze = preprocessing.load_trial_level_events_data(
                gaze,
                fixation_data_folder,
                event_type="fixation",
                file_pattern=r".+_(?P<trial>(?:PRACTICE_)?trial_\d+)_(?P<stimulus>[^_]+_[^_]+_\d+(\.0)?)_fixation.csv",
            )

            gaze = preprocessing.load_trial_level_events_data(
                gaze,
                saccade_data_folder,
                event_type="saccade",
                file_pattern=r".+_(?P<trial>(?:PRACTICE_)?trial_\d+)_(?P<stimulus>[^_]+_[^_]+_\d+(\.0)?)_saccade.csv",
            )

        else:
            pbar.set_description(f"Detecting events {idf}:")

            preprocessing.detect_fixations(gaze)
            preprocessing.detect_saccades(gaze)

            preprocessing.save_events_data(
                "fixation",
                fixation_data_folder,
                session_save_name,
                "trial",
                ["trial", "stimulus"],
                ["onset", "duration", "location_x", "location_y", "page"],
                gaze,
            )

            preprocessing.save_events_data(
                "saccade",
                saccade_data_folder,
                session_save_name,
                "trial",
                ["trial", "stimulus"],
                [
                    "onset",
                    "duration",
                    "amplitude",
                    "peak_velocity",
                    "dispersion",
                    "page",
                ],
                gaze,
            )

        # map to AOIs and create scanpaths
        preprocessing.map_fixations_to_aois(
            gaze,
            sess.stimuli,
        )
        preprocessing.save_scanpaths(constants.OUTPUT_DIR, session_save_name, gaze)

        preprocessing.save_session_metadata(constants.OUTPUT_DIR, idf, gaze)

        # perform the multipleye specific stuff
        multipleye.create_session_overview(
            sess.session_identifier, path=constants.OUTPUT_DIR
        )
        pbar.set_description(f"Creating sanity check report {idf}")
        multipleye.create_sanity_check_report(
            gaze, sess.session_identifier, plotting=True, overwrite=True
        )

    multipleye.create_dataset_overview(path=constants.OUTPUT_DIR)
    multipleye.parse_participant_data(constants.OUTPUT_DIR / "participant_data.csv")


def main():
    """Run MultiplEYE preprocessing with the config file as argument."""
    parser = ArgumentParser(description="Run MultiplEYE preprocessing.")

    parser.add_argument(
        "--config_path",
        type=str,
        default="multipleye_settings_preprocessing.yaml",
        help="Path to the preprocessing configuration YAML file.",
    )
    args = parser.parse_args()
    run_multipleye_preprocessing(args.config_path)


if __name__ == "__main__":
    main()
