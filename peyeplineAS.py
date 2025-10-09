import pymovements as pm
from pathlib import Path
from pymovements.dataset.dataset_files import load_gaze_file
from pymovements.dataset.dataset_definition import DatasetDefinition
from pymovements.gaze import Gaze
from typing import Any
from polars import DataFrame
# from pymovements.gaze.Gaze import compute_event_properties


def create_gaze_frame(raw_file: str, save=True) -> pm.Gaze:
    """
    Parses the gaze samples (i.e. x-y-coordinates and timestamps) from the raw eye-tracking data file.
    :param raw_file: In case of EyeLink experiments this is an asc file. For Tobii a TSV file.
    At the moment only works for EyeLink.
    :param save: If True, the gaze data will be saved as a pickle (=TBD, does pm have this????) file in the same folder as the raw file.
    :return: A pymovements Gaze object containing the gaze data and metadata.
    """
    # TODO: figure out if pm can save gaze data?
    # TODO: what to do about the metadata argument? create a function to properly access it? getter?
    # print file path
    print(f"Parsing raw file: {raw_file}")
    file_path = Path(raw_file)

    # def load_gaze_file(filepath: Path, fileinfo_row: dict[str, Any], definition: DatasetDefinition, preprocessed: bool=False) -> Gaze

    #  metadata_patterns: list[dict[str, Any] | str] | None
    #     List of patterns to match for extracting metadata from custom logged messages.
    #     (default: None)

    gaze = load_gaze_file(
        file_path, {'load_function': 'from_asc', 'load_kwargs': {}}, 'definition': DatasetDefinition(), 'preprocessed': False)
    # {'metadata_patterns': []}
    # print the first 5 rows of the gaze data
    # from tutorial: Every Gaze has some samples with six columns (check Gaze/samples): [time, stimuli_x, stimuli_y, text_id, page_id, pixel].
    # but we have 4 columns: time, pupil, preprocessed, pixel
    print(type(gaze))
    print(gaze.samples.head())
    # print the metadata
    print(gaze.experiment)

    if save:
        # save gaze data as pickle file in the working folder
        gaze.save(file_path.with_suffix(".pkl"), save_experiment=True)
    return gaze


gaze = create_gaze_frame(
    "data/MultiplEYE_SQ_CH_Zurich_1_2025/eye-tracking-sessions/006_SQ_CH_1_ET1/006sqch1.asc", save=True)


def calculate_fixations(gaze: pm.Gaze):
    # TODO: figure out how to use pymovements algorithms to calculate fixations

    #     properties = Gaze.compute_event_properties(
    #         gaze, event_properties=['amplitude', 'dispersion', 'disposition', 'duration', 'location', 'peak_velocity'])
    #   File "/Users/anastassiashaitarova/Documents/postdoc-life/openEye/pymovements/src/pymovements/gaze/gaze.py", line 1100, in compute_event_properties
    #     raise ValueError(
    #     ...<2 lines>...
    #     )
    # ValueError: The following event properties already exist and cannot be recomputed: {'duration'}. Please remove them first.

    # properties = Gaze.compute_event_properties(
    #     gaze, event_properties=['amplitude', 'dispersion', 'disposition', 'location', 'peak_velocity'])
    # print(f"Detected properties: {properties}")
    print(gaze.events.frame)

    gaze.pix2deg()
    gaze.pos2vel('smooth')
    print(gaze.samples.head())


calculate_fixations(gaze)


def calculate_saccades(gaze: pm.Gaze):
    pass


def map_fixations_to_aois():
    """
    The aoi files are stored in the data collection. They are the same for each participant. Excpet for the question answer options.
    :return:
    """
    pass
