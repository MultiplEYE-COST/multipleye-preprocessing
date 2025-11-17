import argparse
import logging
import warnings
from pathlib import Path

from tqdm import tqdm

from preprocessing.data_collection.multipleye_data_collection import MultipleyeDataCollection
from preprocessing.utils.prepare_language_folder import prepare_language_folder


def run_multipleye_sanity_checks(data_collection_name: str):

    prepare_language_folder(data_collection_name)

    this_repo = Path().resolve()
    data_folder_path = this_repo / "data" / data_collection_name

    multipleye = MultipleyeDataCollection.create_from_data_folder(data_folder_path, include_pilots=True)

    sanity_checks_folder = this_repo / "sanity_checks" / data_collection_name
    sanity_checks_folder.mkdir(parents=True, exist_ok=True)

    sessions = [s for s in multipleye]

    for sess in (pbar := tqdm(sessions)):
        idf = sess.session_identifier
        pbar.set_description(f'Creating sanity checks for {idf}:')





    if len(multipleye.excluded_sessions) >= 1:
        warnings.warn(f"Don't forget, those sessions have been excluded from the analysis: {multipleye.excluded_sessions}. "
                      f"Specified 'excluded_sessions.txt'.")


def parse_args():
    parser = argparse.ArgumentParser(description='Run multipleye preprocessing on an experiment file')

    parser.add_argument(
        'data_collection_name',
        type=str,
        help='Name of the folder containing the data collection. E.g. "MultiplEYE_SQ_CH_Zurich_1_2025". '
             'The folder should be located in the "data" directory of this repository. '
             'Otherwise, specify the full path using --full-path.',
    )

    parser.add_argument(
        '--include_pilots',
        action='store_true',
        help='If set, the sanity check will include pilot sessions.',
        default=False,
    )

    parser.add_argument(
        '--full_path',
        type=str,
        help='Full path to the multipleye data folder. E.g. "Users/alice/preprocessing/data"',
    )

    parser.add_argument(
        '--create_plots',
        action='store_true',
        help='If set, the sanity check report will include plots.',
        default=False,
    )

    # TODO: possibly use a yaml config such that it can be easily adapted
    # parser.add_argument(
    #     '--config', '-c',
    #     type=str,
    #     default='config.yaml',
    #     help='Path to the config file, containing the quality thresholds for the report.'
    # )

    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()

    run_multipleye_sanity_checks(**vars(args))
