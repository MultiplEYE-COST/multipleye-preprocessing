import os
from argparse import ArgumentParser

from tqdm import tqdm

from ..models.sid import Sid
from ..utils.logging import get_logger
import preprocessing
from preprocessing import settings

from preprocessing.scripts.prepare_language_folder import prepare_language_folder


def run_preprocessing(config_path: str | None = None):
    settings.load(config_path)
    logger = get_logger()

    # Check for configuration issues after loading
    status_msg = settings.get_config_status_message()
    if status_msg:
        from ..config import package_logger

        package_logger.error(status_msg)
        return

    data_collection_name = settings.DATA_COLLECTION_NAME

    logger.info(
        f"Running MultiplEYE preprocessing for data collection: {data_collection_name}"
    )

    prepare_language_folder(data_collection_name)

    data_folder_path = settings.DATASET_DIR

    if not os.path.exists(data_folder_path):
        raise FileNotFoundError(
            f"Data folder {data_folder_path} does not exist. Please make sure to download the data and place it in the correct folder. "
            f"And check if you have filled in the correct data collection name in the settings."
        )

    if settings.EXPERIMENT_TYPE == "MultiplEYE":
        data_collection = preprocessing.data_collection.MultipleyeDataCollection.create_from_data_folder(
            data_folder_path,
            include_pilots=settings.INCLUDE_PILOTS,
            excluded_sessions=settings.EXCLUDE_SESSIONS,
            included_sessions=settings.INCLUDE_SESSIONS,
        )

    elif settings.EXPERIMENT_TYPE == "MeRID":
        data_collection = (
            preprocessing.data_collection.MeridDataCollection.create_from_data_folder(
                data_folder_path,
                include_pilots=settings.INCLUDE_PILOTS,
                excluded_sessions=settings.EXCLUDE_SESSIONS,
                included_sessions=settings.INCLUDE_SESSIONS,
            )
        )

    else:
        raise ValueError(
            f"Invalid experiment type: {settings.EXPERIMENT_TYPE}. Supported types: [MultiplEYE, MeRID]"
        )

    data_collection.convert_edf_to_asc()
    data_collection.prepare_session_level_information()

    # for sess in multipleye:
    #     if sess.stimuli == 'unknown':
    #         print(sess.session_identifier)

    sessions = [s for s in data_collection]

    for sess in (pbar := tqdm(sessions)):
        idf = sess.session_identifier
        # Use Sid to get a consistent session name for file names, excluding restart postfixes
        session_save_name = Sid.get_session_save_name(idf)

        pbar.set_description(f"Preprocessing session {idf}:")

        asc = sess.asc_path

        # create or load raw data
        raw_data_folder = (
            settings.OUTPUT_DIR / settings.RAW_DATA_FOLDER / session_save_name
        )
        if raw_data_folder.exists() and not settings.OVERWRITE:
            # check if the folder contains the expected number of files, if not, we will overwrite
            num_expected_files = len(sess.completed_stimuli_ids)
            num_files = len(list(raw_data_folder.glob("*.csv")))
            if num_expected_files != num_files:
                raise ValueError(
                    f"Raw data cannot be loaded as the folder for session {idf} does not contain the "
                    f"expected number of files. Please check and select overwrite."
                )

            pbar.set_description(f"Loading samples {idf}:")
            gaze = preprocessing.load_trial_level_raw_data(
                settings.OUTPUT_DIR,
                session_save_name,
                trial_columns=settings.TRIAL_COLS,
                load_metadata=True,
            )

        else:
            pbar.set_description(f"Extracting samples {idf}:")
            gaze = preprocessing.load_gaze_data(
                asc_file=asc,
                lab_config=sess.lab_config,
                session_idf=idf,
                trial_cols=settings.TRIAL_COLS,
            )
            preprocessing.save_raw_data(settings.OUTPUT_DIR, session_save_name, gaze)
            preprocessing.save_session_metadata(
                settings.OUTPUT_DIR, session_save_name, gaze
            )

        sess.pm_gaze_metadata = gaze._metadata
        sess.calibrations = gaze.calibrations
        sess.validations = gaze.validations

        # preprocess gaze data
        pbar.set_description(f"Preprocessing samples {idf}:")
        preprocessing.preprocess_gaze(
            gaze,
        )

        # create or load fixation data
        fixation_data_folder = (
            settings.OUTPUT_DIR / settings.FIXATIONS_FOLDER / session_save_name
        )
        saccade_data_folder = (
            settings.OUTPUT_DIR / settings.SACCADES_FOLDER / session_save_name
        )

        if (
            fixation_data_folder.exists()
            and saccade_data_folder.exists()
            and not settings.OVERWRITE
        ):
            # check if the folder contains the expected number of files, if not, we will overwrite
            num_expected_files = len(sess.completed_stimuli_ids)
            num_files = len(list(fixation_data_folder.glob("*.csv")))

            if num_expected_files != num_files:
                raise ValueError(
                    f"Fixation data cannot be loaded as the folder for session {idf} does not contain the "
                    f"expected number of files. Please check and select overwrite."
                )

            num_files = len(list(saccade_data_folder.glob("*.csv")))
            if num_expected_files != num_files:
                raise ValueError(
                    f"Saccade data cannot be loaded as the folder for session {idf} does not contain the "
                    f"expected number of files. Please check and select overwrite."
                )

            pbar.set_description(f"Loading events {idf}:")
            gaze = preprocessing.load_trial_level_events_data(
                gaze,
                settings.OUTPUT_DIR,
                session_save_name,
                event_type=settings.FIXATION,
                file_pattern=None,
            )

            gaze = preprocessing.load_trial_level_events_data(
                gaze,
                settings.OUTPUT_DIR,
                session_save_name,
                event_type=settings.SACCADE,
                file_pattern=None,
            )

        else:
            pbar.set_description(f"Detecting events {idf}:")

            preprocessing.detect_fixations(gaze)
            preprocessing.detect_saccades(gaze)

            preprocessing.save_events_data(
                settings.FIXATION,
                settings.OUTPUT_DIR,
                session_save_name,
                "trial",
                ["trial", "stimulus"],
                ["onset", "duration", "location_x", "location_y", "page"],
                gaze,
            )

            preprocessing.save_events_data(
                settings.SACCADE,
                settings.OUTPUT_DIR,
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
        preprocessing.save_scanpaths(settings.OUTPUT_DIR, session_save_name, gaze)

        preprocessing.save_session_metadata(
            settings.OUTPUT_DIR, session_save_name, gaze
        )

        rm_folder = (
            settings.OUTPUT_DIR / settings.READING_MEASURES_FOLDER / session_save_name
        )

        if rm_folder.exists() and not settings.OVERWRITE:
            # check if the folder contains the expected number of files, if not, we will overwrite
            num_expected_files = len(sess.completed_stimuli_ids)
            num_files = len(list(rm_folder.glob("*.csv")))
            if num_expected_files != num_files:
                raise ValueError(
                    f"Reading measures cannot be loaded as the folder for session {idf} does not contain the "
                    f"expected number of files. Please check and select overwrite."
                )

            pbar.set_description(f"Loading reading measures {idf}:")
            reading_measures = preprocessing.load_reading_measures(
                settings.OUTPUT_DIR,
                session_save_name,
            )

            data_collection[sess.session_identifier].reading_measures = True

        else:
            pbar.set_description(f"Calculating reading measures {idf}:")
            reading_measures = preprocessing.calculate_reading_measures(
                gaze,
                sess.stimuli,
            )

            preprocessing.save_reading_measures(
                settings.OUTPUT_DIR, session_save_name, reading_measures
            )
            data_collection[sess.session_identifier].reading_measures = True

        pbar.set_description(f"Creating sanity check report {idf}")
        data_collection.create_sanity_check_report(
            gaze,
            sess.session_identifier,
            plotting=True,
            overwrite=True,
            output_dir=settings.OUTPUT_DIR,
        )

        data_collection.create_session_overview(
            sess.session_identifier, path=settings.OUTPUT_DIR
        )

    data_collection.create_dataset_overview(path=settings.OUTPUT_DIR)
    data_collection.parse_participant_data(settings.OUTPUT_DIR / "participant_data.csv")


def main():
    """Run MultiplEYE preprocessing with the config file as argument."""
    parser = ArgumentParser(description="Run MultiplEYE preprocessing.")

    parser.add_argument(
        "--config_path",
        type=str,
        default=None,
        help="Path to the preprocessing configuration YAML file.",
    )
    args = parser.parse_args()
    run_preprocessing(args.config_path)


if __name__ == "__main__":
    main()
