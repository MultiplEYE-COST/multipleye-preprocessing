import pymovements as pm
from pathlib import Path
from pymovements.gaze import Gaze
from pymovements.gaze.io import from_asc
import polars as pl

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
    print(f"Parsing raw file: {raw_file}")

    gaze = from_asc(
        file=raw_file,
        events=True
    )

    # Set screen parameters for degrees of visual angle conversion
    # a must-have in order to convert pixels to degrees of visual angle
    gaze.experiment.screen.distance_cm = 60
    gaze.experiment.screen.height_cm = 28
    gaze.experiment.screen.width_cm = 37

    print(gaze.samples.head())

    # print the metadata
    print(gaze.experiment)

    if save:
        # save gaze data as pickle file in the working folder
        gaze.save(Path(raw_file).with_suffix(".pkl"), save_experiment=True)
    return gaze


gaze = create_gaze_frame(
    "data/MultiplEYE_SQ_CH_Zurich_1_2025/eye-tracking-sessions/006_SQ_CH_1_ET1/006sqch1.asc", save=True)


def calculate_fixations(gaze: pm.Gaze):
    # TODO: figure out how to use pymovements algorithms to calculate fixations

    print()
    print('Print gaze.events.frame:')
    print('# This gaze has parsed events (recorded by the eye tracker during acquisition), not recomputed from samples by PyMovements #')
    print(gaze.events.frame)
    print('Print gaze.samples:')
    print(gaze.samples.head())

    gaze.pix2deg()
    gaze.pos2vel('smooth')

    print('Newly computed fixations:')
    print()
    # recompute events (e.g. with IVT), produces fixations
    gaze.detect(method="ivt", velocity_threshold=30)
    fixations_ivt = gaze.events.frame.filter(pl.col("name") == "fixation")
    print(fixations_ivt.head())


calculate_fixations(gaze)


def calculate_saccades(gaze: pm.Gaze):
    pass


def map_fixations_to_aois():
    """
    The aoi files are stored in the data collection. They are the same for each participant. Excpet for the question answer options.
    :return:
    """
    pass
