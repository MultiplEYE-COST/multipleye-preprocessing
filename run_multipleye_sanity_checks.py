import argparse
import logging
from pathlib import Path

from preprocessing.data_collection.multipleye_data_collection import MultipleyeDataCollection


def run_multipleye_sanity_checks(data_collection_name: str, full_path: str = None, create_plots: bool = True,
                                 include_pilots: bool = False, split: bool = False):
    if full_path is None:
        this_repo = Path().resolve()
        data_folder_path = this_repo / "data" / data_collection_name
    else:
        if full_path.endswith(data_collection_name):
            data_folder_path = Path(full_path)
        else:
            data_folder_path = Path(full_path) / data_collection_name

    if split:
        split = 'split'
    else:
        split = 'all'

    logging.basicConfig(level=logging.INFO, filename=data_folder_path / 'sanity_checks_logfile.log')
    multipleye = MultipleyeDataCollection.create_from_data_folder(str(data_folder_path), include_pilots=include_pilots,
                                                                  different_stimulus_names=split
                                                                  )

    multipleye.create_sanity_check_report(plotting=create_plots)


def parse_args():
    parser = argparse.ArgumentParser(description='Run multipleye preprocessing on an experiment file')

    parser.add_argument(
        'data_collection_name',
        type=str,
        help='Name of the folder containing the data collection. E.g. "MultiplEYE_ET_EE_Tartu_1_2022". '
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
        '--split',
        action='store_true',
        help='If set, this means that the data collection contains sessions that are split into multiple parts. ',
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
