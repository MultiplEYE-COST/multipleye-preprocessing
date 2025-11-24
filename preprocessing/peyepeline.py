import json
import re
from pathlib import Path

import polars as pl
import pymovements as pm
import yaml
from pymovements.stimulus import TextStimulus

from preprocessing.data_collection.stimulus import LabConfig, Stimulus

DEFAULT_EVENT_PROPERTIES = {
    "fixation": [
        ("location", {"position_column": "pixel"}),
        ("dispersion", {}),
    ],
    "saccade": [
        ("amplitude", {}),
        ("peak_velocity", {}),
        ("dispersion", {}),
    ],
}


def load_gaze_data(
        asc_file: Path,
        lab_config: LabConfig,
        session_idf: str,
        trial_cols: list[str] = None,
) -> pm.Gaze:
    """

    :param trial_cols:
    :param gaze_path: if a gaze_path is provided, the function will try to load the gaze data from there
    :param asc_file:
    :param lab_config:
    :param session_idf:
    :return:
    """

    gaze = pm.gaze.from_asc(
        asc_file,
        patterns=[
            r"start_recording_(?P<trial>(?:PRACTICE_)?trial_\d+)_stimulus_(?P<stimulus>[^_]+_[^_]+_\d+)_(?P<page>.+)",
            r"start_recording_(?P<trial>(?:PRACTICE_)?trial_\d+)_(?P<page>familiarity_rating_screen_\d+|subject_difficulty_screen)",
            {"pattern": r"stop_recording_", "column": "trial", "value": None},
            {"pattern": r"stop_recording_", "column": "page", "value": None},
            {
                "pattern": r"start_recording_(?:PRACTICE_)?trial_\d+_stimulus_[^_]+_[^_]+_\d+_page_\d+",
                "column": "activity",
                "value": "reading",
            },
            {
                "pattern": r"start_recording_(?:PRACTICE_)?trial_\d+_stimulus_[^_]+_[^_]+_\d+_question_\d+",
                "column": "activity",
                "value": "question",
            },
            {
                "pattern": r"start_recording_(?:PRACTICE_)?trial_\d+_(familiarity_rating_screen_\d+|subject_difficulty_screen)",
                "column": "activity",
                "value": "rating",
            },
            {"pattern": r"stop_recording_", "column": "activity", "value": None},
            {
                "pattern": r"start_recording_PRACTICE_trial_",
                "column": "practice",
                "value": True,
            },
            {
                "pattern": r"start_recording_trial_",
                "column": "practice",
                "value": False,
            },
            {"pattern": r"stop_recording_", "column": "practice", "value": None},
        ],
        trial_columns=trial_cols,
        add_columns={'session': session_idf},
    )

    # Filter out data outside of trials
    # TODO: Also report time spent outside of trials
    gaze.frame = gaze.frame.filter(
        pl.col("trial").is_not_null() & pl.col("page").is_not_null()
    )

    # Extract metadata from stimulus config and ASC file
    gaze.experiment = pm.Experiment(
        sampling_rate=gaze._metadata["sampling_rate"],
        screen_width_px=lab_config.image_resolution[0],
        screen_height_px=lab_config.image_resolution[1],
        screen_width_cm=lab_config.image_size_cm[0],
        screen_height_cm=lab_config.image_size_cm[1],
        distance_cm=lab_config.screen_distance_cm,
    )

    return gaze


def save_gaze_data(
        gaze: pm.Gaze,
        gaze_path: Path = '',
        events_path: Path = '',
        metadata_dir: Path = '',
) -> None:
    # TODO save metadata properly and also load it properly

    if gaze_path:
        gaze.save_samples(path=gaze_path)
    if events_path:
        gaze.save_events(path=events_path)
    if metadata_dir:
        # TODO pm: this saves the experiment metadata, but there is a lot more metadata as a gaze property,
        #  this should also be saved
        gaze.save(dirpath=metadata_dir, save_events=False, save_samples=False)

        # TODO pm,
        #  why can I only save the gaze metadata through this method?
        metadata = gaze._metadata
        metadata['datetime'] = str(metadata['datetime'])
        # TODO pm: I'd like to save my metadata without having to access a protected argument
        with open(metadata_dir / "gaze_metadata.json", "w", encoding='utf8') as f:
            json.dump(metadata, f)


