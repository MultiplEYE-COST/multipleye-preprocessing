"""Functions for loading and processing gaze data from various formats."""

import json
import logging
import re
from pathlib import Path

import polars as pl
import yaml

import pymovements as pm

from ..config import settings
from ..data_collection.stimulus import LabConfig
from ..models.sid import Sid


def load_gaze_data(
    asc_file: Path,
    lab_config: LabConfig,
    sid: Sid,
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
    sid : Sid
        The session identifier.
    trial_cols : list of str, optional
        List of columns to be associated with trial-level metadata. Default is None.

    Returns
    -------
    pm.Gaze
        A gaze object that encapsulates the processed and structured gaze data,
        along with associated metadata, such as sampling rate, screen configuration,
        and experimental details.
    """

    # Initialize experiment config from lab config. Although sampling rate and resolution are automatically inferred
    # in from_asc(), the function will emit a warning in case the parsed values do not match the experiment specification.
    # This way we perform a sanity check for the experiment configuration.
    experiment = pm.Experiment(
        screen_width_px=lab_config.image_resolution[0],
        screen_height_px=lab_config.image_resolution[1],
        screen_width_cm=lab_config.image_size_cm[0],
        screen_height_cm=lab_config.image_size_cm[1],
        distance_cm=lab_config.screen_distance_cm,
        sampling_rate=lab_config.sampling_frequency_hz,
    )

    gaze = pm.gaze.from_asc(
        asc_file,
        patterns=settings.GAZE_PATTERNS,
        trial_columns=trial_cols,
        add_columns={"session": str(sid)},
        experiment=experiment,
    )

    # Filter out data outside of trials
    # TODO: Also report time spent outside of trials
    gaze.samples = gaze.samples.filter(
        pl.col("trial").is_not_null() & pl.col("page").is_not_null()
    )

    return gaze


def load_trial_level_raw_data(
    directory: Path,
    sid: Sid,
    trial_columns: list[str],
    file_pattern: str | None = None,
    load_metadata: bool = False,
) -> pm.Gaze:
    """Load trial-level raw data from multiple CSV files and construct a gaze object.

    This function aggregates raw data files containing gaze data for one or more trials.

    Parameters
    ----------
    directory : Path
        The base directory for preprocessed data.
    sid : Sid
        The session identifier.
    trial_columns : list of str
        Column names that uniquely identify a trial within the data.
    file_pattern : str, optional
        The file search pattern for raw data CSV files. Defaults to None, which uses settings.RAW_DATA_FILE_GLOB.
    load_metadata : bool, optional
        Whether to load metadata files (`gaze_metadata.json`, `experiment.yaml`,
        `validations.tsv`, `calibrations.tsv`) to enrich the gaze object.

    Returns
    -------
    pm.Gaze
        A gaze object containing the trial-level aggregated gaze data along with
        any associated metadata, validations, calibrations, and experiment settings, if provided.
    """
    data_folder = Path(directory) / settings.RAW_DATA_FOLDER / str(sid)
    if file_pattern is None:
        file_pattern = settings.RAW_DATA_FILE_GLOB

    regex_name = settings.RAW_DATA_FILENAME_REGEX

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

    if initial_df.is_empty():
        raise ValueError(
            f"No raw data files found in {data_folder} with pattern {file_pattern}"
        )

    gaze = pm.Gaze(
        initial_df,
        trial_columns=trial_columns,
        pixel_columns=["pixel_x", "pixel_y"],
    )

    if load_metadata:
        metadata_path = Path(directory) / settings.METADATA_FOLDER / str(sid)

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
    directory: Path,
    sid: Sid,
    event_type: str,
    file_pattern: str | None = None,
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
    directory : Path
        The base directory for preprocessed data.
    sid : Sid
        The session identifier.
    event_type : str
        The type of event to load, must be one of the keys in `DEFAULT_EVENT_PROPERTIES`.
    file_pattern : str, optional
        A pattern for matching CSV file names to extract relevant groups.
        If None, defaults to settings.EVENT_DATA_FILE_GLOB formatted with event_type.

    Returns
    -------
    pm.Gaze
        The updated gaze object with the loaded and integrated event data.
    """
    if event_type == "fixation":
        data_folder = Path(directory) / settings.FIXATIONS_FOLDER / str(sid)
    elif event_type == "saccade":
        data_folder = Path(directory) / settings.SACCADES_FOLDER / str(sid)
    else:
        raise ValueError(
            f"event_type must be {list(settings.EVENT_PROPERTIES.keys())}, got {event_type}"
        )

    if file_pattern is None:
        file_pattern = settings.EVENT_DATA_FILENAME_REGEX.format(event_type=event_type)

    all_events = pl.DataFrame()
    for file in data_folder.glob(
        settings.EVENT_DATA_FILE_GLOB.format(event_type=event_type)
    ):
        trial_df = pl.read_csv(file)

        match = re.match(file_pattern, file.name)
        # go over groups in the name regex and add them as columns
        if match is None:
            logging.info(f"Skipping file {file} for event loading")
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


def load_reading_measures(
    directory: Path,
    sid: Sid,
    file_pattern: str = r".*?(?P<trial>(?:PRACTICE_)?trial_\d+)_(?P<stimulus>.+)_reading_measures\.csv",
) -> pl.DataFrame:
    """Load reading measures from CSV files.

    Parameters
    ----------
    directory : Path
        The base directory for preprocessed data.
    sid : Sid
        The session identifier.
    file_pattern : str, optional
        Regex pattern to extract trial and stimulus from filenames.

    Returns
    -------
    pl.DataFrame
        A DataFrame containing the concatenated reading measures data.
    """
    data_folder = Path(directory) / settings.READING_MEASURES_FOLDER / str(sid)
    # Use glob to find all csv files first, as Path.glob() does not support regex
    files = [f for f in data_folder.glob("*.csv") if re.match(file_pattern, f.name)]

    if len(files) == 0:
        raise ValueError(f"No files found in {data_folder} with pattern {file_pattern}")

    all_trials = []

    for file in files:
        df = pl.read_csv(file)
        # get trial and stimulus from file name
        match = re.match(file_pattern, file.name)
        trial_df = df.with_columns(
            pl.lit(match.group("trial")).alias("trial"),
            pl.lit(match.group("stimulus")).alias("stimulus"),
        )

        all_trials.append(trial_df)

    return pl.concat(all_trials)
