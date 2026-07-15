import os
from argparse import ArgumentParser

from tqdm import tqdm
import polars as pl
import pymovements as pm

from ..utils.logging import get_logger
import preprocessing
from preprocessing import settings

from preprocessing.scripts.prepare_language_folder import prepare_language_folder
from preprocessing.checks.quality_thresholds import write_quality_thresholds
import contextlib


def _compare_data_loss_measures(gaze, sess):
    """Compute measure-based data loss and log comparison to console + CSV.

    Temporary dev function. Compares metadata values (from parsing) against
    pymovements.measure.data_loss() and gaze.measure_events_ratio() to verify
    equivalence before removing the metadata dict.

    The total loss measure is computed here. The blink loss measure is pre-computed
    inside load_gaze_data() and stored in gaze._metadata['_measure_data_loss_ratio_blinks'].
    """
    logger = get_logger()

    meta_total = gaze._metadata.get("data_loss_ratio")
    meta_blink = gaze._metadata.get("data_loss_ratio_blinks")
    meas_blink = gaze._metadata.get("_measure_data_loss_ratio_blinks")

    sr = gaze.experiment.sampling_rate
    if sr is None:
        sr = float(gaze._metadata.get("sampling_rate", 1000.0))

    if "pixel" in gaze.samples.columns:
        data_col = "pixel"
    elif "pixel_x" in gaze.samples.columns:
        data_col = "pixel_x"
    else:
        for col in gaze.samples.columns:
            if col.startswith("x_") and col.endswith("_pix"):
                data_col = col
                break
            if col == "x_pix":
                data_col = col
                break
        else:
            data_col = None

    if data_col is None:
        logger.warning(
            f"[DATA_LOSS_COMPARE] {sess.sid}: could not determine pixel column, "
            f"available: {gaze.samples.columns}",
        )
        return

    trial_cols = settings.TRIAL_COLS if settings.TRIAL_COLS else ["trial", "stimulus"]
    try:
        dl_expr = pm.measure.data_loss(data_col, sampling_rate=sr, unit="ratio")
        meas_total = (
            gaze.samples.group_by(trial_cols)
            .agg(dl_expr)
            .select(pl.col("data_loss_ratio").mean())
            .item()
        )
    except Exception:
        logger.warning(
            f"[DATA_LOSS_COMPARE] {sess.sid}: data_loss measure failed",
            exc_info=True,
        )
        meas_total = None

    sess._measure_data_loss_ratio = meas_total
    sess._measure_data_loss_ratio_blinks = meas_blink

    delta_total = (
        abs(meas_total - meta_total)
        if meta_total is not None and meas_total is not None
        else None
    )
    delta_blink = (
        abs(meas_blink - meta_blink)
        if meta_blink is not None and meas_blink is not None
        else None
    )

    meta_total_str = f"{meta_total:.6f}" if meta_total is not None else "None"
    meas_total_str = f"{meas_total:.6f}" if meas_total is not None else "None"
    dl_total_str = f"{delta_total:.6f}" if delta_total is not None else "N/A"
    meta_blink_str = f"{meta_blink:.6f}" if meta_blink is not None else "None"
    meas_blink_str = f"{meas_blink:.6f}" if meas_blink is not None else "None"
    dl_blink_str = f"{delta_blink:.6f}" if delta_blink is not None else "N/A"

    logger.info(
        f"[COMPARE] data_loss_ratio:        "
        f"metadata={meta_total_str}  measure={meas_total_str}",
    )
    logger.info(
        f"[COMPARE] data_loss_ratio_blinks: "
        f"metadata={meta_blink_str}  measure={meas_blink_str}",
    )
    logger.info(
        f"[COMPARE] delta: total={dl_total_str}  blink={dl_blink_str}",
    )

    # Write to comparison CSV
    comparison_path = settings.OUTPUT_DIR / "data_loss_comparison.csv"
    new_row = pl.DataFrame(
        {
            "sid": [str(sess.sid)],
            "meta_total": [meta_total],
            "meas_total": [meas_total],
            "delta_total": [delta_total],
            "meta_blink": [meta_blink],
            "meas_blink": [meas_blink],
            "delta_blink": [delta_blink],
        }
    )
    if comparison_path.exists():
        existing = pl.read_csv(comparison_path)
        combined = pl.concat([existing, new_row], how="diagonal_relaxed")
    else:
        combined = new_row
        combined = new_row
    combined.write_csv(comparison_path)


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

    write_quality_thresholds(settings.OUTPUT_DIR)

    if settings.RUN_PREFLIGHT_CHECK:
        from ..checks.preflight import run_preflight_check

        run_preflight_check(data_collection)

    data_collection.convert_edf_to_asc()
    data_collection.prepare_session_level_information()

    # for sess in multipleye:
    #     if sess.stimuli == 'unknown':
    #         print(sess.session_identifier)

    sessions = [s for s in data_collection]

    for sess in (pbar := tqdm(sessions)):
        pbar.set_description(f"Preprocessing session {sess.sid}:")

        asc = sess.asc_path

        # create or load raw data
        raw_data_folder = sess.sid.raw_data_dir
        if raw_data_folder.exists() and not settings.OVERWRITE:
            # check if the folder contains the expected number of files, if not, we will overwrite
            num_expected_files = len(sess.completed_stimuli_ids)
            num_files = len(list(raw_data_folder.glob("*.csv")))
            if num_expected_files != num_files:
                raise ValueError(
                    f"Raw data cannot be loaded as the folder for session {sess.sid} does not contain the "
                    f"expected number of files. Please check and select overwrite."
                )

            pbar.set_description(f"Loading samples {sess.sid}:")
            gaze = preprocessing.load_trial_level_raw_data(
                sess.sid,
                trial_columns=settings.TRIAL_COLS,
                load_metadata=True,
            )

        else:
            pbar.set_description(f"Extracting samples {sess.sid}:")
            gaze = preprocessing.load_gaze_data(
                asc_file=asc,
                lab_config=sess.lab_config,
                sid=sess.sid,
                trial_cols=settings.TRIAL_COLS,
                messages=settings.ANSWER_MSG_PATTERNS,
            )

            # filter gaze to only contain data of completed stimuli
            gaze.samples = gaze.samples.filter(
                pl.col("stimulus").is_in(sess.completed_stimuli_names)
            )

            # Compute measure-based data loss for comparison with metadata (dev-only)
            # Must run before save_raw_data() — after saving, columns become
            # pixel_x/pixel_y and blink events are lost.
            _compare_data_loss_measures(gaze, sess)

            preprocessing.save_raw_data(sess.sid, gaze)
            preprocessing.save_session_metadata(sess.sid, gaze)

        sess.pm_gaze_metadata = gaze._metadata
        sess.calibrations = gaze.calibrations
        sess.validations = gaze.validations

        # preprocess gaze data
        pbar.set_description(f"Preprocessing samples {sess.sid}:")
        preprocessing.preprocess_gaze(
            gaze,
        )

        # create or load fixation data
        fixation_data_folder = sess.sid.fixations_dir
        saccade_data_folder = sess.sid.saccades_dir

        if settings.RUN_FIXATION_DETECTION or settings.RUN_SACCADE_DETECTION:
            if gaze is None:
                logger.warning(
                    f"Gaze data missing for {sess.sid}. Skipping event detection."
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
                        f"Fixation data cannot be loaded as the folder for session {sess.sid} does not contain the "
                        f"expected number of files. Please check or select overwrite."
                    )

                num_files = len(list(saccade_data_folder.glob("*.csv")))
                if num_expected_files != num_files:
                    raise ValueError(
                        f"Saccade data cannot be loaded as the folder for session {sess.sid} does not contain the "
                        f"expected number of files. Please check or select overwrite."
                    )

                pbar.set_description(f"Loading events {sess.sid}:")
                gaze = preprocessing.load_trial_level_events_data(
                    gaze,
                    sess.sid,
                    event_type=settings.FIXATION,
                    file_pattern=None,
                )

                gaze = preprocessing.load_trial_level_events_data(
                    gaze,
                    sess.sid,
                    event_type=settings.SACCADE,
                    file_pattern=None,
                )

            else:
                pbar.set_description(f"Detecting events {sess.sid}:")

                if settings.RUN_FIXATION_DETECTION:
                    preprocessing.detect_fixations(gaze)
                if settings.RUN_SACCADE_DETECTION:
                    preprocessing.detect_saccades(gaze)

                if settings.RUN_FIXATION_DETECTION:
                    preprocessing.save_events_data(
                        settings.FIXATION,
                        sess.sid,
                        "trial",
                        ["trial", "stimulus"],
                        ["onset", "duration", "location_x", "location_y", "page"],
                        gaze,
                    )

                if settings.RUN_SACCADE_DETECTION:
                    preprocessing.save_events_data(
                        settings.SACCADE,
                        sess.sid,
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
            pbar.set_description(f"Skipping event detection {sess.sid}:")
            # Load existing if available
            if (
                gaze is not None
                and fixation_data_folder.exists()
                and saccade_data_folder.exists()
            ):
                logger.info(f"Using existing event data for {sess.sid}")
                gaze = preprocessing.load_trial_level_events_data(
                    gaze,
                    sess.sid,
                    event_type=settings.FIXATION,
                    file_pattern=None,
                )
                gaze = preprocessing.load_trial_level_events_data(
                    gaze,
                    sess.sid,
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
                    f"Fixations missing for {sess.sid}. Skipping AOI mapping/scanpaths."
                )
            else:
                preprocessing.map_fixations_to_aois(
                    gaze,
                    sess.stimuli,
                )
                preprocessing.save_scanpaths(sess.sid, gaze)

                preprocessing.save_session_metadata(sess.sid, gaze)

        rm_folder = sess.sid.reading_measures_dir

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
                    f"Gaze/Event data missing or not mapped for {sess.sid}. Skipping reading measures."
                )
            elif rm_folder.exists() and not settings.OVERWRITE:
                # check if the folder contains the expected number of files, if not, we will overwrite
                num_expected_files = len(sess.completed_stimuli_ids)
                num_files = len(list(rm_folder.glob("*.csv")))
                if num_expected_files != num_files:
                    raise ValueError(
                        f"Reading measures cannot be loaded as the folder for session {sess.sid} does not contain the "
                        f"expected number of files. Please check and select overwrite."
                    )

                pbar.set_description(f"Loading reading measures {sess.sid}:")
                reading_measures = preprocessing.load_reading_measures(sess.sid)

                data_collection[sess.session_identifier].reading_measures = True

            else:
                pbar.set_description(f"Calculating reading measures {sess.sid}:")
                reading_measures = preprocessing.calculate_reading_measures(
                    gaze,
                    sess.stimuli,
                )

                preprocessing.save_reading_measures(sess.sid, reading_measures)
                data_collection[sess.session_identifier].reading_measures = True
        else:
            pbar.set_description(f"Skipping reading measures {sess.sid}:")

        # === COMPREHENSION QUESTION ANSWERS ===
        if settings.RUN_COMPREHENSION_ANSWERS:
            answers_csv = sess.sid.answers_dir / f"{sess.sid}_answers.csv"

            if answers_csv.exists() and not settings.OVERWRITE:
                pbar.set_description(f"Loading comprehension answers {sess.sid}")
                sess.answers = True
            else:
                pbar.set_description(f"Collecting comprehension answers {sess.sid}")
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
            pbar.set_description(f"Skipping comprehension answers {sess.sid}:")

        if settings.RUN_SANITY_CHECKS:
            if gaze is None:
                logger.warning(
                    f"Gaze data missing for {sess.sid}. Skipping sanity report."
                )
            else:
                pbar.set_description(f"Creating sanity check report {sess.sid}")
                data_collection.create_sanity_check_report(
                    gaze,
                    sess.session_identifier,
                    plotting=True,
                    overwrite=True,
                    output_dir=settings.OUTPUT_DIR,
                )
        else:
            pbar.set_description(f"Skipping sanity checks {sess.sid}:")

        data_collection.create_session_overview(
            sess.session_identifier, path=settings.OUTPUT_DIR
        )

    data_collection.create_dataset_overview(path=settings.OUTPUT_DIR)
    data_collection.parse_participant_data(settings.OUTPUT_DIR / "participant_data.csv")

    if settings.RUN_PSYCHOMETRIC_TESTS:
        logger.info("Processing psychometric tests...")
        from ..psychometric_tests.preprocess_psychometric_tests import (
            preprocess_all_sessions,
        )

        preprocess_all_sessions(settings.PSYCHOMETRIC_TESTS_DIR)


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