def detect_fixation_and_saccades(
        gaze: pm.Gaze,
        sg_window_length: int = 50,
        sg_degree: int = 2,
) -> None:
    # Savitzky-Golay filter as in https://doi.org/10.3758/BRM.42.1.188

    window_length = round(
        gaze.experiment.sampling_rate / 1000 * sg_window_length)

    if window_length % 2 == 0:  # Must be odd
        window_length += 1

    gaze.pix2deg()
    gaze.pos2vel("savitzky_golay",
                 window_length=window_length, degree=sg_degree)

    # TODO pm: I think the problem here is that is is not clear what ivt is.. it is very hidden, what happens
    #  and for people that are not familiar with ET preprocessing, they also cannot learn anything as it says not
    #  explicitely that this is about fixations
    gaze.detect("ivt")
    gaze.detect("microsaccades")

    for property, kwargs, event_name in [
        ("location", dict(position_column="pixel"), "fixation"),
        ("amplitude", dict(), "saccade"),
        ("peak_velocity", dict(), "saccade"),
        ("dispersion", dict(), "saccade"),
        ("dispersion", dict(), "fixation"),
    ]:
        processor = pm.EventGazeProcessor((property, kwargs))
        new_properties = processor.process(
            gaze.events,
            gaze,
            identifiers=gaze.trial_columns,
            name=event_name,
        )
        join_on = gaze.trial_columns + ["name", "onset", "offset"]
        gaze.events.add_event_properties(new_properties, join_on=join_on)


def preprocess_gaze(
        gaze: pm.Gaze,
        method: str = "savitzky_golay",
        window_ms: int = 50,
        poly_degree: int = 2,
) -> None:
    """
    Convert gaze samples from pixel coordinates to degrees of visual angle (dva),
    and compute velocity for event detection.

    Parameters
    ----------
    gaze : pm.Gaze
        The gaze object containing raw gaze samples.

    method : {"preceding", "neighbors", "fivepoint", "smooth", "savitzky_golay"}, optional
        Velocity estimation method. Default is ``"savitzky_golay"``.

    window_ms : int, optional
        Length of the smoothing/differentiation window in milliseconds.
        Only used when ``method="savitzky_golay"``.
        Default is 50 ms.

    poly_degree : int, optional
        Polynomial degree used in the Savitzky–Golay filter (default = 2).

    Notes
    -----
    This function should be called **before** detecting fixations or saccades,
    since event detection relies on the velocity signal.

    Available velocity estimation methods:
      - ``preceding``: difference between current and previous sample.
      - ``neighbors``: difference between next and previous sample.
      - ``fivepoint``: mean of two preceding and two following samples.
      - ``smooth``: alias of ``fivepoint``.
      - ``savitzky_golay``: fits a local polynomial using a sliding window.
    """
    # Savitzky-Golay filter as in https://doi.org/10.3758/BRM.42.1.188
    window_length = round(gaze.experiment.sampling_rate / 1000 * window_ms)
    if window_length % 2 == 0:
        window_length += 1

    gaze.pix2deg()
    gaze.pos2vel(method, window_length=window_length, degree=poly_degree)


def compute_event_properties(
        gaze: pm.Gaze,
        event_name: str,
        properties: list[tuple[str, dict]],
) -> None:
    """
    Compute and add event properties to `gaze.events`.

    Parameters
    ----------
    gaze : pm.Gaze
        Gaze object containing detected events.
    event_name : str
        Event type ('fixation', 'saccade', ...).
    properties : list[tuple[str, dict]]
        Each tuple defines (property_name, kwargs) passed to EventGazeProcessor.
    """
    join_on = gaze.trial_columns + ["name", "onset", "offset"]

    for prop_name, kwargs in properties:
        processor = pm.EventGazeProcessor((prop_name, kwargs))
        new_props = processor.process(
            gaze.events,
            gaze,
            identifiers=gaze.trial_columns,
            name=event_name,
        )
        gaze.events.add_event_properties(new_props, join_on=join_on)


