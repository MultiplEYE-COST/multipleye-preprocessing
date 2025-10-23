import pymovements as pm
from pathlib import Path
from pymovements.gaze.io import from_asc
import polars as pl
from pymovements.stimulus.text import from_file


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

    # ### Gaze.save() ####

    # def save(
    #     self,
    #     dirpath: str | Path,
    #     *,
    #     save_events: bool | None = None,
    #     save_samples: bool | None = None,
    #     save_experiment: bool | None = None,
    #     verbose: int = 1,
    #     extension: str = 'feather',
    # ) -> Gaze:
    #     """Save data from the Gaze object in the provided directory.

    #     Depending on parameters it may save three files:
    #     * preprocessed gaze in samples (samples)
    #     * calculated gaze events (events)
    #     * metadatata experiment in YAML file (experiment).

    #     Data will be saved as feather or csv files.

    #     Verbosity level (0: no print output, 1: show progress bar, 2: print saved filepaths)

    if save:
        gaze.save(Path(raw_file).parent, save_events=True,
                  save_samples=True, save_experiment=True, extension='feather')
        # more human-readable csv format
        gaze.save(Path(raw_file).parent, save_events=True,
                  save_samples=True, save_experiment=True, extension='csv', verbose=1)

        # there is no built-in pickle save function in pymovements
        # gaze.save(Path(raw_file).with_suffix(".pkl"), save_experiment=True)

    return gaze


def calculate_fixations(gaze: pm.Gaze):
    # TODO: figure out how to use pymovements algorithms to calculate fixations

    print()
    print('Print gaze.events.frame:')
    print('# This gaze has parsed events (recorded by the eye tracker during acquisition), not recomputed from samples by PyMovements #')
    print(gaze.events.frame)
    print('Print gaze.samples:')
    print(gaze.samples.head())

    gaze.pix2deg()
    # Compute gaze positions in degrees of visual angle from pixel position coordinates.
    # This method requires a properly initialized :py:attr:`~.Gaze.experiment` attribute.
    # After success, :py:attr:`~.Gaze.samples` is extended by the resulting dva position columns.

    gaze.pos2vel('smooth')
    # Compute gaze velocity in dva/s from dva position coordinates.
    # This method requires a properly initialized :py:attr:`~.Gaze.experiment` attribute.
    # After success, :py:attr:`~.Gaze.samples` is extended by the resulting velocity columns.

    # Parameters
    # ----------
    # method: str
    #     Computation method. See :func:`~transforms.pos2vel()` for details, default: fivepoint.
    #     (default: 'fivepoint')
    # **kwargs: int | float | str
    #     Additional keyword arguments to be passed to the :func:`~transforms.pos2vel()` method.

    print('Newly computed fixations:')
    print()

    # recompute events (e.g. with IVT), produces fixations
    gaze.detect(method="ivt", velocity_threshold=30, name="fixation.ivt")

    # Detect events by applying a specific event detection method.

    # Parameters
    # ----------
    # method: Callable[..., pm.Events] | str
    #     The event detection method to be applied.
    # eye: str
    #     Select which eye to choose. Valid options are ``auto``, ``left``, ``right`` or ``None``.
    #     If ``auto`` is passed, eye is inferred in the order ``['right', 'left', 'eye']`` from
    #     the available columns in :py:attr:`~.Gaze.samples`. (default: 'auto')
    # clear: bool
    #     If ``True``, event DataFrame will be overwritten with new DataFrame instead of being
    #     merged into the existing one. (default: False)
    # **kwargs: Any
    #     Additional keyword arguments to be passed to the event detection method.

    fixations_ivt = gaze.events.frame.filter(pl.col("name") == "fixation.ivt")
    print(fixations_ivt.head())

    return gaze


def calculate_saccades(gaze: pm.Gaze):

    print()
    print('Print gaze.events.frame before microsaccade detection:')
    print(gaze.events.frame)
    gaze.detect('microsaccades', minimum_duration=12)
    print(gaze.events.frame.filter(pl.col("name") == "microsaccades").head())

    return gaze


def map_fixations_to_aois(gaze: pm.Gaze):
    """
    The aoi files are stored in the data collection. They are the same for each participant. Excpet for the question answer options.
    :return:
    """

    aoi_chars_file = "data/MultiplEYE_SQ_CH_Zurich_1_2025/eye-tracking-sessions/data_piloting_stimuli_MultiplEYE_SQ_CH_Zurich_1_2025participant_id_1_to_5/aoi_stimuli_sq_ch_1/lit_magicmountain_6_aoi.csv"

    stimulus = from_file(
        aoi_path=aoi_chars_file,
        aoi_column="char",
        start_x_column="top_left_x",
        start_y_column="top_left_y",
        width_column="width",
        height_column="height",
        page_column="page",
    )

    print(stimulus.aois.head(10))

    # row = {"x": 160.0, "y": 95.0}  # somewhere over the word "Magjik"
    # aoi = stimulus.get_aoi(row=row, x_eye="x", y_eye="y")
    # print(aoi)

    #  We map each gaze point to an aoi, considering the boundary still part of the area of interest.

    # Parameters
    # ----------
    # aoi_dataframe: pm.stimulus.TextStimulus
    #     Area of interest dataframe.
    # eye: str
    #     String specificer for inferring eye components. Supported values are: auto, mono, left
    #     right, cyclops. Default: auto.
    # gaze_type: str
    #     String specificer for whether to use position or pixel coordinates for
    #     mapping. Default: pixel.

    gaze.map_to_aois(
        aoi_dataframe=stimulus,
        eye="auto",
        gaze_type="pixel"
    )


gaze = create_gaze_frame(
    "data/MultiplEYE_SQ_CH_Zurich_1_2025/eye-tracking-sessions/006_SQ_CH_1_ET1/006sqch1.asc", save=True)

gaze_fixation = calculate_fixations(gaze)

gaze_saccades = calculate_saccades(gaze_fixation)

map_fixations_to_aois(gaze_saccades)
