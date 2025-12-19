from pathlib import Path

from tqdm import tqdm

import preprocessing
from preprocessing.data_collection.merid_data_collection import Merid
from preprocessing.scripts.prepare_language_folder import prepare_language_folder


def run_multipleye_preprocessing(data_collection: str):
    prepare_language_folder(data_collection)

    this_repo = Path().resolve()
    data_folder_path = this_repo / "data" / data_collection_name

    merid = Merid.create_from_data_folder(data_folder_path)

    preprocessed_data_folder = this_repo / "preprocessed_data" / data_collection_name
    preprocessed_data_folder.mkdir(parents=True, exist_ok=True)

    sessions = [s for s in merid]

    for sess in (pbar := tqdm(sessions)):
        idf = sess.session_identifier
        pbar.set_description(f"Preprocessing session {idf}:")

        asc = sess.asc_path
        output_folder = preprocessed_data_folder / idf
        output_folder.mkdir(parents=True, exist_ok=True)

        # TODO pm: it would make a lot more sense if the gaze object was not called gaze but instead session or
        #  something like that. Because ET preprocessing works on the session level and it is odd that there is no session
        gaze, gaze_metadata = preprocessing.create_gaze_data(  # unavailable
            asc_file=asc,
            lab_config=sess.lab_config,
            session_idf=idf,
        )
        preprocessing.save_raw_data(
            output_folder / "raw_data", sess.session_identifier, gaze
        )

        sess.pm_gaze_metadata = gaze_metadata

        preprocessing.detect_fixations(
            gaze,
        )

        preprocessing.detect_saccades(
            gaze,
        )
        # note that saccades are not yet saved
        preprocessing.save_events_data(
            output_folder / "fixations", sess.session_identifier, gaze
        )

        preprocessing.map_fixations_to_aois(
            gaze,
            sess.stimuli,
        )
        preprocessing.save_scanpaths(
            output_folder / "scanpaths", sess.session_identifier, gaze
        )

        preprocessing.save_session_metadata(gaze, output_folder)
        merid.create_session_overview(sess.session_identifier, path=output_folder)

    merid.create_dataset_overview(path=preprocessed_data_folder)


if __name__ == "__main__":
    data_collection_name = "MultiplEYE_ZH_CH_Zurich_1_2025"
    run_multipleye_preprocessing(data_collection_name)