def detect_fixations(
        gaze,
        method: str = "ivt",
        minimum_duration: int = 100,
        velocity_threshold: float = 20.0,
) -> None:
    """
    This function applies a fixation detection method and then computes
    descriptive properties (such as fixation location).

    Parameters
    ----------
    gaze : pm.Gaze
        The gaze object containing gaze samples and trial metadata.

    method : {"ivt", "idt"}, optional
        Event detection method:
        - ``"ivt"`` (Velocity-Threshold Identification):
          Samples are classified as fixations when their velocity is below
          ``velocity_threshold`` degrees/second. Consecutive samples are
          merged into fixation events. This is the default method.
        - ``"idt"`` (Dispersion-Threshold Identification):
          Groups points that remain within a spatial dispersion window for
          at least ``minimum_duration`` ms.

    minimum_duration : int, optional
        Minimum duration (in milliseconds) for a group of samples to be
        classified as a fixation. Default is 100 ms.

    velocity_threshold : float, optional
        Velocity threshold used by the IVT method (in degrees/second).
        Default is 20.0 deg/s.

    Notes
    -----
    After detection, fixation properties (e.g., fixation location) are
    computed and added to ``gaze.events``.
    """
    gaze.detect(method, minimum_duration=minimum_duration,
                velocity_threshold=velocity_threshold)

    compute_event_properties(
        gaze, "fixation", DEFAULT_EVENT_PROPERTIES["fixation"]
    )


def detect_saccades(
        gaze,
        minimum_duration: int = 6,
        threshold_factor: float = 6,
) -> None:
    """
    This function detects saccades (or micro-saccades) using a
    noise-adaptive velocity threshold and then computes properties such as
    saccade amplitude and peak velocity.

    Parameters
    ----------
    gaze : pm.Gaze
        The gaze object containing gaze samples and trial metadata.

    minimum_duration : int, optional
        Minimum duration (in samples) required for a velocity peak to be
        considered a saccade. Default is 6 samples (~12 ms at 500 Hz).
        Shorter events are ignored as noise.

    threshold_factor : float, optional
        Multiplier that determines the velocity threshold relative to the
        noise level in the signal. Increasing this value makes detection
        more conservative (fewer saccades). Default is 6.

    Notes
    -----
    After detection, saccade properties (e.g., amplitude and peak velocity)
    are computed and added to ``gaze.events``.
    """
    gaze.detect("microsaccades", minimum_duration=minimum_duration,
                threshold_factor=threshold_factor)

    compute_event_properties(
        gaze, "saccade", DEFAULT_EVENT_PROPERTIES["saccade"]
    )


def map_fixations_to_aois(
        gaze: pm.Gaze,
        stimuli: list[Stimulus],
) -> None:
    all_aois = pl.DataFrame()
    for stimulus in stimuli:
        aoi = stimulus.text_stimulus.aois
        trial = stimulus.trial_id
        aoi = aoi.with_columns(pl.lit(trial).alias("trial"))
        all_aois = all_aois.vstack(aoi)

    all_aois = TextStimulus(
        all_aois,
        aoi_column="char_idx",
        start_x_column="top_left_x",
        start_y_column="top_left_y",
        width_column="width",
        height_column="height",
        page_column="page",
        trial_column="trial",
    )

    gaze.events.map_to_aois(all_aois, verbose=False)


def save_raw_data(directory: Path, session: str, data: pm.Gaze) -> None:
    directory.mkdir(parents=True, exist_ok=True)

    new_data = data.clone()

    try:
        new_data.unnest()
    except Warning:
        pass

    trials = new_data.split(by="trial", as_dict=False)

    for trial in trials:
        df = trial.frame
        trial = df["trial"][0]
        stimulus = df["stimulus"][0]
        # this is a bit of a hack to make the session names consistent for the file names as the multipleye
        # session names contain infos when it was restarted
        session = session.split("_")[:5]
        session = "_".join(session)
        name = f"{session}_{trial}_{stimulus}_raw_data.csv"
        df = df['time', 'pixel_x', 'pixel_y', 'pupil', 'page']
        df.write_csv(directory / name)


def save_fixation_data(directory: Path, session: str, data: pm.Gaze) -> None:
    directory.mkdir(parents=True, exist_ok=True)

    data.events.unnest()

    # TODO pm save only fixations
    # data.events.frame = data.events.fixations
    fixations = data.events.frame.filter(pl.col("name") == "fixation")

    # trials = data.events.split(by="trial", as_dict=False)

    for group in fixations.partition_by("trial"):
        trial_name = group["trial"][0]
        stimulus = group["stimulus"][0]
        # this is a bit of a hack to make the session names consistent for the file names as the multipleye
        # session names contain infos when it was restarted
        session = session.split("_")[:5]
        session = "_".join(session)

        name = f"{session}_{trial_name}_{stimulus}_fixations.csv"
        df = group.select(["onset", "duration", "location_x", "location_y", "page"])
        df.write_csv(directory / name)


