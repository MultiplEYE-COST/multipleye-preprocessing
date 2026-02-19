"""Functions for saving data."""

import json
from pathlib import Path

import polars as pl

import pymovements as pm
from .. import constants


def save_raw_data(directory: Path, session: str, data: pm.Gaze) -> None:
    directory = Path(directory) / session / constants.RAW_DATA_FOLDER
    directory.mkdir(parents=True, exist_ok=True)

    trials = data.split(by="trial", as_dict=True)

    for (trial_id, _), trial in trials.items():
        stimulus_id = trial.frame["stimulus"][0]
        filename = f"{session}_{trial_id}_{stimulus_id}_raw_data.csv"

        trial.unnest("pixel")
        trial.frame = trial.frame["time", "pixel_x", "pixel_y", "pupil", "page"]

        trial.save_samples(directory / filename)


def save_events_data(
    event_type: str,
    directory: Path,
    session: str,
    split_column: str,
    name_columns: list[str],
    file_columns: list[str],
    data: pm.Gaze,
) -> None:
    """
    Saves events data (fixations or saccades) in separate csv files. The input is expected to be
    produced with pymovements.
    :param event_type: what type of event should be stored. Either "fixation" or "saccade".
    :param directory: the directory where the events data should be stored. The function will create a subfolder
    for the session and event type (fixations or saccades).
    :param session: The name of the session.
    :param split_column: What column to split the events data by. The function will create a separate file for each
    unique value in this column.
    :param name_columns: Column values per split that should be included in the file name.
    :param file_columns: Columns that should be included in the saved csv file.
    :param data: The events data as a pymovements Gaze object.
    """

    directory = (
        Path(directory) / session / constants.FIXATIONS_FOLDER
        if event_type == "fixation"
        else Path(directory) / session / constants.SACCADES_FOLDER
    )
    directory.mkdir(parents=True, exist_ok=True)

    data_copy = data.clone()
    data_copy.events.unnest()

    events = data_copy.events.frame.filter(pl.col("name") == event_type)

    for group in events.partition_by(split_column):
        name = f"{session}"
        for col in name_columns:
            if col not in group.columns:
                raise ValueError(f"Column {col} not found in events data.")
            name += f"_{group[col][0]}"

        name += f"_{event_type}.csv"

        df = group.select(file_columns)
        df.write_csv(directory / name)


def save_scanpaths(directory: Path, session: str, data: pm.Gaze) -> None:
    directory = Path(directory) / session / constants.SCANPATHS_FOLDER
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
        # TODO: what to do about fixations were no aoi is mapped?
        df = df.filter(pl.col("char_idx").is_not_null())
        if df.is_empty():
            continue
        trial = df["trial"][0]
        stimulus = df["stimulus"][0]
        name = f"{session}_{trial}_{stimulus}_scanpath.csv"

        df = df[
            "onset",
            "duration",
            "name",
            "location_x",
            "location_y",
            "char_idx",
            "char",
            "top_left_x",
            "top_left_y",
            "width",
            "height",
            "char_idx_in_line",
            "line_idx",
            "page",
            "word_idx",
            "word_idx_in_line",
            "word",
        ]
        df.write_csv(directory / name)


def save_session_metadata(directory: Path, session: str, gaze: pm.Gaze) -> None:
    directory = Path(directory) / session
    directory.mkdir(parents=True, exist_ok=True)

    metadata = gaze._metadata
    metadata["datetime"] = str(metadata["datetime"])

    # remove validations and calibrations because they are already saved in separate files
    metadata.pop("calibrations", None)
    metadata.pop("validations", None)

    with open(directory / "gaze_metadata.json", "w", encoding="utf8") as f:
        json.dump(metadata, f)

    gaze.save(directory, save_events=False, save_samples=False)

    # both are dfs
    validations = gaze.validations
    calibrations = gaze.calibrations

    validations.write_csv(directory / "validations.tsv", separator="\t")
    calibrations.write_csv(directory / "calibrations.tsv", separator="\t")
