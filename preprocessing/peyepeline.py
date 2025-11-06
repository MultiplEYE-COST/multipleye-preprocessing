import json
from pathlib import Path

from pymovements.stimulus import TextStimulus

from preprocessing.data_collection.stimulus import LabConfig, Stimulus

import pymovements as pm
import polars as pl

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
        gaze_path: str = '',
) -> (pm.Gaze, dict[str, any]):
    """

    :param gaze_path: if a gaze_path is provided, the function will try to load the gaze data from there
    :param asc_file:
    :param lab_config:
    :param session_idf:
    :return:
    """

    trial_cols = ["trial", "stimulus", "screen"]

    gaze = pm.gaze.from_asc(
        asc_file,
        patterns=[
            r"start_recording_(?P<trial>(?:PRACTICE_)?trial_\d+)_stimulus_(?P<stimulus>[^_]+_[^_]+_\d+)_(?P<screen>.+)",
            r"start_recording_(?P<trial>(?:PRACTICE_)?trial_\d+)_(?P<screen>familiarity_rating_screen_\d+|subject_difficulty_screen)",
            {"pattern": r"stop_recording_", "column": "trial", "value": None},
            {"pattern": r"stop_recording_", "column": "screen", "value": None},
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
        pl.col("trial").is_not_null() & pl.col("screen").is_not_null()
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

    return gaze, gaze._metadata


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


def _ensure_velocity_computed(gaze: pm.Gaze):
    """Compute velocity if not already available."""
    window_ms = 50
    poly_degree = 2
    if "velocity" not in gaze.samples.columns:
        # Savitzky-Golay filter as in https://doi.org/10.3758/BRM.42.1.188
        window_length = round(gaze.experiment.sampling_rate / 1000 * window_ms)
        if window_length % 2 == 0:
            window_length += 1
        gaze.pix2deg()
        gaze.pos2vel("savitzky_golay",
                     window_length=window_length, degree=poly_degree)


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


def detect_fixations(gaze):
    """Detect fixations (auto-preprocessing included)."""
    _ensure_velocity_computed(gaze)
    gaze.detect("ivt")
    compute_event_properties(
        gaze, "fixation", DEFAULT_EVENT_PROPERTIES["fixation"])


def detect_saccades(gaze):
    """Detect saccades (auto-preprocessing included)."""
    _ensure_velocity_computed(gaze)
    gaze.detect("microsaccades")
    compute_event_properties(
        gaze, "saccade", DEFAULT_EVENT_PROPERTIES["saccade"])


def map_fixations_to_aois(
        gaze: pm.Gaze,
        stimuli: list[Stimulus],
) -> None:

    all_stimuli = pl.DataFrame()
    for stimulus in stimuli:
        text = stimulus.text_stimulus.aois
        all_stimuli = all_stimuli.vstack(text)

    # TODO pm very ugly work around. I'd like to be able to map to aois for each stimulus separately
    #  https://github.com/pymovements/pymovements/issues/1125
    all_stimuli = TextStimulus(
        all_stimuli,
        aoi_column="char_idx",
        start_x_column="top_left_x",
        start_y_column="top_left_y",
        width_column="width",
        height_column="height",
        page_column="page",
    )

    # aoi mapping does not work if there are saccades in the file.. because then the
    gaze.events.frame = gaze.events.fixations
    gaze.events.map_to_aois(all_stimuli)


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
        name = f"{session}_{trial}_{stimulus}_raw_data.csv"
        df = df['time', 'pixel_x', 'pixel_y', 'pupil', 'screen']
        df.write_csv(directory / name)


def save_fixation_data(directory: Path, session: str, data: pm.Gaze) -> None:
    directory.mkdir(parents=True, exist_ok=True)

    # new_data = data.clone()

    # data.unnest()
    data.events.unnest()

    # TODO pm save only fixations
    # data.events.frame = data.events.fixations
    fixations = data.events.frame.filter(pl.col("name") == "fixation")

    # trials = data.events.split(by="trial", as_dict=False)

    for group in fixations.partition_by("trial"):
        trial_name = group["trial"][0]
        stimulus = group["stimulus"][0]
        name = f"{session}_{trial_name}_{stimulus}_fixations.csv"
        df = group.select(["onset", "duration", "location_x", "location_y"])
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
        trial = df["trial"][0]
        stimulus = df["stimulus"][0]
        name = f"{session}_{trial}_{stimulus}_scanpath.csv"

        df = df[
            'onset', 'duration', 'name', 'location_x', 'location_y', 'char_idx', 'char',
            'top_left_x', 'top_left_y', 'width', 'height', 'char_idx_in_line', 'line_idx',
            'page', 'word_idx', 'word_idx_in_line', 'word']
        df.write_csv(directory / name)


def load_trial_level_raw_data(
        data_folder: Path,
        file_pattern: str = '*_raw_data.csv',
):

    initial_df = pl.DataFrame()
    for file in data_folder.glob(file_pattern):
        trial_df = pl.read_csv(file)

        initial_df = initial_df.vstack(trial_df)

    return initial_df


def save_session_metadata(gaze: pm.Gaze, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)

    metadata = gaze._metadata
    metadata['datetime'] = str(metadata['datetime'])
    # TODO pm: I'd like to save my metadata without having to access a protected argument
    with open(directory / "gaze_metadata.json", "w", encoding='utf8') as f:
        json.dump(metadata, f)

    gaze.save(directory, save_events=False, save_samples=False)