def save_scanpaths(directory: Path, session: str, data: pm.Gaze) -> None:
    directory.mkdir(parents=True, exist_ok=True)

    new_data = data.clone()

    try:
        new_data.unnest()
        new_data.events.unnest()
    except Warning:
        # if the columns are already unnested there is a Warning (which interrupts)
        pass

    trials = new_data.events.split(by="trial", as_dict=False)

    for trial in trials:
        df = trial.frame
        # drop all rows where there has been no aoi mapped
        df = df.filter(pl.col("char_idx").is_not_null())
        if df.is_empty():
            continue
        trial = df["trial"][0]
        stimulus = df["stimulus"][0]
        # this is a bit of a hack to make the session names consistent for the file names as the multipleye
        # session names contain infos when it was restarted
        session = session.split("_")[:5]
        session = "_".join(session)

        name = f"{session}_{trial}_{stimulus}_scanpath.csv"

        df = df[
            'onset', 'duration', 'name', 'location_x', 'location_y', 'char_idx', 'char',
            'top_left_x', 'top_left_y', 'width', 'height', 'char_idx_in_line', 'line_idx',
            'page', 'word_idx', 'word_idx_in_line', 'word']
        df.write_csv(directory / name)


def load_trial_level_raw_data(
        data_folder: Path,
        trial_columns: list[str],
        file_pattern: str = '*_raw_data.csv',
        metadata_path: Path = None,
) -> pm.Gaze:
    regex_name = r".+_(?P<trial>(?:PRACTICE_)?trial_\d+)_(?P<stimulus>[^_]+_[^_]+_\d+)_raw_data"

    initial_df = pl.DataFrame()

    for file in data_folder.glob(file_pattern):
        trial_df = pl.read_csv(
            file,
            schema_overrides={
                'time': pl.Float64,
                'pupil': pl.Float64,
                'pixel_x': pl.Float64,
                'pixel_y': pl.Float64,
                'page': pl.Utf8,
            },
        )
        match = re.match(regex_name, file.stem)
        trial_df = trial_df.with_columns(
            pl.lit(match.group("trial")).alias("trial"),
            pl.lit(match.group("stimulus")).alias("stimulus"),
        )

        initial_df = initial_df.vstack(trial_df)

    gaze = pm.Gaze(
        initial_df,
        trial_columns=trial_columns,
        pixel_columns=['pixel_x', 'pixel_y'],
    )

    if metadata_path:
        with open(metadata_path / "gaze_metadata.json", "r", encoding='utf8') as f:
            metadata = json.load(f)

        gaze._metadata = metadata

        with open(metadata_path / 'experiment.yaml', "r") as f:
            exp = yaml.safe_load(f)

        exp = pm.Experiment.from_dict(exp)

        gaze.experiment = exp

    return gaze


def load_trial_level_fixation_data(
        gaze: pm.Gaze,
        data_folder: Path,
        file_pattern: str = '*_fixations.csv',
) -> pm.Gaze:
    regex_name = r".+_(?P<trial>(?:PRACTICE_)?trial_\d+)_(?P<stimulus>[^_]+_[^_]+_\d+)_fixations"

    initial_df = pl.DataFrame()
    for file in data_folder.glob(file_pattern):
        trial_df = pl.read_csv(file)

        match = re.match(regex_name, file.stem)
        trial_df = trial_df.with_columns(
            pl.lit(match.group("trial")).alias("trial"),
            pl.lit(match.group("stimulus")).alias("stimulus"),
        )

        initial_df = initial_df.vstack(trial_df)

    gaze.events = pm.Events(
        initial_df,
        trial_columns=gaze.trial_columns,
    )

    gaze.events.frame = gaze.events.frame.with_columns(
        pl.lit("fixation").alias("name")
    )

    return gaze


def save_session_metadata(gaze: pm.Gaze, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)

    metadata = gaze._metadata
    metadata['datetime'] = str(metadata['datetime'])

    with open(directory / "gaze_metadata.json", "w", encoding='utf8') as f:
        json.dump(metadata, f)

    gaze.save(directory, save_events=False, save_samples=False)
