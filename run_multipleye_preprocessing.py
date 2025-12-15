import argparse
from pathlib import Path

from tqdm import tqdm

from preprocessing import peyepeline
from preprocessing.data_collection.multipleye_data_collection import MultipleyeDataCollection
from preprocessing.utils.prepare_language_folder import prepare_language_folder
from preprocessing import config


def run_multipleye_preprocessing(data_collection: str):
    prepare_language_folder(data_collection)

    this_repo = Path().resolve()
    data_folder_path = this_repo / "data" / data_collection_name

    multipleye = MultipleyeDataCollection.create_from_data_folder(data_folder_path, include_pilots=True)

    preprocessed_data_folder = this_repo / "preprocessed_data" / data_collection_name
    preprocessed_data_folder.mkdir(parents=True, exist_ok=True)

    sessions = [s for s in multipleye]

    for sess in (pbar := tqdm(sessions)):
        idf = sess.session_identifier
        # this is a bit of a hack to make the session names consistent for the file names as the multipleye
        # session names contain infos when it was restarted
        session_save_name = idf.split("_")[:5]
        session_save_name = "_".join(session_save_name)

        pbar.set_description(f'Preprocessing session {idf}:')

        asc = sess.asc_path
        output_folder = preprocessed_data_folder / idf
        output_folder.mkdir(parents=True, exist_ok=True)

        # create or load raw data
        raw_data_folder = output_folder / "raw_data"
        if raw_data_folder.exists():
            pbar.set_description(f'Loading samples {idf}:')
            gaze = peyepeline.load_trial_level_raw_data(
                raw_data_folder,
                trial_columns=config.TRIAL_COLS,
                metadata_path=output_folder,
            )

        else:
            pbar.set_description(f'Extracting samples {idf}:')
            gaze = peyepeline.load_gaze_data(
                asc_file=asc,
                lab_config=sess.lab_config,
                session_idf=idf,
                trial_cols=config.TRIAL_COLS,
            )
            peyepeline.save_raw_data(raw_data_folder, session_save_name, gaze)
            peyepeline.save_session_metadata(gaze, output_folder)

        sess.pm_gaze_metadata = gaze._metadata
        sess.calibrations = gaze.calibrations
        sess.validations = gaze.validations

        # preprocess gaze data
        pbar.set_description(f'Preprocessing samples {idf}:')
        peyepeline.preprocess_gaze(
            gaze,
        )

        # create or load fixation data
        fixation_data_folder = output_folder / "fixations"
        saccade_data_folder = output_folder / "saccades"
        if fixation_data_folder.exists():
            pbar.set_description(f'Loading events {idf}:')
            gaze = peyepeline.load_trial_level_events_data(
                gaze,
                fixation_data_folder,
                event_type='fixation',
                file_pattern=r".+_(?P<trial>(?:PRACTICE_)?trial_\d+)_(?P<stimulus>[^_]+_[^_]+_\d+)_fixation.csv"
            )

            gaze = peyepeline.load_trial_level_events_data(
                gaze,
                saccade_data_folder,
                event_type='saccade',
                file_pattern=r".+_(?P<trial>(?:PRACTICE_)?trial_\d+)_(?P<stimulus>[^_]+_[^_]+_\d+)_saccade.csv"
            )

        else:
            pbar.set_description(f'Detecting events {idf}:')

            peyepeline.detect_fixations(gaze)
            peyepeline.detect_saccades(gaze)

            peyepeline.save_events_data(
                'fixation',
                fixation_data_folder,
                session_save_name,
                'trial',
                ['trial', 'stimulus'],
                ["onset", "duration", "location_x", "location_y", "page"],
                gaze,
            )

            peyepeline.save_events_data(
                'saccade',
                saccade_data_folder,
                session_save_name,
                'trial',
                ['trial', 'stimulus'],
                ["onset", "duration", "amplitude", "peak_velocity", "dispersion", "page"],
                gaze,
            )

        # map to AOIs and create scanpaths
        peyepeline.map_fixations_to_aois(
            gaze,
            sess.stimuli,
        )
        peyepeline.save_scanpaths(output_folder / 'scanpaths', session_save_name, gaze)

        peyepeline.save_session_metadata(gaze, output_folder)

        # perform the multipleye specific stuff
        multipleye.create_session_overview(sess.session_identifier, path=output_folder)
        pbar.set_description(f'Creating sanity check report {idf}')
        multipleye.create_sanity_check_report(gaze, sess.session_identifier, plotting=True, overwrite=True)

    multipleye.create_dataset_overview(path=preprocessed_data_folder)
    multipleye.parse_participant_data(preprocessed_data_folder / "participant_data.csv")


def parse_args():
    parser = argparse.ArgumentParser()



if __name__ == '__main__':
    parse_args()

    data_collection_name = 'MultiplEYE_PL_PL_Warsaw_1_2025'
    run_multipleye_preprocessing(data_collection_name)
