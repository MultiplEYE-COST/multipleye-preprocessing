"""Functions for loading and processing gaze data from various formats."""

import json
import re
from pathlib import Path

import polars as pl
import yaml

import pymovements as pm

from ..constants import FIXATION, SACCADE
from ..data_collection.stimulus import LabConfig


def load_gaze_data(
    asc_file: Path,
    lab_config: LabConfig,
    session_idf: str,
    trial_cols: list[str] = None,
) -> pm.Gaze:
    """Load sample gaze data from an ASC file.

    This function extracts and processes gaze data: Identify trials, stimulus details, activities,
    and practice sessions by pattern matching.
    Non-trial data is filtered out from the results before returning the processed gaze object.

    Parameters
    ----------
    asc_file : Path
        Path to the ASC file containing gaze data.
    lab_config : LabConfig
        Configuration object containing details about the lab environment,
        including screen resolution, screen size (in cm),
        and the eye-tracking device's sampling rate.
    session_idf : str
        Identifier for the session the gaze data corresponds to.
    trial_cols : list of str, optional
        List of columns to be associated with trial-level metadata. Default is None.

    Returns
    -------
    pm.Gaze
        A gaze object that encapsulates the processed and structured gaze data,
        along with associated metadata, such as sampling rate, screen configuration,
        and experimental details.
    """

    gaze = pm.gaze.from_asc(
        asc_file,
        # TODO: move patterns form here to config, pm dataset definition?
        patterns=[
            r"start_recording_(?P<trial>(?:PRACTICE_)?trial_\d+)_stimulus_(?P<stimulus>[^_]+_[^_]+_\d+(\.0)?)_(?P<page>.+)",
            r"start_recording_(?P<trial>(?:PRACTICE_)?trial_\d+)_(?P<page>familiarity_rating_screen_\d+|subject_difficulty_screen)",
            {"pattern": r"stop_recording_", "column": "trial", "value": None},
            {"pattern": r"stop_recording_", "column": "page", "value": None},
            {
                "pattern": r"start_recording_(?:PRACTICE_)?trial_\d+_stimulus_[^_]+_[^_]+_\d+(\.0)?_page_\d+",
                "column": "activity",
                "value": "reading",
            },
            {
                "pattern": r"start_recording_(?:PRACTICE_)?trial_\d+_stimulus_[^_]+_[^_]+_\d+(\.0)?_question_\d+",
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
        metadata={"session": session_idf},
    )

    # Filter out data outside of trials
    # TODO: Also report time spent outside of trials
    gaze.frame = gaze.frame.filter(
        pl.col("trial").is_not_null() & pl.col("page").is_not_null()
    )

    # Initialize experiment config from lab config. Sampling rate is automatically inferred in from_asc, but we use
    # the one from the final metadata form to perform a sanity check. for pilot data, the value will not be handed
    # to the exp. Atm we need to set the experiment only after parsing gaze because there is a bug / feat which
    # needs to be solved first: https://github.com/pymovements/pymovements/issues/1286
    experiment = pm.Experiment(
        screen_width_px=lab_config.image_resolution[0],
        screen_height_px=lab_config.image_resolution[1],
        screen_width_cm=lab_config.image_size_cm[0],
        screen_height_cm=lab_config.image_size_cm[1],
        distance_cm=lab_config.screen_distance_cm,
    )

    if lab_config.sampling_frequency_hz is not None:
        experiment.sampling_rate = lab_config.sampling_frequency_hz

    else:
        experiment.sampling_rate = gaze._metadata["sampling_rate"]

    gaze.experiment = experiment

    return gaze


DEFAULT_EVENT_PROPERTIES = {
    FIXATION: [
        ("location", {"position_column": "pixel"}),
        ("dispersion", {}),
    ],
    SACCADE: [
        ("amplitude", {}),
        ("peak_velocity", {}),
        ("dispersion", {}),
    ],
}


def load_trial_level_raw_data(
    data_folder: Path,
    trial_columns: list[str],
    file_pattern: str = "*_raw_data.csv",
    metadata_path: Path = None,
) -> pm.Gaze:
    """Load trial-level raw data from multiple CSV files and construct a gaze object.

    This function aggregates raw data files containing gaze data for one or more trials.

    Parameters
    ----------
    data_folder : Path
        The directory where the raw data CSV files are stored.
    trial_columns : list of str
        Column names that uniquely identify a trial within the data.
    file_pattern : str, optional
        The file search pattern for raw data CSV files. Defaults to '*_raw_data.csv'.
    metadata_path : Path, optional
        The folder containing metadata files (`gaze_metadata.json`, `experiment.yaml`,
        `validations.tsv`, `calibrations.tsv`) used to enrich the gaze object.

    Returns
    -------
    pm.Gaze
        A gaze object containing the trial-level aggregated gaze data along with
        any associated metadata, validations, calibrations, and experiment settings, if provided.
    """
    regex_name = r".+_(?P<trial>(?:PRACTICE_)?trial_\d+)_(?P<stimulus>[^_]+_[^_]+_\d+(\.0)?)_raw_data"

    initial_df = pl.DataFrame()

    for file in data_folder.glob(file_pattern):
        trial_df = pl.read_csv(
            file,
            schema_overrides={
                "time": pl.Float64,
                "pupil": pl.Float64,
                "pixel_x": pl.Float64,
                "pixel_y": pl.Float64,
                "page": pl.Utf8,
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
        pixel_columns=["pixel_x", "pixel_y"],
    )

    if metadata_path:
        with open(metadata_path / "gaze_metadata.json", "r", encoding="utf8") as f:
            metadata = json.load(f)

        gaze._metadata = metadata

        with open(metadata_path / "experiment.yaml", "r") as f:
            exp = yaml.safe_load(f)

        with open(metadata_path / "validations.tsv", "r", encoding="utf8") as f:
            validations_df = pl.read_csv(f, separator="\t")

        gaze.validations = validations_df

        with open(metadata_path / "calibrations.tsv", "r", encoding="utf8") as f:
            calibrations_df = pl.read_csv(f, separator="\t")

        gaze.calibrations = calibrations_df

        exp = pm.Experiment.from_dict(exp)

        gaze.experiment = exp

    return gaze


def load_trial_level_events_data(
    gaze: pm.Gaze,
    data_folder: Path,
    event_type: str,
    file_pattern: str = "*_fixation",
) -> pm.Gaze:
    """Load and processes trial-level event data for a given type.

    The function reads CSV files within a specified folder,
    applies a file pattern to match and extract relevant groups,
    and integrates the data into the provided `gaze` object.
    Combine with existing event data if present.

    Parameters
    ----------
    gaze : pm.Gaze
        An object containing gaze data and associated event information.
    data_folder : Path
        The path to the folder containing trial-level event data files in CSV format.
    event_type : str
        The type of event to load, must be one of the keys in `DEFAULT_EVENT_PROPERTIES`.
    file_pattern : str, optional
        A pattern for matching CSV file names to extract relevant groups, by default '*_fixation'.

    Returns
    -------
    pm.Gaze
        The updated gaze object with the loaded and integrated event data.
    """
    if event_type not in DEFAULT_EVENT_PROPERTIES.keys():
        raise ValueError(
            f"event_type must be {DEFAULT_EVENT_PROPERTIES.keys()}, got {event_type}"
        )

    all_events = pl.DataFrame()
    for file in data_folder.glob("*.csv"):
        trial_df = pl.read_csv(file)

        match = re.match(file_pattern, file.name)
        # go over groups in the name regex and add them as columns
        if match is None:
            print(file.name)
        else:
            for group_name in match.groupdict().keys():
                if group_name not in trial_df.columns:
                    trial_df = trial_df.with_columns(
                        pl.lit(match.group(group_name)).alias(group_name)
                    )

        all_events = all_events.vstack(trial_df)

    all_events = all_events.with_columns(pl.lit(event_type).alias("name"))

    # if there have already been events detected, keep them
    if not gaze.events.frame.is_empty():
        original_events = gaze.events.frame

        new_events = pm.Events(
            all_events,
            trial_columns=gaze.trial_columns,
        )

        new_events = new_events.frame.with_columns(pl.lit(event_type).alias("name"))

        # if one df has more columns than the other, add the missing columns with same column type!
        for col in original_events.columns:
            if col not in new_events.columns:
                dtype = original_events[col].dtype
                new_events = new_events.with_columns(
                    pl.lit(None).cast(dtype).alias(col)
                )
        for col in new_events.columns:
            if col not in original_events.columns:
                dtype = new_events[col].dtype
                original_events = original_events.with_columns(
                    pl.lit(None).cast(dtype).alias(col)
                )
        # sort columns to be in the same order
        new_events = new_events.select(original_events.columns)

        all_events = original_events.vstack(new_events)

    gaze.events = pm.Events(
        all_events,
        trial_columns=gaze.trial_columns,
    )

    return gaze
