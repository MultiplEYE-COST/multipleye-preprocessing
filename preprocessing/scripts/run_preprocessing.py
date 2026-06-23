import os
from argparse import ArgumentParser

from tqdm import tqdm
import polars as pl

from ..models.sid import Sid
from ..utils.logging import get_logger
import preprocessing
from preprocessing import settings

from preprocessing.scripts.prepare_language_folder import prepare_language_folder
import contextlib


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
        sid = Sid(idf)

        pbar.set_description(f"Preprocessing session {idf}:")

        asc = sess.asc_path

        # create or load raw data
        raw_data_folder = settings.OUTPUT_DIR / settings.RAW_DATA_FOLDER / str(sid)
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
                sid,
                trial_columns=settings.TRIAL_COLS,
                load_metadata=True,
            )

        else:
            pbar.set_description(f"Extracting samples {idf}:")
            gaze = preprocessing.load_gaze_data(
                asc_file=asc,
                lab_config=sess.lab_config,
                sid=sid,
                trial_cols=settings.TRIAL_COLS,
                messages=settings.ANSWER_MSG_PATTERNS,
            )

            # filter gaze to only contain data of completed stimuli
            gaze.samples = gaze.samples.filter(
                pl.col("stimulus").is_in(sess.completed_stimuli_names)
            )

            preprocessing.save_raw_data(
                settings.OUTPUT_DIR,
                sid,
                gaze,
            )
            preprocessing.save_session_metadata(settings.OUTPUT_DIR, gaze, sid)

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
            settings.OUTPUT_DIR / settings.FIXATIONS_FOLDER / str(sid)
        )
        saccade_data_folder = settings.OUTPUT_DIR / settings.SACCADES_FOLDER / str(sid)

        if settings.RUN_FIXATION_DETECTION or settings.RUN_SACCADE_DETECTION:
            if gaze is None:
                logger.warning(
                    f"Gaze data missing for {idf}. Skipping event detection."
                )
            elif (
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
                        f"expected number of files. Please check or select overwrite."
                    )

                num_files = len(list(saccade_data_folder.glob("*.csv")))
                if num_expected_files != num_files:
                    raise ValueError(
                        f"Saccade data cannot be loaded as the folder for session {idf} does not contain the "
                        f"expected number of files. Please check or select overwrite."
                    )

                pbar.set_description(f"Loading events {idf}:")
                gaze = preprocessing.load_trial_level_events_data(
                    gaze,
                    settings.OUTPUT_DIR,
                    sid,
                    event_type=settings.FIXATION,
                    file_pattern=None,
                )

                gaze = preprocessing.load_trial_level_events_data(
                    gaze,
                    settings.OUTPUT_DIR,
                    sid,
                    event_type=settings.SACCADE,
                    file_pattern=None,
                )

            else:
                pbar.set_description(f"Detecting events {idf}:")

                if settings.RUN_FIXATION_DETECTION:
                    preprocessing.detect_fixations(gaze)
                if settings.RUN_SACCADE_DETECTION:
                    preprocessing.detect_saccades(gaze)

                if settings.RUN_FIXATION_DETECTION:
                    preprocessing.save_events_data(
                        settings.FIXATION,
                        settings.OUTPUT_DIR,
                        sid,
                        "trial",
                        ["trial", "stimulus"],
                        ["onset", "duration", "location_x", "location_y", "page"],
                        gaze,
                    )

                if settings.RUN_SACCADE_DETECTION:
                    preprocessing.save_events_data(
                        settings.SACCADE,
                        settings.OUTPUT_DIR,
                        sid,
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

                # Unnest event columns (e.g. location struct -> location_x/location_y)
                # so downstream code doesn't need to handle struct columns.
                if gaze is not None and gaze.events is not None:
                    with contextlib.suppress(Warning):
                        gaze.events.unnest()
        else:
            pbar.set_description(f"Skipping event detection {idf}:")
            # Load existing if available
            if (
                gaze is not None
                and fixation_data_folder.exists()
                and saccade_data_folder.exists()
            ):
                logger.info(f"Using existing event data for {idf}")
                gaze = preprocessing.load_trial_level_events_data(
                    gaze,
                    settings.OUTPUT_DIR,
                    idf,
                    event_type=settings.FIXATION,
                    file_pattern=None,
                )
                gaze = preprocessing.load_trial_level_events_data(
                    gaze,
                    settings.OUTPUT_DIR,
                    idf,
                    event_type=settings.SACCADE,
                    file_pattern=None,
                )

        # map to AOIs and create scanpaths
        if settings.RUN_FIXATION_DETECTION:  # Mapping depends on fixations
            if (
                gaze is None
                or gaze.events is None
                or gaze.events.frame.filter(
                    pl.col("name") == settings.FIXATION
                ).is_empty()
            ):
                logger.warning(
                    f"Fixations missing for {idf}. Skipping AOI mapping/scanpaths."
                )
            else:
                preprocessing.map_fixations_to_aois(
                    gaze,
                    sess.stimuli,
                )
                preprocessing.save_scanpaths(settings.OUTPUT_DIR, sid, gaze)

                preprocessing.save_session_metadata(settings.OUTPUT_DIR, gaze, sid)

        rm_folder = settings.OUTPUT_DIR / settings.READING_MEASURES_FOLDER / str(sid)

        if settings.RUN_READING_MEASURES:
            if (
                gaze is None
                or gaze.events is None
                or gaze.events.frame.filter(
                    pl.col("name") == settings.FIXATION
                ).is_empty()
                or settings.WORD_IDX_COL not in gaze.events.columns
            ):
                logger.warning(
                    f"Gaze/Event data missing or not mapped for {idf}. Skipping reading measures."
                )
            elif rm_folder.exists() and not settings.OVERWRITE:
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
                    sid,
                )

                data_collection[sess.session_identifier].reading_measures = True

            else:
                pbar.set_description(f"Calculating reading measures {idf}:")
                reading_measures = preprocessing.calculate_reading_measures(
                    gaze,
                    sess.stimuli,
                )

                preprocessing.save_reading_measures(
                    settings.OUTPUT_DIR, sid, reading_measures
                )
                data_collection[sess.session_identifier].reading_measures = True
        else:
            pbar.set_description(f"Skipping reading measures {idf}:")

        # === COMPREHENSION QUESTION ANSWERS ===
        if settings.RUN_COMPREHENSION_ANSWERS:
            answers_csv = (
                settings.OUTPUT_DIR
                / settings.ANSWERS_FOLDER
                / str(sid)
                / f"{str(sid)}_answers.csv"
            )

            if answers_csv.exists() and not settings.OVERWRITE:
                pbar.set_description(f"Loading comprehension answers {idf}")
                sess.answers = True
            else:
                pbar.set_description(f"Collecting comprehension answers {idf}")
                question_order_csv = (
                    sess.session_folder_path
                    / "logfiles"
                    / "question_order_versions.csv"
                )
                if question_order_csv.exists():
                    parsed_answers = None
                    source = "unknown"

                    # 1. Primary source: ASC messages (prefer if gaze exists)
                    if (
                        gaze is not None
                        and gaze.messages is not None
                        and not gaze.messages.is_empty()
                    ):
                        parsed_answers = preprocessing.parse_answers_from_messages(
                            gaze.messages
                        )
                        if parsed_answers is not None and not parsed_answers.is_empty():
                            source = "asc"

                    # 2. Fallback source: experiment logfile
                    if parsed_answers is None or parsed_answers.is_empty():
                        # We only fallback if we really didn't find anything in ASC
                        # OR if extraction was disabled and raw data was missing (gaze is None)
                        parsed_answers = preprocessing.parse_answers_from_logfile(
                            sess.logfile, sess.stimuli_trial_mapping
                        )
                        if not parsed_answers.is_empty():
                            source = "logfile"

                    preprocessing.collect_session_answers(
                        question_order_csv=question_order_csv,
                        stimuli_trial_map=sess.stimuli_trial_mapping,
                        stimuli=sess.stimuli,
                        parsed_answers=parsed_answers,
                        out_path=answers_csv,
                        source=source,
                        completed_stimuli_ids=sess.completed_stimuli_ids,
                    )
                    sess.answers = True
        else:
            pbar.set_description(f"Skipping comprehension answers {idf}:")

        if settings.RUN_SANITY_CHECKS:
            if gaze is None:
                logger.warning(f"Gaze data missing for {idf}. Skipping sanity report.")
            else:
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
        else:
            pbar.set_description(f"Skipping sanity checks {idf}:")

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
