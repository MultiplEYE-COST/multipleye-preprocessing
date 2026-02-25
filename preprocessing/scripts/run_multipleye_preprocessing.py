import os
from argparse import ArgumentParser

from tqdm import tqdm

import preprocessing
from preprocessing import settings


def run_multipleye_preprocessing(config_path: str | None = None):
    settings.load(config_path)

    data_collection_name = settings.DATA_COLLECTION_NAME
    print(
        f"Running MultiplEYE preprocessing for data collection: {data_collection_name}"
    )

    preprocessing.utils.prepare_language_folder(data_collection_name)

    data_folder_path = settings.DATASET_DIR

    if not os.path.exists(data_folder_path):
        raise FileNotFoundError(
            f"Data folder {data_folder_path} does not exist. Please make sure to download the data and place it in the correct folder. "
            f"And check if you have filled in the correct data collection name in the settings."
        )

    multipleye = (
        preprocessing.data_collection.MultipleyeDataCollection.create_from_data_folder(
            data_folder_path,
            include_pilots=settings.INCLUDE_PILOTS,
            excluded_sessions=settings.EXCLUDE_SESSIONS,
            included_sessions=settings.INCLUDE_SESSIONS,
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
        output_folder = settings.OUTPUT_DIR / idf
        output_folder.mkdir(parents=True, exist_ok=True)

        # create or load raw data
        raw_data_folder = output_folder / settings.RAW_DATA_FOLDER
        if raw_data_folder.exists():
            pbar.set_description(f"Loading samples {idf}:")
            gaze = preprocessing.load_trial_level_raw_data(
                raw_data_folder,
                trial_columns=settings.TRIAL_COLS,
                metadata_path=output_folder,
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
            preprocessing.save_session_metadata(settings.OUTPUT_DIR, idf, gaze)

        sess.pm_gaze_metadata = gaze._metadata
        sess.calibrations = gaze.calibrations
        sess.validations = gaze.validations

        # preprocess gaze data
        pbar.set_description(f"Preprocessing samples {idf}:")
        preprocessing.preprocess_gaze(
            gaze,
        )

        # create or load fixation data
        fixation_data_folder = output_folder / settings.FIXATIONS_FOLDER
        saccade_data_folder = output_folder / settings.SACCADES_FOLDER
        if fixation_data_folder.exists():
            pbar.set_description(f"Loading events {idf}:")
            gaze = preprocessing.load_trial_level_events_data(
                gaze,
                fixation_data_folder,
                event_type=settings.FIXATION,
                file_pattern=None,
            )

            gaze = preprocessing.load_trial_level_events_data(
                gaze,
                saccade_data_folder,
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

        preprocessing.save_session_metadata(settings.OUTPUT_DIR, idf, gaze)

        # perform the multipleye specific stuff
        multipleye.create_session_overview(
            sess.session_identifier, path=settings.OUTPUT_DIR
        )
        pbar.set_description(f"Creating sanity check report {idf}")
        multipleye.create_sanity_check_report(
            gaze,
            sess.session_identifier,
            plotting=True,
            overwrite=True,
            output_dir=settings.OUTPUT_DIR,
        )

    multipleye.create_dataset_overview(path=settings.OUTPUT_DIR)
    multipleye.parse_participant_data(settings.OUTPUT_DIR / "participant_data.csv")


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
    run_multipleye_preprocessing(args.config_path)


if __name__ == "__main__":
    main()
