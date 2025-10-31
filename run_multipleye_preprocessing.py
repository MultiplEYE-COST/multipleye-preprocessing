import argparse
from pathlib import Path

from tqdm import tqdm

from prepare_language_folder import prepare_language_folder
from preprocessing import peyepeline
from preprocessing.data_collection.multipleye_data_collection import MultipleyeDataCollection


def run_multipleye_preprocessing(data_collection: str):
    prepare_language_folder(data_collection)

    this_repo = Path().resolve()
    data_folder_path = this_repo / "data" / data_collection_name

    multipleye = MultipleyeDataCollection.create_from_data_folder(data_folder_path)

    preprocessed_data_folder = this_repo / "preprocessed_data" / data_collection_name
    preprocessed_data_folder.mkdir(parents=True, exist_ok=True)

    sessions = [s for s in multipleye]

    for sess in (pbar := tqdm(sessions[:3])):
        idf = sess.session_identifier
        pbar.set_description(f'Preprocessing session {idf}:')

        asc = sess.asc_path
        output_folder = preprocessed_data_folder / idf
        output_folder.mkdir(parents=True, exist_ok=True)

        # TODO pm: it would make a lot more sense if the gaze object was not called gaze but instead session or
        #  something like that. Because ET preprocessing works on the session level and it is odd that there is no session
        gaze = peyepeline.load_gaze_data(
            asc_file=asc,
            lab_config=sess.lab_config,
            session_idf=idf,
            output_dir=output_folder,
            save=True
        )

        peyepeline.preprocess_gaze_data(
            gaze,
            output_dir=output_folder,
            save=True,
            session_idf=idf,
        )

        peyepeline.map_fixations_to_aois(
            gaze,
            idf,
            sess.stimuli,
            save=True,
            output_dir=output_folder,
        )

        multipleye.create_session_overview(sess.session_identifier, path=output_folder)


    multipleye.create_dataset_overview(path=preprocessed_data_folder)



def parse_args():
    parser = argparse.ArgumentParser()


if __name__ == '__main__':
    parse_args()

    data_collection_name = 'MultiplEYE_SQ_CH_Zurich_1_2025'
    run_multipleye_preprocessing(data_collection_name)